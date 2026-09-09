@echo off
chcp 65001 > nul
title LoL Desktop Intelligence Overlay (YOUR.GG Style)
echo ================================================================
echo 🏆 League of Legends Local Desktop Intelligence Overlay
echo ================================================================
echo 1. Riot Live Client Data API (127.0.0.1:2999) Monitoring...
echo 2. Transparent Always-on-Top Click-Through HUD Starting...
echo 3. Riot Policy Safe: 0 Enemy Skill/Spell Cooldowns.
echo ================================================================

cd /d "%~dp0"
python desktop_overlay/main.py
if errorlevel 1 (
    echo [ERROR] Execution failed. Retrying with root path...
    python main.py
)
pause
