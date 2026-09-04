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
from pydantic import BaseModel, Field

from core.state import nexon_api, linked_maple_character
from modules.maple_skill_tracker import maple_watcher, JOB_PRESETS

router = APIRouter(tags=["MapleStory API"])

# ==============================================================================
# 1. Pydantic 요청 스키마 정의
# ==============================================================================
class MapleLinkRequest(BaseModel):
    """메이플스토리 캐릭터 연동 요청 모델"""
    character_name: str             # 연동할 메이플스토리 캐릭터 닉네임 (예: 글자네, 팡이요 등)
    api_key: Optional[str] = None   # 사용자가 직접 발급받은 넥슨 API 키
    auto_apply_preset: bool = Field(True, description="캐릭터의 직업에 맞는 스킬 쿨타임 프리셋 자동 적용 여부")


def find_matching_job_preset(job_name: str) -> Optional[str]:
    """캐릭터 직업명으로 가장 일치하는 스킬 프리셋 키를 탐색"""
    if not job_name:
        return None
    clean_job = job_name.strip()
    
    # 1. 완전 일치
    if clean_job in JOB_PRESETS:
        return clean_job
        
    # 2. 부분 일치 검색
    for p in JOB_PRESETS.keys():
        if p in clean_job or clean_job in p:
            return p
            
    # 3. 특수 별칭 매핑
    alias_map = {
        "불독": "아크메이지(불,독)",
        "썬콜": "아크메이지(썬,콜)",
        "듀블": "듀얼블레이드",
        "나로": "나이트로드",
        "보마": "보우마스터",
        "패파": "패스파인더",
        "플위": "플레임위자드",
        "윈브": "윈드브레이커",
        "나워": "나이트워커",
        "스커": "스트라이커",
        "데슬": "데몬슬레이어",
        "데벤": "데몬어벤져",
        "배메": "배틀메이지",
        "와헌": "와일드헌터",
        "엔버": "엔젤릭버스터",
        "소마": "소울마스터"
    }
    for alias, target in alias_map.items():
        if alias in clean_job and target in JOB_PRESETS:
            return target
            
    return None

# ==============================================================================
# 2. 메이플스토리 캐릭터 연동 API
# ==============================================================================
@router.post("/api/maple/link", summary="메이플스토리 캐릭터 닉네임 연동")
def link_maple_character(req: MapleLinkRequest):
    """
    넥슨 Open API 서버로 OCID(캐릭터 식별자)를 조회한 뒤, 기본 정보/장비/스탯을 파싱하여
    서버 전역 상태(linked_maple_character)에 캐싱하고 직업 프리셋을 자동 연동합니다.
    """
    import core.state as state
    info = nexon_api.get_character_info(req.character_name, api_key=req.api_key)
    if info.get("status") == "success":
        state.linked_maple_character = info
        world_str = f"[{info.get('world')}] " if info.get('world') else ""
        job_name = info.get('job', '')
        
        # 직업 프리셋 자동 탐색 및 적용
        matched_preset = find_matching_job_preset(job_name)
        preset_loaded = False
        if req.auto_apply_preset and matched_preset:
            preset_loaded = maple_watcher.load_preset(matched_preset)
            
        return {
            "status": "success",
            "message": f"{world_str}{info['name']} (Lv.{info['level']} {info['job']}) 연동 완료!",
            "matched_preset": matched_preset,
            "preset_applied": preset_loaded,
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
    """
    import core.state as state
    if state.linked_maple_character:
        return {
            "linked": True,
            "character": state.linked_maple_character,
            "current_preset": maple_watcher.current_preset_name,
            "tracker_running": maple_watcher.is_running
        }
    return {
        "linked": False,
        "character": None,
        "current_preset": maple_watcher.current_preset_name,
        "tracker_running": maple_watcher.is_running
    }

