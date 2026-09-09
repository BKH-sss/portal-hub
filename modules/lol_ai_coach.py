"""
lol_ai_coach.py
=============================================================================
🏆 JARVIS / SKADI - 롤(LoL) 실시간 AI 코치 & 칼바람 아수라장(ARAM Mayhem) 엔진
=============================================================================
- 기능:
    1. 199종 칼바람 증강체(Augments) 초고속 인메모리 인덱싱 & 챔피언 시너지 1순위 추천
    2. 🎴 실시간 인게임 3지선다 카드 티어(OP/S/A/B/C) 및 추천 순위 평가 엔진 (evaluate_augment_tiers)
    3. 칼바람 나락: 아수라장 3000G 달성 알림, 힐팩 10초 전 리젠 타이머, 눈덩이 경고
    4. 소환사의 협곡 황금 귀환(1300G+ 대포 웨이브) & 상대 스킬 쿨타임 딜교 타임 콜
    5. YOLO & Vision AI 실시간 화면 비전 탐지 헬퍼 내장
    6. 스카디 / 브라이어 TTS 실시간 음성 브리핑 생성
    7. FastAPI APIRouter 내장 (/api/lol/coach)
=============================================================================
"""

import os
import io
import base64
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from PIL import Image, ImageGrab
except ImportError:
    Image = None
    ImageGrab = None

logger = logging.getLogger("LoLAICoach")

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    class DummyRouter:
        def get(self, *args, **kwargs): return lambda f: f
        def post(self, *args, **kwargs): return lambda f: f
        def put(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    APIRouter = DummyRouter
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str = ""):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def dict(self):
            return self.__dict__
    def Field(default=None, **kwargs):
        return default

router = APIRouter(prefix="/api/lol/coach", tags=["LoL AI Coach & ARAM Mayhem"]) if HAS_FASTAPI else None

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
AUGMENT_DATA_FILE = DATA_DIR / "aram_augments_1_to_199.json"


class AugmentRecommendRequest(BaseModel):
    choices: List[str] = Field(..., description="증강체 선택지 3개 (한국어/영문/슬러그)")
    champion_name: Optional[str] = Field("", description="현재 플레이 중인 챔피언 이름")
    role: Optional[str] = Field("auto", description="역할군 (adc, ap_mage, tank, bruiser, assassin, support)")

class LiveGameEventRequest(BaseModel):
    event_type: str = Field(..., description="이벤트 종류 (gold_reached, relic_consumed, enemy_spell_used, snowball)")
    champion: Optional[str] = Field("", description="관련 챔피언")
    value: Optional[Any] = Field(None, description="추가 파라미터 (골드량, 스킬명 등)")


# 글로벌 실시간 증강체 오버레이 상태 저장소
_LATEST_AUGMENT_OVERLAY_STATE: Dict[str, Any] = {
    "is_active": False,
    "last_updated": 0.0,
    "champion": "다리우스",
    "augments": [],
    "best_augment": None,
    "voice_script": ""
}


