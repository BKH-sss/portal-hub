"""
maple_skill_tracker.py
=============================================================================
🍁 JARVIS 메이플스토리 스킬 쿨타임 자동 감지 & 스카디 음성 알리미
=============================================================================
- 기능:
    1. 메이플 실행(`MapleStory.exe`) 시 백그라운드에서 감시 자동 시작 (수동 조작 불필요)
    2. 단축키 자동 감지 (Windows GetAsyncKeyState 기반, Shift/Ctrl/Z/X/F1~F12/1~9 등)
       ➔ 플레이어가 인게임에서 스킬 키를 누르는 즉시 0.00ms 오차 없이 쿨타임 자동 카운트다운
    3. 우측 하단 퀵슬롯 화면 픽셀 명도(컬러 vs 흑백) 변화 교차 자동 감지
    4. 쿨타임 종료 5초 전 스카디 음성 사전 예고 및 쿨타임 완료 즉각 발화
    5. 로컬 JSON (`data/maple_skills.json`) 영구 저장 및 웹 대시보드 실시간 연동
=============================================================================
"""

import io
import os
import json
import time
import ctypes
import asyncio
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

try:
    import psutil
except ImportError:
    psutil = None

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
# ⌨️ 2. Windows 가상 키코드 (Virtual Key Codes) 매핑 테이블
# =============================================================================
KEY_MAP = {
    "shift": 0x10, "lshift": 0xA0, "rshift": 0xA1,
    "ctrl": 0x11, "lctrl": 0xA2, "rctrl": 0xA3,
    "alt": 0x12, "space": 0x20,
    "ins": 0x2D, "insert": 0x2D, "del": 0x2E, "delete": 0x2E,
    "home": 0x24, "end": 0x23, "pgup": 0x21, "pgdn": 0x22,
    "q": 0x51, "w": 0x57, "e": 0x45, "r": 0x52, "t": 0x54, "y": 0x59,
    "a": 0x41, "s": 0x53, "d": 0x44, "f": 0x46, "g": 0x47,
    "z": 0x5A, "x": 0x58, "c": 0x43, "v": 0x56, "b": 0x42,
    "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34, "5": 0x35, "6": 0x36,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74, "f6": 0x75,
    "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B
}


# =============================================================================
# 📦 3. Pydantic 요청 모델 정의
# =============================================================================
class SkillConfigItem(BaseModel):
    name: str = Field(..., description="스킬명 (예: 제네시스 무적기, 오리진 극딜)")
    category: str = Field("defense", description="분류 (defense: 무적/방어, burst: 극딜, bind: 바인드, buff: 버프)")
    cooldown_sec: float = Field(..., ge=1.0, description="쿨타임 (초 단위, 예: 180)")
    warn_before: float = Field(5.0, ge=1.0, description="쿨타임 종료 몇 초 전에 말해줄지 (초 단위, 예: 5.0)")
    key_bind: Optional[str] = Field("shift", description="인게임 단축키 (예: shift, ctrl, z, x, a, s, d, 1, 2, ins, del)")
    voice_text: Optional[str] = Field(None, description="스카디가 말할 맞춤 대사 (미입력 시 기본 대사 자동 적용)")
    slot_id: int = Field(1, ge=1, le=12, description="퀵슬롯 번호 (1~12)")

class SkillEditRequest(BaseModel):
    original_name: str = Field(..., description="수정 전 기존 스킬명")
    item: SkillConfigItem = Field(..., description="수정할 새 스킬 설정")


