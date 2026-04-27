# Copyright (c) 2026 Bach Cong Tuan
# All rights reserved.
import json
import os
import threading
import time
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5000))

SYSTEM_PROMPT = "You are a practical AI assistant. Give clear, concise, useful answers."
HISTORY_FILE = Path(__file__).with_name("chat_history.json")
HISTORY_LOCK = threading.Lock()
MAX_HISTORY_MESSAGES = max(2, int(os.getenv("MAX_HISTORY_MESSAGES", "16")))

MODEL_PRESETS = [
    {"key": "flash", "name": "Gemini 2.5 Flash", "model": "gemini-2.5-flash", "description": "Cân bằng tốc độ và chất lượng."},
    {"key": "pro", "name": "Gemini 2.5 Pro", "model": "gemini-2.5-pro", "description": "Lập luận sâu cho yêu cầu khó."},
    {"key": "flash_lite", "name": "Gemini 2.5 Flash-Lite", "model": "gemini-2.5-flash-lite", "description": "Phản hồi cực nhanh."},
]
MODEL_PRESETS_BY_KEY = {item["key"]: item for item in MODEL_PRESETS}

def load_history():
    if not HISTORY_FILE.exists(): return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data[-MAX_HISTORY_MESSAGES:]
    except: return []

def save_history(history):
    HISTORY_FILE.write_text(json.dumps(history[-MAX_HISTORY_MESSAGES:], ensure_ascii=False, indent=2), encoding="utf-8")

CHAT_HISTORY = load_history()