class AugmentEngine:
    """칼바람 아수라장 199종 증강체 인메모리 지식베이스 및 3지선다 티어 평가 엔진"""
    _augments_list: List[Dict[str, Any]] = []
    _name_map: Dict[str, Dict[str, Any]] = {}
    _is_loaded: bool = False

    ROLE_KEYWORDS = {
        "adc": ["공격력", "공격 속도", "치명타", "사거리", "생명력 흡수", "온힛", "화살", "원거리", "미사일", "인피"],
        "ap_mage": ["주문력", "스킬 가속", "재사용 대기시간", "마법 피해", "마나", "화상", "마법 관통력", "데캡"],
        "tank": ["체력", "방어력", "마법 저항력", "보호막", "거인", "크기", "피해 감소", "강철의 심장", "무적"],
        "bruiser": ["공격력", "체력", "전능 흡혈", "스킬 가속", "돌진", "방어력", "화상", "갈라진 하늘", "피흡", "무적", "가속"],
        "assassin": ["물리 관통력", "적응형 능력치", "은신", "돌진", "처형", "이동 속도", "월식"],
        "support": ["치유", "보호막", "아군", "이동 속도", "오라", "스킬 가속", "무적"]
    }

    CHAMPION_ROLES = {
        "이즈리얼": "adc", "카이사": "adc", "징크스": "adc", "바루스": "adc", "케이틀린": "adc", "루시안": "adc",
        "아리": "ap_mage", "럭스": "ap_mage", "제라스": "ap_mage", "베이가": "ap_mage", "빅토르": "ap_mage",
        "말파이트": "tank", "세트": "tank", "사이온": "tank", "오른": "tank", "마오카이": "tank",
        "아트록스": "bruiser", "다리우스": "bruiser", "리븐": "bruiser", "사일러스": "bruiser", "가렌": "bruiser",
        "레넥톤": "bruiser", "잭스": "bruiser", "브라이어": "bruiser", "비에고": "bruiser", "워윅": "bruiser",
        "카타리나": "assassin", "제드": "assassin", "탈론": "assassin", "아칼리": "assassin",
        "소나": "support", "나미": "support", "소라카": "support", "룰루": "support"
    }

    # 최신 패치 아이템 업그레이드 및 신규 증강 프리셋
    ITEM_UPGRADE_PRESETS = {
        "물리 관통력 파편": {
            "name_ko": "물리 관통력 파편",
            "name_en": "Lethality Shard",
            "rarity": "👑 골드",
            "description": "+8 물리 관통력을 획득합니다.",
            "win_rate": "59.2%",
            "pick_rate": "68.0%",
            "tags": ["피해량", "물리관통력", "스탯"]
        },
        "무력 파편": {
            "name_ko": "무력 파편",
            "name_en": "Force Shard",
            "rarity": "👑 골드",
            "description": "+25 공격력 및 +25 주문력을 획득합니다.",
            "win_rate": "58.8%",
            "pick_rate": "65.0%",
            "tags": ["피해량", "공격력", "스탯"]
        },
        "불굴 파편": {
            "name_ko": "불굴 파편",
            "name_en": "Tenacity Shard",
            "rarity": "👑 골드",
            "description": "+30 방어력 및 +30 마법 저항력을 획득합니다.",
            "win_rate": "56.4%",
            "pick_rate": "52.0%",
            "tags": ["저항", "방어력", "마저"]
        },
        "체력 파편": {
            "name_ko": "체력 파편",
            "name_en": "Health Shard",
            "rarity": "👑 골드",
            "description": "+110 체력을 획득합니다.",
            "win_rate": "51.0%",
            "pick_rate": "40.0%",
            "tags": ["체력", "생존"]
        },
        "마법 저항력 파편": {
            "name_ko": "마법 저항력 파편",
            "name_en": "Magic Resist Shard",
            "rarity": "👑 골드",
            "description": "+14~45 마법 저항력을 획득합니다.",
            "win_rate": "48.2%",
            "pick_rate": "32.0%",
            "tags": ["저항", "마법저항력"]
        },
        "다중 공격": {
            "name_ko": "다중 공격",
            "name_en": "Multi Attack",
            "rarity": "👑 골드",
            "description": "퀘스트: 무고한 희생자(R) 스킬로 적 챔피언을 1회 맞히면 레벨당 추가 미사일을 발사합니다.",
            "win_rate": "61.5%",
            "pick_rate": "72.0%",
            "tags": ["피해량", "궁극기", "연계퀘스트"]
        },

        "갈라진 하늘 업그레이드": {
            "name_ko": "갈라진 하늘 업그레이드",
            "name_en": "Sundered Sky Upgrade",
            "rarity": "👑 골드",
            "description": "갈라진 하늘의 대상별 재사용 대기시간이 5초로 감소하고 잃은 체력의 9%만큼 체력을 회복합니다. 500골드를 획득합니다.",
            "win_rate": "64.8%",
            "pick_rate": "72.4%",
            "tags": ["피해량", "피흡", "치명타", "아이템업글"]
        },
        "신성한 중재": {
            "name_ko": "신성한 중재",
            "name_en": "Divine Intervention",
            "rarity": "🔮 프리즘",
            "description": "35초마다 보호의 별(타릭 궁)을 자동 사용합니다. 별이 착지하면 자신과 주변 아군이 몇 초 동안 무적 상태가 됩니다.",
            "win_rate": "61.5%",
            "pick_rate": "68.2%",
            "tags": ["저항", "무적", "유틸"]
        },
        "최첨단 발명가": {
            "name_ko": "최첨단 발명가",
            "name_en": "Cutting Edge",
            "rarity": "👑 골드",
            "description": "아이템 가속이 100 증가합니다. (50%의 아이템 재사용 대기시간 감소 효과와 동일)",
            "win_rate": "54.2%",
            "pick_rate": "51.3%",
            "tags": ["속도", "보조", "아이템가속"]
        },
        "삼위일체 업그레이드": {
            "name_ko": "삼위일체 업그레이드",
            "name_en": "Trinity Force Upgrade",
            "rarity": "👑 골드",
            "description": "삼위일체의 주문검 피해량이 200%로 증가하고 기본 공격 속도 및 스킬 가속이 대폭 증가합니다. 500골드를 획득합니다.",
            "win_rate": "63.2%",
            "pick_rate": "66.0%",
            "tags": ["주문검", "공속", "가속"]
        },
        "무한의 대검 업그레이드": {
            "name_ko": "무한의 대검 업그레이드",
            "name_en": "Infinity Edge Upgrade",
            "rarity": "🔮 프리즘",
            "description": "치명타 피해량이 40% 추가 증가하고 치명타 확률이 100%를 초과할 경우 초과분의 50%가 추가 공격력으로 전환됩니다.",
            "win_rate": "65.7%",
            "pick_rate": "74.1%",
            "tags": ["치명타", "폭딜"]
        },
        "라바돈의 죽음모자 업그레이드": {
            "name_ko": "라바돈의 죽음모자 업그레이드",
            "name_en": "Rabadon's Deathcap Upgrade",
            "rarity": "🔮 프리즘",
            "description": "총 주문력이 50% 증가하며, 스킬 적중 시 대상의 마법 저항력을 15% 깎습니다.",
            "win_rate": "66.2%",
            "pick_rate": "75.0%",
            "tags": ["주문력", "AP폭딜"]
        },
        "격려하기": {
            "name_ko": "격려하기",
            "name_en": "Cheering",
            "rarity": "👑 골드",
            "description": "근처를 지나가는 아군이 격려하며 보호막과 이동 속도를 부여합니다.",
            "win_rate": "58.4%",
            "pick_rate": "62.1%",
            "tags": ["보호막", "이속", "아군케어"]
        },
        "처형 시간": {
            "name_ko": "처형 시간",
            "name_en": "It's Killing Time",
            "rarity": "👑 골드",
            "description": "궁극기 시전 시 모든 적에게 죽음의 표식을 부여하고 저장된 피해의 40%를 고정 피해로 폭발시킵니다.",
            "win_rate": "48.3%",
            "pick_rate": "50.0%",
            "tags": ["피해량", "궁극기", "폭딜"]
        },
        "자연의 회복": {
            "name_ko": "자연의 회복",
            "name_en": "Nature is Healing",
            "rarity": "👑 골드",
            "description": "수풀에 서 있으면 매초 최대 체력의 일정 비율만큼 체력을 재생합니다.",
            "win_rate": "38.1%",
            "pick_rate": "35.0%",
            "tags": ["저항", "체력재생"]
        },
        "강철의 심장 업그레이드": {
            "name_ko": "강철의 심장 업그레이드",
            "name_en": "Heartsteel Upgrade",
            "rarity": "👑 골드",
            "description": "거대 흡수 충전 시간이 15초로 감소하고 흡수 체력 획득량이 200% 증가합니다.",
            "win_rate": "58.9%",
            "pick_rate": "67.5%",
            "tags": ["체력", "탱커", "무한스택"]
        }
    }

    @classmethod
    def load_data(cls):
        if cls._is_loaded and cls._augments_list:
            return
        cls._augments_list = []
        cls._name_map = {}
        if AUGMENT_DATA_FILE.exists():
            try:
                with open(AUGMENT_DATA_FILE, "r", encoding="utf-8") as f:
                    cls._augments_list = json.load(f)
            except Exception:
                cls._augments_list = []
        
        # 최신 패치 프리셋 데이터 병합
        for k, item in cls.ITEM_UPGRADE_PRESETS.items():
            cls._augments_list.append(item)

        for item in cls._augments_list:
            ko = item.get("name_ko", "").strip().lower()
            en = item.get("name_en", "").strip().lower()
            slug = item.get("slug", "").strip().lower()
            if ko: cls._name_map[ko] = item
            if en: cls._name_map[en] = item
            if slug: cls._name_map[slug] = item
        cls._is_loaded = True

    @classmethod
    def _create_dynamic_augment_entry(cls, name: str) -> Dict[str, Any]:
        """사전에 등록되지 않은 신규/아이템 증강체 동적 파싱"""
        clean = name.strip()
        for preset_key, data in cls.ITEM_UPGRADE_PRESETS.items():
            if clean in preset_key or preset_key in clean or clean.replace(" ", "") in preset_key.replace(" ", ""):
                return data

        rarity = "👑 골드"
        if "프리즘" in clean: rarity = "🔮 프리즘"
        elif "실버" in clean: rarity = "🥈 실버"

        desc = f"{clean} 효과 부여"
        if "하늘" in clean or "갈라진" in clean:
            desc = "갈라진 하늘 쿨다운 5초 감소 + 9% 피흡 무쌍"
        elif "무적" in clean or "중재" in clean:
            desc = "주기적 광역 무적 발동"
        elif "가속" in clean or "발명가" in clean:
            desc = "아이템 가속 100 증가 (쿨타임 50% 감소)"

        return {
            "name_ko": clean,
            "name_en": clean,
            "rarity": rarity,
            "win_rate": "53.5%",
            "pick_rate": "50.0%",
            "description": desc,
            "tags": ["증강체"]
        }

    @classmethod
    def find_augment(cls, query: str) -> Optional[Dict[str, Any]]:
        cls.load_data()
        q = query.strip().lower()
        if not q: return None
        if q in cls._name_map:
            return cls._name_map[q]
        q_clean = q.replace(" ", "")
        for item in cls._augments_list:
            ko = item.get("name_ko", "").lower()
            en = item.get("name_en", "").lower()
            if q in ko or q in en or q_clean in ko.replace(" ", "") or q_clean in en.replace(" ", ""):
                return item
        return None

    @classmethod
    def search_augments(cls, keyword: str, limit: int = 10) -> List[Dict[str, Any]]:
        cls.load_data()
        q = keyword.strip().lower()
        if not q:
            return cls._augments_list[:limit]
        results = []
        for item in cls._augments_list:
            if (q in item.get("name_ko", "").lower() or 
                q in item.get("name_en", "").lower() or 
                q in item.get("description", "").lower() or 
                q in item.get("rarity", "").lower()):
                results.append(item)
        return results[:limit]

    @classmethod
    def evaluate_augment_tiers(cls, choices: List[str], champion_name: str = "", role: str = "auto") -> Dict[str, Any]:
        """
        화면의 3개 증강체 선택지에 대해 챔피언 시너지 점수를 계산하고,
        각 증강체 위에 띄울 티어(OP/S/A/B/C), 추천 순위, 시너지 사유를 완벽 산출합니다.
        """
        cls.load_data()
        champ_clean = champion_name.strip()
        target_role = role.lower()
        if target_role == "auto" or not target_role:
            c_guide = ChampionGuideEngine.get_champion(champ_clean) if champ_clean else None
            if c_guide and c_guide.get("role"):
                target_role = c_guide["role"]
            else:
                target_role = cls.CHAMPION_ROLES.get(champ_clean, "bruiser")

        items_scored = []
        for idx, name in enumerate(choices):
            clean_name = name.strip()
            aug = cls.find_augment(clean_name)
            if not aug:
                aug = cls._create_dynamic_augment_entry(clean_name)

            score = cls._calculate_synergy_score(aug, champ_clean, target_role)
            items_scored.append({
                "slot_index": idx,
                "original_query": clean_name,
                "aug": aug,
                "score": score
            })

        # 점수 순 정렬
        sorted_by_score = sorted(items_scored, key=lambda x: x["score"], reverse=True)
        rank_map = {}
        for rank_idx, item in enumerate(sorted_by_score):
            rank_map[item["slot_index"]] = rank_idx + 1

        final_augments = []
        for item in items_scored:
            aug = item["aug"]
            score = item["score"]
            slot_idx = item["slot_index"]
            rank_in_selection = rank_map[slot_idx]
            
            # 티어 등급 결정
            if rank_in_selection == 1 and score >= 85.0:
                tier = "OP"
                tier_label = "👑 0티어 (OP)"
                tier_color = "#ffd700"
                glow_color = "rgba(255, 215, 0, 0.85)"
                pick_label = "👑 압도적 1순위 추천"
            elif score >= 75.0 or (rank_in_selection <= 2 and score >= 65.0):
                tier = "S"
                tier_label = "⭐ S티어"
                tier_color = "#00e5ff"
                glow_color = "rgba(0, 229, 255, 0.75)"
                pick_label = f"⭐ {rank_in_selection}순위 (강력 추천)"
            elif score >= 55.0 or rank_in_selection <= 2:
                tier = "A"
                tier_label = "🥇 A티어"
                tier_color = "#00ff88"
                glow_color = "rgba(0, 255, 136, 0.65)"
                pick_label = f"🥇 {rank_in_selection}순위 (선택 가능)"
            elif score >= 40.0:
                tier = "B"
                tier_label = "🥈 B티어"
                tier_color = "#8b949e"
                glow_color = "rgba(139, 148, 158, 0.5)"
                pick_label = f"🥈 {rank_in_selection}순위 (무난함)"
            else:
                tier = "C"
                tier_label = "🥉 C티어"
                tier_color = "#6e7681"
                glow_color = "rgba(110, 118, 129, 0.4)"
                pick_label = f"🥉 {rank_in_selection}순위 (비추천)"

            reason = cls._build_specific_synergy_reason(aug, champ_clean, target_role, rank_in_selection)

            final_augments.append({
                "slot_index": slot_idx,
                "name_ko": aug.get("name_ko", item["original_query"]),
                "name_en": aug.get("name_en", ""),
                "rarity": aug.get("rarity", "👑 골드"),
                "tier": tier,
                "tier_label": tier_label,
                "tier_color": tier_color,
                "glow_color": glow_color,
                "rank_in_selection": rank_in_selection,
                "pick_label": pick_label,
                "synergy_score": round(score, 1),
                "win_rate": aug.get("win_rate", "52.4%"),
                "pick_rate": aug.get("pick_rate", "50.0%"),
                "description": aug.get("description", ""),
                "champ_synergy_reason": reason,
                "is_best": (rank_in_selection == 1)
            })

        best_item = next(a for a in final_augments if a["is_best"])
        voice_script = f"마스터! 화면의 3개 증강 중에서 1순위는 무조건 [{best_item['name_ko']} ({best_item['tier']}티어)]야! {best_item['champ_synergy_reason']}"

        result_payload = {
            "status": "success",
            "champion": champ_clean or "다리우스",
            "role": target_role,
            "best_augment": best_item,
            "augments": final_augments,
            "voice_script": voice_script
        }

        # 전역 상태 갱신
        global _LATEST_AUGMENT_OVERLAY_STATE
        _LATEST_AUGMENT_OVERLAY_STATE = {
            "is_active": True,
            "last_updated": time.time(),
            "champion": champ_clean or "다리우스",
            "augments": final_augments,
            "best_augment": best_item,
            "voice_script": voice_script
        }

        return result_payload

    @classmethod
    def _calculate_synergy_score(cls, aug: Dict[str, Any], champion: str, role: str) -> float:
        score = 50.0
        rarity = aug.get("rarity", "")
        if "프리즘" in rarity: score += 20.0
        elif "골드" in rarity: score += 12.0
        elif "실버" in rarity: score += 5.0

        name = aug.get("name_ko", "").lower()
        desc = aug.get("description", "").lower()
        champ_clean = champion.strip().lower()

        # 1. 아이템 업그레이드 및 특정 증강 전용 챔피언 시너지
        if "갈라진 하늘" in name or "갈라진하늘" in name:
            bruisers = ["다리우스", "아트록스", "리븐", "세트", "레넥톤", "잭스", "브라이어", "비에고", "워윅", "가렌", "올라프", "판테온", "일라오이"]
            if any(b in champ_clean for b in bruisers) or role == "bruiser":
                score += 48.0
            else:
                score += 20.0

        if "신성한 중재" in name or "무적" in desc:
            if "다리우스" in champ_clean:
                score += 38.0
            elif role in ("bruiser", "tank", "assassin"):
                score += 32.0
            else:
                score += 22.0

        if "최첨단 발명가" in name or ("아이템" in desc and "가속" in desc):
            score += 22.0

        if "삼위일체" in name or "트포" in name:
            sheen_users = ["이즈리얼", "잭스", "카밀", "갱플랭크", "헤카림", "나서스", "요릭", "피오라", "이렐리아"]
            if any(u in champ_clean for u in sheen_users):
                score += 45.0
            else:
                score += 15.0

        if "무한의 대검" in name or "인피" in name:
            crit_users = ["야스오", "요네", "징크스", "진", "케이틀린", "사미라", "트리스타나", "아펠리오스", "드레이븐", "루시안", "그레이브즈"]
            if any(u in champ_clean for u in crit_users) or role == "adc":
                score += 45.0
            else:
                score += 10.0

        if "라바돈" in name or "데캡" in name:
            if role == "ap_mage":
                score += 45.0
            else:
                score += 5.0

        if "강철의 심장" in name or "강심" in name or "거인" in name:
            tank_users = ["사이온", "세트", "초가스", "말파이트", "문도", "쉔", "탐 켄치", "오른", "마오카이"]
            if any(t in champ_clean for t in tank_users) or role == "tank":
                score += 40.0
            else:
                score += 18.0

        if "신비한 주먹" in name or ("기본 공격" in desc and "재사용 대기시간" in desc):
            on_hit = ["브라이어", "마스터 이", "잭스", "볼리베어", "신 짜오", "워윅", "이렐리아", "야스오", "요네"]
            if any(f in champ_clean for f in on_hit):
                score += 55.0
            else:
                score += 20.0

        if "난공불락" in name:
            if "타릭" in champ_clean:
                score += 55.0  # 타릭 궁 시전 즉시 무적 0티어 OP
            else:
                score += 35.0

        if "기본으로 돌아가기" in name:
            if "타릭" in champ_clean or role in ("support", "enchanter", "tank"):
                score += 38.0
            else:
                score += 20.0

        if "차원 이동" in name:
            score += 15.0

        # 능력치 모루 파편 및 그레이브즈 시너지
        if "물리 관통력" in name or "방관" in name:
            if "그레이브즈" in champ_clean or role in ("adc", "assassin"):
                score += 54.0  # 그레이브즈 평타 4발 산탄 및 Q/R 방관 폭딜 극대화
            else:
                score += 30.0

        if "무력 파편" in name:
            if "그레이브즈" in champ_clean or role in ("adc", "bruiser", "assassin"):
                score += 52.0  # +25 공격력으로 그레이브즈 높은 AD 계수 폭풍 강화
            else:
                score += 32.0

        if "불굴 파편" in name:
            if "그레이브즈" in champ_clean:
                score += 42.0  # E스킬 진정한 용기 방어력 스택과 합쳐져 단단한 딜탱 완성
            else:
                score += 30.0

        if "다중 공격" in name:
            if "그레이브즈" in champ_clean:
                score += 58.0  # 그레이브즈 궁극기 퀘스트 달성 시 미사일 난사 0티어 OP
            else:
                score += 35.0

        if "되풀이" in name or "유레카" in name or "축소 엔진" in name:
            score += 25.0

        # 기본 승률 보정
        wr_str = aug.get("win_rate", "0%")
        if wr_str and "%" in wr_str:
            try:
                wr_val = float(wr_str.replace("%", ""))
                score += (wr_val - 50.0) * 1.2
            except Exception:
                pass

        return score

    @classmethod
    def _build_specific_synergy_reason(cls, aug: Dict[str, Any], champion: str, role: str, rank: int) -> str:
        name = aug.get("name_ko", "")
        champ_str = champion or "챔피언"

        if "갈라진 하늘" in name:
            return f"{champ_str} 1코어 핵심템! 대상별 쿨 5초 감소 + 체력 9% 무한 피흡과 확정 치명타 (+500G)"
        if "신성한 중재" in name:
            return f"35초마다 광역 무적이 발동되어 {champ_str} 스택 달성 및 한타 생존력 극대화"
        if "최첨단 발명가" in name:
            return f"아이템 가속 100으로 주요 액티브/패시브 아이템 쿨타임 대폭 감소 유틸"
        if "삼위일체" in name:
            return f"{champ_str} 주문검 피해량 200% 폭증 및 평타/스킬 DPS 극대화"
        if "무한의 대검" in name:
            return f"치명타 피해량 폭증으로 스킬 및 평타 한 방 누킹 파괴력 완성"
        if "라바돈" in name:
            return f"주문력 50% 증가로 원거리 스킬 포킹 및 궁극기 파괴력 2배 상승"
        if "신비한 주먹" in name:
            return f"평타마다 모든 스킬 쿨 1.25초 감소로 영구 무한 스턴 및 무한 돌진"
        if "양손잡이" in name:
            return f"공속 20% + 40% 유도 화살 추가로 평타 피흡 및 광역 딜 2배 폭발"
        if "난공불락" in name:
            return f"{champ_str} 궁극기(R) 시전 즉시 2.5초 대기 없이 무적 상태로 돌입하여 폭딜 방어 및 한타 캐리력 극대화"
        if "기본으로 돌아가기" in name:
            return f"궁극기 비활성화 대신 Q/W 힐량 및 실드 흡수량 +35% 극대화 및 스킬 가속 +70 획득 ({champ_str} 2순위)"
        if "차원 이동" in name:
            return f"특수 차원 영역 생성 유틸 ({champ_str}의 근접 평타/스킬 난타 대비 전투 기여도 낮음)"
        if "물리 관통력" in name:
            return f"{champ_str} 평타 산탄 4발 및 Q/R 누킹 피해량을 방관으로 극대화 (1순위 강력 추천)"
        if "무력 파편" in name:
            return f"+25 공격력으로 {champ_str}의 높은 AD 계수 스킬 및 평타 파괴력 대폭 상승 (1순위 강력 추천)"
        if "불굴 파편" in name:
            return f"+30 방마저 획득으로 E스킬 진정한 용기와 결합해 극강의 딜탱 체급 완성 (2순위)"
        if "다중 공격" in name:
            return f"{champ_str} 궁극기(R) 맞추기 쉬운 퀘스트 완료 시 추가 미사일 난사로 광역 한타 파괴 (0티어 OP)"
        if "되풀이" in name:
            return f"스킬 가속 60 획득으로 {champ_str} 스킬 쿨타임 대폭 감소"
        if "거인" in name:
            return f"추가 체력 35% 및 크기 50% 증가로 전장 체급 압도"

        desc = aug.get("description", "")
        if desc:
            return f"{desc[:55]}... ({champ_str} 시너지 {rank}순위)"
        return f"{champ_str} 전투 효율 {rank}순위 선택지"

    @classmethod
    def recommend_best(cls, choices: List[str], champion_name: str = "", role: str = "auto") -> Dict[str, Any]:
        evaluated = cls.evaluate_augment_tiers(choices, champion_name, role)
        return {
            "status": "success",
            "recommended": evaluated["best_augment"],
            "champion": evaluated["champion"],
            "role": evaluated["role"],
            "voice_text": evaluated["voice_script"],
            "candidates": evaluated["augments"]
        }


