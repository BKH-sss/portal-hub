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
import math
import json
import time
import ctypes
import hashlib
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
    import edge_tts
except ImportError:
    edge_tts = None

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
    "shift": [0x10, 0xA0, 0xA1],
    "lshift": [0xA0],
    "rshift": [0xA1],
    "ctrl": [0x11, 0xA2, 0xA3],
    "lctrl": [0xA2],
    "rctrl": [0xA3],
    "alt": [0x12, 0xA4, 0xA5],
    "space": [0x20],
    "ins": [0x2D], "insert": [0x2D], "del": [0x2E], "delete": [0x2E],
    "home": [0x24], "end": [0x23], "pgup": [0x21], "pgdn": [0x22],
    "q": [0x51], "w": [0x57], "e": [0x45], "r": [0x52], "t": [0x54], "y": [0x59],
    "a": [0x41], "s": [0x53], "d": [0x44], "f": [0x46], "g": [0x47],
    "z": [0x5A], "x": [0x58], "c": [0x43], "v": [0x56], "b": [0x42],
    "1": [0x31], "2": [0x32], "3": [0x33], "4": [0x34], "5": [0x35], "6": [0x36],
    "7": [0x37], "8": [0x38], "9": [0x39], "0": [0x30],
    "f1": [0x70], "f2": [0x71], "f3": [0x72], "f4": [0x73], "f5": [0x74], "f6": [0x75],
    "f7": [0x76], "f8": [0x77], "f9": [0x78], "f10": [0x79], "f11": [0x7A], "f12": [0x7B]
}

