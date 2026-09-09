"""
desktop_overlay/feature_core_item_alert.py
-----------------------------------------------------------------------------
🚨 Feature 2: Enemy Core Item Completion Alert Engine
-----------------------------------------------------------------------------
- Live Client Data API allPlayers 아이템 목록의 시계열 diff 감지
- 시야에 노출된 적이 전설/신화급 핵심 완성 아이템을 구매한 즉시 HUD 알림
- 킬 스위치(ENABLE_CORE_ITEM_ALERT) 연동
-----------------------------------------------------------------------------
"""

import time
import logging
from typing import Dict, List, Any, Optional, Set

try:
    from . import config
    from .match_data_provider import CORE_ITEMS_DATABASE
except ImportError:
    import config
    from match_data_provider import CORE_ITEMS_DATABASE

logger = logging.getLogger("CoreItemAlert")


class CoreItemAlertEngine:
    """상대 핵심 아이템 완성 감지 및 알림 엔진"""

    def __init__(self):
        # 플레이어별 감지된 아이템 ID 세트: {riot_id_or_champ: set(item_ids)}
        self._seen_items_by_player: Dict[str, Set[int]] = {}
        # 최근 알림 기록 (만료 관리용): List[Dict[str, Any]]
        self._recent_alerts: List[Dict[str, Any]] = []

    def reset(self):
        """게임 재시작 시 상태 초기화"""
        self._seen_items_by_player.clear()
        self._recent_alerts.clear()

    def process_players(self, all_players: List[Dict[str, Any]], my_team: str, game_time: float) -> List[Dict[str, Any]]:
        """플레이어 아이템 변화를 검사하여 신규 완성 아이템 알림 리스트 반환"""
        if not config.ENABLE_CORE_ITEM_ALERT:
            return []

        new_alerts = []
        mins, secs = divmod(int(game_time), 60)
        time_str = f"{mins:02d}:{secs:02d}"

        for p in all_players:
            # 적 팀 플레이어만 검사
            if p.get("team") == my_team:
                continue

            champ_name = p.get("championName", "Unknown")
            p_id = p.get("riotId", "") or p.get("summonerName", champ_name)
            current_items = p.get("items", [])

            current_item_ids = set()
            for item in current_items:
                item_id = item.get("itemID", 0)
                if item_id > 0:
                    current_item_ids.add(item_id)

            # 최초 등록 시에는 알림 없이 현재 상태만 기록
            if p_id not in self._seen_items_by_player:
                self._seen_items_by_player[p_id] = current_item_ids
                continue

            previous_item_ids = self._seen_items_by_player[p_id]
            # 새롭게 추가된 아이템 감지
            newly_added_ids = current_item_ids - previous_item_ids

            for item_id in newly_added_ids:
                if item_id in CORE_ITEMS_DATABASE:
                    item_meta = CORE_ITEMS_DATABASE[item_id]
                    alert_entry = {
                        "timestamp": time.time(),
                        "game_time_str": time_str,
                        "champion": champ_name,
                        "item_name": item_meta["name"],
                        "item_type": item_meta["type"],
                        "item_tier": item_meta["tier"],
                        "alert_msg": item_meta["alert_msg"]
                    }
                    new_alerts.append(alert_entry)
                    self._recent_alerts.append(alert_entry)
                    logger.info(f"🚨 [아이템 완성 알림] {champ_name} -> {item_meta['name']} ({time_str})")

            # 상태 갱신
            self._seen_items_by_player[p_id] = current_item_ids

        # 오래된 알림 정리 (15초 경과 시 만료)
        now = time.time()
        self._recent_alerts = [a for a in self._recent_alerts if now - a["timestamp"] < 15.0]

        return self._recent_alerts
