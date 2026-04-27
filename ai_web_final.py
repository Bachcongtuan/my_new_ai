# Copyright (c) 2026 Bach Cong Tuan
# All rights reserved.
import json
import os
import threading
import time
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))

# CẤU HÌNH TỰ HỦY: 300 giây = 5 phút vắng bóng
AUTO_DELETE_SECONDS = 300 
LAST_ACTIVITY_TIME = time.time()

SYSTEM_PROMPT = "You are a practical AI assistant. Give clear, concise, useful answers."
# Folder chứa các file lịch sử riêng biệt
HISTORY_DIR = Path(__file__).parent / "sessions"
HISTORY_DIR.mkdir(exist_ok=True)
HISTORY_LOCK = threading.Lock()

MODEL_PRESETS = [
    {"key": "flash", "name": "Gemini 2.5 Flash", "model": "gemini-2.5-flash", "description": "Tốc độ nhanh, ổn định."},
    {"key": "pro", "name": "Gemini 2.5 Pro", "model": "gemini-2.5-pro", "description": "Lập luận phức tạp."},
]
MODEL_PRESETS_BY_KEY = {item["key"]: item for item in MODEL_PRESETS}

# Từ điển lưu trữ lịch sử trong bộ nhớ: { session_id: [messages] }
SESSIONS = {}

def get_session_file(session_id):
    return HISTORY_DIR / f"chat_{session_id}.json"

def load_all_sessions():
    for f in HISTORY_DIR.glob("chat_*.json"):
        try:
            s_id = f.stem.replace("chat_", "")
            SESSIONS[s_id] = json.loads(f.read_text(encoding="utf-8"))
        except: continue

def save_session(session_id):
    if session_id in SESSIONS:
        f = get_session_file(session_id)
        f.write_text(json.dumps(SESSIONS[session_id], ensure_ascii=False, indent=2), encoding="utf-8")

def auto_delete_worker():
    global LAST_ACTIVITY_TIME
    while True:
        time.sleep(30)
        if time.time() - LAST_ACTIVITY_TIME > AUTO_DELETE_SECONDS:
            with HISTORY_LOCK:
                if SESSIONS:
                    print(f"[{datetime.now()}] Hết thời gian chờ. Đang xóa toàn bộ {len(SESSIONS)} phiên làm việc.")
                    SESSIONS.clear()
                    for f in HISTORY_DIR.glob("*.json"): f.unlink()

