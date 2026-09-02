"""
routers/maple.py
==============================================================================
🍁 넥슨 메이플스토리(MapleStory) Open API 라우터
==============================================================================
이 모듈은 넥슨 공식 Open API(openapi.nexon.com)와 연동하여 사용자의 메이플스토리
본캐릭터 닉네임, 레벨, 직업, 월드, 유니온, 전투력, 착용 아케인/어센틱 심볼 및
장비 세팅 정보를 실시간으로 조회하고 챗봇(엔젤릭버스터/스카디)에 연동하는 라우터입니다.

주요 엔드포인트:
  1) POST /api/maple/link   : 닉네임 및 API Key로 캐릭터 스펙 연동
  2) GET  /api/maple/status : 현재 연동된 메이플 캐릭터의 최신 스펙 조회
==============================================================================
"""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from core.state import nexon_api, linked_maple_character

router = APIRouter(tags=["MapleStory API"])

# ==============================================================================
# 1. Pydantic 요청 스키마 정의
# ==============================================================================
class MapleLinkRequest(BaseModel):
    """메이플스토리 캐릭터 연동 요청 모델"""
    character_name: str             # 연동할 메이플스토리 캐릭터 닉네임 (예: 글자네, 팡이요 등)
    api_key: Optional[str] = None   # 사용자가 직접 발급받은 넥슨 API 키 (선택 사항, 미입력 시 서버 기본 키 사용)

# ==============================================================================
# 2. 메이플스토리 캐릭터 연동 API
# ==============================================================================
@router.post("/api/maple/link", summary="메이플스토리 캐릭터 닉네임 연동")
def link_maple_character(req: MapleLinkRequest):
    """
    넥슨 Open API 서버로 OCID(캐릭터 식별자)를 조회한 뒤, 기본 정보/장비/스탯을 파싱하여
    서버 전역 상태(linked_maple_character)에 캐싱합니다.
    이후 챗봇 대화 시 유저의 실제 레벨과 템세팅에 맞춘 조언이 가능해집니다.
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
    """
    현재 시스템에 연동되어 있는 메이플스토리 캐릭터의 상세 스펙 정보를 반환합니다.
    (연동되지 않은 경우 linked: False 반환)
    """
    import core.state as state
    if state.linked_maple_character:
        return {"linked": True, "character": state.linked_maple_character}
    return {"linked": False, "character": None}
