# Copyright (c) 2026 Bach Cong Tuan
# All rights reserved.
import json
import os
import threading
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request

# --- CONFIGURATION ---
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))
SYSTEM_PROMPT = "You are a practical AI assistant. Give clear, concise, useful answers."

# Quản lý phiên và lịch sử
SESSIONS_DIR = Path(__file__).parent / "sessions"
SESSIONS_DIR.mkdir(exist_ok=True)
SESSION_LOCK = threading.Lock()
MAX_HISTORY = 20

MODEL_PRESETS = [
    {"key": "flash", "name": "Gemini 2.5 Flash", "model": "gemini-2.5-flash", "desc": "Cân bằng tốc độ và chất lượng."},
    {"key": "pro", "name": "Gemini 2.5 Pro", "model": "gemini-2.5-pro", "desc": "Lập luận chuyên sâu cho yêu cầu khó."},
    {"key": "flash_lite", "name": "Gemini 2.5 Flash-Lite", "model": "gemini-2.5-flash-lite", "desc": "Phản hồi cực nhanh."},
]
MODEL_MAP = {m["key"]: m for m in MODEL_PRESETS}

def get_session_history(sid: str) -> list:
    path = SESSIONS_DIR / f"{sid}.json"
    if not path.exists(): return []
    try: return json.loads(path.read_text(encoding="utf-8"))
    except: return []

def save_session_history(sid: str, history: list):
    path = SESSIONS_DIR / f"{sid}.json"
    path.write_text(json.dumps(history[-MAX_HISTORY:], ensure_ascii=False), encoding="utf-8")

