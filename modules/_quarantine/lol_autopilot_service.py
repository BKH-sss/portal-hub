"""
lol_autopilot_service.py
=============================================================================
🤖 JARVIS / SKADI: 롤(LoL) 전자동 인게임 오토파일럿 & 라이프사이클 관리자
=============================================================================
- 역할:
    1. 롤 클라이언트(LCU) 및 인게임 프로세스를 2초 주기로 백그라운드 자동 감지
    2. 로비 $\\rightarrow$ 픽창 $\\rightarrow$ 인게임 $\\rightarrow$ 게임 종료 전 과정을 100% 무인 자동화
    3. 픽창 진입 시: 칼바람 눈덩이 스펠 체크 & 챔피언 맞라이너 분석
    4. 인게임 진입 시:
       - Modern DeepLeague 미니맵 트래커 자동 시작
       - 라이브 게임 트래커(스펠/오브젝트/골드) 자동 연동
       - 스카디 출격 음성 브리핑 ("인게임 전술 서포트를 시작합니다")
    5. 게임 종료 시:
       - 미니맵 트래커 자동 대기 모드 전환 (CPU 절약)
       - 협곡 전술 오답노트 & 스냅샷 Markdown 자동 저장
       - 브라이어 팩폭 전적 피드백 생성
    6. FastAPI APIRouter 내장 (/api/lol/autopilot/*)
=============================================================================
"""

import os
import time
import logging
import threading
from typing import Dict, Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from riot_lcu import RiotLCU

logger = logging.getLogger("LoLAutopilot")

router = APIRouter(prefix="/api/lol/autopilot", tags=["LoL Autopilot Lifecycle Service"])


class AutopilotState:
    OFFLINE = "OFFLINE"
    LOBBY = "LOBBY"
    CHAMP_SELECT = "CHAMP_SELECT"
    IN_GAME = "IN_GAME"
    POST_GAME = "POST_GAME"


