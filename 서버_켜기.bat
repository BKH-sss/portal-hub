@echo off
chcp 65001 >nul
title AI 비서 런처
cd /d "%~dp0"
echo J.A.R.V.I.S 런처 앱을 시작합니다...
start /b pythonw launcher.py
exit