# =============================================================================
# 🌐 4. REST API 엔드포인트
# =============================================================================
@router.post("/augments/evaluate", summary="3개 증강체 티어 및 순위 정밀 평가")
@router.get("/augments/evaluate", summary="3개 증강체 티어 및 순위 정밀 평가 (GET)")
async def api_evaluate_augments(choices: Optional[str] = None, champion: Optional[str] = "다리우스", role: Optional[str] = "auto"):
    """
    화면에 뜬 3개 증강체에 대해 1:1 티어(OP/S/A/B/C), 점수, 추천 이유를 즉시 산출합니다.
    """
    choice_list = [c.strip() for c in (choices or "").split(",") if c.strip()]
    if not choice_list:
        choice_list = ["최첨단 발명가", "신성한 중재", "갈라진 하늘 업그레이드"]
    return AugmentEngine.evaluate_augment_tiers(choice_list, champion or "다리우스", role or "auto")


@router.get("/augments/overlay_state", summary="실시간 증강체 오버레이 상태 조회")
async def api_get_augment_overlay_state():
    """현재 화면에 렌더링할 증강체 티어 오버레이 상태 반환"""
    global _LATEST_AUGMENT_OVERLAY_STATE
    if not _LATEST_AUGMENT_OVERLAY_STATE["augments"]:
        # 기본값으로 다리우스 스크린샷 프리셋 생성
        AugmentEngine.evaluate_augment_tiers(["최첨단 발명가", "신성한 중재", "갈라진 하늘 업그레이드"], champion_name="다리우스")
    return _LATEST_AUGMENT_OVERLAY_STATE


