"""
desktop_overlay/feature_return_predictor.py
-----------------------------------------------------------------------------
⏳ Feature 3: Laner Return Timing Prediction Engine (Statistical Estimate)
-----------------------------------------------------------------------------
- ⚠️ 라이엇 공정성 가이드 준수: "확정 정보가 아닌 통계적 추정치(예상)"임을 명시
- 라인 상대 사망 시: 리스폰 타이머 + 우물 구매/라인 이동 시간(20~23초) 계산
- "약 N초 후 복귀 예상" 카운트다운 및 웨이브 관리 행동 팁 제공
-----------------------------------------------------------------------------
"""

import logging
from typing import Dict, List, Any, Optional

try:
    from . import config
    from .match_data_provider import LANE_TRAVEL_TIME_ESTIMATES
except ImportError:
    import config
    from match_data_provider import LANE_TRAVEL_TIME_ESTIMATES

logger = logging.getLogger("ReturnPredictor")


class LanerReturnPredictor:
    """라인 상대 복귀 타이밍 통계적 추정 엔진"""

    @classmethod
    def predict_return_timing(cls, all_game_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """상대 라이너의 사망 및 리스폰 상태를 기반으로 라인 복귀 시점 통계적 추정"""
        if not config.ENABLE_RETURN_PREDICTION:
            return None

        active_player = all_game_data.get("activePlayer", {})
        all_players = all_game_data.get("allPlayers", [])

        if not active_player or not all_players:
            return None

        # 1. 내 정보 추출
        my_riot_id = active_player.get("riotId", "") or active_player.get("summonerName", "")
        my_team = "ORDER"
        my_position = "TOP"

        for p in all_players:
            p_id = p.get("riotId", "") or p.get("summonerName", "")
            if p_id == my_riot_id or p.get("summonerName") == active_player.get("summonerName"):
                my_team = p.get("team", "ORDER")
                my_position = p.get("position", "TOP")
                break

        # 2. 맞라인 상대 탐색
        enemy_laner = None
        for p in all_players:
            if p.get("team") != my_team and p.get("position") == my_position:
                enemy_laner = p
                break

        if not enemy_laner:
            # 포지션 없을 시 첫 번째 적
            for p in all_players:
                if p.get("team") != my_team:
                    enemy_laner = p
                    break

        if not enemy_laner:
            return None

        champ_name = enemy_laner.get("championName", "상대 라이너")
        is_dead = enemy_laner.get("isDead", False)
        respawn_timer = float(enemy_laner.get("respawnTimer", 0.0))

        # 라인별 이동 시간 기준치 (초)
        travel_time = LANE_TRAVEL_TIME_ESTIMATES.get(my_position, 22)

        if is_dead and respawn_timer > 0:
            total_return_estimate = int(respawn_timer + travel_time)
            mins, secs = divmod(total_return_estimate, 60)

            return {
                "is_active": True,
                "is_dead": True,
                "champion": champ_name,
                "position": my_position,
                "respawn_remain": int(respawn_timer),
                "estimated_return_seconds": total_return_estimate,
                "estimated_time_str": f"{total_return_estimate}초",
                "label": "⏳ [상대 복귀 예상 (통계적 추정치)]",
                "action_advice": "웨이브를 타워에 완전히 밀어넣고 안전하게 귀환하세요."
            }
        else:
            return {
                "is_active": True,
                "is_dead": False,
                "champion": champ_name,
                "position": my_position,
                "label": "🟢 [상대 라인전 중]",
                "action_advice": "상대 미니언 막타 타이밍에 평타/스킬 딜교환 시도"
            }
