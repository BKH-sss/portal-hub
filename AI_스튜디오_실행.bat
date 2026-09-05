@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title 스카디 AI 화가 스튜디오 (RTX 4080 SUPER)
cd /d "%~dp0"
python launch_studio.py
if %errorlevel% neq 0 (
    echo.
    echo [오류 발생] 런처 실행 중 문제가 발생했습니다.
    pause
)