def html_page():
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini Private Chat</title>
  <style>
    :root {{
      --bg: #0d1117; --line: #30363d; --text: #c9d1d9; --accent: #58a6ff;
    }}
    body {{ margin: 0; font-family: sans-serif; color: var(--text); background: var(--bg); display: flex; justify-content: center; padding: 10px; }}
    .shell {{ width: 100%; max-width: 800px; height: 92vh; border: 1px solid var(--line); border-radius: 12px; display: grid; grid-template-rows: auto 1fr auto; background: #161b22; }}
    .topbar {{ padding: 10px 20px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; }}
    .chat {{ padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }}
    .message {{ max-width: 85%; padding: 10px; border-radius: 8px; border: 1px solid var(--line); font-size: 15px; white-space: pre-wrap; }}
    .user {{ align-self: flex-end; background: #1f2937; }}
    .assistant {{ align-self: flex-start; background: #0d1117; }}
    .composer {{ padding: 15px; border-top: 1px solid var(--line); }}
    form {{ display: flex; gap: 10px; }}
    textarea {{ flex: 1; height: 40px; background: #010409; color: white; border: 1px solid var(--line); border-radius: 6px; padding: 10px; outline: none; resize: none; }}
    button {{ background: #238636; color: white; border: none; padding: 0 15px; border-radius: 6px; font-weight: bold; }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div><strong>Gemini</strong> <small id="devId" style="color:gray; font-size:10px;"></small></div>
      <select id="modelSelect" style="background:#010409; color:white; border:1px solid var(--line);">
        {"".join([f'<option value="{m["key"]}">{m["name"]}</option>' for m in MODEL_PRESETS])}
      </select>
    </header>
    <section class="chat" id="chat"></section>
    <footer class="composer">
      <form id="chatForm">
        <textarea id="messageInput" placeholder="Hỏi gì đó..."></textarea>
        <button type="submit">Gửi</button>
      </form>
    </footer>
  </main>
  <script>
    // TẠO ID RIÊNG CHO ĐIỆN THOẠI NÀY
    let sessionId = localStorage.getItem("chat_session_id");
    if(!sessionId) {{
        sessionId = "mob_" + Math.random().toString(36).substring(2, 15);
        localStorage.setItem("chat_session_id", sessionId);
    }}
    document.getElementById("devId").textContent = "ID: " + sessionId;

    const chat = document.getElementById("chat");
    const input = document.getElementById("messageInput");

    function append(role, text) {{
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
      append("user", msg);
      const aiDiv = append("assistant", "...");
      
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
        let txt = "";
        while (true) {{
          const {{ value, done }} = await reader.read();
          if (done) break;
          txt += new TextDecoder().decode(value);
          aiDiv.textContent = txt;
          chat.scrollTop = chat.scrollHeight;
        }}
      }} catch(e) {{ aiDiv.textContent = "Lỗi kết nối."; }}
      finally {{ input.disabled = false; input.focus(); }}
    }};

    async function load() {{
      const res = await fetch("/api/history?session_id=" + sessionId);
      const data = await res.json();
      chat.innerHTML = "";
      data.history.forEach(m => append(m.role, m.content));
    }}
    load();
  </script>
</body>
</html>
"""

class AIRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        time_update()
        if self.path.startswith("/api/history"):
            query = parse.parse_qs(parse.urlparse(self.path).query)
            s_id = query.get("session_id", ["default"])[0]
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            with HISTORY_LOCK:
                hist = SESSIONS.get(s_id, [])
                self.wfile.write(json.dumps({"history": hist}).encode())
        else:
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(html_page().encode())

    def do_POST(self):
        time_update()
        if self.path == "/api/chat":
            size = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(size).decode())
            self.handle_chat(data)

    def handle_chat(self, data):
        self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
        msg = data.get("message", ""); s_id = data.get("session_id", "default")
        model = MODEL_PRESETS_BY_KEY.get(data.get("model_key"), MODEL_PRESETS[0])["model"]
        
        try:
            with HISTORY_LOCK:
                if s_id not in SESSIONS: SESSIONS[s_id] = []
                current_hist = SESSIONS[s_id]
            
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            ctx = [{"role": "user" if h["role"] == "user" else "model", "parts": [{"text": h["content"]}]} for h in current_hist]
            ctx.append({"role": "user", "parts": [{"text": msg}]})
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {"contents": ctx, "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]}}
            
            req = request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with request.urlopen(req) as res:
                ans = json.loads(res.read().decode())["candidates"][0]["content"]["parts"][0]["text"]
            
            # Streaming giả lập
            acc = ""
            for word in ans.split(' '):
                self.wfile.write((word + " ").encode()); self.wfile.flush()
                acc += word + " "; time.sleep(0.02)
            
            with HISTORY_LOCK:
                SESSIONS[s_id].append({"role": "user", "content": msg})
                SESSIONS[s_id].append({"role": "assistant", "content": acc.strip()})
                # Giới hạn 20 câu mỗi session
                SESSIONS[s_id] = SESSIONS[s_id][-20:]
                save_session(s_id)
        except Exception as e: self.wfile.write(f"Lỗi: {str(e)}".encode())

def time_update():
    global LAST_ACTIVITY_TIME
    LAST_ACTIVITY_TIME = time.time()

def run():
    load_all_sessions()
    threading.Thread(target=auto_delete_worker, daemon=True).start()
    print(f"Server chạy cổng {PORT}. ID riêng cho từng máy. Tự hủy sau 5p."); 
    ThreadingHTTPServer((HOST, PORT), AIRequestHandler).serve_forever()

if __name__ == "__main__":
    run()
