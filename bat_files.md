# 서버_끄기.bat
`at
@echo off
color 0c
echo ========================================
echo     AI ê   
echo ========================================
echo.
echo 1)  ̽ (uvicorn)  ...
taskkill /f /im python.exe /fi "WINDOWTITLE eq *uvicorn*" 2>nul
taskkill /f /im python.exe 2>nul

echo 2) Ҹ API (GPT-SoVITS)  ...
taskkill /f /im cmd.exe /fi "WINDOWTITLE eq GPT-SoVITS API" 2>nul

echo.
echo   μ Ǿϴ!
pause

`

# 서버_켜기.bat
`at
@echo off
color 0b
echo ========================================
echo     AI ê   ڵ 
echo    [  2 : Gemini 2.5 Flash  ]
echo ========================================
echo.
echo [ý üũ]
echo - ä  :  Gemini 2.5 Flash (ʰ/)
echo - /м  :  Ollama (Llama 3.1)
echo.
echo    Դϴ... ø ٷּ!

cd /d "C:\Users\skbkh\Desktop\html\chat bot"

:: ī Ҹ  (GPT-SoVITS) ׶ 
echo - Ҹ  : GPT-SoVITS API (ī)  ...
start "GPT-SoVITS API" /MIN cmd /c "cd /d tts_engine_sovits\GPT-SoVITS-main && chcp 65001 && set PYTHONIOENCODING=utf-8 && call .\venv_sovits\Scripts\activate.bat && python api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml"

::  ê ȭ 
start "" "http://localhost:8000/chatbot.html"

:: ̽  
python -m uvicorn brain_server:app --port 8000

pause

`

# 외부접속기_실행.bat
`at
﻿@echo off
color 0b
cd /d "%~dp0"
python tunnel.py
pause

`

