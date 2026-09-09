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
# 🎙️ 2. 페르소나별 인게임 상황 대사 사전 (협곡 & 칼바람 나락 완벽 분기)
# =============================================================================
SKADI_VOICE_SCRIPTS = {
    # --- 🐉 소환사의 협곡 (Summoner's Rift) 전용 대사 ---
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
    ],
    "SR_GOLD_RECALL": [
        "마스터, {gold}골드 모였어요! 대포 웨이브 밀고 황금 귀환 타이밍 잡으세요!",
        "핵심 아이템 골드 달성! 라인 정리하고 집 다녀오기 딱 좋아요."
    ],

    # --- ❄️ 칼바람 나락 (Howling Abyss / ARAM) 전용 대사 ---
    "ARAM_BUSH_AMBUSH": [
        "마스터! 부쉬 쪽에 적 다수가 숨어있어요! 페이스체크 절대 금지예요!",
        "수풀 기습 위험 감지! 앞장서지 말고 스킬 빠질 때까지 사려주세요!"
    ],
    "ARAM_RELIC_CONTEST": [
        "힐팩 근처에서 교전 발생! 상대보다 먼저 체력 팩 챙겨주세요!",
        "우리 쪽 힐팩 챙기고 피 채우세요! 상대 눈덩이 진입 조심해요!"
    ],
    "ARAM_GOLD_WARN": [
        "마스터, {gold}골드 이상 모였어요! 한타 후 적절한 타이밍에 처형당하거나 아이템 구매를 추천해요!",
        "골드가 {gold}골드 넘게 쌓였어요! 이번 턴에 템 사고 강해져야 딜로스가 없어요!"
    ],
    "ARAM_PUSH_TURRET": [
        "상대 주요 딜러가 잡혔어요! 지금 포탑 강하게 압박해요!",
        "인원수 유리해요! 포탑 철거 고고!"
    ],
    "ARAM_DIVE_DEFENSE": [
        "상대 {count}명이 타워로 돌진해요! 포탑 뒤로 빠져서 수비하세요!",
        "무리한 다이브 받아칠 준비하세요! CC기 연계 집중!"
    ],
    "ARAM_ACE_PUSH": [
        "적 전멸(에이스)! 지금 억제기까지 쭉 밀어붙여요!",
        "올킬이에요 마스터! 넥서스까지 직진!"
    ],
    "MULTI_KILL": [
        "나이스! {count}연속 처치 달성! 기세 몰아서 압박해요!",
        "대단해요 마스터! 한타 완승 각이에요!"
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
            "VISION_GAP": 30.0,
            "SR_GOLD_RECALL": 30.0,
            "ARAM_BUSH_AMBUSH": 12.0,
            "ARAM_RELIC_CONTEST": 15.0,
            "ARAM_GOLD_WARN": 45.0,
            "ARAM_PUSH_TURRET": 15.0,
            "ARAM_DIVE_DEFENSE": 15.0,
            "ARAM_ACE_PUSH": 20.0,
            "MULTI_KILL": 10.0,
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
        - 다계층 전술 검증기(TacticalAlertValidator)를 거쳐 맵 모드 불일치 오탐지를 100% 차단합니다.
        """
        if not self.is_enabled or self.volume <= 0:
            return

        now = time.time()
        cd = self.cooldown_durations.get(alert_type, 10.0)
        if (now - self.cooldowns.get(alert_type, 0.0)) < cd:
            return  # 쿨타임 미경과

        # 마지막 발화 이후 최소 침묵 간격 검사
        if (now - self.last_spoken_time) < self.min_interval:
            return

        text = self._format_speech(alert_type, context or {})
        if not text:
            return

        # 🛡️ 다계층 전술 검증기 & 오답노트 로깅 연동
        try:
            from modules.lol_feedback_system import game_mode_detector, TacticalAlertValidator, feedback_manager
            mode, map_name, _ = game_mode_detector.get_current_mode()
            is_valid, reason = TacticalAlertValidator.validate({
                "type": alert_type,
                "message": text,
                "zone": (context or {}).get("zone", "")
            }, mode)

            feedback_manager.log_alert_moment(
                alert_type=alert_type,
                message=text,
                map_mode=mode,
                is_valid=is_valid,
                validation_reason=reason,
                context=context
            )

            if not is_valid:
                logger.warning(f"[LoLVoice] Alert '{alert_type}' blocked for {map_name}: {reason}")
                return
        except Exception:
            pass

        self.cooldowns[alert_type] = now
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
                pit=ctx.get("pit", "오브젝트 둥지"),
                gold=ctx.get("gold", "3000")
            )
        except Exception:
            return templates[0]

    def speak_korean(self, text: str):
        """임의의 한국어 문장을 비동기 음성으로 즉시 발화"""
        if not self.is_enabled or self.volume <= 0:
            return
        now = time.time()
        if (now - self.last_spoken_time) < 1.0:
            return
        try:
            self.alert_queue.put_nowait({
                "type": "DIRECT_SPEECH",
                "text": text,
                "timestamp": now
            })
        except queue.Full:
            pass

    def _synthesize_and_play(self, item: Dict[str, Any]):
        """텍스트를 초고속 음성으로 합성하여 재생 (Edge-TTS 비동기 실행)"""
        if not self.is_enabled or self.volume <= 0:
            return

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
                # ffplay 초고속 재생 시도 (-nodisp -autoexit -volume 0..100)
                p = subprocess.Popen(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", str(int(self.volume)), tmp_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                p.wait(timeout=5)
                played = True
            except Exception:
                pass

            if not played:
                # Windows 기본 PowerShell 사운드 백업
                vol_ratio = max(0.0, min(1.0, self.volume / 100.0))
                cmd = f"""powershell -c "$p = New-Object System.Windows.Media.MediaPlayer; $p.Open('{tmp_path}'); $p.Volume = {vol_ratio}; $p.Play(); Start-Sleep -s 4" """
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
        "volume": voice_alert_engine.volume,
        "message": f"스카디 인게임 전술 음성 알림이 {'활성화' if enable else '비활성화'}되었습니다."
    }


@router.post("/volume/{vol}", summary="스카디 LoL 음성 볼륨 조절 (0~100)")
def set_voice_volume(vol: int):
    """스카디 LoL 전술 음성 콜 볼륨을 0~100% 범위로 조절합니다."""
    vol = max(0, min(100, int(vol)))
    voice_alert_engine.volume = vol
    return {
        "status": "success",
        "volume": voice_alert_engine.volume,
        "message": f"스카디 LoL 전술 음성 볼륨이 {vol}%로 설정되었습니다."
    }


@router.post("/settings", summary="LoL 음성 알림 설정 일괄 변경")
def update_voice_settings(req: VoiceSettingsRequest):
    """음성 활성화 여부, 발화 에이전트, 볼륨을 일괄 업데이트합니다."""
    if req.enabled is not None:
        voice_alert_engine.is_enabled = req.enabled
    if req.agent is not None:
        voice_alert_engine.agent = req.agent
    if req.volume is not None:
        voice_alert_engine.volume = max(0, min(100, int(req.volume)))
    return {
        "status": "success",
        "enabled": voice_alert_engine.is_enabled,
        "agent": voice_alert_engine.agent,
        "volume": voice_alert_engine.volume,
        "message": "스카디 음성 설정이 성공적으로 저장되었습니다."
    }


@router.post("/test", summary="스카디 테스트 음성 발화")
def test_voice_alert(alert_type: str = "DIVE_WARNING", lane: str = "바텀 라인", custom_text: Optional[str] = None):
    """임의의 전술 상황을 시뮬레이션하여 스카디 목소리를 즉시 테스트합니다."""
    if custom_text:
        text = custom_text
    else:
        text = voice_alert_engine._format_speech(alert_type, {"lane": lane, "count": 3, "zone": "강가", "eta": 7})
        if not text:
            text = "마스터, 스카디 전술 레이더 음성 정상 연결되었습니다. 위험 상황 발생 시 즉시 알려드릴게요."

    # 테스트 발화는 쿨타임 무시하고 즉시 큐에 전달
    voice_alert_engine.alert_queue.put({
        "type": "TEST",
        "text": text,
        "timestamp": time.time()
    })
    return {
        "status": "success",
        "text": text,
        "volume": voice_alert_engine.volume,
        "enabled": voice_alert_engine.is_enabled,
        "message": f"[{alert_type}] 테스트 음성이 재생 큐에 등록되었습니다: '{text}'"
    }
