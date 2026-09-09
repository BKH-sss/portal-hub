@echo off
chcp 65001 > nul
title JARVIS LoL Real-Time Augment Overlay
cd /d "%~dp0"
echo ==============================================================================
echo 🎴 JARVIS / SKADI: 롤(LoL) 실시간 인게임 증강체 최상위 투명 오버레이 HUD
echo ==============================================================================
echo * 100%% 클릭 투과(WS_EX_TRANSPARENT)로 게임 조작에 방해되지 않습니다.
echo * 화면에 3개 증강체 선택 카드가 나타나면 자동으로 티어 뱃지가 표시됩니다.
echo * 웹 오버레이: http://127.0.0.1:8000/overlay/augments
echo ==============================================================================
echo.
python "%~dp0modules\lol_live_augment_overlay.py"
pause