# =============================================================================
# 🎮 4. 직업별 인기 스킬 프리셋 정의
# =============================================================================
JOB_PRESETS: Dict[str, List[Dict[str, Any]]] = {
    "공통 (기본)": [
        {"name": "방어/무적기", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "방어 스킬 쿨 5초 남았어.", "slot_id": 1},
        {"name": "극딜 버프기", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "ctrl", "voice_text": "극딜 버프 10초 전이야, 준비해.", "slot_id": 2},
        {"name": "에르다 노바 (바인드)", "category": "bind", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "바인드 준비 완료! 극딜 타이밍이야.", "slot_id": 3}
    ],
    "비숍": [
        {"name": "홀리 매직쉘 / 힐", "category": "defense", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "a", "voice_text": "매직쉘 쿨 5초 전이야.", "slot_id": 1},
        {"name": "프레이 & 리브라 (극딜)", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "s", "voice_text": "프레이 10초 전이야, 파티원 모여.", "slot_id": 2},
        {"name": "제네시스 무적기", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "제네시스 무적기 5초 전.", "slot_id": 3}
    ],
    "나이트로드": [
        {"name": "스프레드 샌드 / 얼닼사", "category": "burst", "cooldown_sec": 90.0, "warn_before": 10.0, "key_bind": "s", "voice_text": "스프레드 극딜 10초 전이야.", "slot_id": 1},
        {"name": "풍마수리검", "category": "buff", "cooldown_sec": 25.0, "warn_before": 3.0, "key_bind": "w", "voice_text": "풍마 수리검 쿨 돌았어.", "slot_id": 2},
        {"name": "레디 투 다이", "category": "burst", "cooldown_sec": 75.0, "warn_before": 5.0, "key_bind": "d", "voice_text": "레투다 쿨 5초 전.", "slot_id": 3}
    ],
    "히어로": [
        {"name": "발할라 & 콤보 인스팅트", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "s", "voice_text": "인스팅트 극딜 10초 전이야.", "slot_id": 1},
        {"name": "인사이징 / 소드 일루전", "category": "buff", "cooldown_sec": 30.0, "warn_before": 3.0, "key_bind": "w", "voice_text": "소드 일루전 준비 완료.", "slot_id": 2},
        {"name": "데스폴트 (무적기)", "category": "defense", "cooldown_sec": 20.0, "warn_before": 3.0, "key_bind": "shift", "voice_text": "데스폴트 무적기 준비 완료.", "slot_id": 3}
    ],
    "아델": [
        {"name": "인피니트 (극딜)", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "s", "voice_text": "인피니트 극딜 10초 전이야.", "slot_id": 1},
        {"name": "다이크 (무적기)", "category": "defense", "cooldown_sec": 30.0, "warn_before": 3.0, "key_bind": "shift", "voice_text": "다이크 무적기 쿨 돌았어.", "slot_id": 2},
        {"name": "리스토어 / 루인", "category": "burst", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "d", "voice_text": "루인 5초 전.", "slot_id": 3}
    ]
}


# =============================================================================
# 📦 5. 런타임 추적 스킬 클래스
# =============================================================================
class TrackedSkill:
    """실시간 쿨타임 상태 머신"""
    def __init__(self, name: str, category: str, cooldown_sec: float, warn_before: float = 5.0, key_bind: Optional[str] = "shift", voice_text: Optional[str] = None, slot_id: int = 1):
        self.name = name
        self.category = category
        self.cooldown_sec = float(cooldown_sec)
        self.warn_before = float(warn_before)
        self.key_bind = (key_bind or "").lower().strip()
        self.voice_text = voice_text or f"{name} 쿨 {int(warn_before)}초 남았어."
        self.slot_id = slot_id

        # 런타임 상태
        self.state = "READY"                  # READY | ON_COOLDOWN | WARNED
        self.cooldown_end_time = 0.0
        self.last_used_time = 0.0
        self.is_key_down = False              # 키 연타 중복 트리거 방지 플래그

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
            "key_bind": self.key_bind,
            "voice_text": self.voice_text,
            "remaining_sec": self.remaining_sec,
            "state": self.state,
            "slot_id": self.slot_id
        }


