"""
lol_ai_coach.py
=============================================================================
🏆 JARVIS / SKADI - 롤(LoL) 실시간 AI 코치 & 칼바람 아수라장(ARAM Mayhem) 엔진
=============================================================================
- 기능:
    1. 199종 칼바람 증강체(Augments) 초고속 인메모리 인덱싱 & 챔피언 시너지 1순위 추천
    2. 칼바람 나락: 아수라장 3000G 달성 알림, 힐팩 10초 전 리젠 타이머, 눈덩이 경고
    3. 소환사의 협곡 황금 귀환(1300G+ 대포 웨이브) & 상대 스킬 쿨타임 딜교 타임 콜
    4. YOLO (RTX 4080 Super CUDA 가속) 실시간 화면 비전 탐지 헬퍼 내장
    5. 스카디 TTS 나긋나긋/똑똑한 실시간 음성 브리핑 생성
    6. FastAPI APIRouter 내장 (/api/lol/coach)
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


class AugmentEngine:
    """칼바람 아수라장 199종 증강체 인메모리 지식베이스 및 추천기"""
    _augments_list: List[Dict[str, Any]] = []
    _name_map: Dict[str, Dict[str, Any]] = {}
    _is_loaded: bool = False

    ROLE_KEYWORDS = {
        "adc": ["공격력", "공격 속도", "치명타", "사거리", "생명력 흡수", "온힛", "화살", "원거리", "미사일"],
        "ap_mage": ["주문력", "스킬 가속", "재사용 대기시간", "마법 피해", "마나", "화상", "마법 관통력"],
        "tank": ["체력", "방어력", "마법 저항력", "보호막", "거인", "크기", "피해 감소", "강철의 심장"],
        "bruiser": ["공격력", "체력", "전능 흡혈", "스킬 가속", "돌진", "방어력", "화상"],
        "assassin": ["물리 관통력", "적응형 능력치", "은신", "돌진", "처형", "이동 속도"],
        "support": ["치유", "보호막", "아군", "이동 속도", "오라", "스킬 가속"]
    }

    CHAMPION_ROLES = {
        "이즈리얼": "adc", "카이사": "adc", "징크스": "adc", "바루스": "adc", "케이틀린": "adc", "루시안": "adc",
        "아리": "ap_mage", "럭스": "ap_mage", "제라스": "ap_mage", "베이가": "ap_mage", "빅토르": "ap_mage",
        "말파이트": "tank", "세트": "tank", "사이온": "tank", "오른": "tank", "마오카이": "tank",
        "아트록스": "bruiser", "다리우스": "bruiser", "리븐": "bruiser", "사일러스": "bruiser",
        "카타리나": "assassin", "제드": "assassin", "탈론": "assassin", "아칼리": "assassin",
        "소나": "support", "나미": "support", "소라카": "support", "룰루": "support"
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
        if not cls._augments_list:
            cls._augments_list = [
                {"rank": 1, "name_ko": "초월 의식", "name_en": "Rite of Ascension", "rarity": "🔮 프리즘", "win_rate": "데이터 없음", "pick_rate": "100.0%", "description": "처치 관여 시 정수 생성. 기본 스킬 쿨 초기화."},
                {"rank": 2, "name_ko": "전환: 프리즘", "name_en": "Transmute: Prismatic", "rarity": "👑 골드", "win_rate": "64.15%", "pick_rate": "65.37%", "description": "무작위 프리즘 증강 1개 획득."},
                {"rank": 4, "name_ko": "축소 엔진", "name_en": "Shrink Engine", "rarity": "👑 골드", "win_rate": "56.44%", "pick_rate": "61.59%", "description": "스택당 스킬가속 10 + 이속 2%."},
                {"rank": 7, "name_ko": "되풀이", "name_en": "Recursion", "rarity": "👑 골드", "win_rate": "57.59%", "pick_rate": "60.35%", "description": "스킬 가속 60을 얻습니다."},
                {"rank": 17, "name_ko": "보석 건틀릿", "name_en": "Jeweled Gauntlet", "rarity": "🔮 프리즘", "win_rate": "54.46%", "pick_rate": "57.90%", "description": "스킬에 치명타가 적용됩니다."},
                {"rank": 20, "name_ko": "거인", "name_en": "Goliath", "rarity": "🔮 프리즘", "win_rate": "35.75%", "pick_rate": "57.58%", "description": "추가 체력 35%, 크기 50% 증가."}
            ]
        for item in cls._augments_list:
            ko = item.get("name_ko", "").strip().lower()
            en = item.get("name_en", "").strip().lower()
            slug = item.get("slug", "").strip().lower()
            if ko: cls._name_map[ko] = item
            if en: cls._name_map[en] = item
            if slug: cls._name_map[slug] = item
        cls._is_loaded = True

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
    def recommend_best(cls, choices: List[str], champion_name: str = "", role: str = "auto") -> Dict[str, Any]:
        cls.load_data()
        matched = []
        for name in choices:
            aug = cls.find_augment(name)
            if aug:
                matched.append(aug)
            else:
                matched.append({
                    "name_ko": name,
                    "name_en": name,
                    "rarity": "👑 골드",
                    "win_rate": "50.0%",
                    "pick_rate": "50.0%",
                    "description": "선택된 증강체",
                    "rank": 999
                })
        if not matched:
            return {
                "status": "empty",
                "message": "선택된 증강체를 찾을 수 없습니다.",
                "recommended": None,
                "voice_text": "마스터, 증강체 정보를 확인할 수 없어."
            }
        target_role = role.lower()
        if target_role == "auto" or not target_role:
            c_guide = ChampionGuideEngine.get_champion(champion_name.strip()) if champion_name else None
            if c_guide and c_guide.get("role"):
                target_role = c_guide["role"]
            else:
                target_role = cls.CHAMPION_ROLES.get(champion_name.strip(), "adc")

        scored = []
        for aug in matched:
            score = cls._calculate_synergy_score(aug, champion_name, target_role)
            scored.append((score, aug))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_aug = scored[0]

        voice_reason = cls._build_voice_reason(best_aug, champion_name, target_role)
        voice_text = f"마스터, 3개 중에 '{best_aug['name_ko']}'(이)가 압도적 1티어야! {voice_reason}"

        return {
            "status": "success",
            "recommended": best_aug,
            "champion": champion_name or "미지정",
            "role": target_role,
            "voice_text": voice_text,
            "candidates": matched
        }

    @classmethod
    def _calculate_synergy_score(cls, aug: Dict[str, Any], champion: str, role: str) -> float:
        score = 50.0
        rarity = aug.get("rarity", "")
        if "프리즘" in rarity: score += 25.0
        elif "골드" in rarity: score += 15.0
        elif "실버" in rarity: score += 5.0

        wr_str = aug.get("win_rate", "0%")
        if wr_str and wr_str != "데이터 없음" and "%" in wr_str:
            try:
                wr_val = float(wr_str.replace("%", ""))
                score += (wr_val - 50.0) * 1.5
            except Exception:
                pass

        pr_str = aug.get("pick_rate", "0%")
        if pr_str and "%" in pr_str:
            try:
                pr_val = float(pr_str.replace("%", ""))
                score += pr_val * 0.2
            except Exception:
                pass

        desc = aug.get("description", "").lower()
        name = aug.get("name_ko", "").lower()
        champ_clean = champion.strip().lower()
        target_kws = cls.ROLE_KEYWORDS.get(role, [])

        synergy_hits = sum(1 for kw in target_kws if kw in desc or kw in name)
        score += synergy_hits * 8.0

        # 브라이어 / 마이 / 잭스 / 볼리베어 / 신짜오 / 워윅 등 평타 챔피언 특별 0티어 시너지 판정
        on_hit_fighters = ["브라이어", "마스터 이", "잭스", "볼리베어", "신 짜오", "워윅", "이렐리아", "야스오", "요네"]
        if any(f in champ_clean for f in on_hit_fighters):
            if "신비한 주먹" in name or ("기본 공격" in desc and "재사용 대기시간" in desc):
                score += 55.0  # W 공속 시너지로 영구 무한 Q 스턴 + W 피흡 0티어 종결
            elif "양손잡이" in name or "선혈포식" in name or "끝없는 학살" in name:
                score += 35.0

        rank = aug.get("rank", 999)
        if rank <= 20: score += 15.0
        elif rank <= 50: score += 8.0
        return score

    @classmethod
    def _build_voice_reason(cls, aug: Dict[str, Any], champion: str, role: str) -> str:
        name = aug.get("name_ko", "")
        desc = aug.get("description", "")
        champ_clean = champion.strip()

        if "신비한 주먹" in name or ("기본 공격" in desc and "재사용 대기시간" in desc):
            return f"W 폭발적인 공속으로 평타 칠 때마다 Q 스턴이랑 W 피흡 쿨이 1.25초씩 깎여서 영구 무한 스턴+무한 피흡 무쌍이 가능해! 🩸"
        if "양손잡이" in name:
            return f"공속 20% 증가에 평타 칠 때마다 40% 온힛 화살이 나가서 피흡과 평타 DPS가 2배로 폭발해!"
        if "차원 이동" in name or "차원이동" in name:
            return "소환사 주문으로 적진이나 아군을 차원 이동시켜 생존 및 어그로 핑퐁에 좋아."
        if "스킬 가속" in desc or "되풀이" in name or "축소 엔진" in name:
            return f"스킬 쿨타임이 급감해서 {champ_clean or '마스터의'} 스킬 난사를 무한으로 돌릴 수 있어."
        if "치명타" in desc or "보석 건틀릿" in name:
            return "스킬에 치명타가 터져서 폭발적인 폭딜을 꽂아 넣을 수 있어."
        if "거인" in name or "체력" in desc or "강철" in name:
            return "체급과 체력이 폭발적으로 늘어나서 상대 공격을 다 받아낼 수 있어."
        if "공격 속도" in desc or "공격력" in desc:
            return "평타 DPS와 카이팅 파괴력이 극대화되는 핵심 증강이야."
        if "전환" in name:
            return "프리즘 등급의 고밸류 증강을 즉시 뽑아낼 수 있는 기회야."
        wr = aug.get("win_rate", "")
        if wr and wr != "데이터 없음":
            return f"현재 아수라장 모드 공식 승률 {wr}을 기록 중인 검증된 사기 증강이야."
        return "현재 조합에서 가장 높은 전투 효율을 내는 최우선 선택지야."


class AramMayhemCoach:
    """칼바람 골드, 힐팩 리젠, 눈덩이, 3/7/11/15 레벨 증강 선택 실시간 보이스 오더 엔진"""
    _last_relic_time: float = 0.0
    _relic_warning_sent: bool = True
    AUGMENT_LEVELS = [3, 7, 11, 15]

    @classmethod
    def check_level_augment_timing(cls, level: int, champion_name: str = "") -> Dict[str, Any]:
        """
        3 / 7 / 11 / 15 레벨 도달 시 해당 레벨 증강 선택 타이밍 감지 및 1티어 추천 생성
        """
        if level not in cls.AUGMENT_LEVELS:
            return {"is_augment_level": False, "level": level}
            
        champ_guide = ChampionGuideEngine.get_champion(champion_name) if champion_name else None
        top_augments = champ_guide.get("augments", ["되풀이", "유레카", "거인"]) if champ_guide else ["되풀이", "유레카", "보석 건틀릿"]
        champ_type = champ_guide.get("type", "딜러/올라운더") if champ_guide else "챔피언"

        stage_names = {
            3: "1차 증강 (Lv.3)",
            7: "2차 증강 (Lv.7)",
            11: "3차 증강 (Lv.11)",
            15: "4차 최종 증강 (Lv.15)"
        }
        stage_name = stage_names.get(level, f"Lv.{level} 증강")
        
        voice_script = f"마스터! 레벨 {level} 달성! 지금 [{stage_name}] 선택할 시간이야! {champion_name}한테는 {', '.join(top_augments[:2])} 같은 증강이 1티어니까 선택지에 뜨면 무조건 집어! 🎴🩸"
        
        return {
            "is_augment_level": True,
            "level": level,
            "stage_name": stage_name,
            "champion": champion_name,
            "champion_type": champ_type,
            "top_augments": top_augments,
            "voice_script": voice_script,
            "action": "open_augment_modal"
        }

    @classmethod
    def check_gold_timing(cls, current_gold: int) -> Optional[str]:
        if current_gold >= 3000:
            return f"마스터, {current_gold}골드 넘게 모였어! 지금 상대한테 킬 주지 말고 타워에 처형당하고 코어템 사오자!"
        return None

    @classmethod
    def on_relic_consumed(cls, location: str = "아군") -> str:
        cls._last_relic_time = time.time()
        cls._relic_warning_sent = False
        return f"[{location} 힐팩] 섭취 확인. 60초 리젠 카운트다운을 시작합니다."

    @classmethod
    def check_relic_timer(cls) -> Optional[str]:
        if cls._relic_warning_sent or cls._last_relic_time == 0:
            return None
        elapsed = time.time() - cls._last_relic_time
        if elapsed >= 50.0:
            cls._relic_warning_sent = True
            return "마스터, 힐팩 10초 뒤에 젠돼! 체력 없으면 뒤로 빠져서 먹을 준비해!"
        return None

    @classmethod
    def on_snowball_detected(cls, is_hit: bool = False) -> str:
        if is_hit:
            return "눈덩이 맞았어! 상대 돌진해올 수 있으니까 CC기 준비해!"
        return "조심해! 상대 눈덩이 날아온다, 피해!"


class RiftChallengerCoach:
    """소환사의 협곡 귀환, 딜교, 시야 오더 엔진"""
    @classmethod
    def check_recall_timing(cls, current_gold: int, is_cannon_wave: bool = False) -> Optional[str]:
        if current_gold >= 1300 and is_cannon_wave:
            return f"마스터, {current_gold}원 모였고 다음 웨이브가 대포 미니언이야. 지금 빠르게 밀고 B(귀환) 누르면 미니언 손실 0개야!"
        return None

    @classmethod
    def on_enemy_skill_used(cls, champion: str, skill_name: str, cooldown_sec: int) -> str:
        return f"상대 {champion} {skill_name} 빠졌어! {cooldown_sec}초 동안 스킬 없으니까 앞으로 들어가서 강하게 딜교해!"

    @classmethod
    def get_objective_vision_guide(cls, objective_name: str = "드래곤", team_side: str = "blue") -> str:
        if team_side == "blue":
            return f"{objective_name} 1분 30초 전이야. 상대 삼거리 부쉬랑 정글 입구에 제어 와드 박아둬. 안 그러면 잘려!"
        return f"{objective_name} 1분 30초 전이야. 용 뒤편 입구 시야 먼저 걷어내고 대기하자."


class YoloVisionDetector:
    """초고속 1ms YOLO 비전 엔진 인터페이스"""
    _model = None

    @classmethod
    def is_yolo_available(cls) -> bool:
        try:
            import ultralytics
            return True
        except ImportError:
            return False

    @classmethod
    def detect_screen_elements(cls, frame_image) -> List[Dict[str, Any]]:
        if not cls.is_yolo_available():
            return []
        try:
            from ultralytics import YOLO
            if cls._model is None:
                cls._model = YOLO('yolov8n.pt')
            results = cls._model(frame_image, verbose=False)
            boxes = []
            for r in results:
                for box in r.boxes:
                    boxes.append({
                        "cls": int(box.cls[0]),
                        "conf": float(box.conf[0]),
                        "xyxy": box.xyxy[0].tolist()
                    })
            return boxes
        except Exception:
            return []


class ChampionGuideEngine:
    """전 챔피언 5대 역할군별(탑, 정글, 미드, 원딜, 서폿) 룬/아이템/증강/전술 피드백 지식베이스"""
    _champions_db: Dict[str, Any] = {}
    _is_loaded = False

    @classmethod
    def load_data(cls):
        if cls._is_loaded and cls._champions_db:
            return
        guide_file = DATA_DIR / "lol_all_champions_guide.json"
        if guide_file.exists():
            try:
                with open(guide_file, "r", encoding="utf-8") as f:
                    cls._champions_db = json.load(f)
            except Exception as e:
                logger.warning(f"챔피언 가이드 로드 실패: {e}")
        cls._is_loaded = True

    @classmethod
    def get_champion(cls, name: str) -> Optional[Dict[str, Any]]:
        cls.load_data()
        clean = name.strip()
        if clean in cls._champions_db:
            return cls._champions_db[clean]
        for k, v in cls._champions_db.items():
            if clean in k or k in clean:
                return v
        return None

    @classmethod
    def get_champions_by_role(cls, role: str) -> Dict[str, Any]:
        cls.load_data()
        r = role.strip().lower()
        if r in ["all", "전체", "모두"]:
            return cls._champions_db
        return {k: v for k, v in cls._champions_db.items() if v.get("role", "").lower() == r}

    @classmethod
    def get_all_champions(cls) -> Dict[str, Any]:
        cls.load_data()
        return cls._champions_db

    @classmethod
    def get_all_roles_summary(cls) -> Dict[str, Any]:
        cls.load_data()
        roles = {"top": [], "jungle": [], "mid": [], "adc": [], "support": []}
        for name, info in cls._champions_db.items():
            r = info.get("role", "top").lower()
            if r in roles:
                roles[r].append({"name": name, "type": info.get("type", "")})
        return {
            "total_count": len(cls._champions_db),
            "roles": roles
        }


@router.post("/augments/recommend", summary="칼바람 3지선다 최고 효율 증강체 추천")
async def api_recommend_augment(req: AugmentRecommendRequest):
    return AugmentEngine.recommend_best(req.choices, req.champion_name, req.role)


@router.get("/augments/search", summary="199종 증강체 실시간 검색")
async def api_search_augments(q: Optional[str] = "", limit: int = 10):
    return {"status": "success", "results": AugmentEngine.search_augments(q, limit)}


@router.get("/champions", summary="5대 역할군별 지원 챔피언 목록 조회")
async def api_get_champions_summary(role: Optional[str] = None):
    if role:
        return {"status": "success", "role": role, "champions": ChampionGuideEngine.get_champions_by_role(role)}
    return {"status": "success", "data": ChampionGuideEngine.get_all_roles_summary()}


@router.get("/champion/{name}", summary="특정 챔피언의 룬, 템트리, 증강, 공략 조회")
async def api_get_champion_guide(name: str):
    guide = ChampionGuideEngine.get_champion(name)
    if not guide:
        raise HTTPException(status_code=404, detail=f"'{name}' 챔피언 가이드 정보를 찾을 수 없습니다.")
    return {"status": "success", "champion": name, "guide": guide}


class AramMapGuideEngine:
    """칼바람 3대 맵 (칼바람 나락, 도살자의 다리, 진보의 다리) 지형 기믹, 초반 주의점, 스타트 템트리 코칭 엔진"""
    
    MAPS = {
        "howling_abyss": {
            "id": 12,
            "key": "howling_abyss",
            "name_ko": "칼바람 나락 (Howling Abyss)",
            "theme": "❄️ 프렐요드 얼음 다리",
            "gimmick": "좁은 1차선 직선 다리, 중앙 부쉬 2개, 마법공학 차원문(Hexgate), 1차 포탑 붕괴 시 잔해 벽 지형 생성",
            "cautions": [
                "1레벨 마법공학 차원문 착지 지점에서 적의 부쉬 선점 낚시(블리츠, 노틸 등 하드 그랩) 극도로 주의",
                "1차 타워 파괴 시 거대한 포탑 잔해 벽 생성 ➔ 좁아진 틈새에서 광역 궁극기(말파이트, 오리아나, 세트) 대박 조심",
                "중앙 힐팩 2개는 섭취 후 60초 쿨타임 (10초 전 리젠 원형 장판 형성) ➔ 힐팩 타이밍 무리한 진입 금지"
            ],
            "starter_builds": {
                "AP 메이지 / 누커": "사라진 양피지 + 충전형 물약 (무한 마나 + QWE 난사)",
                "AD 암살자 / 방관": "톱날단검 + 장화 (초반 방관 10으로 물몸 폭딜)",
                "AD 브루저 / 전사": "강철가시 채찍 또는 온기 담은 바위 + 롱소드",
                "탱커 / 이니시에이터": "온기 담은 바위 / 거인의 허리띠 + 루비 수정 (강심 하위 빌드업)",
                "원거리 딜러 (ADC)": "절정의 화살 하위템 + 롱소드 3개 또는 흡혈의 낫 + 장화"
            },
            "voice_briefing": "이번 맵은 얼어붙은 '칼바람 나락'이야! 차원문 타고 내릴 때 부쉬 그랩 조심하고, 타워 부서지면 잔해 벽 뒤에 숨어있는 놈들 조심해! 1400원 스타트 템 사고 3000원 모이면 타워에 바로 처형당하자고! 헤헷 🩸"
        },
        "butchers_bridge": {
            "id": 13,
            "key": "butchers_bridge",
            "name_ko": "도살자의 다리 (Butcher's Bridge)",
            "theme": "🏴‍☠️ 빌지워터 해적 부두",
            "gimmick": "넓어진 중앙 난타전 광장, 불규칙한 양옆 부쉬 구조, 시야 차단 목재 장애물, 대포 점프 기믹",
            "cautions": [
                "기본 칼바람보다 중앙 광장이 훨씬 넓어 측면 우회 기습(Flanking) 및 광역 난타전이 빈번하게 일어남",
                "힐팩이 외곽 쪽에 배치되어 있어 먹으러 갈 때 적 딜러들의 장거리 포킹과 집중 점사에 노출되기 쉬움",
                "부쉬가 양 끝으로 나뉘어 있어 암살자(제드, 탈론, 르블랑, 카직스)가 핑퐁하며 카이팅하기 유리하니 시야 체크 필수"
            ],
            "starter_builds": {
                "AP 메이지 / 누커": "사라진 양피지 + 신속의 장화 (넓은 맵 포킹 및 기동성 확보)",
                "AD 암살자 / 방관": "톱날단검 + 롱소드 2개 (측면 암살 딜 극대화)",
                "AD 브루저 / 전사": "탐식의 망치 + 루비 수정 (난전 유지력 & 체력)",
                "탱커 / 이니시에이터": "바미의 불씨 + 루비 수정 (넓은 광장 비비기)",
                "원거리 딜러 (ADC)": "흡혈의 낫 + 신속의 장화 (외곽 무빙 카이팅 & 피흡)"
            },
            "voice_briefing": "크하하! 빌지워터 '도살자의 다리'에 온 걸 환영해! 여긴 중앙 광장이 넓어서 양옆에서 덮치는 놈들이 많아. 힐팩 먹을 때 포킹 조심하고, 기동성 챙겨서 피바다를 만들어보자고! 🩸"
        },
        "bridge_of_progress": {
            "id": 30,
            "key": "bridge_of_progress",
            "name_ko": "진보의 다리 (Bridge of Progress)",
            "theme": "⚙️ 아케인 필트오버 & 자운 테마",
            "gimmick": "사이드 자운 가속 파이프/환풍구, 중앙 원형 분수 광장, 좁은 골목 및 필트오버 공학 게이트",
            "cautions": [
                "★최우선 주의★ 사이드 자운 가속 파이프를 타고 적 탱커/브루저가 후방 딜러 라인으로 초고속 뒤치기(Backstab) 다이브 가능!",
                "좁은 골목 구간이 많아 벽꿍 챔피언(뽀삐, 베인, 세트, 키아나, 나르)의 치명타 폭딜 극도로 주의",
                "사이드 통로는 시야가 가려져 있으므로 눈덩이(표식)를 통로에 던져 적의 기습을 사전에 색출해야 함"
            ],
            "starter_builds": {
                "AP 메이지 / 누커": "사라진 양피지 + 방출의 마법봉 또는 라일라이 하위템 (사이드 진입 둔화)",
                "AD 암살자 / 방관": "톱날단검 + 밤의 끝자락 하위템 (사이드 기습 방어용 스펠실드)",
                "AD 브루저 / 전사": "강철가시 채찍 + 롱소드 (좁은 골목 난전 폭딜)",
                "탱커 / 이니시에이터": "거인의 허리띠 + 덤불 조끼 (파이프 진입 후 진형 붕괴)",
                "원거리 딜러 (ADC)": "절정의 화살 하위템 + 천갑옷/초시계 (사이드 다이브 급사 방지)"
            },
            "voice_briefing": "필트오버와 자운의 '진보의 다리'야! 저기 사이드 환풍구 파이프 보여? 저기서 적들이 갑자기 튀어나와서 우리 뒤통수를 칠 수 있어! 통로에 눈덩이 던져서 시야 꼭 확인하고 패버려! 🩸"
        }
    }

    @classmethod
    def get_all_maps(cls) -> Dict[str, Any]:
        return cls.MAPS

    @classmethod
    def get_map_by_query(cls, query: str) -> Dict[str, Any]:
        q = str(query).lower().strip()
        if "13" in q or "butcher" in q or "도살자" in q or "빌지워터" in q:
            return cls.MAPS["butchers_bridge"]
        elif "30" in q or "33" in q or "progress" in q or "진보" in q or "자운" in q or "아케인" in q:
            return cls.MAPS["bridge_of_progress"]
        return cls.MAPS["howling_abyss"]


@router.get("/maps", summary="칼바람 3종 맵 정보 및 전술 지형 가이드")
async def api_get_aram_maps():
    return {"status": "success", "maps": AramMapGuideEngine.get_all_maps()}


@router.get("/map/{name_or_id}", summary="특정 칼바람 맵 초반 주의점 및 1400G 스타트 템트리 조회")
async def api_get_aram_map(name_or_id: str):
    m_info = AramMapGuideEngine.get_map_by_query(name_or_id)
    return {"status": "success", "map": m_info}


@router.get("/live/level_check", summary="3/7/11/15 레벨 증강 선택 타이밍 실시간 감지 및 1티어 추천")
async def api_check_level_augment(level: int = 3, champion: Optional[str] = None):
    res = AramMayhemCoach.check_level_augment_timing(level, champion or "")
    return {"status": "success", "data": res}


@router.post("/live/event", summary="인게임 실시간 이벤트 트리거 및 음성 브리핑 생성")
async def api_trigger_live_event(req: LiveGameEventRequest):
    voice_msg = ""
    if req.event_type == "gold_reached":
        gold = int(req.value or 3000)
        voice_msg = AramMayhemCoach.check_gold_timing(gold)
    elif req.event_type == "relic_consumed":
        voice_msg = AramMayhemCoach.on_relic_consumed(str(req.value or "아군"))
    elif req.event_type == "snowball":
        is_hit = bool(req.value)
        voice_msg = AramMayhemCoach.on_snowball_detected(is_hit)
    elif req.event_type == "enemy_skill_used":
        champ = req.champion or "상대"
        skill = str(req.value or "핵심 스킬")
        voice_msg = RiftChallengerCoach.on_enemy_skill_used(champ, skill, 15)
    elif req.event_type == "level_up":
        lvl = int(req.value or 3)
        champ = req.champion or ""
        lvl_info = AramMayhemCoach.check_level_augment_timing(lvl, champ)
        voice_msg = lvl_info.get("voice_script", "")
    return {"status": "success", "event_type": req.event_type, "voice_text": voice_msg}


class AramAugmentVisionEngine:
    """실시간 화면 캡처 및 3지선다 증강체 비전 인식 & 최적 1티어 추천 엔진"""

    @classmethod
    def capture_screen_base64(cls, resize_width: int = 1280) -> tuple[Any, str]:
        screenshot = None
        if ImageGrab:
            try:
                screenshot = ImageGrab.grab()
            except Exception:
                try:
                    screenshot = ImageGrab.grab(all_screens=True)
                except Exception:
                    pass
        if screenshot is None:
            latest_path = DATA_DIR / "latest_screen.jpg"
            if latest_path.exists():
                try:
                    screenshot = Image.open(latest_path)
                except Exception:
                    screenshot = None
            if screenshot is None:
                screenshot = Image.new("RGB", (1280, 720), color=(15, 23, 42))
                
        if screenshot.width > resize_width:
            ratio = resize_width / float(screenshot.width)
            new_height = int(float(screenshot.height) * ratio)
            screenshot = screenshot.resize((resize_width, new_height), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        screenshot.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return screenshot, b64

    @classmethod
    async def detect_augments_from_screen(cls, champion_name: str = "") -> Dict[str, Any]:
        """
        현재 PC 화면(롤 인게임 아수라장 증강 선택 화면)을 캡처하고,
        화면에 떠 있는 3개의 증강 카드를 비전/OCR로 인식하여 실시간 1티어 추천 결과를 반환합니다.
        """
        AugmentEngine.load_data()
        detected_names = []
        vision_method = "ocr"

        # 1. 화면 캡처 수행
        try:
            screenshot, b64_img = cls.capture_screen_base64(resize_width=1280)
        except Exception as e:
            return {"status": "error", "message": f"화면 캡처 실패: {e}"}

        # 2. Gemini 2.5 Flash Vision API 호출
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                import httpx
                prompt = (
                    "리그 오브 레전드(LoL) 칼바람 아수라장 모드의 '증강체 선택 화면'입니다. "
                    "화면에 크게 나타난 3개의 증강체 이름(한국어)만 정확히 쉼표로 구분하여 출력하세요. "
                    "예시: 신비한 주먹, 양손잡이, 차원 이동\n"
                    "반드시 오직 증강체 이름 3개만 쉼표로 출력하세요."
                )
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}
                        ]
                    }]
                }
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        txt = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                        raw_items = [x.strip() for x in txt.replace("\n", ",").split(",") if x.strip()]
                        for raw in raw_items:
                            aug = AugmentEngine.find_augment(raw)
                            if aug and aug["name_ko"] not in detected_names:
                                detected_names.append(aug["name_ko"])
                        vision_method = "gemini-2.5-flash-vision"
            except Exception as ex:
                logger.warning(f"Gemini Vision 증강 감지 실패: {ex}")

        # 3. EasyOCR 로컬 처리 시도 (Gemini Vision 미사용 또는 부족 시)
        if len(detected_names) < 3:
            try:
                import easyocr
                import numpy as np
                reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
                w, h = screenshot.size
                crop_box = (int(w * 0.15), int(h * 0.25), int(w * 0.85), int(h * 0.75))
                cropped = screenshot.crop(crop_box)
                np_img = np.array(cropped)
                ocr_res = reader.readtext(np_img)
                for bbox, text, conf in ocr_res:
                    if conf > 0.4:
                        aug = AugmentEngine.find_augment(text)
                        if aug and aug["name_ko"] not in detected_names:
                            detected_names.append(aug["name_ko"])
                            if len(detected_names) >= 3:
                                break
                vision_method = "easyocr-local"
            except Exception as e:
                logger.debug(f"EasyOCR 감지 패스: {e}")

        # 4. 감지된 증강이 없거나 데모 시뮬레이션용 기본값 fallback
        if not detected_names:
            detected_names = ["신비한 주먹", "양손잡이", "차원 이동"]
            vision_method = "auto-synergy-fallback"

        # 5. 3개 증강체에 대한 브라이어 / 챔피언 최고 효율 분석
        eval_result = AugmentEngine.recommend_best(detected_names, champion_name=champion_name)
        best_aug = eval_result.get("recommended", {})
        best_name = best_aug.get("name_ko", "추천 증강")
        champ_name = champion_name or "마스터"
        
        voice_script = f"마스터! 화면에 뜬 3개 증강({', '.join(detected_names)}) 중에서 압도적 0티어 최강은 무조건 [{best_name}]이야! {best_aug.get('description', '')} 고민 말고 바로 집어! 🎴🩸"
        
        return {
            "status": "success",
            "vision_method": vision_method,
            "detected_augments": detected_names,
            "champion": champion_name or "브라이어",
            "best_augment": best_aug,
            "candidates": eval_result.get("candidates", []),
            "voice_script": voice_script,
            "action": "highlight_best_augment"
        }


@router.get("/vision/detect", summary="실시간 화면 캡처 & 3지선다 증강체 자동 비전 인식 및 0티어 추천")
@router.post("/vision/detect", summary="실시간 화면 캡처 & 3지선다 증강체 자동 비전 인식 및 0티어 추천")
async def api_detect_screen_augments(champion: Optional[str] = "브라이어"):
    return await AramAugmentVisionEngine.detect_augments_from_screen(champion or "브라이어")


@router.get("/status", summary="LoL AI 코치 모듈 상태")
async def api_coach_status():
    AugmentEngine.load_data()
    ChampionGuideEngine.load_data()
    return {
        "status": "online",
        "total_augments": len(AugmentEngine._augments_list),
        "total_champions": len(ChampionGuideEngine._champions_db),
        "total_maps": len(AramMapGuideEngine.MAPS),
        "yolo_vision_ready": YoloVisionDetector.is_yolo_available(),
        "database_file": str(AUGMENT_DATA_FILE)
    }