# --- HTML & CSS UI ---
def html_page() -> str:
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini Crystal UI</title>
  <style>
    :root {{
      --bg: #030712;
      --glass: rgba(17, 24, 39, 0.7);
      --border: rgba(255, 255, 255, 0.08);
      --accent: #10b981;
      --accent-glow: rgba(16, 185, 129, 0.2);
      --text: #f9fafb;
      --text-dim: #9ca3af;
      --user-msg: #1f2937;
      --ai-msg: rgba(31, 41, 55, 0.4);
    }}

    * {{ box-sizing: border-box; -webkit-font-smoothing: antialiased; }}
    
    body {{
      margin: 0; padding: 20px; min-height: 100vh;
      background: var(--bg);
      background-image: 
        radial-gradient(circle at 0% 0%, rgba(16, 185, 129, 0.05) 0%, transparent 50%),
        radial-gradient(circle at 100% 100%, rgba(59, 130, 246, 0.05) 0%, transparent 50%);
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      color: var(--text);
      display: flex; justify-content: center; align-items: center;
    }}

    .app-container {{
      width: 100%; max-width: 1200px; height: 90vh;
      background: var(--glass);
      backdrop-filter: blur(20px);
      border: 1px solid var(--border);
      border-radius: 24px;
      display: flex; flex-direction: column;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
      overflow: hidden;
    }}

    .header {{
      padding: 20px 32px;
      border-bottom: 1px solid var(--border);
      display: flex; justify-content: space-between; align-items: center;
      background: rgba(255,255,255,0.02);
    }}

    .brand h1 {{ margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }}
    .brand span {{ font-size: 12px; color: var(--text-dim); }}

    .controls {{ display: flex; gap: 12px; align-items: center; }}
    
    select, button.secondary {{
      background: rgba(255,255,255,0.05);
      border: 1px solid var(--border);
      color: white; padding: 8px 14px; border-radius: 10px;
      font-size: 13px; cursor: pointer; transition: 0.2s;
    }}
    
    button.secondary:hover {{ background: rgba(255,255,255,0.1); }}

    .chat-view {{
      flex: 1; overflow-y: auto; padding: 32px;
      display: flex; flex-direction: column; gap: 24px;
      scroll-behavior: smooth;
    }}

    /* Thanh cuộn đẹp */
    .chat-view::-webkit-scrollbar {{ width: 6px; }}
    .chat-view::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 10px; }}

    .message {{
      max-width: 80%; padding: 16px 20px; border-radius: 18px;
      line-height: 1.6; font-size: 15px; position: relative;
      animation: slideUp 0.3s ease-out;
    }}

    .message.user {{
      align-self: flex-end; background: var(--user-msg);
      border-bottom-right-radius: 4px;
      border: 1px solid rgba(255,255,255,0.05);
    }}

    .message.assistant {{
      align-self: flex-start; background: var(--ai-msg);
      border-bottom-left-radius: 4px;
      border: 1px solid var(--border);
    }}

    .input-wrapper {{
      padding: 24px 32px; border-top: 1px solid var(--border);
      background: rgba(0,0,0,0.2);
    }}

    .input-box {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: 16px; padding: 8px;
      display: flex; align-items: flex-end; gap: 12px;
      transition: 0.3s;
    }}

    .input-box:focus-within {{
      border-color: var(--accent);
      box-shadow: 0 0 0 4px var(--accent-glow);
    }}

    textarea {{
      flex: 1; background: transparent; border: none; color: white;
      padding: 12px; resize: none; outline: none; font-size: 15px;
      max-height: 200px; font-family: inherit;
    }}

    .btn-send {{
      background: var(--accent); color: #064e3b;
      border: none; width: 44px; height: 44px; border-radius: 12px;
      cursor: pointer; font-weight: bold; transition: 0.2s;
      display: flex; align-items: center; justify-content: center;
    }}

    .btn-send:hover {{ transform: scale(1.05); filter: brightness(1.1); }}
    .btn-send:disabled {{ opacity: 0.5; cursor: not-allowed; }}

    @keyframes slideUp {{
      from {{ opacity: 0; transform: translateY(10px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    @media (max-width: 768px) {{
      body {{ padding: 0; }}
      .app-container {{ height: 100vh; border-radius: 0; border: none; }}
      .header {{ padding: 16px; }}
    </style>
</head>
<body>
  <div class="app-container">
    <header class="header">
      <div class="brand">
        <h1>Gemini AI</h1>
        <span id="status">Sẵn sàng kết nối</span>
      </div>
      <div class="controls">
        <select id="modelSelect">
          {"".join([f'<option value="{m["key"]}">{m["name"]}</option>' for m in MODEL_PRESETS])}
        </select>
        <button class="secondary" onclick="clearHistory()">Xóa Chat</button>
      </div>
    </header>

    <div class="chat-view" id="chat"></div>

    <div class="input-wrapper">
      <form id="chatForm" class="input-box">
        <textarea id="msgIn" rows="1" placeholder="Hỏi bất cứ điều gì..." required></textarea>
        <button type="submit" class="btn-send" id="btnSend">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
        </button>
      </form>
    </div>
  </div>

  <script>
    const chat = document.getElementById("chat");
    const input = document.getElementById("msgIn");
    const form = document.getElementById("chatForm");
    const btn = document.getElementById("btnSend");
    const status = document.getElementById("status");

    // Lấy ID định danh máy khách
    let sid = localStorage.getItem("sid") || "s_" + Math.random().toString(36).substr(2, 9);
    localStorage.setItem("sid", sid);

    function append(role, text) {{
      const div = document.createElement("div");
      div.className = `message ${{role}}`;
      div.innerText = text;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
      return div;
    }}

    form.onsubmit = async (e) => {{
      e.preventDefault();
      const val = input.value.trim(); if(!val) return;
      
      input.value = ""; input.style.height = "auto";
      append("user", val);
      const aiMsg = append("assistant", "...");
      
      input.disabled = true; btn.disabled = true;
      status.innerText = "Đang xử lý...";

      try {{
        const res = await fetch("/api/chat", {{
          method: "POST",
          body: JSON.stringify({{ 
            message: val, 
            sid: sid, 
            model: document.getElementById("modelSelect").value 
          }})
        }});
        const data = await res.json();
        aiMsg.innerText = data.reply || "Lỗi phản hồi.";
      }} catch(err) {{
        aiMsg.innerText = "Không thể kết nối API.";
      }} finally {{
        input.disabled = false; btn.disabled = false;
        status.innerText = "Sẵn sàng";
        input.focus();
      }}
    }};

    async function clearHistory() {{
      if(!confirm("Xóa toàn bộ hội thoại?")) return;
      await fetch("/api/clear?sid=" + sid, {{ method: "POST" }});
      chat.innerHTML = "";
    }}

    // Tự động giãn nở textarea
    input.oninput = function() {{
      this.style.height = "auto";
      this.style.height = (this.scrollHeight) + "px";
    }};

    // Load lịch sử cũ
    (async () => {{
      const res = await fetch("/api/history?sid=" + sid);
      const data = await res.json();
      data.history.forEach(m => append(m.role, m.content));
    }})();
  </script>
</body>
</html>
"""

class AIHandler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_page().encode("utf-8"))
        elif self.path.startswith("/api/history"):
            params = parse.parse_qs(parse.urlparse(self.path).query)
            sid = params.get("sid", ["default"])[0]
            self.send_json({"history": get_session_history(sid)})

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(content_len).decode('utf-8'))

        if self.path == "/api/chat":
            sid = data.get("sid", "default")
            msg = data.get("message", "")
            model_key = data.get("model", "flash")
            model_code = MODEL_MAP.get(model_key, MODEL_PRESETS[0])["model"]
            
            # API CALL
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            history = get_session_history(sid)
            
            contents = [{"role": "user" if h["role"] == "user" else "model", "parts": [{"text": h["content"]}]} for h in history]
            contents.append({"role": "user", "parts": [{"text": msg}]})

            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_code}:generateContent?key={api_key}"
                payload = {"contents": contents, "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]}}
                req = request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
                
                with request.urlopen(req) as response:
                    res_data = json.loads(response.read().decode())
                    reply = res_data["candidates"][0]["content"]["parts"][0]["text"]
                
                # Cập nhật lịch sử
                history.append({"role": "user", "content": msg})
                history.append({"role": "assistant", "content": reply})
                save_session_history(sid, history)
                
                self.send_json({"reply": reply})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path.startswith("/api/clear"):
            params = parse.parse_qs(parse.urlparse(self.path).query)
            sid = params.get("sid", ["default"])[0]
            (SESSIONS_DIR / f"{sid}.json").unlink(missing_ok=True)
            self.send_json({"status": "cleared"})

def run():
    server = ThreadingHTTPServer((HOST, PORT), AIHandler)
    print(f"Server chạy tại Port: {PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run()
