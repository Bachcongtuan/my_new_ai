# Copyright (c) 2026 Bach Cong Tuan
# All rights reserved.
import json
import os
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request

HOST = "0.0.0.0"
# Dòng 13: Tự động lấy Port từ Render, nếu không có thì dùng 5000
PORT = int(os.environ.get("PORT", 5000))

SYSTEM_PROMPT = (
    "You are a practical AI assistant. Give clear, concise, useful answers."
)
HISTORY_FILE = Path(__file__).with_name("chat_history.json")
HISTORY_LOCK = threading.Lock()
MAX_HISTORY_MESSAGES = max(2, int(os.getenv("MAX_HISTORY_MESSAGES", "16")))
LEGACY_MODEL_NOTICE = (
    "Hệ thống đã tự động cập nhật lên các mô hình Gemini mới nhất."
)
MODEL_PRESETS = [
    {
        "key": "flash",
        "name": "Gemini 2.5 Flash",
        "model": "gemini-2.5-flash",
        "description": "Cân bằng giữa tốc độ và chất lượng.",
        "legacy": "",
        "status": "stable",
    },
    {
        "key": "pro",
        "name": "Gemini 2.5 Pro",
        "model": "gemini-2.5-pro",
        "description": "Lập luận chuyên sâu cho các yêu cầu khó.",
        "legacy": "",
        "status": "stable",
    },
    {
        "key": "flash_lite",
        "name": "Gemini 2.5 Flash-Lite",
        "model": "gemini-2.5-flash-lite",
        "description": "Tốc độ phản hồi cực nhanh.",
        "legacy": "",
        "status": "stable",
    },
    {
        "key": "compat",
        "name": "Gemini 2.0 Flash",
        "model": "gemini-2.0-flash",
        "description": "Mô hình tương thích văn bản.",
        "legacy": "",
        "status": "deprecated",
    },
]
MODEL_PRESETS_BY_KEY = {item["key"]: item for item in MODEL_PRESETS}
DEFAULT_MODEL_KEY = os.getenv("AI_DEFAULT_MODEL_KEY", "flash").strip().lower()

def get_default_model_key() -> str:
    if DEFAULT_MODEL_KEY in MODEL_PRESETS_BY_KEY:
        return DEFAULT_MODEL_KEY
    return "flash"

def get_model_choice(model_key: str | None = None) -> dict[str, str]:
    key = (model_key or "").strip().lower()
    if key in MODEL_PRESETS_BY_KEY:
        return MODEL_PRESETS_BY_KEY[key]
    return MODEL_PRESETS_BY_KEY[get_default_model_key()]

def get_model_catalog_payload(model_key: str | None = None) -> dict:
    selected = get_model_choice(model_key)
    return {
        "models": [dict(item) for item in MODEL_PRESETS],
        "default_model_key": get_default_model_key(),
        "selected_model_key": selected["key"],
        "selected_model": selected["model"],
        "selected_model_name": selected["name"],
        "legacy_notice": LEGACY_MODEL_NOTICE,
    }

def utc_timestamp() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        payload = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    normalized = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        created_at = str(item.get("created_at", "")).strip() or utc_timestamp()
        if role in {"user", "assistant"} and content:
            normalized.append(
                {"role": role, "content": content, "created_at": created_at}
            )
    return normalized[-MAX_HISTORY_MESSAGES:]

