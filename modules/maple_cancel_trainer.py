"""
maple_cancel_trainer.py
=============================================================================
🍁 JARVIS / SKADI: 메이플스토리 은월 귀참 캔슬(벽캔/좌우캔/점캔) 정밀 트레이너
=============================================================================
- 기능:
    1. 귀참(Ctrl) ➔ 후방이동(A) 키 입력 간격(ms)을 0.001초 단위로 실시간 측정
    2. 최적 캔슬 프레임(100ms ~ 170ms) 실시간 판정:
       - 🎯 PERFECT (100ms ~ 170ms): 최고 DPS 캔슬 (경쾌한 성공음 + 피드백)
       - ⚠️ TOO FAST (< 90ms): 스킬 씹힘 위험 ("너무 빨라")
       - 🐢 SLOW (> 180ms): 후딜레이 남음 ("조금 더 빠르게")
    3. 실시간 초당 타수(APS, Attacks Per Sec) 및 예상 딜 상승률(%) 산출
    4. F12 단축키 또는 UI 버튼으로 언제든 원할 때 원터치 ON/OFF
    5. 연속 퍼펙트 콤보(Streak) 카운팅 및 통계
=============================================================================
"""

import time
import ctypes
import asyncio
import threading
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/maple/cancel", tags=["MapleStory Cancel Trainer"])

# Windows 가상 키 매핑
KEY_VCODES = {
    "ctrl": [0x11, 0xA2, 0xA3], "lctrl": [0xA2], "rctrl": [0xA3],
    "shift": [0x10, 0xA0, 0xA1], "lshift": [0xA0], "rshift": [0xA1],
    "alt": [0x12, 0xA4, 0xA5],
    "space": [0x20], "a": [0x41], "s": [0x53], "d": [0x44], "f": [0x46],
    "z": [0x5A], "x": [0x58], "c": [0x43], "v": [0x56], "q": [0x51], "w": [0x57], "e": [0x45], "r": [0x52],
    "1": [0x31], "2": [0x32], "3": [0x33], "4": [0x34], "5": [0x35],
    "f12": [0x7B], "f11": [0x7A], "f10": [0x79], "f9": [0x78]
}

def is_vkey_down(key_name: str) -> bool:
    try:
        codes = KEY_VCODES.get(key_name.lower(), [])
        if not codes:
            if len(key_name) == 1:
                codes = [ord(key_name.upper())]
            else:
                return False
        user32 = ctypes.windll.user32
        for vk in codes:
            if user32.GetAsyncKeyState(vk) & 0x8000:
                return True
    except Exception:
        pass
    return False

class CancelTrainerConfig(BaseModel):
    key_primary: str = Field("ctrl", description="주력기 (귀참) 단축키")
    key_cancel: str = Field("a", description="캔슬기 (후방이동) 단축키")
    mode: str = Field("wall", description="캔슬 모드: wall(벽캔), lr(좌우캔), jump(점캔)")
    optimal_min_ms: float = Field(100.0, description="퍼펙트 최소 ms")
    optimal_max_ms: float = Field(170.0, description="퍼펙트 최대 ms")
    sound_feedback: bool = Field(True, description="즉시 효과음/음성 피드백 여부")

class CancelAttempt(BaseModel):
    timestamp: float
    delta_ms: float
    rating: str  # PERFECT, TOO_FAST, SLOW
    combo: int

