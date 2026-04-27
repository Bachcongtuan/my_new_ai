# AI Web Chat

This project restores a simple AI chat web app that matches the existing
`on-ai.bat` launcher.

## Run

1. Set your Gemini API key.
2. Start the app with `on-ai.bat` or `python ai_web_final.py`.
3. Open `http://0.0.0.0:5000`.

## Environment variables

```powershell
$env:GEMINI_API_KEY="your_key_here"
python ai_web_final.py
```

## GitHub-safe launcher

- `on-ai.bat`: public launcher, safe to commit
- `on-ai.example.bat`: template for local key setup
- `on-ai.local.bat`: your local secret file, ignored by Git

Example `on-ai.local.bat`:

```bat
@echo off
set GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
```

## Optional variables

- `AI_MODEL`: override the default model.
- `MAX_HISTORY_MESSAGES`: number of messages persisted in `chat_history.json`.

## Files

- `ai_web_final.py`: web server, chat UI, API integration.
- `chat_history.json`: created automatically after the first message.
# AI Web Chat(bản việt)

Dự án này khôi phục một ứng dụng web trò chuyện AI đơn giản phù hợp với trình khởi chạy hiện có
`on-ai.bat`.

## Chạy

1. Thiết lập khóa API Gemini của bạn.

2. Khởi chạy ứng dụng bằng `on-ai.bat` hoặc `python ai_web_final.py`.

3. Mở `http://0.0.0.0:5000`.

## Biến môi trường

```powershell
$env:GEMINI_API_KEY="your_key_here"
python ai_web_final.py
```

## Trình khởi chạy an toàn cho GitHub

- `on-ai.bat`: trình khởi chạy công khai, an toàn để commit
- `on-ai.example.bat`: mẫu thiết lập khóa cục bộ
- `on-ai.local.bat`: tệp bí mật cục bộ của bạn, bị Git bỏ qua

Ví dụ `on-ai.local.bat`:

```bat

@echo off
set GEMINI_API_KEY=YOUR_GEMINI_API_KEY_HERE
```

## Biến tùy chọn

- `AI_MODEL`: ghi đè mô hình mặc định.

- `MAX_HISTORY_MESSAGES`: số lượng tin nhắn được lưu trữ trong `chat_history.json`.

## Các tập tin

- `ai_web_final.py`: máy chủ web, giao diện người dùng trò chuyện, tích hợp API.

- `chat_history.json`: được tạo tự động sau tin nhắn đầu tiên.