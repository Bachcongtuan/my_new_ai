@echo off
cd /d D:\dev\My_AI\AI_2
title Gemini AI Server

if exist on-ai.local.bat call on-ai.local.bat

if "%GEMINI_API_KEY%"=="" (
  echo GEMINI_API_KEY chua duoc cai dat.
  echo Hay tao on-ai.local.bat tu on-ai.example.bat hoac set bien moi truong truoc khi chay.
  pause
  exit /b 1
)

echo Dang khoi dong Python Backend...
start /b python ai_web_final.py

echo Doi server trong 3 giay...
timeout /t 3 /nobreak > nul

echo Dang mo giao dien web...
start http://127.0.0.1:5000
