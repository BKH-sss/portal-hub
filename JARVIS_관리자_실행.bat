@echo off
chcp 65001 >nul
title JARVIS Assistant (Administrator Mode)

:: 1. 관리자 권한 확인 및 자동 승격 (UAC 창 팝업)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [안내] 메이플스토리 인게임 키 입력을 완벽하게 감지하기 위해 관리자 권한으로 실행합니다...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: 2. 프로젝트 폴더로 이동
cd /d "%~dp0"

echo ==============================================================================
echo 🍁 JARVIS Assistant & 메이플스토리 스킬 트래커 (관리자 모드 실행 완료)
echo ==============================================================================
echo  - 메이플스토리 게임 창이 켜져 있거나 포커스되어 있어도 키 입력을 100% 감지합니다.
echo  - 백그라운드 서버 및 AI 스카디 음성 엔진을 시작합니다...
echo ==============================================================================
echo.

python launcher.py
