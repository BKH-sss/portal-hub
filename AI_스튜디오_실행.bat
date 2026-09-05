@echo off
set "PATH=%LOCALAPPDATA%\Microsoft\WindowsApps;C:\Program Files\Git\cmd;%PATH%"
if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe" (
    set "PY=%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"
) else (
    set "PY=python"
)
cd /d "%~dp0"
"%PY%" launch_studio.py
if %errorlevel% neq 0 (
    echo [Error] Failed to launch Skadi Studio.
    pause
)