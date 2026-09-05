@echo off
cd /d "%~dp0"
python launch_portal.py
if %errorlevel% neq 0 (
    echo [Error] Failed to launch Portal.
    pause
)