"""
routers/maple.py
==============================================================================
🍁 넥슨 메이플스토리(MapleStory) Open API 라우터
==============================================================================
이 모듈은 넥슨 공식 Open API(openapi.nexon.com)와 연동하여 사용자의 메이플스토리
본캐릭터 닉네임, 레벨, 직업, 월드, 길드, 전투력, 대표 아바타 외형 이미지를
실시간으로 조회하고 챗봇(엔젤릭버스터/스카디) 및 관리자 패널의 47+ 직업 프리셋과 자동 연동합니다.

주요 엔드포인트:
  1) POST /api/maple/link   : 닉네임 및 API Key로 캐릭터 스펙 연동 & 프리셋 자동 적용
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
    character_name: str             # 연동할 메이플스토리 캐릭터 닉네임 (예: re흔들린은월, 타락파워전사 등)
    api_key: Optional[str] = None   # 사용자가 직접 발급받은 넥슨 API 키 (선택)
    auto_apply_preset: bool = Field(True, description="캐릭터의 직업에 맞는 스킬 쿨타임 프리셋 자동 적용 여부")


def find_matching_job_preset(job_name_or_query: str) -> Optional[str]:
    """캐릭터 직업명 또는 닉네임 문자열로부터 가장 일치하는 스킬 프리셋 키를 정밀 탐색"""
    if not job_name_or_query:
        return None
    clean_query = job_name_or_query.strip()
    
    # 1. 완전 일치
    if clean_query in JOB_PRESETS:
        return clean_query
        
    # 2. 직업 키워드가 쿼리 안에 포함되어 있는지 탐색 (예: 're흔들린은월' -> '은월', '비숍키우기' -> '비숍')
    # 긴 이름(예: '다크나이트', '아크메이지(불,독)')을 짧은 이름보다 먼저 매칭하기 위해 길이 내림차순 정렬
    sorted_presets = sorted(JOB_PRESETS.keys(), key=len, reverse=True)
    for p in sorted_presets:
        if p in clean_query:
            return p
            
    # 3. 특수 별칭 / 축약어 매핑 (예: '불독', '나로', '듀블', '데벤', '엔버' 등)
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
        "소마": "소울마스터",
        "데슬": "데몬슬레이어",
        "데벤": "데몬어벤져",
        "데벤져": "데몬어벤져",
        "배메": "배틀메이지",
        "와헌": "와일드헌터",
        "엔버": "엔젤릭버스터",
        "닼나": "다크나이트",
        "팔라": "팔라딘",
        "캐슈": "캐논슈터",
        "메르": "메르세데스",
        "루미": "루미너스",
        "블래": "블래스터",
        "메카": "메카닉",
        "키네": "키네시스",
        "은월": "은월"
    }
    for alias, target in alias_map.items():
        if alias in clean_query and target in JOB_PRESETS:
            return target
            
    # 4. 역방향 부분 일치
    for p in sorted_presets:
        if clean_query in p:
            return p
            
    return None

# ==============================================================================
# 2. 메이플스토리 캐릭터 연동 API
# ==============================================================================
@router.post("/api/maple/link", summary="메이플스토리 캐릭터 닉네임 연동")
def link_maple_character(req: MapleLinkRequest):
    """
    넥슨 Open API 서버로 OCID(캐릭터 식별자)를 조회한 뒤, 기본 정보/장비/스탯/외형 이미지를 파싱하여
    서버 전역 상태(linked_maple_character)에 캐싱하고 직업 프리셋을 자동 연동합니다.
    (만약 넥슨 API 조회 제한/오류 발생 시에도 닉네임에 포함된 직업명을 스마트 감지하여 즉시 프리셋을 적용합니다)
    """
    import core.state as state
    clean_name = req.character_name.strip()
    if not clean_name:
        return {"status": "error", "message": "캐릭터 닉네임을 입력해주세요."}

    # 1. 넥슨 공식 Open API 조회 시도
    info = nexon_api.get_character_info(clean_name, api_key=req.api_key)
    
    if info.get("status") == "success":
        state.linked_maple_character = info
        world_str = f"[{info.get('world')}] " if info.get('world') else ""
        job_name = info.get('job', '')
        
        # 캐릭터 직업에 대응하는 스킬 프리셋 자동 탐색 및 적용
        matched_preset = find_matching_job_preset(job_name)
        preset_loaded = False
        if req.auto_apply_preset and matched_preset:
            preset_loaded = maple_watcher.load_preset(matched_preset)
            
        guild_str = f" ({info.get('guild')})" if info.get('guild') and info.get('guild') != '없음' else ""
        combat_str = f" | 전투력: {info.get('combat_power')}" if info.get('combat_power') and info.get('combat_power') != '0' else ""
        
        return {
            "status": "success",
            "message": f"{world_str}{info['name']} (Lv.{info['level']} {info['job']}{guild_str}{combat_str}) 연동 완료!",
            "matched_preset": matched_preset,
            "preset_applied": preset_loaded,
            "data": info
        }
    else:
        # 2. 스마트 Fallback: 닉네임 또는 입력 텍스트에서 직업명 감지
        matched_preset = find_matching_job_preset(clean_name)
        if matched_preset:
            preset_loaded = False
            if req.auto_apply_preset:
                preset_loaded = maple_watcher.load_preset(matched_preset)
            
            fallback_info = {
                "status": "success",
                "name": clean_name,
                "level": 0,
                "job": matched_preset,
                "world": "연동(직업 감지)",
                "guild": "없음",
                "combat_power": "-",
                "image": ""
            }
            state.linked_maple_character = fallback_info
            
            return {
                "status": "success",
                "message": f"'{clean_name}'에서 직업 [{matched_preset}] 감지! 스킬 프리셋이 자동 적용되었습니다.",
                "matched_preset": matched_preset,
                "preset_applied": preset_loaded,
                "data": fallback_info,
                "fallback": True
            }
            
        return {
            "status": "error",
            "message": info.get("message", f"'{clean_name}' 캐릭터를 찾을 수 없습니다. 닉네임 또는 직업명을 확인해주세요.")
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