def save_history(history: list[dict]) -> None:
    HISTORY_FILE.write_text(
        json.dumps(history[-MAX_HISTORY_MESSAGES:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

CHAT_HISTORY = load_history()

def add_history(role: str, content: str) -> None:
    with HISTORY_LOCK:
        CHAT_HISTORY.append(
            {
                "role": role,
                "content": content.strip(),
                "created_at": utc_timestamp(),
            }
        )
        del CHAT_HISTORY[:-MAX_HISTORY_MESSAGES]
        save_history(CHAT_HISTORY)

def clear_history() -> None:
    with HISTORY_LOCK:
        CHAT_HISTORY.clear()
        save_history(CHAT_HISTORY)

def snapshot_history() -> list[dict]:
    with HISTORY_LOCK:
        return [dict(item) for item in CHAT_HISTORY]

def post_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=90) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

def call_gemini(history: list[dict], user_message: str, model_code: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Thiếu GEMINI_API_KEY. Vui lòng cài đặt trong Environment Variables.")

    contents = []
    for item in history[-MAX_HISTORY_MESSAGES:]:
        role = "model" if item["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": item["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.7},
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{parse.quote(model_code)}:generateContent?key={parse.quote(api_key)}"
    )
    response = post_json(url, {"Content-Type": "application/json"}, payload)
    try:
        parts = response["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise RuntimeError(f"Gemini trả về rỗng: {response}")
        return text
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError(f"Phản hồi không mong đợi: {response}") from exc

def generate_reply(history: list[dict], user_message: str, model_code: str) -> str:
    return call_gemini(history, user_message, model_code)

def html_page() -> str:
    default_model = get_model_choice()
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini Web Chat</title>
  <style>
    :root {{
      --bg: #0d1117;
      --panel: rgba(14, 21, 31, 0.82);
      --panel-2: rgba(23, 32, 48, 0.92);
      --line: rgba(173, 188, 206, 0.18);
      --text: #edf4ff;
      --muted: #9db0c8;
      --accent: #6ee7c8;
      --accent-2: #ffb36b;
      --user: #15364b;
      --assistant: #1c293d;
      --danger: #ff7f7f;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI Variable", "Trebuchet MS", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(110, 231, 200, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(255, 179, 107, 0.16), transparent 30%),
        linear-gradient(135deg, #091018 0%, #101826 45%, #1a1427 100%);
      display: grid;
      place-items: center;
      padding: 10px;
    }}

    .shell {{
      width: 95vw;
      max-width: 95vw;
      min-height: 82vh;
      border: 1px solid var(--line);
      border-radius: 28px;
      overflow: hidden;
      background: var(--panel);
      backdrop-filter: blur(12px);
      box-shadow: 0 30px 80px rgba(0, 0, 0, 0.38);
      display: grid;
      grid-template-rows: auto 1fr auto;
    }}

    .topbar {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      padding: 20px 22px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.04), transparent);
    }}

    .title {{ margin: 0; font-size: 24px; font-weight: 700; }}
    .meta {{ color: var(--muted); font-size: 14px; }}
    .actions {{ display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }}

    button {{
      border: 0;
      border-radius: 14px;
      padding: 12px 16px;
      font: inherit;
      cursor: pointer;
      transition: all 120ms ease;
    }}

    button:hover {{ transform: translateY(-1px); }}
    button:disabled {{ cursor: wait; opacity: 0.6; }}

    .ghost {{
      background: rgba(255,255,255,0.06);
      color: var(--text);
      border: 1px solid var(--line);
    }}

    .picker {{ display: flex; flex-direction: column; gap: 6px; min-width: 320px; }}
    .picker span {{ color: var(--muted); font-size: 12px; }}

    select {{
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.06);
      color: var(--text);
      padding: 11px 14px;
      font: inherit;
    }}

    .primary {{
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: #04131c;
      font-weight: 700;
    }}

    .chat {{ padding: 22px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }}

    .message {{
      max-width: min(80%, 720px);
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      line-height: 1.5;
      white-space: pre-wrap;
      animation: fadeUp 180ms ease;
    }}

    .message.user {{ align-self: flex-end; background: var(--user); }}
    .message.assistant {{ align-self: flex-start; background: var(--assistant); }}
    .message .stamp {{ display: block; margin-top: 8px; color: var(--muted); font-size: 12px; }}

    .composer {{ border-top: 1px solid var(--line); background: var(--panel-2); padding: 18px; }}
    .composer form {{ display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: end; }}

    textarea {{
      width: 100%;
      min-height: 68px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      padding: 14px 16px;
      font: inherit;
      outline: none;
    }}

    .status {{ margin-top: 10px; min-height: 20px; color: var(--muted); font-size: 14px; }}
    .error {{ color: var(--danger); }}
    .empty {{ padding: 24px; border: 1px dashed var(--line); border-radius: 18px; color: var(--muted); text-align: center; }}

    @keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}

    @media (max-width: 700px) {{
      .shell {{ width: 100%; min-height: 92vh; border-radius: 22px; }}
      .topbar {{ flex-direction: column; align-items: flex-start; }}
      .composer form {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div>
        <h1 class="title">Gemini Web Chat</h1>
        <div class="meta" id="modelMeta">Preset: <strong>{default_model["name"]}</strong> | Model: <strong>{default_model["model"]}</strong></div>
        <div class="meta" style="font-size: 12px; margin-top: 4px;" id="modelHint">{default_model["description"]}</div>
      </div>
      <div class="actions">
        <label class="picker">
          <span>Chọn mô hình</span>
          <select id="modelSelect"></select>
        </label>
        <button class="ghost" id="clearButton" type="button">Xóa lịch sử</button>
      </div>
    </header>

    <section class="chat" id="chat"></section>

    <footer class="composer">
      <form id="chatForm">
        <textarea id="messageInput" placeholder="Nhập tin nhắn... (Shift+Enter để xuống dòng)" required></textarea>
        <button class="primary" id="sendButton" type="submit">Gửi</button>
      </form>
      <div class="status" id="status"></div>
    </footer>
  </main>

  <script>
    const chat = document.getElementById("chat");
    const form = document.getElementById("chatForm");
    const input = document.getElementById("messageInput");
    const sendButton = document.getElementById("sendButton");
    const clearButton = document.getElementById("clearButton");
    const modelSelect = document.getElementById("modelSelect");
    const modelMeta = document.getElementById("modelMeta");
    const modelHint = document.getElementById("modelHint");
    const statusNode = document.getElementById("status");
    const MODEL_STORAGE_KEY = "gemini_web_chat_model_key";
    let modelCatalog = [];
    let defaultModelKey = "{default_model["key"]}";

    function escapeHtml(text) {{
      return text.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
    }}

    function setStatus(message, isError = false) {{
      statusNode.textContent = message || "";
      statusNode.className = isError ? "status error" : "status";
    }}

    function getSelectedModel() {{
      const selectedKey = modelSelect.value || defaultModelKey;
      return modelCatalog.find((item) => item.key === selectedKey) || modelCatalog[0] || null;
    }}

    function updateModelUi() {{
      const selected = getSelectedModel();
      if (!selected) return;

      localStorage.setItem(MODEL_STORAGE_KEY, selected.key);
      // Đã xóa hiển thị Port ở đây (Sửa lỗi dòng 541 cũ)
      modelMeta.innerHTML = `Preset: <strong>${{escapeHtml(selected.name)}}</strong> | Model: <strong>${{escapeHtml(selected.model)}}</strong>`;
      modelHint.textContent = selected.description;
    }}

    function renderModels(payload) {{
      modelCatalog = payload.models || [];
      defaultModelKey = payload.default_model_key || defaultModelKey;
      const storedKey = localStorage.getItem(MODEL_STORAGE_KEY);
      const initialKey = modelCatalog.some((item) => item.key === storedKey) ? storedKey : defaultModelKey;

      modelSelect.innerHTML = "";
      for (const item of modelCatalog) {{
        const option = document.createElement("option");
        option.value = item.key;
        option.textContent = `${{item.name}}`;
        modelSelect.appendChild(option);
      }}
      modelSelect.value = initialKey;
      updateModelUi();
    }}

    function renderHistory(history) {{
      chat.innerHTML = "";
      if (!history.length) {{
        // Việt hóa thông báo trống
        chat.innerHTML = '<div class="empty">Không có tin nhắn. Hãy nhắn một thứ gì đó để bắt đầu!</div>';
        return;
      }}

      for (const item of history) {{
        const node = document.createElement("article");
        node.className = `message ${{item.role}}`;
        node.innerHTML = `<div>${{escapeHtml(item.content)}}</div><span class="stamp">${{item.role === 'user' ? 'Bạn' : 'AI'}} | ${{item.created_at}}</span>`;
        chat.appendChild(node);
      }}
      chat.scrollTop = chat.scrollHeight;
    }}

    async function loadModels() {{
      const response = await fetch("/api/models");
      const data = await response.json();
      renderModels(data);
    }}

    async function loadHistory() {{
      const response = await fetch("/api/history");
      const data = await response.json();
      renderHistory(data.history || []);
    }}

    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      const message = input.value.trim();
      if (!message) return;

      input.disabled = true;
      sendButton.disabled = true;
      setStatus("AI đang suy nghĩ...");

      try {{
        const selected = getSelectedModel();
        const response = await fetch("/api/chat", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ message, model_key: selected.key }})
        }});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Lỗi kết nối.");
        
        renderHistory(data.history || []);
        input.value = "";
        setStatus("Sẵn sàng.");
      }} catch (err) {{
        setStatus(err.message, true);
      }} finally {{
        input.disabled = false;
        sendButton.disabled = false;
        input.focus();
      }}
    }});

    clearButton.addEventListener("click", async () => {{
      if (!confirm("Xóa toàn bộ lịch sử chat?")) return;
      await fetch("/api/clear", {{ method: "POST" }});
      renderHistory([]);
    }});

    modelSelect.addEventListener("change", updateModelUi);
    
    input.addEventListener("keydown", (event) => {{
      if (event.key === "Enter" && !event.shiftKey) {{
        event.preventDefault();
        form.requestSubmit();
      }}
    }});

    loadModels().then(loadHistory);
  </script>
</body>
</html>
"""

class AIRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status: int, payload: str) -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/":
            self.send_html(HTTPStatus.OK, html_page())
        elif self.path == "/api/models":
            self.send_json(HTTPStatus.OK, get_model_catalog_payload())
        elif self.path == "/api/history":
            self.send_json(HTTPStatus.OK, {"history": snapshot_history()})
        else:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        if self.path == "/api/chat":
            self.handle_chat()
        elif self.path == "/api/clear":
            clear_history()
            self.send_json(HTTPStatus.OK, {"history": []})
        else:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def handle_chat(self) -> None:
        try:
            size = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            message = str(payload.get("message", "")).strip()
            model_choice = get_model_choice(str(payload.get("model_key", "")))
            
            reply = generate_reply(snapshot_history(), message, model_choice["model"])
            add_history("user", message)
            add_history("assistant", reply)
            
            self.send_json(HTTPStatus.OK, {
                "reply": reply,
                "history": snapshot_history(),
                "model_name": model_choice["name"]
            })
        except Exception as exc:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AIRequestHandler)
    print(f"Máy chủ đang chạy tại Port: {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == "__main__":
    run()