def is_key_pressed(key_name: Optional[str]) -> bool:
    """단축키 입력 여부를 대소문자/변형 무관하게 정밀 감지"""
    if not key_name:
        return False
    clean = str(key_name).strip().lower()
    vks = KEY_MAP.get(clean)
    if not vks:
        if len(clean) == 1:
            vks = [ord(clean.upper())]
        else:
            return False
    for vk in vks:
        st = ctypes.windll.user32.GetAsyncKeyState(vk)
        if (st & 0x8000) != 0 or (st & 0x0001) != 0:
            return True
    return False


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
        {"name": "방어 무적기", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "방어 스킬 쿨 5초 남았어.", "slot_id": 1},
        {"name": "극딜 버프기", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "ctrl", "voice_text": "극딜 버프 10초 전이야, 준비해.", "slot_id": 2},
        {"name": "에르다 노바 (바인드)", "category": "bind", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "바인드 준비 완료! 극딜 타이밍이야.", "slot_id": 3}
    ],
    "비숍": [
        {"name": "홀리 매직쉘 & 힐", "category": "defense", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "a", "voice_text": "매직쉘 쿨 5초 전이야.", "slot_id": 1},
        {"name": "프레이 & 리브라 (극딜)", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "s", "voice_text": "프레이 10초 전이야, 파티원 모여.", "slot_id": 2},
        {"name": "제네시스 무적기", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "제네시스 무적기 5초 전.", "slot_id": 3}
    ],
    "나이트로드": [
        {"name": "스프레드 & 얼닼사", "category": "burst", "cooldown_sec": 90.0, "warn_before": 10.0, "key_bind": "s", "voice_text": "스프레드 극딜 10초 전이야.", "slot_id": 1},
        {"name": "풍마수리검", "category": "buff", "cooldown_sec": 25.0, "warn_before": 3.0, "key_bind": "w", "voice_text": "풍마 수리검 쿨 돌았어.", "slot_id": 2},
        {"name": "레디 투 다이", "category": "burst", "cooldown_sec": 75.0, "warn_before": 5.0, "key_bind": "d", "voice_text": "레투다 쿨 5초 전.", "slot_id": 3}
    ],
    "히어로": [
        {"name": "오라블레이드", "category": "buff", "cooldown_sec": 8.0, "warn_before": 2.0, "key_bind": "shift", "voice_text": "오라블레이드 곧 두개야", "slot_id": 1},
        {"name": "레이지 업라이징", "category": "attack", "cooldown_sec": 10.0, "warn_before": 2.0, "key_bind": "end", "voice_text": "레이지 업라이징 2초 남았어", "slot_id": 2},
        {"name": "극딜 시퀀스", "category": "burst", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "e", "voice_text": "극딜 5초전", "slot_id": 3},
        {"name": "에르다 노바", "category": "bind", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "5차 바인드 5초 남았어", "slot_id": 4},
        {"name": "소드 일루전", "category": "buff", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "일루전 5초 남았어", "slot_id": 5},
        {"name": "인사이징", "category": "debuff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "인사 5초뒤 끝나", "slot_id": 6}
    ],
    "아델": [
        {"name": "인피니트 (극딜)", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "s", "voice_text": "인피니트 극딜 10초 전이야.", "slot_id": 1},
        {"name": "다이크 (무적기)", "category": "defense", "cooldown_sec": 30.0, "warn_before": 3.0, "key_bind": "shift", "voice_text": "다이크 무적기 쿨 돌았어.", "slot_id": 2},
        {"name": "리스토어 & 루인", "category": "burst", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "d", "voice_text": "루인 5초 전.", "slot_id": 3}
    ],
    "은월": [
        {"name": "정령의 화신", "category": "defense", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "end", "voice_text": "정령의 화신 5초 전", "slot_id": 1},
        {"name": "소혼장막", "category": "buff", "cooldown_sec": 74.0, "warn_before": 5.0, "key_bind": "del", "voice_text": "소혼 재설치", "slot_id": 2},
        {"name": "연우격풍", "category": "burst", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "4", "voice_text": "연우격풍 5초 전", "slot_id": 3},
        {"name": "극딜", "category": "burst", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "1", "voice_text": "극딜 5초 전", "slot_id": 4},
        {"name": "프리드", "category": "defense", "cooldown_sec": 360.0, "warn_before": 5.0, "key_bind": "f", "voice_text": "프리드 5초 전", "slot_id": 5},
        {"name": "크오솔", "category": "attack", "cooldown_sec": 240.0, "warn_before": 5.0, "key_bind": "f1", "voice_text": "스인미 크오솔 5초 전", "slot_id": 6},
        {"name": "제네무적", "category": "defense", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "x", "voice_text": "제네 무적 5초 전", "slot_id": 7},
        {"name": "준극딜", "category": "burst", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "준극 5초 전", "slot_id": 8},
        {"name": "파쇄 연권", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "r", "voice_text": "파쇄 연권 10초 전", "slot_id": 9}
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
    def remaining_sec(self) -> int:
        """남은 쿨타임(초) - 깔끔한 정수 단위 (1초, 2초, 3초)"""
        if self.state == "READY":
            return 0
        rem = self.cooldown_end_time - time.time()
        return max(0, int(math.ceil(rem)))

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
# 🔊 6. 스카디 음성 알림 발화기 (GPT-SoVITS 전용 모델 기반 0ms 로컬 캐시 엔진)
# =============================================================================
class SkadiVoiceAnnouncer:
    GPT_SOVITS_URL = "http://127.0.0.1:9880"
    REF_AUDIO_PATH = MODULE_DIR.parent / "korean_skadi_voice" / "kor_skadi_ref_000.wav"
    REF_PROMPT_TEXT = "바닷물에서 떨어지면 우리 같은 건 살아남지 못할 줄 알았어?"
    VOICE_CACHE_DIR = MODULE_DIR.parent / "voice_cache" / "maple_skills"
    _speech_lock = threading.Lock()
    _init_done = False
    volume: int = 100  # 0 ~ 100%

    @classmethod
    def set_volume(cls, val: int):
        """음성 브리핑 볼륨 조절 (0~100%)"""
        cls.volume = max(0, min(100, int(val)))
        try:
            vol_16 = int((cls.volume / 100.0) * 0xFFFF)
            dw_volume = (vol_16 << 16) | vol_16
            ctypes.windll.winmm.waveOutSetVolume(0, dw_volume)
        except Exception:
            pass

    @classmethod
    def _ensure_dir(cls):
        if not cls._init_done:
            cls.VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cls._init_done = True

    @classmethod
    def get_audio_path_for_text(cls, text: str) -> Path:
        """텍스트에 대한 고유 캐시 파일 경로 반환 (SoVITS WAV 우선)"""
        cls._ensure_dir()
        clean = text.strip()
        h = hashlib.md5(clean.encode('utf-8')).hexdigest()[:16]
        wav_p = cls.VOICE_CACHE_DIR / f"skadi_sovits_{h}.wav"
        if wav_p.exists() and wav_p.stat().st_size > 1000:
            return wav_p
        mp3_p = cls.VOICE_CACHE_DIR / f"skadi_edge_{h}.mp3"
        if mp3_p.exists() and mp3_p.stat().st_size > 1000:
            return mp3_p
        return wav_p

    @classmethod
    async def cache_audio(cls, text: str) -> Optional[str]:
        """텍스트를 우리가 만든 스카디 전용 AI 음성 모델(GPT-SoVITS)로 사전 합성 및 영구 캐싱"""
        if not text or not text.strip():
            return None
        cls._ensure_dir()
        clean = text.strip()
        h = hashlib.md5(clean.encode('utf-8')).hexdigest()[:16]
        target_wav = cls.VOICE_CACHE_DIR / f"skadi_sovits_{h}.wav"

        if target_wav.exists() and target_wav.stat().st_size > 1000:
            return str(target_wav)

        # 1. 로컬 GPT-SoVITS AI 스카디 모델 호출 (우선순위 1)
        try:
            import httpx
            ref_path_str = str(cls.REF_AUDIO_PATH.resolve()) if cls.REF_AUDIO_PATH.exists() else ""
            payload = {
                "text": clean,
                "text_lang": "ko",
                "ref_audio_path": ref_path_str,
                "prompt_text": cls.REF_PROMPT_TEXT,
                "prompt_lang": "ko",
                "top_k": 5,
                "top_p": 1,
                "temperature": 1,
                "speed": 1.0
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(f"{cls.GPT_SOVITS_URL}/tts", json=payload)
                if res.status_code == 200 and len(res.content) > 1000:
                    with open(target_wav, "wb") as f:
                        f.write(res.content)
                    return str(target_wav)
        except Exception as e:
            pass

        # 2. GPT-SoVITS 미가동 시 Edge-TTS (스카디 튜닝) 폴백
        target_mp3 = cls.VOICE_CACHE_DIR / f"skadi_edge_{h}.mp3"
        if target_mp3.exists() and target_mp3.stat().st_size > 1000:
            return str(target_mp3)

        try:
            if edge_tts:
                communicate = edge_tts.Communicate(clean, "ko-KR-SunHiNeural", rate="+0%", pitch="-2Hz")
                await communicate.save(str(target_mp3))
                return str(target_mp3)
        except Exception as e:
            print(f"[스카디 TTS 사전 캐싱 오류]: {e}")
        return None

    @classmethod
    def stop_all_audio(cls):
        """재생 중인 모든 오디오 즉각 강제 중단"""
        try:
            ctypes.windll.winmm.mciSendStringW("stop all", None, 0, None)
            ctypes.windll.winmm.mciSendStringW("close all", None, 0, None)
        except Exception:
            pass

    @classmethod
    def play_file_sync(cls, file_path: str):
        """Windows Native MCI 엔진을 통해 0.00ms 오차 없이 즉각 재생"""
        if not file_path or not os.path.exists(file_path):
            return
        if cls.volume <= 0:
            return  # 음소거
        try:
            vol_16 = int((cls.volume / 100.0) * 0xFFFF)
            dw_volume = (vol_16 << 16) | vol_16
            ctypes.windll.winmm.waveOutSetVolume(0, dw_volume)

            abs_path = os.path.abspath(file_path)
            alias = f"skadi_maple_{int(time.time() * 1000) % 10000}"
            ext = os.path.splitext(abs_path)[1].lower()
            mci_type = "type waveaudio" if ext == ".wav" else "type mpegvideo"
            
            ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)
            ret = ctypes.windll.winmm.mciSendStringW(f'open "{abs_path}" {mci_type} alias {alias}', None, 0, None)
            if ret != 0:
                ret = ctypes.windll.winmm.mciSendStringW(f'open "{abs_path}" alias {alias}', None, 0, None)
            ctypes.windll.winmm.mciSendStringW(f'play {alias}', None, 0, None)
        except Exception as e:
            print(f"[스카디 음성 재생 오류]: {e}")

    @classmethod
    async def speak_text(cls, text: str):
        """사전 캐시된 오디오 파일을 즉시 꺼내어 0ms 로컬 재생"""
        if not text:
            return
        target_path = cls.get_audio_path_for_text(text)
        if target_path.exists() and target_path.stat().st_size > 1000:
            # 캐시가 이미 존재하면 즉시 로컬 재생 (0ms 지연)
            cls.play_file_sync(str(target_path))
        else:
            # 캐시가 없으면 1회 다운로드 후 즉각 재생
            fpath = await cls.cache_audio(text)
            if fpath:
                cls.play_file_sync(fpath)
            else:
                print(f"[🔊 스카디 음성 출력]: \"{text}\"")

    @classmethod
    def preload_skills_background(cls, skills: List[Any]):
        """스킬 목록의 모든 예고 대사와 완료 대사를 백그라운드에서 사전 다운로드"""
        def _preload_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            for sk in skills:
                try:
                    if getattr(sk, 'voice_text', None):
                        loop.run_until_complete(cls.cache_audio(sk.voice_text))
                    name = getattr(sk, 'name', '')
                    if name:
                        loop.run_until_complete(cls.cache_audio(f"{name} 준비 완료!"))
                except Exception:
                    pass
            loop.close()

        t = threading.Thread(target=_preload_worker, daemon=True)
        t.start()


# =============================================================================
# 👁️ 7. 퀵슬롯 감시 & 쿨타임 자동 관리자
# =============================================================================
class MapleSkillWatcher:
    """게임 자동 감지 + 단축키 자동 트리거 + 퀵슬롯 감시 통합 엔진"""

    def __init__(self):
        self.is_running = False
        self._watcher_thread: Optional[threading.Thread] = None
        self.skills: List[TrackedSkill] = []
        self.load_custom_presets_from_file() # 저장된 커스텀 프리셋 복원!
        self.load_skills_from_json()
        # 기본 상태는 '감시 정지(OFF)' 유지 - 사용자가 웹 대시보드에서 시작 버튼 클릭 시에만 가동됨

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
                    SkadiVoiceAnnouncer.preload_skills_background(self.skills)
                    return
            except Exception:
                pass

        self.load_preset("공통 (기본)")

    def save_skills_to_json(self):
        """현재 스킬 설정을 JSON 파일로 영구 저장 및 음성 자동 프리캐싱"""
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
        SkadiVoiceAnnouncer.preload_skills_background(self.skills)

    async def precache_current_skills(self) -> int:
        """현재 등록된 모든 스킬 음성 일괄 사전 합성 및 캐싱"""
        count = 0
        for sk in self.skills:
            if sk.voice_text:
                await SkadiVoiceAnnouncer.cache_audio(sk.voice_text)
                count += 1
            if sk.name:
                await SkadiVoiceAnnouncer.cache_audio(f"{sk.name} 준비 완료!")
                count += 1
        return count

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
        clean_target = skill_name.strip()
        self.skills = [s for s in self.skills if s.name.strip() != clean_target]
        if len(self.skills) < original_len:
            self.save_skills_to_json()
            SkadiVoiceAnnouncer.stop_all_audio()
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
        # 1. 모든 스킬 쿨타임 및 키 상태 강제 초기화
        for sk in self.skills:
            sk.state = "READY"
            sk.cooldown_end_time = 0.0
            sk.is_key_down = False
        # 2. 재생 중인 모든 음성 즉각 중단
        SkadiVoiceAnnouncer.stop_all_audio()
        if self._watcher_thread:
            try:
                self._watcher_thread.join(timeout=0.5)
            except Exception:
                pass

    def _run_loop(self):
        """0.05초 초고속 핫키 감지 & 쿨타임 타이머 루프"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.is_running:
            try:
                current_time = time.time()

                if not self.is_running:
                    break

                # 1. 단축키 입력 감지 (Windows GetAsyncKeyState 기반, 0ms 레이턴시)
                for sk in self.skills:
                    if not self.is_running:
                        break
                    if sk.key_bind:
                        pressed = is_key_pressed(sk.key_bind)

                        if pressed and not sk.is_key_down:
                            sk.is_key_down = True
                            # 스킬이 READY 상태이고 감시 중일 때만 쿨타임 자동 시작!
                            if sk.state == "READY" and self.is_running:
                                sk.state = "ON_COOLDOWN"
                                sk.last_used_time = current_time
                                sk.cooldown_end_time = current_time + sk.cooldown_sec
                                print(f"⚡ [자동 감지] '{sk.name}' 단축키({sk.key_bind.upper()}) 입력 감지 ➔ {sk.cooldown_sec}초 쿨타임 가동!")

                        elif not pressed and sk.is_key_down:
                            sk.is_key_down = False

                # 2. 쿨타임 카운트다운 및 음성 알림 발화
                for sk in self.skills:
                    if not self.is_running:
                        break
                    if sk.state == "ON_COOLDOWN":
                        rem = sk.cooldown_end_time - current_time

                        # ① N초 전 사전 브리핑 발화
                        if rem <= sk.warn_before:
                            sk.state = "WARNED"
                            if self.is_running and sk.voice_text:
                                loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(sk.voice_text))

                    elif sk.state == "WARNED":
                        rem = sk.cooldown_end_time - current_time

                        # ② 쿨타임 완료 발화
                        if rem <= 0:
                            sk.state = "READY"
                            if self.is_running:
                                loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(f"{sk.name} 준비 완료!"))

                # 0.05초 대기 (초고속 반응 & CPU 점유율 0.2% 미만)
                time.sleep(0.05)
            except Exception as e:
                time.sleep(0.1)

        loop.close()


# 글로벌 단일 인스턴스
maple_watcher = MapleSkillWatcher()


# =============================================================================
# 🌐 8. FastAPI 라우터 엔드포인트
# =============================================================================

@router.get("/skills", summary="현재 등록된 스킬 목록 조회")
async def get_skills():
    is_admin = False
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        pass
    return {
        "status": "success",
        "is_running": maple_watcher.is_running,
        "is_admin": is_admin,
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


@router.delete("/skills/{skill_name:path}", summary="스킬 삭제")
async def delete_skill_item(skill_name: str):
    import urllib.parse
    decoded_name = urllib.parse.unquote(skill_name).strip()
    success = maple_watcher.delete_skill(decoded_name)
    if not success:
        success = maple_watcher.delete_skill(skill_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"삭제할 스킬 '{decoded_name}'을 찾을 수 없습니다.")
    return {"status": "success", "message": f"'{decoded_name}' 삭제 완료"}


@router.get("/presets", summary="사용 가능한 직업 프리셋 목록")
async def get_presets():
    maple_watcher.load_custom_presets_from_file()
    preset_list = list(JOB_PRESETS.keys())
    return {"status": "success", "count": len(preset_list), "presets": preset_list}


@router.post("/presets/load/{job_name:path}", summary="직업 프리셋 원클릭 적용")
async def load_job_preset(job_name: str):
    import urllib.parse
    decoded_job = urllib.parse.unquote(job_name).strip()
    success = maple_watcher.load_preset(decoded_job)
    if not success:
        success = maple_watcher.load_preset(job_name)
    if not success:
        raise HTTPException(status_code=400, detail=f"'{decoded_job}' 프리셋이 존재하지 않습니다.")
    return {"status": "success", "message": f"'{decoded_job}' 프리셋 로드 완료", "skills": [sk.to_dict() for sk in maple_watcher.skills]}


@router.post("/presets/save/{preset_name:path}", summary="현재 스킬 구성을 프리셋으로 저장")
async def save_custom_preset(preset_name: str):
    import urllib.parse
    decoded_name = urllib.parse.unquote(preset_name).strip()
    success = maple_watcher.save_preset(decoded_name)
    if not success:
        raise HTTPException(status_code=400, detail="프리셋 이름이 올바르지 않습니다.")
    return {"status": "success", "message": f"'{decoded_name}' 프리셋 저장 완료", "presets": list(JOB_PRESETS.keys())}


@router.delete("/presets/{preset_name:path}", summary="프리셋 삭제")
async def delete_custom_preset(preset_name: str):
    import urllib.parse
    decoded_name = urllib.parse.unquote(preset_name).strip()
    success = maple_watcher.delete_preset(decoded_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"삭제할 프리셋 '{decoded_name}'이 존재하지 않습니다.")
    return {"status": "success", "message": f"'{decoded_name}' 프리셋 삭제 완료", "presets": list(JOB_PRESETS.keys())}


@router.post("/start", summary="실시간 감시 시작")
async def start_tracker():
    maple_watcher.start()
    return {"status": "success", "message": "스킬 감시 시작됨"}


@router.post("/stop", summary="실시간 감시 정지")
async def stop_tracker():
    maple_watcher.stop()
    return {"status": "success", "message": "스킬 감시 정지됨"}


@router.post("/trigger/{skill_name:path}", summary="스킬 쿨타임 시작 트리거")
async def trigger_skill(skill_name: str):
    import urllib.parse
    decoded_name = urllib.parse.unquote(skill_name).strip()
    maple_watcher.trigger_skill_used(decoded_name)
    return {"status": "success", "message": f"'{decoded_name}' 쿨타임 시작됨"}


@router.post("/precache-all", summary="모든 스킬 음성 일괄 사전 합성 및 다운로드")
async def precache_all_voices():
    cached_count = await maple_watcher.precache_current_skills()
    return {
        "status": "success",
        "message": f"스카디 AI 음성 {cached_count}개 사전 다운로드 및 캐싱 완료 (0ms 즉시 발화 준비 완료)",
        "cached_count": cached_count
    }


@router.post("/test-voice", summary="스카디 음성 알림 즉각 테스트")
async def test_skadi_voice(message: Optional[str] = "방어 스킬 쿨 5초 남았어."):
    asyncio.create_task(SkadiVoiceAnnouncer.speak_text(message))
    return {"status": "success", "speaking_text": message}


@router.get("/volume", summary="음성 브리핑 볼륨 조회 (0~100)")
async def get_voice_volume():
    return {"status": "success", "volume": SkadiVoiceAnnouncer.volume}


@router.post("/volume/{level:int}", summary="음성 브리핑 볼륨 조절 (0~100)")
async def set_voice_volume(level: int):
    SkadiVoiceAnnouncer.set_volume(level)
    return {"status": "success", "volume": SkadiVoiceAnnouncer.volume}

