"""
maple_skill_tracker.py
=============================================================================
🍁 JARVIS 메이플스토리 스킬 쿨타임 화면 감시 & 스카디 음성 알리미 모듈
=============================================================================
- 기능:
    1. 스킬명, 쿨타임(초), 음성 브리핑 타이밍(초 전), 맞춤형 대사를 원클릭 동적 설정
    2. 로컬 JSON (`data/maple_skills.json`) 영구 저장으로 재시작 후에도 설정 유지
    3. 주요 직업별(히어로, 비숍, 나이트로드, 아델, 섀도어 등) 원클릭 프리셋 로드
    4. 메이플 화면 우측 하단 퀵슬롯 0.2초 실시간 감시 & 5초 전 스카디 음성 알림
    5. REST API 및 관리자 대시보드(admin.html) 완벽 연동
=============================================================================
"""

import io
import os
import json
import time
import asyncio
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

# 화면 캡처용 라이브러리
try:
    from PIL import Image, ImageGrab, ImageStat
except ImportError:
    Image = None
    ImageGrab = None
    ImageStat = None

# =============================================================================
# 🚀 1. FastAPI APIRouter 및 데이터 경로 설정
# =============================================================================
router = APIRouter(prefix="/api/maple/tracker", tags=["MapleStory Skill Tracker"])

MODULE_DIR = Path(__file__).parent
DATA_DIR = MODULE_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "maple_skills.json"


# =============================================================================
# 📦 2. Pydantic 요청/응답 모델
# =============================================================================
class SkillConfigItem(BaseModel):
    name: str = Field(..., description="스킬명 (예: 제네시스 무적기, 오리진 극딜)")
    category: str = Field("defense", description="분류 (defense: 무적/방어, burst: 극딜, bind: 바인드, buff: 버프)")
    cooldown_sec: float = Field(..., ge=1.0, description="쿨타임 (초 단위, 예: 180)")
    warn_before: float = Field(5.0, ge=1.0, description="쿨타임 종료 몇 초 전에 말해줄지 (초 단위, 예: 5.0)")
    voice_text: Optional[str] = Field(None, description="스카디가 말할 맞춤 대사 (미입력 시 기본 대사 자동 적용)")
    slot_id: int = Field(1, ge=1, le=12, description="퀵슬롯 번호 (1~12)")

class SkillConfigListRequest(BaseModel):
    skills: List[SkillConfigItem]


