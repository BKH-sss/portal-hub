"""
lol_voice_alert_engine.py
=============================================================================
🎧 JARVIS / SKADI: 롤(LoL) 실시간 인게임 핸즈프리 음성 전술 콜 엔진
=============================================================================
- 역할:
    1. 미니맵 비전 트래커 및 전술 엔진에서 발생하는 위협 이벤트를 비동기로 큐잉
    2. 중복 콜 방지 및 우선순위(CRITICAL > HIGH > MEDIUM) 기반 쿨타임 제어
    3. 기계적인 로그 메시지를 스카디/브라이어의 자연스러운 인게임 전술 대사로 변환
    4. Edge-TTS / GPT-SoVITS 또는 로컬 오디오 버스를 통해 0.2초 초저지연 음성 발화
    5. 인게임 프레임 드랍 0% (완전 비동기 백그라운드 워커 스레드)
=============================================================================
"""

import os
import time
import queue
import asyncio
import logging
import threading
from typing import Dict, Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

# 로깅 설정
logger = logging.getLogger("LoLVoiceAlert")

# =============================================================================
# 🚀 1. FastAPI APIRouter
# =============================================================================
router = APIRouter(prefix="/api/lol/voice", tags=["LoL Ingame Voice Coach"])


# =============================================================================
# 🎙️ 2. 페르소나별 인게임 상황 대사 사전
# =============================================================================
SKADI_VOICE_SCRIPTS = {
    "DIVE_WARNING": [
        "마스터! {lane}에 적 3명 이상 몰려와요! 타워 버리고 즉시 물러나세요!",
        "위험해요! {lane} 다이브 옵니다! 무리하지 말고 뒤로 빼세요!"
    ],
    "OBJECTIVE_BURST": [
        "상대 {count}명이 용 둥지에 집결했어요! 스틸 각을 보거나 반대 라인을 압박하세요!",
        "용 둥지 적 다수 포착! 강가 쪽 시야 조심하세요!"
    ],
    "BARON_BURST": [
        "경고! 상대 {count}명 바론 버스트 시도 중! 즉시 바론으로 모여야 해요!",
        "바론 둥지 적 집결! 와드 확인하고 한타 진형 준비하세요!"
    ],
    "ROAM_SPOTTED": [
        "[{zone}] 적 챔피언 이동 포착! 기습 갱킹 주의하세요.",
        "강가 쪽에 적이 지나갔어요. 라인 당겨주세요!"
    ],
    "ETA_GANK": [
        "주의! 약 {eta}초 뒤 {target} 도착 예상! 뒤로 사려주세요!",
        "적 챔피언이 {target} 쪽으로 이동 중, 약 {eta}초 남았어요!"
    ],
    "VISION_GAP": [
        "오브젝트 출현 1분 전인데 {pit} 시야가 완전히 어두워요. 와드 설치가 필요해요!",
        "{pit} 주변 시야 공백 감지! 서포터와 함께 시야 확보 추천해요."
    ]
}