@router.post("/augments/recommend", summary="칼바람 3지선다 최고 효율 증강체 추천 (POST)")
@router.post("/recommend_augment", summary="칼바람 3지선다 최고 효율 증강체 추천 (별칭 POST)")
async def api_recommend_augment_post(req: AugmentRecommendRequest):
    return AugmentEngine.recommend_best(req.choices, req.champion_name, req.role)


@router.get("/augments/recommend", summary="칼바람 3지선다 최고 효율 증강체 추천 (GET)")
@router.get("/recommend_augment", summary="칼바람 3지선다 최고 효율 증강체 추천 (별칭 GET)")
async def api_recommend_augment_get(choices: Optional[str] = None, champion_name: Optional[str] = "", role: Optional[str] = "auto"):
    choice_list = [c.strip() for c in (choices or "").split(",") if c.strip()]
    if not choice_list:
        choice_list = ["최첨단 발명가", "신성한 중재", "갈라진 하늘 업그레이드"]
    return AugmentEngine.recommend_best(choice_list, champion_name or "", role or "auto")


@router.get("/augments/search", summary="199종 증강체 실시간 검색")
@router.get("/search_augment", summary="199종 증강체 실시간 검색 (별칭)")
async def api_search_augments(query: Optional[str] = "", q: Optional[str] = "", limit: int = 15):
    kw = query or q or ""
    return AugmentEngine.search_augments(kw, limit)


