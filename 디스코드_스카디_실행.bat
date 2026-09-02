@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Skadi Discord Bot

set "PYTHON_EXE="

:: 1. Check if 'python' works
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=python"
    goto :FOUND
)

:: 2. Check if 'py' works
where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=py"
    goto :FOUND
)

:: 3. Check WindowsApps paths
if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"
    goto :FOUND
)

for /d %%D in ("%LOCALAPPDATA%\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.*") do (
    if exist "%%D\python.exe" (
        set "PYTHON_EXE=%%D\python.exe"
        goto :FOUND
    )
)

:FOUND
if "%PYTHON_EXE%"=="" (
    echo [ERROR] Python not found. Please install Python or add it to PATH.
    pause
    exit /b 1
)

cd /d "%~dp0\discord_bot" 2>nul || cd /d "%~dp0"

echo ========================================================
echo   Skadi Discord Bot Launcher
echo   Python: %PYTHON_EXE%
echo ========================================================
echo.

"%PYTHON_EXE%" discord_skadi_bot.py
if %errorlevel% neq 0 (
    echo.
    echo [Exit Code: %errorlevel%]
)
pause
