"""
routers/lol.py
------------------------------------------------------------
⚔️ 리그 오브 레전드(LoL) 실시간 LCU 연동 & 브라이어/스카디 브리핑 라우터.
- 롤 클라이언트(LCU) 연결 상태 확인 (/api/riot/status)
- 브라이어 전적 분석 및 실시간 팩폭 피드백 (/api/briar/feedback)
- 인게임 실시간 이벤트(킬/데스/오브젝트/아이템 골드) 브리핑 (/api/lol/event)
- 게임 이벤트 수신 및 TTS 자동 트리거 (/game-event)
------------------------------------------------------------
"""

import asyncio
from typing import Optional, Dict, Any
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from core.state import riot_lcu, manager
from briar_feedback_engine import generate_briar_feedback

router = APIRouter(tags=["League of Legends (LoL)"])

# ============================================================
# 1. Pydantic 요청 스키마 정의
# ============================================================
class GameEventRequest(BaseModel):
    """인게임 실시간 이벤트 요청 모델"""
    event_type: str
    data: Optional[Dict[str, Any]] = None

# ============================================================
# 2. 롤 LCU 클라이언트 상태 및 브라이어 전적 피드백 API
# ============================================================
@router.get("/api/riot/status", summary="롤 클라이언트(LCU) 연결 상태")
async def get_riot_status():
    """로컬 League of Legends 클라이언트와의 LCU 통신 상태를 비동기로 조회합니다."""
    return await asyncio.to_thread(riot_lcu.get_current_status)

@router.get("/api/briar/feedback", summary="브라이어 최근 5게임 전적 피드백")
def get_briar_feedback():
    """
    롤 LCU로부터 최근 5게임 전적을 조회하고, 
    브라이어 AI가 유저의 KDA/CS/승률을 직설적으로 피드백합니다.
    """
    history = riot_lcu.get_match_history(count=5)
    if history.get('status') == 'error':
        return {"feedback": f"전적 조회 실패! {history.get('message')}", "text_only": "에러 났어!"}
    
    summoner_name = history.get('summoner_name', '알수없음')
    matches = history.get('matches', [])
    
    feedback = generate_briar_feedback(matches, summoner_name)
    text_only = feedback.split("<br>")[-1] if "<br>" in feedback else feedback
    text_only = text_only.replace("*", "").strip()
    
    return {"feedback": feedback, "text_only": text_only}

# ============================================================
# 3. 인게임 실시간 이벤트 & 전략 브리핑 API
# ============================================================
@router.post("/api/lol/event", summary="롤 인게임 실시간 전략 브리핑")
async def handle_lol_event(event_data: dict, background_tasks: BackgroundTasks):
    """
    LCU API 또는 비전(YOLO) 모니터로부터 롤 이벤트(챔프픽, 골드도달, 오브젝트젠 등)를 수신하여
    스카디의 상황별 전략 브리핑 멘트를 생성하고 웹소켓으로 클라이언트에 전달합니다.
    """
    event_type = event_data.get("type")
    mode = event_data.get("mode", "CLASSIC")
    briefing_text = ""

    if event_type == "CHAMP_LOCK":
        my_champ = event_data.get("my_champ")
        enemy_champ = event_data.get("enemy_champ", "알수없음")
        if mode == "ARAM":
            briefing_text = f"칼바람 {my_champ} 떴네. 첫 증강은 무조건 보석 장갑이나 전쟁광 집고, 첫 템은 절망 정수 사와. 스펠은 무조건 눈덩이 들어!"
        else:
            briefing_text = f"상대 미드 {enemy_champ}네. 초반 견제 심하니까 콩콩이 대신 난입 들고 뼈방패 무조건 챙겨."
            
    elif event_type == "GAME_START":
        enemy_tier = event_data.get("enemy_tier", "플레티넘 4")
        briefing_text = f"상대 라이너 {enemy_tier}야. 방심하지 말고 초반 3레벨 갱 조심해."

    elif event_type == "GOLD_REACHED":
        target_item = event_data.get("target_item")
        briefing_text = f"돈 다 모였어. 억지 딜교 하지 말고 라인만 밀고 집 가서 {target_item} 뽑아와."

    elif event_type == "ENEMY_KILL":
        respawn_time = event_data.get("respawn_time", 15)
        briefing_text = f"나이스. 적 부활 {respawn_time}초, 라인 복귀까지 30초 남았어. 타워 채굴하고 바로 빠져."

    elif event_type == "OBJECTIVE_10SEC":
        obj_name = event_data.get("objective", "용")
        briefing_text = f"{obj_name} 젠 10초 전이야! 정글러 위치 확인하고 시야부터 지워!"

    elif event_type == "PLAYER_DEATH":
        briefing_text = "아니 거기서 각도 안 좁히고 왜 들어가! 다음 턴에는 스펠 확인하고 천천히 진입해."

    else:
        return {"status": "ignored", "msg": "알 수 없는 이벤트"}

    if briefing_text:
        # 실시간 브로드캐스트 전송
        await manager.broadcast({
            "type": "lol_briefing",
            "event": event_type,
            "text": briefing_text
        })
        return {"status": "success", "text": briefing_text}

    return {"status": "failed", "msg": "브리핑 텍스트 생성 실패"}

@router.post("/game-event", summary="외부 게임 이벤트 수신")
async def receive_game_event(req: GameEventRequest):
    """외부 감시 프로세스로부터 게임 이벤트를 수신하여 처리합니다."""
    event_type = req.event_type
    data = req.data or {}
    return {"status": "received", "event_type": event_type, "data": data}
