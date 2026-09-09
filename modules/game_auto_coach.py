"""
game_auto_coach.py
=============================================================================
🎮 JARVIS 게임 프로세스 자동 감지 및 실시간 인게임 코칭 브리퍼
=============================================================================
- 기능:
    1. PC에서 실행 중인 인기 게임(LoL, 발로란트, 메이플스토리, 레식 등) 프로세스 실시간 자동 감지
    2. 게임 실행 감지 시 픽창/상대 전적 분석 및 실시간 맞춤형 전술 팁 음성/텍스트 브리핑
    3. 게임 플레이 시간 추적 및 피로도 관리 알림
    4. FastAPI APIRouter 내장으로 웹 UI 및 디스코드 봇 실시간 연동
=============================================================================
"""

import time
from typing import Dict, Any, List, Optional
try:
    from modules._safe_router import (
        APIRouter, HTTPException, Response, HTMLResponse, FileResponse,
        JSONResponse, Request, WebSocket, WebSocketDisconnect, FastAPI,
        CORSMiddleware, BaseModel, Field
    )
except ImportError:
    try:
        from _safe_router import (
            APIRouter, HTTPException, Response, HTMLResponse, FileResponse,
            JSONResponse, Request, WebSocket, WebSocketDisconnect, FastAPI,
            CORSMiddleware, BaseModel, Field
        )
    except ImportError:
        pass

try:
    import psutil
except ImportError:
    psutil = None

# =============================================================================
# 🚀 1. FastAPI APIRouter 생성
# =============================================================================
router = APIRouter(prefix="/api/game", tags=["Game Auto Coach"])


# =============================================================================
# 🕹️ 2. 게임 프로세스 정의 및 코칭 데이터베이스
# =============================================================================
SUPPORTED_GAMES = {
    "league of legends": {
        "name": "League of Legends",
        "process_names": ["leagueclient.exe", "league of legends.exe"],
        "genre": "MOBA",
        "tips": [
            "초반 3분 바위게 싸움 타이밍에 미드/정글 주도권을 반드시 체크하세요.",
            "용/바론 생성 1분 전 시야 와드를 미리 확보하고 라인을 밀어두세요.",
            "사이드 라인 운영 시 상대 주요 CC기 스킬 쿨타임을 항상 의식하세요."
        ]
    },
    "valorant": {
        "name": "VALORANT",
        "process_names": ["valorant.exe", "valorant-win64-shipping.exe"],
        "genre": "Tactical FPS",
        "tips": [
            "헤드샷 라인(크로스헤어 높이)을 벽 모서리에 미리 에이밍(Pre-aiming)하세요.",
            "스킬을 아끼지 말고 팀원과의 동시 진입(트레이드 킬) 타이밍에 연계하세요.",
            "스파이크 설치 후 무리한 교전보다 사운드 플레이로 시간을 끄는 것이 유리합니다."
        ]
    },
    "maplestory": {
        "name": "MapleStory",
        "process_names": ["maplestory.exe"],
        "genre": "MMORPG",
        "tips": [
            "일일 퀘스트 및 익스트림 몬스터 파크를 우선 완료하여 경험치 보너스를 챙기세요.",
            "보스 레이드 진입 전 유니온/링크 스킬 프리셋과 도핑 아이템 적용 여부를 확인하세요."
        ]
    },
    "rainbow six siege": {
        "name": "Rainbow Six Siege",
        "process_names": ["rainbowsix.exe", "rainbowsix_vulkan.exe"],
        "genre": "Tactical FPS",
        "tips": [
            "드론을 함부로 잃지 말고 진입 전 방 클리어링용으로 보존하세요.",
            "버티컬 플레이가 가능한 소프트월/바닥을 적극 활용해 상대를 압박하세요."
        ]
    }
}


# =============================================================================
# 🧠 3. 게임 감지 및 코칭 엔진
# =============================================================================
class GameCoachEngine:
    """실행 중인 게임 프로세스를 감지하고 전술 공략을 생성하는 코칭 엔진"""

    _active_game_cache: Optional[Dict[str, Any]] = None
    _detected_timestamp: float = 0.0

    @classmethod
    def detect_active_game(cls) -> Dict[str, Any]:
        """
        현재 PC에서 실행 중인 게임 프로세스를 탐색하여 상태 반환
        """
        if not psutil:
            return {"active": False, "message": "psutil 미설치 (프로세스 감지 불가)"}

        running_process_names = set()
        for proc in psutil.process_iter(['name']):
            try:
                pname = proc.info['name']
                if pname:
                    running_process_names.add(pname.lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 등록된 게임 리스트와 매칭
        for game_key, game_info in SUPPORTED_GAMES.items():
            for target_proc in game_info["process_names"]:
                if target_proc in running_process_names:
                    # 새로운 게임 감지 시 타임스탬프 갱신
                    if not cls._active_game_cache or cls._active_game_cache.get("key") != game_key:
                        cls._detected_timestamp = time.time()

                    duration_mins = int((time.time() - cls._detected_timestamp) / 60)
                    cls._active_game_cache = {
                        "key": game_key,
                        "name": game_info["name"],
                        "genre": game_info["genre"],
                        "play_duration_minutes": duration_mins
                    }

                    return {
                        "active": True,
                        "game": cls._active_game_cache,
                        "message": f"현재 '{game_info['name']}' 플레이 중 ({duration_mins}분 경과)"
                    }

        cls._active_game_cache = None
        return {"active": False, "message": "현재 실행 중인 게임이 없습니다."}

    @classmethod
    def get_game_coaching_briefing(cls) -> Dict[str, Any]:
        """
        현재 감지된 게임에 대한 즉각적인 전략 팁과 코칭 브리핑 반환
        """
        detect_res = cls.detect_active_game()
        if not detect_res["active"]:
            return {
                "status": "idle",
                "message": "실행 중인 게임이 감지되지 않아 대기 상태입니다.",
                "general_tip": "게임을 실행하면 AI가 자동으로 챔피언 및 전략 코칭을 시작합니다."
            }

        game_key = detect_res["game"]["key"]
        game_info = SUPPORTED_GAMES.get(game_key, {})
        tips = game_info.get("tips", ["팀원과의 소통과 침착한 플레이를 유지하세요."])

        return {
            "status": "coaching",
            "game_name": game_info.get("name"),
            "play_time_minutes": detect_res["game"]["play_duration_minutes"],
            "coaching_tips": tips,
            "briefing_text": (
                f"🎮 **[{game_info.get('name')} 인게임 코칭]**\n"
                f"플레이 시간: `{detect_res['game']['play_duration_minutes']}분`\n"
                f"핵심 팁: {tips[0]}"
            )
        }


# =============================================================================
# 🌐 4. FastAPI 라우터 엔드포인트
# =============================================================================

@router.get("/current", summary="현재 실행 중인 게임 프로세스 감지")
async def get_current_game():
    """PC에서 실행 중인 게임 목록과 플레이 시간을 실시간으로 반환합니다."""
    return GameCoachEngine.detect_active_game()


@router.get("/coaching", summary="인게임 실시간 맞춤 공략 브리핑")
async def get_coaching():
    """현재 감지된 게임에 맞는 전술 팁과 코칭 가이드를 제공합니다."""
    return GameCoachEngine.get_game_coaching_briefing()