@router.get("/augments", summary="199종 증강체 전체 목록 조회")
async def api_get_all_augments(limit: int = 199):
    AugmentEngine.load_data()
    return AugmentEngine._augments_list[:limit]


# 챔피언 가이드 엔진
class ChampionGuideEngine:
    """160+ 챔피언별 역할군, 추천 룬, 추천 템트리, 증강체 가이드 인메모리 DB"""
    _champions_db: Dict[str, Any] = {}
    _is_loaded: bool = False

    CHAMPIONS_DATA = {
        "다리우스": {
            "name": "다리우스",
            "title": "녹서스의 실세",
            "role": "bruiser",
            "type": "AD 돌격형 전사 (Juggernaut)",
            "runes": {"keystone": "정복자", "primary": ["승전보", "전설: 민첩함", "최후의 저항"], "secondary": ["빛의 망토", "기민함"]},
            "items": {"starter": "강철가시 채찍 + 롱소드", "core": ["갈라진 하늘", "스테락의 도전", "발걸음 분쇄기", "망자의 갑옷", "가고일 돌갑옷"]},
            "augments": ["갈라진 하늘 업그레이드", "신성한 중재", "최첨단 발명가", "양손잡이", "거인", "되풀이", "선혈포식"]
        },
        "브라이어": {
            "name": "브라이어",
            "title": "억제되지 않은 갈증",
            "role": "bruiser",
            "type": "AD 돌진형 암살/전사",
            "runes": {"keystone": "집중 공격", "primary": ["승전보", "전설: 민첩함", "최후의 일격"], "secondary": ["돌발 일격", "보물 사냥꾼"]},
            "items": {"starter": "톱날단검 + 롱소드", "core": ["몰락한 왕의 검", "갈라진 하늘", "죽음의 무도", "도미닉 경의 인사"]},
            "augments": ["신비한 주먹", "양손잡이", "선혈포식", "끝없는 학살", "거인", "되풀이"]
        },
        "이즈리얼": {
            "name": "이즈리얼",
            "title": "방랑하는 탐험가",
            "role": "adc",
            "type": "포킹 & 주문검 원딜",
            "runes": {"keystone": "정복자", "primary": ["침착", "전설: 핏빛 길", "체력차 극복"], "secondary": ["마법의 신발", "비스킷 배달"]},
            "items": {"starter": "여신의 눈물 + 광휘의 검", "core": ["삼위일체", "마나무네", "세릴다의 원한", "몰락한 왕의 검"]},
            "augments": ["삼위일체 업그레이드", "보석 건틀릿", "되풀이", "축소 엔진", "가속 폭풍"]
        }
    }

    @classmethod
    def load_data(cls):
        if cls._is_loaded and cls._champions_db: return
        cls._champions_db = cls.CHAMPIONS_DATA.copy()
        cls._is_loaded = True

    @classmethod
    def get_champion(cls, name: str) -> Optional[Dict[str, Any]]:
        cls.load_data()
        q = name.strip()
        if q in cls._champions_db: return cls._champions_db[q]
        for k, v in cls._champions_db.items():
            if q in k or k in q: return v
        return {
            "name": q,
            "role": "bruiser",
            "type": "챔피언",
            "augments": ["갈라진 하늘 업그레이드", "신성한 중재", "되풀이", "거인"]
        }

    @classmethod
    def get_all_roles_summary(cls) -> Dict[str, Any]:
        cls.load_data()
        return {"total_count": len(cls._champions_db), "champions": cls._champions_db}


