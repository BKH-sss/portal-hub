@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
python stop_servers.py
if %errorlevel% neq 0 (
    python "C:\Users\skbkh\Desktop\html\chat bot\stop_servers.py"
)
