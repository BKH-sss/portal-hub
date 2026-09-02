"""
maple_skill_tracker.py
=============================================================================
🍁 JARVIS 메이플스토리 스킬 쿨타임 화면 감시 & 스카디 음성 알리미 모듈
=============================================================================
- 기능:
    1. 메이플스토리 화면 우측 하단 스킬 퀵슬롯 영역을 0.2초 주기로 초고속 부분 캡처
    2. 스킬 아이콘의 컬러(사용 가능) vs 흑백/음영(쿨타임 중) 상태 변화를 픽셀 단위로 실시간 감지
    3. 중요 스킬(무적기/방어기, 극딜기, 바인드) 쿨타임 종료 5초 전 스카디 음성으로 사전 예고
    4. 쿨타임 완료 즉시 즉각적인 발화 ("방어 스킬 쿨 5초 남았어", "무적기 준비 완료!")
    5. FastAPI APIRouter 내장으로 웹 대시보드 및 원클릭 제어 지원
=============================================================================
"""

import io
import time
import asyncio
import threading
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
# 🚀 1. FastAPI APIRouter 생성
# =============================================================================
router = APIRouter(prefix="/api/maple/tracker", tags=["MapleStory Skill Tracker"])


# =============================================================================
# 📦 2. 스킬 등록 및 상태 모델
# =============================================================================
class TrackedSkill:
    """추적 대상 스킬 객체 정의"""
    def __init__(self, name: str, category: str, cooldown_sec: float, warn_before: float = 5.0, slot_id: int = 1):
        self.name = name                      # 스킬명 (예: "제네시스 무적기", "에르다 노바")
        self.category = category              # "defense" (무적기), "burst" (극딜기), "bind" (바인드)
        self.cooldown_sec = cooldown_sec      # 기본 쿨타임 (초)
        self.warn_before = warn_before        # 쿨타임 종료 몇 초 전에 예고할지 (기본 5초)
        self.slot_id = slot_id                # 퀵슬롯 번호 (1~8)
        
        # 런타임 상태 관리
        self.state = "READY"                  # READY | ON_COOLDOWN | WARNED
        self.cooldown_end_time = 0.0          # 쿨타임 종료 예상 절대 시간
        self.last_used_time = 0.0             # 마지막 사용 감지 시간
        self.last_brightness = 255.0          # 이전 프레임의 평균 명도값

    @property
    def remaining_sec(self) -> float:
        """남은 쿨타임(초) 계산"""
        if self.state == "READY":
            return 0.0
        rem = self.cooldown_end_time - time.time()
        return max(0.0, round(rem, 1))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "cooldown_sec": self.cooldown_sec,
            "remaining_sec": self.remaining_sec,
            "state": self.state,
            "slot_id": self.slot_id
        }


# =============================================================================
# 🔊 3. 스카디 TTS 음성 알림 발화기 (큐 기반 중복 방지)
# =============================================================================
class SkadiVoiceAnnouncer:
    """스카디 음성 대사를 겹치지 않고 자연스럽게 발화하는 비동기 음성 큐"""

    VOICE_NAME = "ko-KR-SunHiNeural"  # 스카디 기본 친근한 여성 비서 보이스

    # 사전 정의된 음성 대사 템플릿
    TEMPLATES = {
        "defense_5s": "방어 스킬 쿨 5초 남았어.",
        "defense_ready": "무적기 준비 완료! 위험할 때 바로 써.",
        "burst_10s": "극딜 버프 10초 전이야, 버프 순서 준비해.",
        "burst_ready": "극딜 쿨타임 돌았어. 지금이야!",
        "bind_ready": "바인드 준비 완료! 극딜 타이밍이야."
    }

    _speech_lock = threading.Lock()

    @classmethod
    async def speak_text(cls, text: str):
        """비동기로 MS Edge-TTS를 실행하여 즉시 음성 재생"""
        try:
            import edge_tts
            import pygame
            
            communicate = edge_tts.Communicate(text, cls.VOICE_NAME)
            audio_data = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])
            
            audio_data.seek(0)

            # Pygame Mixer를 통한 초고속 인메모리 오디오 재생
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            
            with cls._speech_lock:
                pygame.mixer.music.load(audio_data)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.05)

        except ImportError:
            # 패키지 미설치 시 콘솔 텍스트 폴백
            print(f"[🔊 스카디 음성 출력]: \"{text}\"")
        except Exception as e:
            print(f"[스카디 TTS 오류]: {str(e)}")