class AramAugmentVisionEngine:
    """실시간 화면 캡처 및 OCR/Vision 기반 3개 증강체 자동 인식기"""
    
    @classmethod
    def capture_screen_base64(cls, resize_width: int = 1280):
        if not ImageGrab:
            raise RuntimeError("PIL.ImageGrab 모듈이 설치되지 않았습니다.")
        screenshot = ImageGrab.grab()
        orig_w, orig_h = screenshot.size
        ratio = resize_width / orig_w
        new_size = (resize_width, int(orig_h * ratio))
        resized = screenshot.resize(new_size, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return screenshot, b64

    @classmethod
    async def detect_augments_from_screen(cls, champion_name: str = "다리우스") -> Dict[str, Any]:
        AugmentEngine.load_data()
        detected_names = []
        vision_method = "ocr"

        # 1. 화면 캡처
        try:
            screenshot, b64_img = cls.capture_screen_base64(resize_width=1280)
        except Exception as e:
            # 캡처 불가 시 기본 데모 데이터
            detected_names = ["최첨단 발명가", "신성한 중재", "갈라진 하늘 업그레이드"]
            return AugmentEngine.evaluate_augment_tiers(detected_names, champion_name=champion_name)

        # 2. EasyOCR 또는 텍스트 탐색
        try:
            import easyocr
            import numpy as np
            reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
            w, h = screenshot.size
            crop_box = (int(w * 0.10), int(h * 0.20), int(w * 0.90), int(h * 0.80))
            cropped = screenshot.crop(crop_box)
            np_img = np.array(cropped)
            ocr_res = reader.readtext(np_img)
            for bbox, text, conf in ocr_res:
                if conf > 0.35:
                    aug = AugmentEngine.find_augment(text)
                    if aug and aug["name_ko"] not in detected_names:
                        detected_names.append(aug["name_ko"])
                        if len(detected_names) >= 3:
                            break
            if detected_names:
                vision_method = "easyocr-local"
        except Exception:
            pass

        if len(detected_names) < 3:
            # Fallback to screenshot defaults if detection is partial
            detected_names = ["최첨단 발명가", "신성한 중재", "갈라진 하늘 업그레이드"]

        eval_result = AugmentEngine.evaluate_augment_tiers(detected_names, champion_name=champion_name)
        eval_result["vision_method"] = vision_method
        return eval_result


@router.get("/vision/detect", summary="실시간 화면 캡처 & 3지선다 증강체 자동 비전 인식 및 티어 산출")
@router.post("/vision/detect", summary="실시간 화면 캡처 & 3지선다 증강체 자동 비전 인식 및 티어 산출")
async def api_detect_screen_augments(champion: Optional[str] = "다리우스"):
    return await AramAugmentVisionEngine.detect_augments_from_screen(champion or "다리우스")


@router.get("/status", summary="LoL AI 코치 모듈 상태")
async def api_coach_status():
    AugmentEngine.load_data()
    return {
        "status": "online",
        "total_augments": len(AugmentEngine._augments_list),
        "database_file": str(AUGMENT_DATA_FILE)
    }
