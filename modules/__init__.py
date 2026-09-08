"""
modules/__init__.py
==============================================================================
🚀 JARVIS / SKADI 확장 모듈 패키지 (Modular Extensions Suite)
==============================================================================
이 패키지는 윈도우 OS 제어, 캘린더 일정 관리, 메이플 스킬 쿨타임 트래커,
실시간 게임 코칭, 저지연 오디오 스트리머, Anthropic MCP 서버를 제공합니다.
환경별(Linux/Render/Windows) 종속성 누락 시에도 개별 모듈이 독립 동작하도록 안전 로드 지원.
==============================================================================
"""

import logging

logger = logging.getLogger("ModulesSuite")

all_extension_routers = []

def _safe_import(module_name: str, router_attr: str = "router"):
    try:
        mod = __import__(f"modules.{module_name}", fromlist=[router_attr])
        r = getattr(mod, router_attr, None)
        if r:
            all_extension_routers.append(r)
        return r
    except Exception as e:
        logger.debug(f"모듈 {module_name} 로드 건너뜀 (환경 차이 등): {e}")
        return None

system_router = _safe_import("system_os_controller")
schedule_router = _safe_import("schedule_manager")
mcp_router = _safe_import("mcp_server")
extension_vision_router = _safe_import("screen_vision_agent")
audio_stream_router = _safe_import("realtime_audio_streamer")
journal_router = _safe_import("daily_journal_writer")
game_coach_router = _safe_import("game_auto_coach")
maple_tracker_router = _safe_import("maple_skill_tracker")
maple_cancel_router = _safe_import("maple_cancel_trainer")
lol_coach_router = _safe_import("lol_ai_coach")
lol_minimap_router = _safe_import("lol_minimap_tracker")
lol_voice_router = _safe_import("lol_voice_alert_engine")
lol_eta_router = _safe_import("lol_gank_eta_predictor")
lol_overlay_router = _safe_import("lol_overlay_hud")
lol_vision_gap_router = _safe_import("lol_vision_gap_checker")
lol_snapshot_router = _safe_import("lol_snapshot_reviewer")
extension_router = _safe_import("jarvis_extension_router", "extension_router")

# 직접 사용 가능한 핵심 비즈니스 로직 안전 로드
try:
    from modules.schedule_manager import ScheduleManager, ScheduleCreateRequest
except Exception:
    ScheduleManager = None
    ScheduleCreateRequest = None

try:
    from modules.google_calendar_engine import google_calendar_engine, GoogleCalendarEngine
except Exception:
    google_calendar_engine = None
    GoogleCalendarEngine = None

__all__ = [
    "system_router",
    "schedule_router",
    "mcp_router",
    "extension_vision_router",
    "audio_stream_router",
    "journal_router",
    "game_coach_router",
    "maple_tracker_router",
    "lol_coach_router",
    "lol_minimap_router",
    "lol_voice_router",
    "lol_eta_router",
    "lol_overlay_router",
    "lol_vision_gap_router",
    "lol_snapshot_router",
    "extension_router",
    "all_extension_routers",
    "ScheduleManager",
    "ScheduleCreateRequest",
    "google_calendar_engine",
    "GoogleCalendarEngine"
]
