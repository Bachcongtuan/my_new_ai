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

# --- CONFIG ---
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))
AUTO_DELETE_SECONDS = 300 
LAST_ACTIVITY_TIME = time.time()

SYSTEM_PROMPT = "You are a practical AI assistant. Give clear, concise, useful answers."
HISTORY_DIR = Path(__file__).parent / "sessions"
HISTORY_DIR.mkdir(exist_ok=True)
HISTORY_LOCK = threading.Lock()

MODEL_PRESETS = [
    {"key": "flash", "name": "Gemini 2.5 Flash", "model": "gemini-2.5-flash", "desc": "Fast balanced default for web chat."},
    {"key": "pro", "name": "Gemini 2.5 Pro", "model": "gemini-2.5-pro", "desc": "Complex reasoning and creativity."},
    {"key": "flash_lite", "name": "Gemini 2.5 Flash-Lite", "model": "gemini-2.5-flash-lite", "desc": "Lightweight and fastest response."},
]
MODEL_PRESETS_BY_KEY = {item["key"]: item for item in MODEL_PRESETS}
SESSIONS = {}

def update_activity():
    global LAST_ACTIVITY_TIME
    LAST_ACTIVITY_TIME = time.time()

def auto_delete_worker():
    global SESSIONS
    while True:
        time.sleep(5)
        if time.time() - LAST_ACTIVITY_TIME > AUTO_DELETE_SECONDS:
            with HISTORY_LOCK:
                if SESSIONS or list(HISTORY_DIR.glob("*.json")):
                    SESSIONS.clear()
                    for f in HISTORY_DIR.glob("*.json"):
                        try: f.unlink()
                        except: pass

