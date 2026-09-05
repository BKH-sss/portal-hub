@echo off
chcp 65001 >nul
title 스카디 AI 화가 스튜디오 (RTX 4080 SUPER)
cd /d "%~dp0"

echo.
echo ================================================================
echo   [스카디 AI 화가 스튜디오] WebUI Forge + RTX 4080 SUPER
echo   화가 UI: http://127.0.0.1:8000/skadi_studio.html
echo ================================================================
echo.

:: 1. 8000번 포트 (brain_server) 확인 및 구동
netstat -ano | findstr :8000 | findstr LISTENING >nul
if %errorlevel% neq 0 (
    echo [1/3] JARVIS 백엔드 서버(brain_server:8000)를 시작합니다...
    start /b python -m uvicorn brain_server:app --port 8000
    timeout /t 2 /nobreak >nul
) else (
    echo [1/3] JARVIS 백엔드 서버가 이미 작동 중입니다 (포트 8000).
)

:: 2. 스카디 AI 화가 스튜디오 브라우저 열기 (skadi_studio.html)
echo [2/3] 스카디 AI 화가 스튜디오 웹페이지를 엽니다...
start "" "http://127.0.0.1:8000/skadi_studio.html"

:: 3. WebUI Forge (7860 포트) 확인 및 가동
netstat -ano | findstr :7860 | findstr LISTENING >nul
if %errorlevel% neq 0 (
    if exist "A:\AI_Studio\stable-diffusion-webui-forge\webui-user.bat" (
        echo [3/3] WebUI Forge (RTX 4080 SUPER 렌더링 코어)를 실행합니다...
        start "WebUI Forge Engine" cmd /k "cd /d A:\AI_Studio\stable-diffusion-webui-forge && call webui-user.bat"
    ) else (
        echo [3/3] WebUI Forge 경로(A:\AI_Studio)를 찾을 수 없습니다.
    )
) else (
    echo [3/3] WebUI Forge가 이미 작동 중입니다 (포트 7860).
)

echo.
echo 🎨 스카디 AI 화가 스튜디오가 브라우저에 열렸습니다!
timeout /t 2 /nobreak >nul
exit
