@echo off
chcp 65001 >nul
title 4차 산업 포털 (맨유 일정/날씨/AI뉴스)
cd /d "%~dp0"

echo ====================================================
echo  NEXT PULSE - 4차 산업 브리핑 및 맨유 축구 포털
echo ====================================================
echo.

:: 8000번 포트가 켜져 있는지 확인
netstat -ano | findstr :8000 | findstr LISTENING >nul
if %errorlevel% neq 0 (
    echo [1/2] 백엔드 서버(brain_server)를 시작합니다...
    start /b python -m uvicorn brain_server:app --port 8000
    timeout /t 3 /nobreak >nul
) else (
    echo [1/2] 백엔드 서버가 이미 정상 작동 중입니다.
)

echo [2/2] 웹 브라우저에서 포털 페이지를 엽니다...
start http://127.0.0.1:8000/portal

echo.
echo 포털 웹사이트가 브라우저에 열렸습니다!
exit
