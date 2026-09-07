@echo off
chcp 65001 > nul
title JARVIS / SKADI - 롤 증강체 인게임 네이티브 오버레이 HUD
color 0b

echo ===============================================================================
echo   🏆 JARVIS / SKADI: 롤 칼바람·아레나 증강체 네이티브 투명 오버레이 HUD
echo ===============================================================================
echo.
echo   [안내] 
echo    • 마우스 클릭이 게임 안으로 100%% 통과(Click-Through)되어 플레이에 전혀 방해되지 않습니다.
echo    • 롤 클라이언트(League of Legends) 실행 시 3개 증강체 상단에 1:1로 자동 정렬됩니다.
echo    • 6단계 티어([OP], [S], [A], [B], [C], [D]) 및 슬롯별 단독 리롤 지침을 실시간 표시합니다.
echo.
echo   [단축키]
echo    • F9 : 오버레이 즉시 보이기 / 숨기기 토글
echo    • Ctrl + C : 오버레이 종료
echo.
echo ===============================================================================
echo [실행 중] 네이티브 투명 오버레이 HUD 창을 로드합니다...
echo.

python "%~dp0modules\lol_augment_native_window.py"

if %errorlevel% neq 0 (
    echo.
    echo [오류] 실행 도중 문제가 발생했습니다. (Python 실행 환경 확인 필요)
    pause
)