def html_page():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini Web Chat</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card: #1e293b;
      --border: rgba(255, 255, 255, 0.1);
      --text-main: #f1f5f9;
      --text-dim: #94a3b8;
      --accent: #10b981;
      --user-msg: #334155;
      --ai-msg: #1e293b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 20px; font-family: 'Inter', system-ui, sans-serif;
      background: #020617; color: var(--text-main);
      display: flex; justify-content: center; align-items: center; min-height: 100vh;
    }}
    .container {{
      width: 100%; max-width: 1100px; height: 90vh;
      background: var(--card); border: 1px solid var(--border);
      border-radius: 16px; display: flex; flex-direction: column;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); overflow: hidden;
    }}
    .header {{
      padding: 24px; border-bottom: 1px solid var(--border);
      display: flex; justify-content: space-between; align-items: flex-start;
    }}
    .brand h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
    .brand p {{ margin: 4px 0 0; font-size: 13px; color: var(--text-dim); line-height: 1.5; }}
    .controls {{ display: flex; flex-direction: column; align-items: flex-end; gap: 10px; }}
    
    .chat-area {{ flex: 1; padding: 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; background: rgba(0,0,0,0.1); }}
    .msg {{ max-width: 80%; padding: 14px 18px; border-radius: 12px; font-size: 15px; line-height: 1.6; border: 1px solid var(--border); }}
    .user {{ align-self: flex-end; background: var(--user-msg); border-bottom-right-radius: 4px; }}
    .assistant {{ align-self: flex-start; background: var(--ai-msg); border-bottom-left-radius: 4px; }}
    
    .input-area {{ padding: 24px; border-top: 1px solid var(--border); }}
    .input-box {{
      position: relative; display: flex; align-items: flex-end;
      background: rgba(15, 23, 42, 0.6); border: 1px solid var(--border);
      border-radius: 12px; padding: 12px;
    }}
    textarea {{
      flex: 1; background: transparent; border: none; color: white;
      resize: none; font-family: inherit; font-size: 15px; outline: none; padding: 8px;
    }}
    .send-btn {{
      background: #d1fae5; color: #064e3b; border: none; padding: 10px 20px;
      border-radius: 8px; font-weight: 600; cursor: pointer; transition: 0.2s;
    }}
    .send-btn:hover {{ background: var(--accent); color: white; }}
    .footer-note {{ margin-top: 10px; font-size: 12px; color: var(--text-dim); }}
    
    select, button.clear-btn {{
      background: #1e293b; color: white; border: 1px solid var(--border);
      padding: 8px 12px; border-radius: 8px; cursor: pointer;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header class="header">
      <div class="brand">
        <h1>Gemini Web Chat</h1>
        <p id="modelDesc">Fast balanced default for web chat. Closest replacement for Gemini 1.5 Flash.</p>
      </div>
      <div class="controls">
        <div style="font-size:12px; color:var(--text-dim)">Model preset</div>
        <div style="display:flex; gap:10px;">
          <select id="modelSelect">
            {"".join([f'<option value="{m["key"]}">{m["name"]} | {m["model"]}</option>' for m in MODEL_PRESETS])}
          </select>
          <button class="clear-btn" onclick="location.reload()">Clear history</button>
        </div>
      </div>
    </header>

    <div class="chat-area" id="chat"></div>

    <div class="input-area">
      <form id="chatForm" class="input-box">
        <textarea id="msgInput" rows="1" placeholder="Ask anything. Shift+Enter for a new line."></textarea>
        <button type="submit" class="send-btn">Send</button>
      </form>
      <div class="footer-note" id="status">Ready.</div>
    </div>
  </div>

  <script>
    let sessionId = localStorage.getItem("chat_sid") || ("m_" + Math.random().toString(36).substring(2, 10));
    localStorage.setItem("chat_sid", sessionId);

    const chat = document.getElementById("chat");
    const input = document.getElementById("msgInput");
    const status = document.getElementById("status");
    const modelSelect = document.getElementById("modelSelect");
    const displayedIds = new Set();

    function append(role, text, id = null) {{
      if(id && displayedIds.has(id)) return null;
      if(id) displayedIds.add(id);
      const div = document.createElement("div");
      div.className = `msg ${{role}}`;
      div.textContent = text;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
      return div;
    }}

    document.getElementById("chatForm").onsubmit = async (e) => {{
      e.preventDefault();
      const msg = input.value.trim(); if(!msg) return;
      input.value = ""; input.disabled = true;
      append("user", msg, "u" + Date.now());
      const aiDiv = append("assistant", "...", "a" + Date.now());
      
      try {{
        const res = await fetch("/api/chat", {{
          method: "POST",
          body: JSON.stringify({{ message: msg, session_id: sessionId, model_key: modelSelect.value }})
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
      }} catch(e) {{ aiDiv.textContent = "Error connecting to server."; }}
      finally {{ input.disabled = false; input.focus(); }}
    }};

    async function sync() {{
      const res = await fetch("/api/history?session_id=" + sessionId);
      const data = await res.json();
      if(data.history.length === 0 && displayedIds.size > 0) {{
          chat.innerHTML = ""; displayedIds.clear();
          status.textContent = "History cleared.";
      }} else {{
          data.history.forEach(m => append(m.role, m.content, m.id));
      }}
    }}
    setInterval(sync, 5000); sync();
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
            
            # Stream effect
            acc = ""
            for word in ans.split(' '):
                self.wfile.write((word + " ").encode()); self.wfile.flush()
                acc += word + " "; time.sleep(0.01)
            
            with HISTORY_LOCK:
                SESSIONS[sid].append({"role": "user", "content": msg, "id": str(uuid.uuid4())})
                SESSIONS[sid].append({"role": "assistant", "content": acc.strip(), "id": str(uuid.uuid4())})
                SESSIONS[sid] = SESSIONS[sid][-20:]
                (HISTORY_DIR / f"{sid}.json").write_text(json.dumps(SESSIONS[sid], ensure_ascii=False))
        except Exception as e: self.wfile.write(f"Error: {str(e)}".encode())

def run():
    for f in HISTORY_DIR.glob("*.json"):
        try: SESSIONS[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except: pass
    threading.Thread(target=auto_delete_worker, daemon=True).start()
    print(f"UI Server running on port {PORT}..."); ThreadingHTTPServer((HOST, PORT), AIRequestHandler).serve_forever()

if __name__ == "__main__":
    run()
