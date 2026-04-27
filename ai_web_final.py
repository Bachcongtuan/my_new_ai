# Copyright (c) 2026 Bach Cong Tuan
# All rights reserved.
import json
import os
import threading
import uuid
import random
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request

# --- CẤU HÌNH ---
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))
SYSTEM_PROMPT = "You are a practical AI assistant. Give clear, concise, useful answers."

# Quản lý file và session
SESSIONS_DIR = Path(__file__).parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)
MAX_HISTORY = 20

MODEL_PRESETS = [
    {"key": "flash", "name": "Gemini 2.5 Flash", "model": "gemini-2.5-flash"},
    {"key": "pro", "name": "Gemini 2.5 Pro", "model": "gemini-2.5-pro"},
    {"key": "flash_lite", "name": "Gemini 2.5 Flash-Lite", "model": "gemini-2.5-flash-lite"},
]
MODEL_MAP = {m["key"]: m for m in MODEL_PRESETS}

# Lấy danh sách Keys từ môi trường
API_KEYS = [
    os.getenv("GEMINI_API_KEY_1", "").strip(),
    os.getenv("GEMINI_API_KEY_2", "").strip(),
    os.getenv("GEMINI_API_KEY_3", "").strip()
]
# Loại bỏ các key trống
API_KEYS = [k for k in API_KEYS if k]

def get_session_history(sid: str) -> list:
    path = SESSIONS_DIR / f"{sid}.json"
    if not path.exists(): return []
    try: return json.loads(path.read_text(encoding="utf-8"))
    except: return []

def save_session_history(sid: str, history: list):
    path = SESSIONS_DIR / f"{sid}.json"
    path.write_text(json.dumps(history[-MAX_HISTORY:], ensure_ascii=False), encoding="utf-8")

def html_page() -> str:
    # (Phần CSS giữ nguyên giao diện đẹp từ bản trước bạn thích)
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini Crystal UI (Multi-Key)</title>
  <style>
    :root {{
      --bg: #030712; --glass: rgba(17, 24, 39, 0.7); --border: rgba(255, 255, 255, 0.08);
      --accent: #10b981; --text: #f9fafb; --text-dim: #9ca3af; --user-msg: #1f2937; --ai-msg: rgba(31, 41, 55, 0.4);
    }}
    body {{
      margin: 0; padding: 20px; min-height: 100vh; background: var(--bg);
      background-image: radial-gradient(circle at 0% 0%, rgba(16, 185, 129, 0.05) 0%, transparent 50%);
      font-family: 'Inter', sans-serif; color: var(--text); display: flex; justify-content: center; align-items: center;
    }}
    .app-container {{
      width: 100%; max-width: 1100px; height: 90vh; background: var(--glass);
      backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 24px;
      display: flex; flex-direction: column; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); overflow: hidden;
    }}
    .header {{ padding: 20px 32px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }}
    .chat-view {{ flex: 1; overflow-y: auto; padding: 32px; display: flex; flex-direction: column; gap: 20px; }}
    .message {{ max-width: 80%; padding: 14px 18px; border-radius: 18px; line-height: 1.6; animation: slideUp 0.3s; }}
    .user {{ align-self: flex-end; background: var(--user-msg); border-bottom-right-radius: 4px; }}
    .assistant {{ align-self: flex-start; background: var(--ai-msg); border: 1px solid var(--border); border-bottom-left-radius: 4px; }}
    .input-wrapper {{ padding: 24px; border-top: 1px solid var(--border); }}
    .input-box {{ background: rgba(255,255,255,0.03); border: 1px solid var(--border); border-radius: 14px; padding: 10px; display: flex; gap: 10px; }}
    textarea {{ flex: 1; background: transparent; border: none; color: white; resize: none; outline: none; font-size: 15px; }}
    .btn-send {{ background: var(--accent); border: none; padding: 10px 20px; border-radius: 10px; cursor: pointer; font-weight: bold; }}
    @keyframes slideUp {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; }} }}
  </style>