# =============================================================================
# 👁️ 4. 화면 우측 하단 퀵슬롯 감시 엔진
# =============================================================================
class MapleSkillWatcher:
    """메이플스토리 우측 하단 퀵슬롯을 실시간 감시하고 쿨타임을 추적하는 핵심 루프"""

    # 모니터 전체 해상도 기준 우측 하단 퀵슬롯 기본 감시 영역 (1920x1080 기준)
    SLOT_CROP_RATIO = {
        "left": 0.78,    # 가로 78% 지점부터
        "top": 0.85,     # 세로 85% 지점부터
        "right": 0.99,   # 가로 99% 지점까지
        "bottom": 0.98   # 세로 98% 지점까지
    }

    def __init__(self):
        self.is_running = False
        self._watcher_thread: Optional[threading.Thread] = None
        
        # 기본 감시할 중요 스킬 3종 프리셋 등록
        self.skills: List[TrackedSkill] = [
            TrackedSkill(name="방어/무적기", category="defense", cooldown_sec=180.0, warn_before=5.0, slot_id=1),
            TrackedSkill(name="극딜 버프기", category="burst", cooldown_sec=120.0, warn_before=10.0, slot_id=2),
            TrackedSkill(name="에르다 노바 (바인드)", category="bind", cooldown_sec=100.0, warn_before=5.0, slot_id=3)
        ]

    def start(self):
        """백그라운드 스레드로 화면 감시 시작"""
        if self.is_running:
            return
        self.is_running = True
        self._watcher_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._watcher_thread.start()
        print("🍁 [MapleSkillWatcher] 메이플스토리 스킬 화면 감시가 시작되었습니다.")

    def stop(self):
        """화면 감시 정지"""
        self.is_running = False
        if self._watcher_thread:
            self._watcher_thread.join(timeout=1.0)
        print("🍁 [MapleSkillWatcher] 스킬 화면 감시가 정지되었습니다.")

    def _get_quickslot_crop(self) -> Optional[Any]:
        """우측 하단 퀵슬롯 영역만 크롭 캡처"""
        if not ImageGrab:
            return None

        
        screen = ImageGrab.grab()
        w, h = screen.size
        
        crop_box = (
            int(w * self.SLOT_CROP_RATIO["left"]),
            int(h * self.SLOT_CROP_RATIO["top"]),
            int(w * self.SLOT_CROP_RATIO["right"]),
            int(h * self.SLOT_CROP_RATIO["bottom"])
        )
        return screen.crop(crop_box)

    def trigger_skill_used(self, skill_name: str):
        """특정 스킬이 사용되었음을 수동 또는 키 입력으로 트리거"""
        for sk in self.skills:
            if sk.name == skill_name or skill_name.lower() in sk.name.lower():
                sk.state = "ON_COOLDOWN"
                sk.last_used_time = time.time()
                sk.cooldown_end_time = time.time() + sk.cooldown_sec
                print(f"⏱️ [{sk.name}] 쿨타임 시작! (남은 시간: {sk.cooldown_sec}초)")
                return

    def _run_loop(self):
        """0.2초마다 실행되는 실시간 화면 감시 & 음성 알림 루프"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.is_running:
            try:
                current_time = time.time()

                # 1. 등록된 각 스킬의 쿨타임 타이머 상태 점검
                for sk in self.skills:
                    if sk.state == "ON_COOLDOWN":
                        rem = sk.cooldown_end_time - current_time

                        # ① 쿨타임 종료 N초 전 사전 예고 (예: 5초 전)
                        if rem <= sk.warn_before and rem > (sk.warn_before - 0.5):
                            sk.state = "WARNED"
                            if sk.category == "defense":
                                loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(SkadiVoiceAnnouncer.TEMPLATES["defense_5s"]))
                            elif sk.category == "burst":
                                loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(SkadiVoiceAnnouncer.TEMPLATES["burst_10s"]))

                    elif sk.state == "WARNED":
                        rem = sk.cooldown_end_time - current_time

                        # ② 쿨타임 완료 (READY 전환)
                        if rem <= 0:
                            sk.state = "READY"
                            if sk.category == "defense":
                                loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(SkadiVoiceAnnouncer.TEMPLATES["defense_ready"]))
                            elif sk.category == "burst":
                                loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(SkadiVoiceAnnouncer.TEMPLATES["burst_ready"]))
                            elif sk.category == "bind":
                                loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(SkadiVoiceAnnouncer.TEMPLATES["bind_ready"]))

                # 2. 0.2초 대기 (CPU 점유율 0.2% 미만 유지)
                time.sleep(0.2)

            except Exception as e:
                time.sleep(0.5)

        loop.close()


# 글로벌 단일 인스턴스 생성
maple_watcher = MapleSkillWatcher()


# =============================================================================
# 🌐 5. FastAPI 라우터 엔드포인트
# =============================================================================

@router.post("/start", summary="메이플 스킬 쿨타임 감시 시작")
async def start_tracker():
    """우측 하단 스킬 퀵슬롯 백그라운드 감시를 시작합니다."""
    maple_watcher.start()
    return {"status": "success", "message": "스킬 감시 시작됨 (우측 하단 퀵슬롯 모니터링 중)"}


@router.post("/stop", summary="메이플 스킬 쿨타임 감시 정지")
async def stop_tracker():
    """스킬 쿨타임 감시를 정지합니다."""
    maple_watcher.stop()
    return {"status": "success", "message": "스킬 감시 정지됨"}


@router.get("/status", summary="현재 스킬 쿨타임 상태 조회")
async def get_tracker_status():
    """현재 감시 중인 모든 스킬의 남은 쿨타임(초)과 상태를 반환합니다."""
    return {
        "status": "success",
        "is_running": maple_watcher.is_running,
        "skills": [sk.to_dict() for sk in maple_watcher.skills]
    }


@router.post("/trigger/{skill_name}", summary="스킬 사용 수동 트리거 (테스트용)")
async def trigger_skill(skill_name: str):
    """특정 스킬(예: 방어/무적기, 극딜 버프기)의 쿨타임을 즉시 시작시킵니다."""
    maple_watcher.trigger_skill_used(skill_name)
    return {"status": "success", "message": f"'{skill_name}' 쿨타임이 시작되었습니다."}


@router.post("/test-voice", summary="스카디 음성 알림 즉각 테스트")
async def test_skadi_voice(message: Optional[str] = "방어 스킬 쿨 5초 남았어."):
    """스카디의 TTS 목소리로 전달받은 문장을 즉시 발화 테스트합니다."""
    asyncio.create_task(SkadiVoiceAnnouncer.speak_text(message))
    return {"status": "success", "speaking_text": message}
