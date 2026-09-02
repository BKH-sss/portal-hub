"""
modules/__init__.py
==============================================================================
🚀 JARVIS / SKADI 확장 모듈 패키지 (Modular Extensions Suite)
==============================================================================
이 패키지는 윈도우 OS 제어, 캘린더 일정 관리, 메이플 스킬 쿨타임 트래커,
실시간 게임 코칭, 저지연 오디오 스트리머, Anthropic MCP 서버를 제공합니다.
==============================================================================
"""

from modules.system_os_controller import router as system_router
from modules.schedule_manager import router as schedule_router
from modules.mcp_server import router as mcp_router
from modules.screen_vision_agent import router as extension_vision_router
from modules.realtime_audio_streamer import router as audio_stream_router
from modules.daily_journal_writer import router as journal_router
from modules.game_auto_coach import router as game_coach_router
from modules.maple_skill_tracker import router as maple_tracker_router
from modules.jarvis_extension_router import extension_router

all_extension_routers = [
    system_router,
    schedule_router,
    mcp_router,
    extension_vision_router,
    audio_stream_router,
    journal_router,
    game_coach_router,
    maple_tracker_router
]

__all__ = [
    "system_router",
    "schedule_router",
    "mcp_router",
    "extension_vision_router",
    "audio_stream_router",
    "journal_router",
    "game_coach_router",
    "maple_tracker_router",
    "extension_router",
    "all_extension_routers"
]
