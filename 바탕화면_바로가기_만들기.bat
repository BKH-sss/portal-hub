@echo off
chcp 65001 >nul
cd /d "%~dp0"
python create_shortcut.py
echo.
echo ========================================================
echo  바탕화면에 'J.A.R.V.I.S Assistant' 전용 앱 아이콘이 생성되었습니다!
echo  이제 바탕화면에서 아이콘을 더블클릭하여 바로 실행하세요.
echo ========================================================
echo.
pause