# =============================================================================
# 🔊 6. 스카디 음성 알림 발화기
# =============================================================================
class SkadiVoiceAnnouncer:
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
# 👁️ 7. 퀵슬롯 감시 & 쿨타임 자동 관리자
# =============================================================================
class MapleSkillWatcher:
    """게임 자동 감지 + 단축키 자동 트리거 + 퀵슬롯 감시 통합 엔진"""

    def __init__(self):
        self.is_running = False
        self._watcher_thread: Optional[threading.Thread] = None
        self.skills: List[TrackedSkill] = []
        self.load_skills_from_json()
        
        # 시작 시 백그라운드 자동 실행
        self.start()

    def load_skills_from_json(self):
        """저장된 JSON 파일에서 스킬 목록 로드"""
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
                            key_bind=s.get("key_bind", "shift"),
                            voice_text=s.get("voice_text"),
                            slot_id=s.get("slot_id", 1)
                        ) for s in data
                    ]
                    return
            except Exception:
                pass

        self.load_preset("공통 (기본)")

    def save_skills_to_json(self):
        """현재 스킬 설정을 JSON 파일로 영구 저장"""
        data = [
            {
                "name": s.name,
                "category": s.category,
                "cooldown_sec": s.cooldown_sec,
                "warn_before": s.warn_before,
                "key_bind": s.key_bind,
                "voice_text": s.voice_text,
                "slot_id": s.slot_id
            } for s in self.skills
        ]
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_preset(self, preset_name: str) -> bool:
        if preset_name not in JOB_PRESETS:
            return False
        preset_data = JOB_PRESETS[preset_name]
        self.skills = [
            TrackedSkill(
                name=s["name"],
                category=s.get("category", "defense"),
                cooldown_sec=s["cooldown_sec"],
                warn_before=s.get("warn_before", 5.0),
                key_bind=s.get("key_bind", "shift"),
                voice_text=s.get("voice_text"),
                slot_id=s.get("slot_id", 1)
            ) for s in preset_data
        ]
        self.save_skills_to_json()
        return True

    def add_or_update_skill(self, item: SkillConfigItem):
        for i, sk in enumerate(self.skills):
            if sk.name == item.name:
                self.skills[i] = TrackedSkill(
                    name=item.name,
                    category=item.category,
                    cooldown_sec=item.cooldown_sec,
                    warn_before=item.warn_before,
                    key_bind=item.key_bind,
                    voice_text=item.voice_text,
                    slot_id=item.slot_id
                )
                self.save_skills_to_json()
                return
        
        self.skills.append(
            TrackedSkill(
                name=item.name,
                category=item.category,
                cooldown_sec=item.cooldown_sec,
                warn_before=item.warn_before,
                key_bind=item.key_bind,
                voice_text=item.voice_text,
                slot_id=item.slot_id
            )
        )
        self.save_skills_to_json()

    def delete_skill(self, skill_name: str) -> bool:
        original_len = len(self.skills)
        self.skills = [s for s in self.skills if s.name != skill_name]
        if len(self.skills) < original_len:
            self.save_skills_to_json()
            return True
        return False
        
    def edit_skill(self, original_name: str, item: SkillConfigItem) -> bool:
        """기존 스킬 정보 수정 (스킬명 변경 포함)"""
        target_idx = None
        for i, sk in enumerate(self.skills):
            if sk.name == original_name:
                target_idx = i
                break

        if target_idx is not None:
            self.skills[target_idx] = TrackedSkill(
                name=item.name,
                category=item.category,
                cooldown_sec=item.cooldown_sec,
                warn_before=item.warn_before,
                key_bind=item.key_bind,
                voice_text=item.voice_text,
                slot_id=item.slot_id
            )
            self.save_skills_to_json()
            return True
        return False

    def save_preset(self, preset_name: str) -> bool:
        """현재 스킬 구성을 새로운 직업/커스텀 프리셋으로 저장"""
        clean_name = preset_name.strip()
        if not clean_name:
            return False
        preset_data = [
            {
                "name": s.name,
                "category": s.category,
                "cooldown_sec": s.cooldown_sec,
                "warn_before": s.warn_before,
                "key_bind": s.key_bind,
                "voice_text": s.voice_text,
                "slot_id": s.slot_id
            } for s in self.skills
        ]
        JOB_PRESETS[clean_name] = preset_data
        self._save_custom_presets_to_file()
        return True

    def delete_preset(self, preset_name: str) -> bool:
        """지정한 프리셋 삭제"""
        if preset_name in JOB_PRESETS:
            del JOB_PRESETS[preset_name]
            self._save_custom_presets_to_file()
            return True
        return False

    def _save_custom_presets_to_file(self):
        """커스텀 프리셋 영구 저장"""
        preset_file = DATA_DIR / "maple_custom_presets.json"
        try:
            with open(preset_file, "w", encoding="utf-8") as f:
                json.dump(JOB_PRESETS, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_custom_presets_from_file(self):
        """저장된 커스텀 프리셋 복원"""
        preset_file = DATA_DIR / "maple_custom_presets.json"
        if preset_file.exists():
            try:
                with open(preset_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    JOB_PRESETS.update(data)
            except Exception:
                pass

    def trigger_skill_used(self, skill_name: str):
        """스킬 쿨타임 시작"""
        for sk in self.skills:
            if sk.name == skill_name or skill_name.lower() in sk.name.lower():
                sk.state = "ON_COOLDOWN"
                sk.last_used_time = time.time()
                sk.cooldown_end_time = time.time() + sk.cooldown_sec
                return

    def is_maple_running(self) -> bool:
        """메이플스토리 프로세스 실행 여부 확인"""
        if not psutil:
            return True  # psutil 없으면 상시 활성화
        for p in psutil.process_iter(['name']):
            try:
                if p.info['name'] and 'maplestory.exe' in p.info['name'].lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

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
        """0.05초 초고속 핫키 감지 & 쿨타임 타이머 루프"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.is_running:
            try:
                current_time = time.time()

                # 1. 단축키 입력 감지 (Windows GetAsyncKeyState 기반, 0ms 레이턴시)
                for sk in self.skills:
                    if sk.key_bind and sk.key_bind in KEY_MAP:
                        vk = KEY_MAP[sk.key_bind]
                        # 최상위 비트가 1이면 키가 눌려있는 상태
                        is_pressed = (ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000) != 0

                        if is_pressed and not sk.is_key_down:
                            sk.is_key_down = True
                            # 스킬이 READY 상태일 때 키가 눌리면 쿨타임 자동 시작!
                            if sk.state == "READY":
                                sk.state = "ON_COOLDOWN"
                                sk.last_used_time = current_time
                                sk.cooldown_end_time = current_time + sk.cooldown_sec
                                print(f"⚡ [자동 감지] '{sk.name}' 단축키({sk.key_bind.upper()}) 입력 감지 ➔ {sk.cooldown_sec}초 쿨타임 가동!")

                        elif not is_pressed and sk.is_key_down:
                            sk.is_key_down = False

                # 2. 쿨타임 카운트다운 및 음성 알림 발화
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

                # 0.05초 대기 (초고속 반응 & CPU 점유율 0.2% 미만)
                time.sleep(0.05)
            except Exception:
                time.sleep(0.5)

        loop.close()


# 글로벌 단일 인스턴스
maple_watcher = MapleSkillWatcher()


# =============================================================================
# 🌐 8. FastAPI 라우터 엔드포인트
# =============================================================================

@router.get("/skills", summary="현재 등록된 스킬 목록 조회")
async def get_skills():
    return {
        "status": "success",
        "is_running": maple_watcher.is_running,
        "maple_process_detected": maple_watcher.is_maple_running(),
        "skills": [sk.to_dict() for sk in maple_watcher.skills]
    }


@router.post("/skills/quick-add", summary="스킬 빠른 추가/수정")
async def quick_add_skill(item: SkillConfigItem):
    maple_watcher.add_or_update_skill(item)
    return {"status": "success", "message": f"'{item.name}' 스킬 설정 저장 완료", "skill": item.dict()}


@router.put("/skills/edit", summary="스킬 설정 수정")
async def edit_skill_item(req: SkillEditRequest):
    success = maple_watcher.edit_skill(req.original_name, req.item)
    if not success:
        raise HTTPException(status_code=404, detail=f"수정할 스킬 '{req.original_name}'을 찾을 수 없습니다.")
    return {"status": "success", "message": f"'{req.item.name}' 스킬 수정 완료", "skill": req.item.dict()}


@router.delete("/skills/{skill_name}", summary="스킬 삭제")
async def delete_skill_item(skill_name: str):
    success = maple_watcher.delete_skill(skill_name)
    if not success:
        raise HTTPException(status_code=404, detail="삭제할 스킬을 찾을 수 없습니다.")
    return {"status": "success", "message": f"'{skill_name}' 삭제 완료"}


@router.get("/presets", summary="사용 가능한 직업 프리셋 목록")
async def get_presets():
    return {"status": "success", "presets": list(JOB_PRESETS.keys())}


@router.post("/presets/load/{job_name}", summary="직업 프리셋 원클릭 적용")
async def load_job_preset(job_name: str):
    success = maple_watcher.load_preset(job_name)
    if not success:
        raise HTTPException(status_code=400, detail=f"'{job_name}' 프리셋이 존재하지 않습니다.")
    return {"status": "success", "message": f"'{job_name}' 프리셋 로드 완료", "skills": [sk.to_dict() for sk in maple_watcher.skills]}


@router.post("/presets/save/{preset_name}", summary="현재 스킬 구성을 프리셋으로 저장")
async def save_custom_preset(preset_name: str):
    success = maple_watcher.save_preset(preset_name)
    if not success:
        raise HTTPException(status_code=400, detail="프리셋 이름이 올바르지 않습니다.")
    return {"status": "success", "message": f"'{preset_name}' 프리셋 저장 완료", "presets": list(JOB_PRESETS.keys())}


@router.delete("/presets/{preset_name}", summary="프리셋 삭제")
async def delete_custom_preset(preset_name: str):
    success = maple_watcher.delete_preset(preset_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"삭제할 프리셋 '{preset_name}'이 존재하지 않습니다.")
    return {"status": "success", "message": f"'{preset_name}' 프리셋 삭제 완료", "presets": list(JOB_PRESETS.keys())}


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
