@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
color 0c
echo ========================================
echo     AI 비서 서버 종료 스크립트
echo ========================================
echo.
echo 1) 메인 비서 (uvicorn) 및 파이썬 프로세스 종료 중...
taskkill /f /im python.exe 2>nul
taskkill /f /im python3.11.exe 2>nul
taskkill /f /im python3.exe 2>nul
taskkill /f /im pythonw.exe 2>nul

echo 2) 목소리 API (GPT-SoVITS) 종료 중...
taskkill /f /im cmd.exe /fi "WINDOWTITLE eq GPT-SoVITS API" 2>nul

echo.
echo 모든 프로세스가 완전히 종료되었습니다!
pause