</head>
<body>
  <div class="app-container">
    <header class="header">
      <div><h2 style="margin:0">Gemini Pro</h2><span id="st" style="font-size:12px;color:var(--text-dim)">Keys sẵn sàng: {len(API_KEYS)}</span></div>
      <select id="md" style="background:#111827;color:white;border:1px solid var(--border);padding:5px;border-radius:8px;">
        {"".join([f'<option value="{m["key"]}">{m["name"]}</option>' for m in MODEL_PRESETS])}
      </select>
    </header>
    <div class="chat-view" id="chat"></div>
    <div class="input-wrapper">
      <form id="f" class="input-box">
        <textarea id="in" rows="1" placeholder="Nhập tin nhắn..."></textarea>
        <button type="submit" class="btn-send">Gửi</button>
      </form>
    </div>
  </div>
  <script>
    const chat = document.getElementById("chat"), input = document.getElementById("in"), st = document.getElementById("st");
    let sid = localStorage.getItem("sid") || "s_" + Math.random().toString(36).substr(2, 9);
    localStorage.setItem("sid", sid);

    function add(r, t) {{
      const d = document.createElement("div"); d.className = `message ${{r}}`; d.innerText = t;
      chat.appendChild(d); chat.scrollTop = chat.scrollHeight; return d;
    }}

    document.getElementById("f").onsubmit = async (e) => {{
      e.preventDefault(); const v = input.value.trim(); if(!v) return;
      input.value = ""; add("user", v); const ai = add("assistant", "...");
      try {{
        const res = await fetch("/api/chat", {{
          method: "POST",
          body: JSON.stringify({{ message: v, sid: sid, model: document.getElementById("md").value }})
        }});
        const data = await res.json();
        ai.innerText = data.reply || data.error;
      }} catch {{ ai.innerText = "Lỗi kết nối."; }}
    }};

    (async () => {{
      const res = await fetch("/api/history?sid=" + sid);
      const data = await res.json();
      data.history.forEach(m => add(m.role, m.content));
    }})();
  </script>
</body>
</html>
"""

class AIHandler(BaseHTTPRequestHandler):
    # Biến tĩnh để theo dõi key hiện tại
    key_index = 0

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(html_page().encode())
        elif self.path.startswith("/api/history"):
            sid = parse.parse_qs(parse.urlparse(self.path).query).get("sid", ["default"])[0]
            self.send_json({"history": get_session_history(sid)})

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(content_len).decode())

        if self.path == "/api/chat":
            sid, msg, model_key = data.get("sid"), data.get("message"), data.get("model")
            model_code = MODEL_MAP.get(model_key, MODEL_PRESETS[0])["model"]
            history = get_session_history(sid)
            
            contents = [{"role": "user" if h["role"] == "user" else "model", "parts": [{"text": h["content"]}]} for h in history]
            contents.append({"role": "user", "parts": [{"text": msg}]})

            success = False
            reply = ""
            
            # Cơ chế xoay vòng Key (Thử tối đa bằng số lượng Key bạn có)
            for _ in range(len(API_KEYS)):
                current_key = API_KEYS[AIHandler.key_index]
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_code}:generateContent?key={current_key}"
                    payload = {"contents": contents, "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]}}
                    req = request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
                    
                    with request.urlopen(req, timeout=15) as res:
                        res_data = json.loads(res.read().decode())
                        reply = res_data["candidates"][0]["content"]["parts"][0]["text"]
                        success = True
                        break # Thành công thì thoát vòng lặp
                except Exception as e:
                    # Nếu lỗi (hết quota), chuyển sang key tiếp theo
                    AIHandler.key_index = (AIHandler.key_index + 1) % len(API_KEYS)
                    reply = f"Key {AIHandler.key_index} bị lỗi, đang thử Key tiếp theo..."
            
            if success:
                history.append({"role": "user", "content": msg})
                history.append({"role": "assistant", "content": reply})
                save_session_history(sid, history)
                self.send_json({"reply": reply})
            else:
                self.send_json({"error": "Tất cả 3 Keys đều hết hạn mức hoặc lỗi."}, 500)

def run():
    print(f"Hệ thống Multi-Key đang chạy tại Port: {PORT} với {len(API_KEYS)} Keys.")
    ThreadingHTTPServer((HOST, PORT), AIHandler).serve_forever()

if __name__ == "__main__": run()
