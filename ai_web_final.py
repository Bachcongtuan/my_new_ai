# Copyright (c) 2026 Bach Cong Tuan
# All rights reserved.
import json
import os
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import parse, request

# --- CẤU HÌNH HỆ THỐNG ---
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))
AUTO_DELETE_SECONDS = 300  # 5 phút tự hủy
LAST_ACTIVITY_TIME = time.time()

SYSTEM_PROMPT = "You are a practical AI assistant. Give clear, concise, useful answers."
HISTORY_DIR = Path(__file__).parent / "sessions"
HISTORY_DIR.mkdir(exist_ok=True)
HISTORY_LOCK = threading.Lock()
MAX_HISTORY_MESSAGES = 20

MODEL_PRESETS = [
    {"key": "flash", "name": "Gemini 2.5 Flash", "model": "gemini-2.5-flash"},
    {"key": "pro", "name": "Gemini 2.5 Pro", "model": "gemini-2.5-pro"},
    {"key": "flash_lite", "name": "Gemini 2.5 Flash-Lite", "model": "gemini-2.5-flash-lite"},
]
MODEL_PRESETS_BY_KEY = {item["key"]: item for item in MODEL_PRESETS}

SESSIONS = {}

# --- CÁC HÀM XỬ LÝ LOGIC ---

def update_activity():
    """Cập nhật mốc thời gian hoạt động cuối cùng mỗi khi có request"""
    global LAST_ACTIVITY_TIME
    LAST_ACTIVITY_TIME = time.time()

def auto_delete_worker():
    """Luồng chạy ngầm kiểm tra tự hủy mỗi 5 giây"""
    global SESSIONS
    while True:
        time.sleep(5)  # Check 5 giây một lần
        if time.time() - LAST_ACTIVITY_TIME > AUTO_DELETE_SECONDS:
            with HISTORY_LOCK:
                if SESSIONS or list(HISTORY_DIR.glob("*.json")):
                    SESSIONS.clear()
                    for f in HISTORY_DIR.glob("*.json"):
                        try: f.unlink()
                        except: pass
                    print(f"[{datetime.now()}] Hệ thống đã tự động xóa sạch dữ liệu sau 5p.")

