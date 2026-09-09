"""
desktop_overlay/main.py
-----------------------------------------------------------------------------
🏆 LoL Local Desktop Overlay Application - Main Entry Point
-----------------------------------------------------------------------------
- Riot Live Client Data API (127.0.0.1:2999) 1Hz 백그라운드 폴링
- 게임 시작 시 오버레이 자동 등장, 게임 종료 시 자동 대기/숨김 (0 부하)
- 4대 정식 기능 (딜교 팁, 아이템 완성, 복귀 예상, 타임라인) 통합 연동
-----------------------------------------------------------------------------
"""

import sys
import time
import threading
import logging
from pathlib import Path

# 경로 설정
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

try:
    from . import config
    from .riot_live_client import RiotLiveClient
    from .feature_early_lane_tips import EarlyLaneTipsEngine
    from .feature_core_item_alert import CoreItemAlertEngine
    from .feature_return_predictor import LanerReturnPredictor
    from .feature_event_timeline import EventTimelineEngine
    from .overlay_window import OverlayWindow
except ImportError:
    import config
    from riot_live_client import RiotLiveClient
    from feature_early_lane_tips import EarlyLaneTipsEngine
    from feature_core_item_alert import CoreItemAlertEngine
    from feature_return_predictor import LanerReturnPredictor
    from feature_event_timeline import EventTimelineEngine
    from overlay_window import OverlayWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [LoLOverlay] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("MainOverlayApp")


class LoLOverlayApp:
    """오버레이 라이프사이클 관리자"""

    def __init__(self):
        self.client = RiotLiveClient()
        self.window = OverlayWindow()
        self.item_alert_engine = CoreItemAlertEngine()
        self._is_running = True

    def _polling_worker(self):
        """백그라운드 데이터 수집 및 엔진 처리 스레드"""
        logger.info("🎮 LoL 라이브 클라이언트 모니터링 스레드 시작 (127.0.0.1:2999)")
        was_in_game = False

        while self._is_running:
            try:
                # 1. 게임 활성화 여부 검사
                is_active = self.client.is_game_active()

                if not is_active:
                    if was_in_game:
                        logger.info("🏁 게임 종료 감지 -> 오버레이 대기 모드 전환")
                        self.item_alert_engine.reset()
                        was_in_game = False
                    
                    # 대기 상태 렌더링
                    state = {
                        "is_in_game": False,
                        "game_time_str": "00:00",
                        "my_champion": "대기 중",
                        "lane_tip": None,
                        "item_alerts": [],
                        "return_prediction": None,
                        "timeline": []
                    }
                    self.window.root.after(0, self.window.update_data, state)
                    time.sleep(config.POLL_INTERVAL_STANDBY)
                    continue

                # 2. 게임 중인 경우 전체 데이터 수집
                all_data = self.client.get_all_game_data()
                if not all_data:
                    time.sleep(config.POLL_INTERVAL_IN_GAME)
                    continue

                if not was_in_game:
                    logger.info("⚔️ 롤 인게임 감지! 오버레이 HUD 활성화")
                    was_in_game = True
                    self.window.root.after(0, self.window.show)

                # 게임 시간 및 플레이어 팀 판별
                game_data = all_data.get("gameData", {})
                game_time = float(game_data.get("gameTime", 0.0))
                mins, secs = divmod(int(game_time), 60)
                game_time_str = f"{mins:02d}:{secs:02d}"

                active_player = all_data.get("activePlayer", {})
                all_players = all_data.get("allPlayers", [])
                events_list = all_data.get("events", {}).get("Events", [])

                my_team = "ORDER"
                my_champ = "Champion"
                my_id = active_player.get("riotId", "") or active_player.get("summonerName", "")
                for p in all_players:
                    p_id = p.get("riotId", "") or p.get("summonerName", "")
                    if p_id == my_id or p.get("summonerName") == active_player.get("summonerName"):
                        my_team = p.get("team", "ORDER")
                        my_champ = p.get("championName", "Champion")
                        break

                # 3. 4대 기능 데이터 산출
                lane_tip = EarlyLaneTipsEngine.get_matchup_tip(all_data)
                item_alerts = self.item_alert_engine.process_players(all_players, my_team, game_time)
                return_pred = LanerReturnPredictor.predict_return_timing(all_data)
                timeline = EventTimelineEngine.parse_events(events_list, my_team)

                state = {
                    "is_in_game": True,
                    "game_time_str": game_time_str,
                    "my_champion": my_champ,
                    "lane_tip": lane_tip,
                    "item_alerts": item_alerts,
                    "return_prediction": return_pred,
                    "timeline": timeline
                }

                # 4. GUI 스레드로 안전 전달
                self.window.root.after(0, self.window.update_data, state)

            except Exception as e:
                logger.debug(f"폴링 루프 예외: {e}")

            time.sleep(config.POLL_INTERVAL_IN_GAME)

    def start(self):
        """앱 시작"""
        # 백그라운드 워커 스레드 가동
        th = threading.Thread(target=self._polling_worker, daemon=True)
        th.start()

        # 메인 UI 루프 실행
        try:
            self.window.run_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self._is_running = False


if __name__ == "__main__":
    app = LoLOverlayApp()
    app.start()