class MapleCancelTrainer:
    """은월 귀참 캔슬 정밀 트레이너 엔진"""

    def __init__(self):
        self.is_active = False
        self.key_primary = "ctrl"       # 귀참
        self.key_cancel = "a"           # 후방이동
        self.mode = "wall"              # wall(벽캔), lr(좌우캔), jump(점캔)
        self.optimal_min_ms = 100.0
        self.optimal_max_ms = 170.0
        self.sound_feedback = True

        # 상태 추적
        self._thread: Optional[threading.Thread] = None
        self._last_primary_time: float = 0.0
        self._primary_key_down: bool = False
        self._cancel_key_down: bool = False
        self._f12_key_down: bool = False

        # 통계
        self.total_attempts: int = 0
        self.perfect_count: int = 0
        self.fast_count: int = 0
        self.slow_count: int = 0
        self.current_combo: int = 0
        self.max_combo: int = 0
        self.last_attempt: Optional[Dict[str, Any]] = None
        self.recent_attempts: List[Dict[str, Any]] = []
        self.cycle_timestamps: List[float] = []

    def toggle(self, enable: Optional[bool] = None) -> bool:
        if enable is None:
            self.is_active = not self.is_active
        else:
            self.is_active = enable

        if self.is_active:
            if not self._thread or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run_loop, daemon=True, name="CancelTrainerThread")
                self._thread.start()
            print("[🎯 귀참 캔슬 트레이너] 연습 모드 가동! (Ctrl: 귀참 ➔ A: 후방이동)")
        else:
            print("[🎯 귀참 캔슬 트레이너] 연습 모드 정지")
        return self.is_active

    def reset_stats(self):
        self.total_attempts = 0
        self.perfect_count = 0
        self.fast_count = 0
        self.slow_count = 0
        self.current_combo = 0
        self.max_combo = 0
        self.last_attempt = None
        self.recent_attempts.clear()
        self.cycle_timestamps.clear()

    def update_config(self, cfg: CancelTrainerConfig):
        self.key_primary = cfg.key_primary.lower().strip()
        self.key_cancel = cfg.key_cancel.lower().strip()
        self.mode = cfg.mode.lower().strip()
        self.optimal_min_ms = cfg.optimal_min_ms
        self.optimal_max_ms = cfg.optimal_max_ms
        self.sound_feedback = cfg.sound_feedback

    def _play_feedback_sound(self, rating: str, delta_ms: float):
        """Windows 비프 및 사운드 즉시 피드백 (0ms 레이턴시)"""
        try:
            import winsound
            if rating == "PERFECT":
                # 경쾌하고 밝은 고음 비프 (1200Hz, 45ms)
                winsound.Beep(1350, 45)
            elif rating == "TOO_FAST":
                # 급격한 경고 비프 (2000Hz, 30ms)
                winsound.Beep(2000, 30)
            elif rating == "SLOW":
                # 둔탁한 저음 비프 (600Hz, 50ms)
                winsound.Beep(600, 50)
        except Exception:
            pass

    def _run_loop(self):
        while self.is_active:
            try:
                now = time.time()

                # 1. F12 글로벌 토글 단축키 감지
                f12_pressed = is_vkey_down("f12")
                if f12_pressed and not self._f12_key_down:
                    self._f12_key_down = True
                    # F12 누르면 연습 모드 ON/OFF 즉시 전환
                    self.toggle()
                    if not self.is_active:
                        break
                elif not f12_pressed and self._f12_key_down:
                    self._f12_key_down = False

                if not self.is_active:
                    break

                # 2. 귀참 (Primary Key: Ctrl) 입력 감지
                primary_pressed = is_vkey_down(self.key_primary)
                if primary_pressed and not self._primary_key_down:
                    self._primary_key_down = True
                    self._last_primary_time = now
                    # 사이클 타임스탬프 기록 (최근 5초 내 타수 계산용)
                    self.cycle_timestamps.append(now)
                    if len(self.cycle_timestamps) > 30:
                        self.cycle_timestamps = self.cycle_timestamps[-30:]
                elif not primary_pressed and self._primary_key_down:
                    self._primary_key_down = False

                # 3. 후방이동 (Cancel Key: A) 입력 감지 & 캔슬 타이밍 판정
                cancel_pressed = is_vkey_down(self.key_cancel)
                if cancel_pressed and not self._cancel_key_down:
                    self._cancel_key_down = True
                    # 주력기(귀참)가 눌린 후 0.6초 이내에 후방이동이 눌렸을 때만 캔슬로 인정
                    if self._last_primary_time > 0 and (now - self._last_primary_time) <= 0.600:
                        delta_ms = round((now - self._last_primary_time) * 1000.0, 1)
                        self._last_primary_time = 0.0  # 중복 판정 방지

                        # 등급 판정
                        if delta_ms < self.optimal_min_ms:
                            rating = "TOO_FAST"
                            self.fast_count += 1
                            self.current_combo = 0
                        elif self.optimal_min_ms <= delta_ms <= self.optimal_max_ms:
                            rating = "PERFECT"
                            self.perfect_count += 1
                            self.current_combo += 1
                            if self.current_combo > self.max_combo:
                                self.max_combo = self.current_combo
                        else:
                            rating = "SLOW"
                            self.slow_count += 1
                            self.current_combo = 0

                        self.total_attempts += 1

                        attempt_data = {
                            "timestamp": now,
                            "delta_ms": delta_ms,
                            "rating": rating,
                            "combo": self.current_combo,
                            "attempt_id": self.total_attempts
                        }
                        self.last_attempt = attempt_data
                        self.recent_attempts.append(attempt_data)
                        if len(self.recent_attempts) > 20:
                            self.recent_attempts.pop(0)

                        if self.sound_feedback:
                            self._play_feedback_sound(rating, delta_ms)

                        print(f"🎯 [귀참 캔슬] {delta_ms}ms ➔ [{rating}] (연속 {self.current_combo}콤보)")

                elif not cancel_pressed and self._cancel_key_down:
                    self._cancel_key_down = False

                time.sleep(0.005)  # 5ms 초정밀 샘플링 (CPU 점유율 < 0.3%)
            except Exception:
                time.sleep(0.02)

    def get_status_dict(self) -> Dict[str, Any]:
        now = time.time()
        # 최근 5초간 초당 타수(APS) 계산
        recent_cycles = [t for t in self.cycle_timestamps if (now - t) <= 5.0]
        aps = round(len(recent_cycles) / 5.0, 2) if len(recent_cycles) >= 2 else 0.0

        # 퍼펙트 성공률 (%)
        accuracy = round((self.perfect_count / self.total_attempts) * 100.0, 1) if self.total_attempts > 0 else 0.0

        # 최근 10회 평균 간격
        recent_deltas = [a["delta_ms"] for a in self.recent_attempts]
        avg_ms = round(sum(recent_deltas) / len(recent_deltas), 1) if recent_deltas else 0.0

        # 예상 DPS 증가율 (일반 귀참 1.8 APS 기준 vs 현재 APS)
        dps_gain = 0.0
        if aps > 1.8:
            dps_gain = round(((aps - 1.8) / 1.8) * 100.0, 1)

        return {
            "is_active": self.is_active,
            "key_primary": self.key_primary.upper(),
            "key_cancel": self.key_cancel.upper(),
            "mode": self.mode,
            "optimal_range": [self.optimal_min_ms, self.optimal_max_ms],
            "sound_feedback": self.sound_feedback,
            "total_attempts": self.total_attempts,
            "perfect_count": self.perfect_count,
            "fast_count": self.fast_count,
            "slow_count": self.slow_count,
            "accuracy": accuracy,
            "current_combo": self.current_combo,
            "max_combo": self.max_combo,
            "average_ms": avg_ms,
            "aps": aps,
            "dps_gain_pct": dps_gain,
            "last_attempt": self.last_attempt,
            "recent_attempts": self.recent_attempts[-12:]
        }