def html_page():
    default_model = MODEL_PRESETS[0]
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemini Web Chat</title>
  <style>
    :root {{
      --bg: #0d1117; --panel: rgba(14, 21, 31, 0.82); --line: rgba(173, 188, 206, 0.18);
      --text: #edf4ff; --muted: #9db0c8; --accent: #6ee7c8; --user: #15364b; --assistant: #1c293d;
    }}
    body {{ margin: 0; font-family: sans-serif; color: var(--text); background: #091018; display: grid; place-items: center; padding: 10px; }}
    .shell {{ width: 95vw; max-width: 1000px; height: 90vh; border: 1px solid var(--line); border-radius: 20px; background: var(--panel); display: grid; grid-template-rows: auto 1fr auto; overflow: hidden; }}
    .topbar {{ padding: 15px 20px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; }}
    .chat {{ padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; }}
    .message {{ max-width: 85%; padding: 12px 16px; border-radius: 15px; line-height: 1.5; white-space: pre-wrap; }}
    .user {{ align-self: flex-end; background: var(--user); }}
    .assistant {{ align-self: flex-start; background: var(--assistant); }}
    .composer {{ padding: 20px; border-top: 1px solid var(--line); }}
    form {{ display: flex; gap: 10px; }}
    textarea {{ flex: 1; height: 50px; border-radius: 10px; background: rgba(255,255,255,0.05); color: white; padding: 10px; border: 1px solid var(--line); outline: none; }}
    button {{ padding: 0 20px; border-radius: 10px; border: none; background: var(--accent); color: #000; font-weight: bold; cursor: pointer; }}
    .empty {{ text-align: center; color: var(--muted); margin-top: 50px; }}
    .typing {{ font-style: italic; color: var(--accent); font-size: 14px; margin-top: 5px; }}
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div><strong>Gemini Chat</strong></div>
      <select id="modelSelect">
        {"".join([f'<option value="{m["key"]}">{m["name"]}</option>' for m in MODEL_PRESETS])}
      </select>
    </header>
    <section class="chat" id="chat"></section>
    <footer class="composer">
      <form id="chatForm">
        <textarea id="messageInput" placeholder="Nhập câu hỏi..."></textarea>
        <button type="submit" id="sendBtn">Gửi</button>
      </form>
      <div id="status" style="font-size:12px; color:gray; margin-top:5px;"></div>
    </footer>
  </main>

  <script>
    const chat = document.getElementById("chat");
    const form = document.getElementById("chatForm");
    const input = document.getElementById("messageInput");
    const modelSelect = document.getElementById("modelSelect");

    function appendMessage(role, text) {{
      const div = document.createElement("div");
      div.className = `message ${{role}}`;
      div.textContent = text;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
      return div;
    }}

    form.onsubmit = async (e) => {{
      e.preventDefault();
      const msg = input.value.trim();
      if(!msg) return;
      
      input.value = "";
      appendMessage("user", msg);

      // Tạo bóng tin nhắn cho AI để điền chữ dần vào
      const aiMsgDiv = appendMessage("assistant", "...");
      aiMsgDiv.textContent = ""; 

      try {{
        const response = await fetch("/api/chat", {{
          method: "POST",
          body: JSON.stringify({{ message: msg, model_key: modelSelect.value }})
        }});

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = "";

        while (true) {{
          const {{ value, done }} = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, {{ stream: true }});
          fullText += chunk;
          // Cập nhật giao diện ngay lập tức khi nhận được một phần text
          aiMsgDiv.textContent = fullText;
          chat.scrollTop = chat.scrollHeight;
        }}
      }} catch (err) {{
        aiMsgDiv.textContent = "Lỗi kết nối API.";
      }}
    }};

    // Load lịch sử ban đầu
    async function init() {{
      const res = await fetch("/api/history");
      const data = await res.json();
      if(data.history.length === 0) {{
        chat.innerHTML = '<div class="empty">Chào bạn! Hãy nhắn gì đó để bắt đầu.</div>';
      }} else {{
        data.history.forEach(m => appendMessage(m.role, m.content));
      }}
    }}
    init();
  </script>
</body>
</html>
"""

class AIRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(html_page().encode())
        elif self.path == "/api/history":
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"history": CHAT_HISTORY}).encode())

    def do_POST(self):
        if self.path == "/api/chat":
            size = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(size).decode())
            self.handle_streaming_chat(data)

    def handle_streaming_chat(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        user_msg = data.get("message", "")
        model_key = data.get("model_key", "flash")
        model_code = MODEL_PRESETS_BY_KEY.get(model_key, MODEL_PRESETS[0])["model"]

        # Gọi API Gemini (giả lập streaming bằng cách chia nhỏ phản hồi)
        # Để streaming thật 100%, cần dùng thư viện hỗ trợ stream của Google, 
        # nhưng ở đây chúng ta dùng kĩ thuật "Generator" để UI hiện ra từ từ.
        
        try:
            api_key = os.getenv("GEMINI_API_KEY", "").strip()
            # Ở đây tôi lấy full phản hồi rồi chia nhỏ gửi về client để tạo hiệu ứng mượt mà
            # mà không làm hỏng cấu trúc mã hiện tại của bạn.
            
            # (Phần gọi API rút gọn để bạn dễ theo dõi)
            full_reply = self.call_gemini_full(user_msg, model_code, api_key)
            
            # Gửi từng từ về client để hiện ra từ từ
            words = full_reply.split(' ')
            accumulated_reply = ""
            for word in words:
                chunk = (word + " ").encode()
                self.wfile.write(chunk)
                self.wfile.flush()
                accumulated_reply += word + " "
                time.sleep(0.05) # Tốc độ hiện chữ

            with HISTORY_LOCK:
                CHAT_HISTORY.append({"role": "user", "content": user_msg})
                CHAT_HISTORY.append({"role": "assistant", "content": accumulated_reply.strip()})
                save_history(CHAT_HISTORY)

        except Exception as e:
            self.wfile.write(f"Lỗi: {str(e)}".encode())

    def call_gemini_full(self, msg, model, key):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        payload = {"contents": [{"role": "user", "parts": [{"text": msg}]}]}
        req = request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with request.urlopen(req) as res:
            res_data = json.loads(res.read().decode())
            return res_data["candidates"][0]["content"]["parts"][0]["text"]

def run():
    server = ThreadingHTTPServer((HOST, PORT), AIRequestHandler)
    print(f"Server chạy tại port {PORT}..."); server.serve_forever()

if __name__ == "__main__":
    run()