def html_page():
    """Giao diện Web tích hợp Session ID và Auto-Sync"""
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini Private Chat</title>
  <style>
    :root {{
      --bg: #0d1117; --panel: rgba(14, 21, 31, 0.9); --line: rgba(173, 188, 206, 0.15);
      --text: #edf4ff; --accent: #6ee7c8; --user: #15364b; --assistant: #1c293d;
    }}
    body {{
      margin: 0; min-height: 100vh; font-family: sans-serif; color: var(--text);
      background: #091018; display: grid; place-items: center; padding: 10px;
    }}
    .shell {{
      width: 95vw; max-width: 900px; height: 90vh; border: 1px solid var(--line);
      border-radius: 20px; background: var(--panel); display: grid; grid-template-rows: auto 1fr auto; overflow: hidden;
    }}
    .topbar {{ padding: 15px 20px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; }}
    .chat {{ padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }}
    .message {{ max-width: 85%; padding: 12px 16px; border-radius: 15px; line-height: 1.5; white-space: pre-wrap; font-size: 15px; border: 1px solid var(--line); }}
    .user {{ align-self: flex-end; background: var(--user); }}
    .assistant {{ align-self: flex-start; background: var(--assistant); }}
    .composer {{ padding: 20px; border-top: 1px solid var(--line); }}
    form {{ display: flex; gap: 10px; }}
    textarea {{ flex: 1; height: 50px; border-radius: 10px; background: rgba(255,255,255,0.05); color: white; padding: 12px; border: 1px solid var(--line); outline: none; resize: none; }}
    button {{ padding: 0 20px; border-radius: 10px; border: none; background: var(--accent); color: #000; font-weight: bold; cursor: pointer; }}
    .info {{ font-size: 10px; color: gray; }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div><strong>Gemini Chat</strong> <span class="info" id="sidDisplay"></span></div>
      <select id="modelSelect" style="background:#0d1117; color:white; border:1px solid var(--line); border-radius:5px;">
        {"".join([f'<option value="{m["key"]}">{m["name"]}</option>' for m in MODEL_PRESETS])}
      </select>
    </header>
    <section class="chat" id="chat"></section>
    <footer class="composer">
      <form id="chatForm">
        <textarea id="messageInput" placeholder="Nhập câu hỏi..."></textarea>
        <button type="submit">Gửi</button>
      </form>
    </footer>
  </main>
  <script>
    // ID RIÊNG CHO MỖI ĐIỆN THOẠI
    let sessionId = localStorage.getItem("chat_sid");
    if(!sessionId) {{
        sessionId = "m_" + Math.random().toString(36).substring(2, 10);
        localStorage.setItem("chat_sid", sessionId);
    }}
    document.getElementById("sidDisplay").textContent = "ID: " + sessionId;

    const chat = document.getElementById("chat");
    const input = document.getElementById("messageInput");
    const displayedIds = new Set();

    function append(role, text, id = null) {{
      if(id && displayedIds.has(id)) return null;
      if(id) displayedIds.add(id);
      const div = document.createElement("div");
      div.className = `message ${{role}}`;
      div.textContent = text;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
      return div;
    }}

    document.getElementById("chatForm").onsubmit = async (e) => {{
      e.preventDefault();
      const msg = input.value.trim(); if(!msg) return;
      input.value = ""; input.disabled = true;
      append("user", msg, "u_" + Date.now());
      const aiDiv = append("assistant", "...", "a_" + Date.now());

      try {{
        const res = await fetch("/api/chat", {{
          method: "POST",
          body: JSON.stringify({{ 
            message: msg, 
            session_id: sessionId,
            model_key: document.getElementById("modelSelect").value 
          }})
        }});
        const reader = res.body.getReader();
        let full = "";
        while (true) {{
          const {{ value, done }} = await reader.read();
          if (done) break;
          full += new TextDecoder().decode(value);
          aiDiv.textContent = full;
          chat.scrollTop = chat.scrollHeight;
        }}
      }} catch(e) {{ aiDiv.textContent = "Lỗi kết nối."; }}
      finally {{ input.disabled = false; input.focus(); setTimeout(loadHistory, 1000); }}
    }};

    async function loadHistory() {{
      const res = await fetch("/api/history?session_id=" + sessionId);
      const data = await res.json();
      if(data.history.length === 0 && displayedIds.size > 0) {{
          chat.innerHTML = ""; displayedIds.clear();
      }} else {{
          data.history.forEach(m => append(m.role, m.content, m.id));
      }}
    }}
    
    // ĐỒNG BỘ 5 GIÂY MỘT LẦN
    setInterval(loadHistory, 5000); 
    loadHistory();
  </script>
</body>
</html>
"""

class AIRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        update_activity()
        if self.path.startswith("/api/history"):
            qs = parse.parse_qs(parse.urlparse(self.path).query)
            sid = qs.get("session_id", ["default"])[0]
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            with HISTORY_LOCK:
                hist = SESSIONS.get(sid, [])
                self.wfile.write(json.dumps({"history": hist}).encode())
        else:
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(html_page().encode())

    def do_POST(self):
        update_activity()
        if self.path == "/api/chat":
            size = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(size).decode())
            self.handle_chat(data)

    def handle_chat(self, data):
        self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
        msg = data.get("message", ""); sid = data.get("session_id", "default")
        model = MODEL_PRESETS_BY_KEY.get(data.get("model_key"), MODEL_PRESETS[0])["model"]
        
        try:
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            with HISTORY_LOCK:
                if sid not in SESSIONS: SESSIONS[sid] = []
                hist = SESSIONS[sid]

            ctx = [{"role": "user" if h["role"] == "user" else "model", "parts": [{"text": h["content"]}]} for h in hist]
            ctx.append({"role": "user", "parts": [{"text": msg}]})
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {"contents": ctx, "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]}}
            
            req = request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with request.urlopen(req) as res:
                ans = json.loads(res.read().decode())["candidates"][0]["content"]["parts"][0]["text"]
            
            acc = ""
            for word in ans.split(' '):
                self.wfile.write((word + " ").encode()); self.wfile.flush()
                acc += word + " "; time.sleep(0.02)
            
            with HISTORY_LOCK:
                SESSIONS[sid].append({"role": "user", "content": msg, "id": str(uuid.uuid4())})
                SESSIONS[sid].append({"role": "assistant", "content": acc.strip(), "id": str(uuid.uuid4())})
                SESSIONS[sid] = SESSIONS[sid][-MAX_HISTORY_MESSAGES:]
                # Lưu file session
                f = HISTORY_DIR / f"{sid}.json"
                f.write_text(json.dumps(SESSIONS[sid], ensure_ascii=False), encoding="utf-8")
        except Exception as e: self.wfile.write(f"Lỗi: {str(e)}".encode())

def run():
    # Load lại lịch sử cũ từ file nếu có
    for f in HISTORY_DIR.glob("*.json"):
        try: SESSIONS[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except: pass
    threading.Thread(target=auto_delete_worker, daemon=True).start()
    print(f"Server chạy cổng {PORT}. Check 5s/lần. Tự hủy sau 5p vắng bóng.")
    ThreadingHTTPServer((HOST, PORT), AIRequestHandler).serve_forever()

if __name__ == "__main__":
    run()