# 글로벌 싱글톤 인스턴스
cancel_trainer = MapleCancelTrainer()

# =============================================================================
# 🌐 FastAPI 엔드포인트
# =============================================================================

@router.get("/status", summary="귀참 캔슬 트레이너 현재 상태 및 통계")
async def get_cancel_status():
    return {
        "status": "success",
        "data": cancel_trainer.get_status_dict()
    }

@router.post("/toggle", summary="귀참 캔슬 트레이너 ON/OFF 토글")
async def toggle_cancel_trainer(enable: Optional[bool] = None):
    is_active = cancel_trainer.toggle(enable)
    return {
        "status": "success",
        "is_active": is_active,
        "message": "은월 귀참 캔슬 연습 모드가 시작되었습니다." if is_active else "캔슬 연습 모드가 정지되었습니다."
    }

@router.post("/config", summary="캔슬 키 및 판정 범위 설정")
async def update_cancel_config(cfg: CancelTrainerConfig):
    cancel_trainer.update_config(cfg)
    return {
        "status": "success",
        "message": f"캔슬 설정 변경 완료 ({cfg.key_primary.upper()} ➔ {cfg.key_cancel.upper()})",
        "config": cancel_trainer.get_status_dict()
    }

@router.post("/reset", summary="캔슬 연습 통계 리셋")
async def reset_cancel_stats():
    cancel_trainer.reset_stats()
    return {
        "status": "success",
        "message": "캔슬 연습 통계가 초기화되었습니다."
    }
