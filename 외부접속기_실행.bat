@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
color 0a
echo ========================================================
echo     외부 접속 터널 실행 스크립트
echo ========================================================
echo.
cd /d "%~dp0"
python tunnel.py
pause
