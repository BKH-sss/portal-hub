@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
color 0c
title AI 시스템 및 스튜디오 전체 종료

echo ========================================================
echo   🛑 AI 시스템 및 스튜디오 전체 종료 스크립트
echo ========================================================
echo.

echo 1) JARVIS 백엔드 서버(8000 포트) 및 Python 프로세스 종료 중...
taskkill /f /im python.exe 2>nul
taskkill /f /im python3.11.exe 2>nul
taskkill /f /im python3.exe 2>nul
taskkill /f /im pythonw.exe 2>nul

echo 2) WebUI Forge (7860 포트) 및 렌더링 엔진 콘솔 종료 중...
taskkill /f /fi "WINDOWTITLE eq WebUI Forge*" 2>nul
taskkill /f /fi "WINDOWTITLE eq AI Image Studio*" 2>nul

echo 3) 목소리 API (GPT-SoVITS:9880) 종료 중...
taskkill /f /im cmd.exe /fi "WINDOWTITLE eq GPT-SoVITS API" 2>nul

echo 4) 외부 접속기(Cloudflare Tunnel) 종료 중...
taskkill /f /im cloudflared.exe 2>nul

echo.
echo ========================================================
echo   ✅ 모든 AI 서버 및 스튜디오 프로세스가 완전히 종료되었습니다!
echo ========================================================
echo.
timeout /t 3
