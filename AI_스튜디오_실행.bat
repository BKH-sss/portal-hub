@echo off
cd /d "%~dp0"
python launch_studio.py
if %errorlevel% neq 0 (
    echo [Error] Failed to launch Skadi Studio.
    pause
)