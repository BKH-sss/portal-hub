"""
routers/lol.py
==============================================================================
⚔️ 리그 오브 레전드(LoL) 실시간 LCU 연동 & 브라이어/스카디 브리핑 라우터
==============================================================================
이 모듈은 로컬에 켜진 롤 클라이언트(LCU: League Client Update)의 메모리 및 API를
실시간 감지하여 소환사 정보, 최근 전적, 인게임 킬/데스/용/바론 이벤트를 추출하고,
브라이어 AI의 실시간 음성 피드백 및 전략 브리핑을 생성하는 라우터입니다.

주요 엔드포인트:
  1) GET  /api/riot/status    : 롤 클라이언트 연결 및 소환사 이름/레벨 상태
  2) GET  /api/briar/feedback : 최근 5게임 전적 조회 및 브라이어의 팩폭 피드백
  3) POST /api/lol/event      : 인게임 이벤트(용 처치, 한타 대패 등) 실시간 브리핑
  4) POST /game-event         : 외부 연동 게임 이벤트 수신 및 WebSocket 브로드캐스트
==============================================================================
"""

import asyncio
from typing import Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from core.state import riot_lcu, manager
from briar_feedback_engine import generate_briar_feedback

router = APIRouter(tags=["League of Legends (LoL)"])

# ==============================================================================
# 1. Pydantic 요청 스키마 정의
# ==============================================================================
class GameEventRequest(BaseModel):
    """인게임 실시간 이벤트 요청 모델"""
    event_type: str                         # 이벤트 종류 (예: DRAGON_KILL, BARON_KILL, ACE, LEVEL_UP 등)
    data: Optional[Dict[str, Any]] = None   # 세부 데이터 (처치자, 현재 골드, 킬스코어 등)

# ==============================================================================
# 2. 롤 LCU 클라이언트 상태 및 브라이어 전적 피드백 API
# ==============================================================================
@router.get("/api/riot/status", summary="롤 클라이언트(LCU) 연결 상태")
async def get_riot_status():
    """
    로컬 PC에서 롤 클라이언트(LeagueClientUx.exe)가 실행 중인지 락파일(lockfile)을 
    자동 감지하여 현재 소환사 이름, 티어, 클라이언트 상태를 비동기로 반환합니다.
    """
    return await asyncio.to_thread(riot_lcu.get_current_status)

@router.get("/api/briar/feedback", summary="브라이어 최근 5게임 전적 피드백")
def get_briar_feedback():
    """
    롤 LCU API를 통해 최근 5게임의 매치 히스토리(KDA, 딜량, CS, 승패)를 읽어온 뒤,
    브라이어 캐릭터 AI가 특유의 흡혈귀 성격으로 유저를 놀리거나 칭찬하는 팩폭 분석평을 작성합니다.
    """
    history = riot_lcu.get_match_history(count=5)
    if history.get('status') == 'error':
        return {"feedback": f"전적 조회 실패! {history.get('message')}", "text_only": "에러 났어!"}
    
    summoner_name = history.get('summoner_name', '알수없음')
    matches = history.get('matches', [])
    
    # 팩폭 피드백 텍스트 생성
    feedback = generate_briar_feedback(matches, summoner_name)
    text_only = feedback.split("<br>")[-1] if "<br>" in feedback else feedback
    text_only = text_only.replace("*", "").strip()
    
    return {"feedback": feedback, "text_only": text_only}

# ==============================================================================
# 3. 인게임 실시간 이벤트 & 전략 브리핑 API
# ==============================================================================
@router.post("/api/lol/event", summary="롤 인게임 실시간 전략 브리핑")
async def handle_lol_event(req: GameEventRequest):
    """
    게임 도중 발생하는 중요 순간(용 버프 획득, 바론 스틸, 사망 등)을 전달받아
    WebSocket으로 연결된 모든 화면 UI에 브로드캐스트하고 스카디/브라이어의 즉각적인 음성 브리핑을 트리거합니다.
    """
    event_type = req.event_type.upper()
    data = req.data or {}

    # 상황별 전략 브리핑 메시지 템플릿
    messages = {
        "DRAGON_KILL": f"용을 처치했어! 다음 용 타이머 확인하고 바텀 시야 잡아둬.",
        "BARON_KILL": f"바론 획득 성공! 미드/바텀 라인 밀어넣고 억제기 공략 준비해.",
        "ACE": f"적 팀 전멸(에이스)! 지금 당장 타워나 오브젝트 밀어야 해!",
        "DEATH": f"차분하게... 데스 타이머 동안 다음 코어 아이템 골드 계산해둬.",
        "ITEM_PURCHASE": f"코어 아이템 완성! 다음 한타에서 궁극기 타이밍 노려봐."
    }

    briefing = messages.get(event_type, f"게임 내 중요 이벤트 감지: {event_type}")

    # 실시간 WebSocket 클라이언트 전송
    await manager.broadcast({
        "type": "lol_event",
        "event": event_type,
        "briefing": briefing,
        "data": data
    })

    return {"status": "success", "event": event_type, "briefing": briefing}

@router.post("/game-event", summary="게임 이벤트 웹훅 수신")
async def receive_game_event(req: GameEventRequest, background_tasks: BackgroundTasks):
    """
    외부 오버레이 앱이나 게임 감시 데몬으로부터 비동기 이벤트를 전달받는 공용 엔드포인트입니다.
    """
    await manager.broadcast({
        "type": "external_game_event",
        "payload": req.dict()
    })
    return {"status": "acknowledged"}
