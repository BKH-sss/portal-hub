"""
routers/maple.py
------------------------------------------------------------
🍁 넥슨 메이플스토리(MapleStory) Open API 라우터.
- 유저 캐릭터 닉네임 연동 및 상세 스펙 조회 (/api/maple/link)
- 레벨, 직업, 월드, 전투력, 착용 장비 정보 제공
------------------------------------------------------------
"""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from core.state import nexon_api, linked_maple_character

router = APIRouter(tags=["MapleStory API"])

# ============================================================
# 1. Pydantic 요청 스키마 정의
# ============================================================
class MapleLinkRequest(BaseModel):
    """메이플스토리 캐릭터 연동 요청 모델"""
    character_name: str
    api_key: Optional[str] = None

# ============================================================
# 2. 캐릭터 연동 엔드포인트
# ============================================================
@router.post("/api/maple/link", summary="메이플스토리 캐릭터 닉네임 연동")
def link_maple_character(req: MapleLinkRequest):
    """
    넥슨 Open API를 통해 유저의 메이플 캐릭터(레벨, 직업, 장비 등)를 조회하고 
    챗봇의 컨텍스트에 연동하여 맞춤형 메이플 브리핑을 제공합니다.
    """
    import core.state as state
    info = nexon_api.get_character_info(req.character_name, api_key=req.api_key)
    if info.get("status") == "success":
        state.linked_maple_character = info
        world_str = f"[{info.get('world')}] " if info.get('world') else ""
        return {
            "status": "success",
            "message": f"{world_str}{info['name']} (Lv.{info['level']} {info['job']}) 연동 완료!",
            "data": info
        }
    else:
        return {
            "status": "error",
            "message": info.get("message", "연동 실패 (API Key가 없거나 캐릭터가 존재하지 않습니다)")
        }

@router.get("/api/maple/status", summary="현재 연동된 메이플 캐릭터 상태")
def get_maple_status():
    """현재 시스템에 연동된 메이플스토리 캐릭터 정보를 반환합니다."""
    import core.state as state
    if state.linked_maple_character:
        return {"linked": True, "character": state.linked_maple_character}
    return {"linked": False, "character": None}