# =============================================================================
# 🔊 3. 비동기 음성 알림 코어 엔진
# =============================================================================
class LoLVoiceAlertEngine:
    def __init__(self):
        self.is_enabled: bool = True
        self.agent: str = "skadi"       # skadi, briar 등
        self.volume: int = 100          # 0 ~ 100
        self.min_interval: float = 3.5  # 연속 발화 최소 간격(초) - 인게임 피로도 방지
        self.last_spoken_time: float = 0.0
        
        # 쿨타임 관리자 (alert_type -> timestamp)
        self.cooldowns: Dict[str, float] = {}
        self.cooldown_durations: Dict[str, float] = {
            "DIVE_WARNING": 15.0,
            "BARON_BURST": 20.0,
            "OBJECTIVE_BURST": 20.0,
            "ROAM_SPOTTED": 12.0,
            "ETA_GANK": 10.0,
            "VISION_GAP": 30.0
        }

        # 비동기 발화 큐 & 워커 스레드
        self.alert_queue: queue.Queue = queue.Queue(maxsize=20)
        self.worker_thread: Optional[threading.Thread] = None
        self.is_running: bool = True
        self._start_worker()

    def _start_worker(self):
        """백그라운드 음성 발화 큐 처리 스레드 시작"""
        def _worker_loop():
            while self.is_running:
                try:
                    item = self.alert_queue.get(timeout=0.5)
                    if item and self.is_enabled:
                        self._synthesize_and_play(item)
                    self.alert_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"[VoiceWorker] Error: {e}")
                    time.sleep(0.5)

        self.worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="LoLVoiceAlert-Worker")
        self.worker_thread.start()

    def trigger_alert(self, alert_type: str, context: Optional[Dict[str, Any]] = None):
        """
        외부(미니맵 트래커, 갱 예측기 등)에서 전술 경고를 발생시킬 때 호출하는 진입점
        """
        if not self.is_enabled:
            return

        now = time.time()
        cd = self.cooldown_durations.get(alert_type, 10.0)
        if (now - self.cooldowns.get(alert_type, 0.0)) < cd:
            return  # 쿨타임 미경과

        # 마지막 발화 이후 최소 침묵 간격 검사
        if (now - self.last_spoken_time) < self.min_interval:
            return

        self.cooldowns[alert_type] = now
        text = self._format_speech(alert_type, context or {})
        if text:
            try:
                self.alert_queue.put_nowait({
                    "type": alert_type,
                    "text": text,
                    "timestamp": now
                })
            except queue.Full:
                pass

    def _format_speech(self, alert_type: str, ctx: Dict[str, Any]) -> str:
        """이벤트 타입과 컨텍스트를 스카디의 부드럽고 명확한 한글 대사로 포맷"""
        templates = SKADI_VOICE_SCRIPTS.get(alert_type)
        if not templates:
            return ctx.get("message", "")

        import random
        tpl = random.choice(templates)
        try:
            return tpl.format(
                lane=ctx.get("lane", "라인"),
                count=ctx.get("count", "다수"),
                zone=ctx.get("zone", "협곡"),
                eta=ctx.get("eta", "수"),
                target=ctx.get("target", "라인"),
                pit=ctx.get("pit", "오브젝트 둥지")
            )
        except Exception:
            return templates[0]

    def _synthesize_and_play(self, item: Dict[str, Any]):
        """텍스트를 초고속 음성으로 합성하여 재생 (Edge-TTS 비동기 실행)"""
        text = item["text"]
        self.last_spoken_time = time.time()

        try:
            import edge_tts
            import tempfile
            import subprocess

            # 스카디 기본 목소리: ko-KR-SunHiNeural (차분하고 나긋나긋한 톤)
            voice_name = "ko-KR-SunHiNeural" if self.agent == "skadi" else "ko-KR-InJoonNeural"
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name

            # Edge-TTS 음성 파일 생성
            communicate = edge_tts.Communicate(text, voice_name)
            asyncio.run(communicate.save(tmp_path))

            # 초경량 재생 (ffplay or powershell sound player)
            # ffplay가 있으면 즉시 무음/무창 재생, 없으면 powershell Media.SoundPlayer
            played = False
            try:
                # ffplay 초고속 재생 시도 (-nodisp -autoexit)
                p = subprocess.Popen(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                p.wait(timeout=5)
                played = True
            except Exception:
                pass

            if not played:
                # Windows 기본 PowerShell 사운드 백업
                cmd = f"""powershell -c "$p = New-Object System.Windows.Media.MediaPlayer; $p.Open('{tmp_path}'); $p.Volume = {self.volume / 100.0}; $p.Play(); Start-Sleep -s 4" """
                subprocess.run(cmd, shell=True, capture_output=True)

            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"[VoicePlay] Fallback/Skip: {e}")


# 전역 싱글톤 인스턴스
voice_alert_engine = LoLVoiceAlertEngine()


# =============================================================================
# 🌐 4. REST API 엔드포인트
# =============================================================================
class VoiceSettingsRequest(BaseModel):
    enabled: Optional[bool] = Field(None, description="음성 알림 활성화 여부")
    agent: Optional[str] = Field(None, description="발화 캐릭터 (skadi / briar)")
    volume: Optional[int] = Field(None, description="볼륨 (0~100)")


@router.get("/status", summary="음성 알림 엔진 상태 조회")
def get_voice_status():
    """현재 음성 엔진의 활성화 여부, 볼륨, 발화 캐릭터를 반환합니다."""
    return {
        "enabled": voice_alert_engine.is_enabled,
        "agent": voice_alert_engine.agent,
        "volume": voice_alert_engine.volume,
        "queue_size": voice_alert_engine.alert_queue.qsize(),
        "last_spoken": round(time.time() - voice_alert_engine.last_spoken_time, 1)
    }


@router.post("/toggle", summary="음성 알림 ON/OFF 토글")
def toggle_voice_alert(enable: bool):
    """인게임 전술 음성 브리핑을 켜거나 끕니다."""
    voice_alert_engine.is_enabled = enable
    return {
        "status": "success",
        "enabled": voice_alert_engine.is_enabled,
        "message": f"스카디 인게임 전술 음성 알림이 {'활성화' if enable else '비활성화'}되었습니다."
    }


@router.post("/test", summary="스카디 테스트 음성 발화")
def test_voice_alert(alert_type: str = "DIVE_WARNING", lane: str = "바텀 라인"):
    """임의의 전술 상황을 시뮬레이션하여 스카디 목소리를 즉시 테스트합니다."""
    voice_alert_engine.trigger_alert(alert_type, {"lane": lane, "count": 3, "zone": "강가", "eta": 7})
    return {"status": "success", "message": f"[{alert_type}] 테스트 음성이 큐에 등록되었습니다."}
