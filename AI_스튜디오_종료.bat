@echo off
cd /d "%~dp0"
python stop_servers.py
if %errorlevel% neq 0 (
    echo [Error] Failed to stop servers.
    pause
)