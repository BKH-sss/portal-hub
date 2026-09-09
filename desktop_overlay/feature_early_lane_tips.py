"""
desktop_overlay/feature_early_lane_tips.py
-----------------------------------------------------------------------------
⚔️ Feature 1: Early Laning Trade Tips Engine (Level 1~4 Matchup Guidance)
-----------------------------------------------------------------------------
- 게임 시작 ~ 6분 (1~4레벨 라인전 초반) 실시간 상성 브리핑
- 내 챔피언과 상대 맞라인 챔피언 딜교환 타이밍 및 핵심 전략 안내
-----------------------------------------------------------------------------
"""

import logging
from typing import Dict, List, Any, Optional

try:
    from . import config
    from .match_data_provider import CHAMPION_EARLY_LANE_TIPS, DEFAULT_LANE_TIP
except ImportError:
    import config
    from match_data_provider import CHAMPION_EARLY_LANE_TIPS, DEFAULT_LANE_TIP

logger = logging.getLogger("EarlyLaneTips")


class EarlyLaneTipsEngine:
    """초반 라인 딜 교환 팁 엔진"""

    @classmethod
    def get_matchup_tip(cls, all_game_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """라이브 게임 데이터에서 맞라인 상성을 분석하여 딜교 팁 생성"""
        if not config.ENABLE_EARLY_LANE_TIPS:
            return None

        game_data = all_game_data.get("gameData", {})
        game_time = float(game_data.get("gameTime", 0.0))

        # 게임 시간 6분(360초) 초과 시 초반 라인전 단계 종료로 간주
        if game_time > 360.0:
            return {
                "is_active": False,
                "reason": "초반 라인전 단계 종료 (6분 초과)"
            }

        active_player = all_game_data.get("activePlayer", {})
        all_players = all_game_data.get("allPlayers", [])

        if not active_player or not all_players:
            return None

        # 1. 내 챔피언 정보 및 팀/포지션 탐색
        my_riot_id = active_player.get("riotId", "") or active_player.get("summonerName", "")
        my_champ = ""
        my_team = ""
        my_position = ""

        for p in all_players:
            p_id = p.get("riotId", "") or p.get("summonerName", "")
            if p_id == my_riot_id or p.get("summonerName") == active_player.get("summonerName"):
                my_champ = p.get("championName", "")
                my_team = p.get("team", "ORDER")
                my_position = p.get("position", "")
                break

        if not my_champ:
            return None

        # 2. 상대 맞라인 챔피언 탐색 (같은 position 우선)
        enemy_laner = None
        for p in all_players:
            if p.get("team") != my_team:
                if my_position and p.get("position") == my_position:
                    enemy_laner = p
                    break

        # 포지션 매칭 안될 시 첫 번째 적 플레이어 폴백
        if not enemy_laner:
            for p in all_players:
                if p.get("team") != my_team:
                    enemy_laner = p
                    break

        enemy_champ = enemy_laner.get("championName", "Enemy") if enemy_laner else "Enemy"

        # 3. 매치업 팁 데이터 추출
        my_tip_data = CHAMPION_EARLY_LANE_TIPS.get(my_champ, DEFAULT_LANE_TIP)
        enemy_tip_data = CHAMPION_EARLY_LANE_TIPS.get(enemy_champ, DEFAULT_LANE_TIP)

        mins, secs = divmod(int(game_time), 60)
        time_str = f"{mins:02d}:{secs:02d}"

        return {
            "is_active": True,
            "game_time": time_str,
            "my_champion": my_champ,
            "enemy_champion": enemy_champ,
            "my_name_ko": my_tip_data.get("name_ko", my_champ),
            "enemy_name_ko": enemy_tip_data.get("name_ko", enemy_champ),
            "spike_level": my_tip_data.get("spike_level", 2),
            "my_style": my_tip_data.get("style", "안정적 파밍"),
            "my_advantage_tip": my_tip_data.get("tip_advantage", "선 2레벨 달성 시 과감한 딜교환 시도"),
            "enemy_counter_tip": enemy_tip_data.get("counter_tip", "상대 주요 스킬이 빗나간 후 딜교환 진입")
        }