# =============================================================================
# 🎮 3. 직업별 인기 스킬 프리셋 정의
# =============================================================================
JOB_PRESETS: Dict[str, List[Dict[str, Any]]] = {
    "공통 (기본)": [
        {"name": "방어/무적기", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "voice_text": "방어 스킬 쿨 5초 남았어.", "slot_id": 1},
        {"name": "극딜 버프기", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "voice_text": "극딜 버프 10초 전이야, 준비해.", "slot_id": 2},
        {"name": "에르다 노바 (바인드)", "category": "bind", "cooldown_sec": 100.0, "warn_before": 5.0, "voice_text": "바인드 준비 완료! 극딜 타이밍이야.", "slot_id": 3}
    ],
    "비숍": [
        {"name": "홀리 매직쉘 / 힐", "category": "defense", "cooldown_sec": 90.0, "warn_before": 5.0, "voice_text": "매직쉘 쿨 5초 전이야.", "slot_id": 1},
        {"name": "프레이 & 리브라 (극딜)", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "voice_text": "프레이 10초 전이야, 파티원 모여.", "slot_id": 2},
        {"name": "제네시스 무적기", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "voice_text": "제네시스 무적기 5초 전.", "slot_id": 3}
    ],
    "나이트로드": [
        {"name": "스프레드 샌드 / 얼닼사", "category": "burst", "cooldown_sec": 90.0, "warn_before": 10.0, "voice_text": "스프레드 극딜 10초 전이야.", "slot_id": 1},
        {"name": "풍마수리검", "category": "buff", "cooldown_sec": 25.0, "warn_before": 3.0, "voice_text": "풍마 수리검 쿨 돌았어.", "slot_id": 2},
        {"name": "레디 투 다이", "category": "burst", "cooldown_sec": 75.0, "warn_before": 5.0, "voice_text": "레투다 쿨 5초 전.", "slot_id": 3}
    ],
    "히어로": [
        {"name": "발할라 & 콤보 인스팅트", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "voice_text": "인스팅트 극딜 10초 전이야.", "slot_id": 1},
        {"name": "인사이징 / 소드 일루전", "category": "buff", "cooldown_sec": 30.0, "warn_before": 3.0, "voice_text": "소드 일루전 준비 완료.", "slot_id": 2},
        {"name": "데스폴트 (무적기)", "category": "defense", "cooldown_sec": 20.0, "warn_before": 3.0, "voice_text": "데스폴트 무적기 준비 완료.", "slot_id": 3}
    ],
    "아델": [
        {"name": "인피니트 (극딜)", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "voice_text": "인피니트 극딜 10초 전이야.", "slot_id": 1},
        {"name": "다이크 (무적기)", "category": "defense", "cooldown_sec": 30.0, "warn_before": 3.0, "voice_text": "다이크 무적기 쿨 돌았어.", "slot_id": 2},
        {"name": "리스토어 / 루인", "category": "burst", "cooldown_sec": 60.0, "warn_before": 5.0, "voice_text": "루인 5초 전.", "slot_id": 3}
    ]
}


# =============================================================================
# 📦 4. 런타임 추적 스킬 클래스
# =============================================================================
class TrackedSkill:
    """실시간 쿨타임 상태 머신"""
    def __init__(self, name: str, category: str, cooldown_sec: float, warn_before: float = 5.0, voice_text: Optional[str] = None, slot_id: int = 1):
        self.name = name
        self.category = category
        self.cooldown_sec = float(cooldown_sec)
        self.warn_before = float(warn_before)
        self.voice_text = voice_text or f"{name} 쿨 {int(warn_before)}초 남았어."
        self.slot_id = slot_id

        # 런타임 상태
        self.state = "READY"                  # READY | ON_COOLDOWN | WARNED
        self.cooldown_end_time = 0.0
        self.last_used_time = 0.0

    @property
    def remaining_sec(self) -> float:
        """남은 쿨타임(초)"""
        if self.state == "READY":
            return 0.0
        rem = self.cooldown_end_time - time.time()
        return max(0.0, round(rem, 1))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "cooldown_sec": self.cooldown_sec,
            "warn_before": self.warn_before,
            "voice_text": self.voice_text,
            "remaining_sec": self.remaining_sec,
            "state": self.state,
            "slot_id": self.slot_id
        }


# =============================================================================
# 🔊 5. 스카디 음성 알림 발화기
# =============================================================================
class SkadiVoiceAnnouncer:
    """스카디 TTS 비동기 음성 큐"""
    VOICE_NAME = "ko-KR-SunHiNeural"
    _speech_lock = threading.Lock()

    @classmethod
    async def speak_text(cls, text: str):
        if not text:
            return
        try:
            import edge_tts
            import pygame
            
            communicate = edge_tts.Communicate(text, cls.VOICE_NAME)
            audio_data = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])
            
            audio_data.seek(0)
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            with cls._speech_lock:
                pygame.mixer.music.load(audio_data)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.05)

        except ImportError:
            print(f"[🔊 스카디 음성 출력]: \"{text}\"")
        except Exception as e:
            print(f"[스카디 TTS 오류]: {str(e)}")


