"""
jarvis_extension_router.py
=============================================================================
🌟 JARVIS 통합 확장 라우터 (All-in-One Extension Router)
=============================================================================
- 역할:
    1. 새롭게 추가된 모든 모듈(OS 제어, 캘린더/할일, MCP 서버, 네이티브 도구, 관리자 대시보드)을
       단 하나의 APIRouter로 통합 래핑합니다.
    2. 기존 `brain_server.py`에 단 2줄의 코드로 모든 기능을 마운트할 수 있습니다.
=============================================================================
"""

import sys
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse

# 상위 디렉토리 참조 추가
CURRENT_DIR = Path(__file__).parent
sys.path.append(str(CURRENT_DIR.parent))

# 1. 분리된 신규 모듈 라우터 임포트
from modules.system_os_controller import router as system_router
from modules.schedule_manager import router as schedule_router
from modules.mcp_server import router as mcp_router
from modules.screen_vision_agent import router as vision_router
from modules.realtime_audio_streamer import router as audio_stream_router
from modules.daily_journal_writer import router as journal_router
from modules.game_auto_coach import router as game_coach_router
from modules.maple_skill_tracker import router as maple_tracker_router
from modules.lol_minimap_tracker import router as lol_minimap_router
from modules.lol_voice_alert_engine import router as lol_voice_router
from modules.lol_gank_eta_predictor import router as lol_eta_router
from modules.lol_overlay_hud import router as lol_overlay_router
from modules.lol_vision_gap_checker import router as lol_vision_gap_router
from modules.lol_snapshot_reviewer import router as lol_snapshot_router

# 2. 통합 확장 라우터 생성
extension_router = APIRouter()

# 3. 하위 서브 라우터 일괄 포함
extension_router.include_router(system_router)
extension_router.include_router(schedule_router)
extension_router.include_router(mcp_router)
extension_router.include_router(vision_router)
extension_router.include_router(audio_stream_router)
extension_router.include_router(journal_router)
extension_router.include_router(game_coach_router)
extension_router.include_router(maple_tracker_router)
extension_router.include_router(lol_minimap_router)
extension_router.include_router(lol_voice_router)
extension_router.include_router(lol_eta_router)
extension_router.include_router(lol_overlay_router)
extension_router.include_router(lol_vision_gap_router)
extension_router.include_router(lol_snapshot_router)



# 4. 관리자 대시보드 UI (`/admin`) 서빙 엔드포인트
@extension_router.get("/admin", summary="JARVIS 통합 관측 대시보드 UI", tags=["Admin Dashboard"])
async def serve_admin_dashboard():
    """admin.html 파일을 브라우저에 렌더링합니다."""
    admin_html_path = CURRENT_DIR / "admin.html"
    return FileResponse(str(admin_html_path), media_type="text/html")


# =============================================================================
# 🚀 단독 테스트 실행기 (Standalone Runner)
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    test_app = FastAPI(title="JARVIS Extension Server (Standalone Test)")
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(extension_router)

    print("=================================================================")
    print("🚀 JARVIS 통합 확장 모듈 테스트 서버가 시작되었습니다.")
    print("👉 대시보드 접속 URL: http://localhost:8000/admin")
    print("👉 API 문서(Swagger): http://localhost:8000/docs")
    print("=================================================================")
    uvicorn.run(test_app, host="0.0.0.0", port=8000)