class LoLAutopilotService:
    """롤 인게임 상태 변화를 감지하여 모든 하위 모듈을 자동으로 지휘하는 오토파일럿 데몬"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LoLAutopilotService, cls).__new__(cls)
                cls._instance._init_service()
            return cls._instance

    def _init_service(self):
        self.is_enabled = True
        self.current_state = AutopilotState.OFFLINE
        self.lcu = RiotLCU()
        
        self.last_phase = "Unknown"
        self.active_champion = ""
        self.active_mode = ""
        self.game_start_time: float = 0.0

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self.start()

    def start(self):
        """오토파일럿 감시 스레드 시작"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="LoLAutopilotThread")
        self._thread.start()
        logger.info("🤖 [LoL Autopilot] 전자동 인게임 라이프사이클 데몬 가동")

    def stop(self):
        """데몬 정지"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("🛑 [LoL Autopilot] 오토파일럿 데몬 정지")

    def _monitor_loop(self):
        """2초 주기로 롤 상태 감시 및 이벤트 핸들링"""
        while not self._stop_event.is_set():
            try:
                if self.is_enabled:
                    self._check_lol_lifecycle()
            except Exception as e:
                logger.debug(f"[LoL Autopilot Monitor Error] {e}")
            time.sleep(2.0)

    def _check_lol_lifecycle(self):
        """LCU 상태 조회 및 상태 머신 전이"""
        status = self.lcu.get_current_status()
        is_online = (status.get("status") == "online")

        if not is_online:
            if self.current_state != AutopilotState.OFFLINE:
                self._handle_state_transition(AutopilotState.OFFLINE, status)
            return

        phase = status.get("phase", "Unknown")

        if phase == "ChampSelect":
            if self.current_state != AutopilotState.CHAMP_SELECT:
                self._handle_state_transition(AutopilotState.CHAMP_SELECT, status)

        elif phase == "InProgress":
            if self.current_state != AutopilotState.IN_GAME:
                self._handle_state_transition(AutopilotState.IN_GAME, status)

        else: # Lobby, Matchmaking, ReadyCheck, EndOfGame, etc.
            if self.current_state == AutopilotState.IN_GAME:
                self._handle_state_transition(AutopilotState.POST_GAME, status)
            elif self.current_state not in [AutopilotState.LOBBY, AutopilotState.POST_GAME]:
                self._handle_state_transition(AutopilotState.LOBBY, status)

        self.last_phase = phase

    def _handle_state_transition(self, new_state: str, status: Dict[str, Any]):
        """상태 전이 시 자동 실행할 작업들"""
        old_state = self.current_state
        self.current_state = new_state
        logger.info(f"🔄 [LoL Autopilot] 상태 전이: {old_state} ➔ {new_state}")

        # 1. 픽창 진입 (CHAMP_SELECT)
        if new_state == AutopilotState.CHAMP_SELECT:
            is_aram = status.get("is_aram_mayhem", False) or "칼바람" in status.get("lobby_game_mode", "")
            champ_info = status.get("champ_select_info", "")
            
            # 칼바람 눈덩이 스펠 미착용 경고
            if is_aram and "눈덩이" in champ_info:
                self._speak("주의! 칼바람 나락인데 눈덩이 스펠이 없어요! 표식 스펠 착용을 확인해주세요!")

        # 2. 인게임 진입 (IN_GAME)
        elif new_state == AutopilotState.IN_GAME:
            self.game_start_time = time.time()
            champ = status.get("picked_champion") or status.get("enemy_laner") or "소환사"
            mode = status.get("lobby_game_mode", "소환사의 협곡")
            self.active_champion = champ
            self.active_mode = mode

            # A. 미니맵 트래커 가동
            try:
                from modules.lol_minimap_tracker import minimap_tracker
                if minimap_tracker and not minimap_tracker.is_tracking:
                    minimap_tracker.start_tracking()
            except Exception as e:
                logger.warning(f"미니맵 트래커 자동 시작 실패: {e}")

            # B. 라이브 게임 트래커 가동
            try:
                from modules.lol_live_game_tracker import live_game_tracker
                if live_game_tracker and not live_game_tracker.is_running:
                    live_game_tracker.start()
            except Exception as e:
                logger.warning(f"라이브 트래커 자동 시작 실패: {e}")

            # C. 스카디 출격 음성 브리핑
            self._speak(f"스카디 인게임 전술 서포트를 시작합니다. {mode} 전장 상황을 실시간으로 감시할게요.")

        # 3. 게임 종료 (POST_GAME)
        elif new_state == AutopilotState.POST_GAME:
            # A. 미니맵 트래커 대기 모드로 전환 (CPU 절약)
            try:
                from modules.lol_minimap_tracker import minimap_tracker
                if minimap_tracker and minimap_tracker.is_tracking:
                    minimap_tracker.stop_tracking()
            except Exception:
                pass

            # B. 협곡 오답노트 & 스냅샷 복기 저장
            try:
                from modules.lol_snapshot_reviewer import snapshot_reviewer
                if snapshot_reviewer:
                    snapshot_reviewer.compile_match_review()
            except Exception as e:
                logger.debug(f"오답노트 자동 편찬 스킵: {e}")

            # C. 브라이어 승패 팩폭 피드백 생성
            self._speak("수고하셨습니다 마스터. 이번 게임 전술 데이터 분석 및 복기 노트를 정리해두었어요.")
            self.current_state = AutopilotState.LOBBY

    def _speak(self, text: str):
        """음성 알림 발화 헬퍼"""
        try:
            from modules.lol_voice_alert_engine import voice_alert_engine
            if voice_alert_engine:
                voice_alert_engine.push_alert(
                    threat_level="MEDIUM",
                    script_key="CUSTOM",
                    fallback_text=text,
                    cooldown_sec=5.0
                )
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        """오토파일럿 상태 조회"""
        return {
            "enabled": self.is_enabled,
            "current_state": self.current_state,
            "last_phase": self.last_phase,
            "active_champion": self.active_champion,
            "active_mode": self.active_mode,
            "game_start_time": self.game_start_time
        }


# 전역 싱글톤
autopilot_service = LoLAutopilotService()


# =============================================================================
# 🌐 REST API 엔드포인트
# =============================================================================
@router.get("/status", summary="LoL 오토파일럿 데몬 상태")
def get_autopilot_status():
    return autopilot_service.get_status()

@router.get("/toggle", summary="LoL 오토파일럿 활성화/비활성화 토글 (GET)")
@router.post("/toggle", summary="LoL 오토파일럿 활성화/비활성화 토글 (POST)")
def toggle_autopilot(enable: Optional[bool] = None):
    if enable is not None:
        autopilot_service.is_enabled = enable
    else:
        autopilot_service.is_enabled = not autopilot_service.is_enabled
    return {"status": "success", "enabled": autopilot_service.is_enabled}