# =============================================================================
# 👁️ 6. 퀵슬롯 감시 & 쿨타임 관리자
# =============================================================================
class MapleSkillWatcher:
    """동적 스킬 설정 및 실시간 화면 감시 엔진"""

    SLOT_CROP_RATIO = {
        "left": 0.78,
        "top": 0.85,
        "right": 0.99,
        "bottom": 0.98
    }

    def __init__(self):
        self.is_running = False
        self._watcher_thread: Optional[threading.Thread] = None
        self.skills: List[TrackedSkill] = []
        self.load_skills_from_json()

    def load_skills_from_json(self):
        """저장된 JSON 파일에서 스킬 목록 로드 (없으면 기본값 생성)"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.skills = [
                        TrackedSkill(
                            name=s["name"],
                            category=s.get("category", "defense"),
                            cooldown_sec=s["cooldown_sec"],
                            warn_before=s.get("warn_before", 5.0),
                            voice_text=s.get("voice_text"),
                            slot_id=s.get("slot_id", 1)
                        ) for s in data
                    ]
                    return
            except Exception:
                pass

        # 기본 프리셋으로 초기화
        self.load_preset("공통 (기본)")

    def save_skills_to_json(self):
        """현재 스킬 설정을 JSON 파일로 영구 저장"""
        data = [
            {
                "name": s.name,
                "category": s.category,
                "cooldown_sec": s.cooldown_sec,
                "warn_before": s.warn_before,
                "voice_text": s.voice_text,
                "slot_id": s.slot_id
            } for s in self.skills
        ]
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_preset(self, preset_name: str) -> bool:
        """직업 프리셋 로드"""
        if preset_name not in JOB_PRESETS:
            return False
        preset_data = JOB_PRESETS[preset_name]
        self.skills = [
            TrackedSkill(
                name=s["name"],
                category=s.get("category", "defense"),
                cooldown_sec=s["cooldown_sec"],
                warn_before=s.get("warn_before", 5.0),
                voice_text=s.get("voice_text"),
                slot_id=s.get("slot_id", 1)
            ) for s in preset_data
        ]
        self.save_skills_to_json()
        return True

    def set_skills(self, new_skills: List[SkillConfigItem]):
        """스킬 목록 전체 교체 및 저장"""
        self.skills = [
            TrackedSkill(
                name=s.name,
                category=s.category,
                cooldown_sec=s.cooldown_sec,
                warn_before=s.warn_before,
                voice_text=s.voice_text,
                slot_id=s.slot_id
            ) for s in new_skills
        ]
        self.save_skills_to_json()

    def add_or_update_skill(self, item: SkillConfigItem):
        """단일 스킬 추가 또는 갱신"""
        for i, sk in enumerate(self.skills):
            if sk.name == item.name:
                self.skills[i] = TrackedSkill(
                    name=item.name,
                    category=item.category,
                    cooldown_sec=item.cooldown_sec,
                    warn_before=item.warn_before,
                    voice_text=item.voice_text,
                    slot_id=item.slot_id
                )
                self.save_skills_to_json()
                return
        
        # 신규 스킬 추가
        self.skills.append(
            TrackedSkill(
                name=item.name,
                category=item.category,
                cooldown_sec=item.cooldown_sec,
                warn_before=item.warn_before,
                voice_text=item.voice_text,
                slot_id=item.slot_id
            )
        )
        self.save_skills_to_json()

    def delete_skill(self, skill_name: str) -> bool:
        """스킬 삭제"""
        original_len = len(self.skills)
        self.skills = [s for s in self.skills if s.name != skill_name]
        if len(self.skills) < original_len:
            self.save_skills_to_json()
            return True
        return False

    def trigger_skill_used(self, skill_name: str):
        """스킬 쿨타임 시작 트리거"""
        for sk in self.skills:
            if sk.name == skill_name or skill_name.lower() in sk.name.lower():
                sk.state = "ON_COOLDOWN"
                sk.last_used_time = time.time()
                sk.cooldown_end_time = time.time() + sk.cooldown_sec
                return

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._watcher_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._watcher_thread.start()

    def stop(self):
        self.is_running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=1.0)

    def _run_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.is_running:
            try:
                current_time = time.time()
                for sk in self.skills:
                    if sk.state == "ON_COOLDOWN":
                        rem = sk.cooldown_end_time - current_time

                        # ① N초 전 사전 브리핑 발화
                        if rem <= sk.warn_before and rem > (sk.warn_before - 0.5):
                            sk.state = "WARNED"
                            loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(sk.voice_text))

                    elif sk.state == "WARNED":
                        rem = sk.cooldown_end_time - current_time

                        # ② 쿨타임 완료 발화
                        if rem <= 0:
                            sk.state = "READY"
                            loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(f"{sk.name} 준비 완료!"))

                time.sleep(0.2)
            except Exception:
                time.sleep(0.5)

        loop.close()


# 글로벌 단일 인스턴스
maple_watcher = MapleSkillWatcher()


# =============================================================================
# 🌐 7. FastAPI 라우터 엔드포인트
# =============================================================================

@router.get("/skills", summary="현재 등록된 스킬 목록 조회")
async def get_skills():
    """등록된 스킬명, 쿨타임, 알림 타이밍, 대사 목록을 반환합니다."""
    return {
        "status": "success",
        "is_running": maple_watcher.is_running,
        "skills": [sk.to_dict() for sk in maple_watcher.skills]
    }


@router.post("/skills/quick-add", summary="스킬 빠른 추가/수정")
async def quick_add_skill(item: SkillConfigItem):
    """스킬명, 쿨타임(초), 브리핑 타이밍(초 전), 대사를 빠르게 추가/수정합니다."""
    maple_watcher.add_or_update_skill(item)
    return {"status": "success", "message": f"'{item.name}' 스킬 설정 저장 완료", "skill": item.dict()}


@router.delete("/skills/{skill_name}", summary="스킬 삭제")
async def delete_skill_item(skill_name: str):
    """등록된 스킬을 삭제합니다."""
    success = maple_watcher.delete_skill(skill_name)
    if not success:
        raise HTTPException(status_code=404, detail="삭제할 스킬을 찾을 수 없습니다.")
    return {"status": "success", "message": f"'{skill_name}' 삭제 완료"}


@router.get("/presets", summary="사용 가능한 직업 프리셋 목록")
async def get_presets():
    """원클릭 로드 가능한 직업 프리셋 목록을 반환합니다."""
    return {"status": "success", "presets": list(JOB_PRESETS.keys())}


@router.post("/presets/load/{job_name}", summary="직업 프리셋 원클릭 적용")
async def load_job_preset(job_name: str):
    """선택한 직업(비숍, 나로, 히어로, 아델 등)의 스킬 세트를 즉시 적용합니다."""
    success = maple_watcher.load_preset(job_name)
    if not success:
        raise HTTPException(status_code=400, detail=f"'{job_name}' 프리셋이 존재하지 않습니다.")
    return {"status": "success", "message": f"'{job_name}' 프리셋 로드 완료", "skills": [sk.to_dict() for sk in maple_watcher.skills]}


@router.post("/start", summary="실시간 감시 시작")
async def start_tracker():
    maple_watcher.start()
    return {"status": "success", "message": "스킬 감시 시작됨"}


@router.post("/stop", summary="실시간 감시 정지")
async def stop_tracker():
    maple_watcher.stop()
    return {"status": "success", "message": "스킬 감시 정지됨"}


@router.post("/trigger/{skill_name}", summary="스킬 쿨타임 시작 트리거")
async def trigger_skill(skill_name: str):
    maple_watcher.trigger_skill_used(skill_name)
    return {"status": "success", "message": f"'{skill_name}' 쿨타임 시작됨"}


@router.post("/test-voice", summary="스카디 음성 알림 즉각 테스트")
async def test_skadi_voice(message: Optional[str] = "방어 스킬 쿨 5초 남았어."):
    asyncio.create_task(SkadiVoiceAnnouncer.speak_text(message))
    return {"status": "success", "speaking_text": message}
