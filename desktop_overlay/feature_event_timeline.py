"""
desktop_overlay/feature_event_timeline.py
-----------------------------------------------------------------------------
⏱️ Feature 4: Gold & Objective Event Timeline Engine
-----------------------------------------------------------------------------
- Riot Live Client Data API /eventdata 실시간 파싱
- 킬(FirstBlood/MultiKill/Ace), 드래곤/바론/전령 처치, 포탑 파괴 시계열 리스트
- 킬 스위치(ENABLE_EVENT_TIMELINE) 연동
-----------------------------------------------------------------------------
"""

import logging
from typing import Dict, List, Any, Optional

try:
    from . import config
except ImportError:
    import config

logger = logging.getLogger("EventTimeline")


class EventTimelineEngine:
    """골드 및 오브젝트 이벤트 타임라인 파서"""

    DRAGON_TYPES = {
        "Earth": "대지 드래곤 🟤",
        "Water": "바다 드래곤 🔵",
        "Fire": "화염 드래곤 🔴",
        "Air": "바람 드래곤 ⚪",
        "Hextech": "마법공학 드래곤 ⚡",
        "Chemtech": "화학공학 드래곤 🟢",
        "Elder": "장로 드래곤 👑"
    }

    @classmethod
    def parse_events(cls, events_list: List[Dict[str, Any]], my_team: str = "ORDER") -> List[Dict[str, Any]]:
        """이벤트 목록을 읽어 가독성 높은 타임라인 엔트리로 변환"""
        if not config.ENABLE_EVENT_TIMELINE or not events_list:
            return []

        timeline_entries = []

        for ev in events_list:
            ev_name = ev.get("EventName", "")
            ev_time = float(ev.get("EventTime", 0.0))
            mins, secs = divmod(int(ev_time), 60)
            time_str = f"{mins:02d}:{secs:02d}"

            entry = None

            if ev_name == "GameStart":
                entry = {"time": time_str, "icon": "🏁", "title": "게임 시작", "desc": "소환사의 협곡 전투 개시"}

            elif ev_name == "FirstBlood":
                recipient = ev.get("Recipient", "소환사")
                entry = {"time": time_str, "icon": "🩸", "title": "퍼스트 블러드", "desc": f"{recipient} 첫 킬 달성 (+400G)"}

            elif ev_name == "ChampionKill":
                killer = ev.get("KillerName", "Unknown")
                victim = ev.get("VictimName", "Unknown")
                entry = {"time": time_str, "icon": "⚔️", "title": "챔피언 처치", "desc": f"{killer} ➔ {victim}"}

            elif ev_name == "DragonKill":
                dragon_raw = ev.get("DragonType", "Water")
                dragon_ko = cls.DRAGON_TYPES.get(dragon_raw, f"{dragon_raw} 드래곤")
                killer = ev.get("KillerName", "")
                entry = {"time": time_str, "icon": "🐉", "title": "드래곤 처치", "desc": f"{dragon_ko} ({killer})"}

            elif ev_name == "HeraldKill":
                killer = ev.get("KillerName", "")
                entry = {"time": time_str, "icon": "👾", "title": "협곡의 전령 처치", "desc": f"전령의 눈 획득 ({killer})"}

            elif ev_name == "BaronKill":
                killer = ev.get("KillerName", "")
                entry = {"time": time_str, "icon": "🟣", "title": "내셔 남작(바론) 처치", "desc": f"남작의 손길 버프 획득 ({killer})"}

            elif ev_name == "TurretKilled":
                turret_id = ev.get("TurretKilled", "")
                killer = ev.get("KillerName", "")
                lane = "외곽"
                if "T1" in turret_id: lane = "1차"
                elif "T2" in turret_id: lane = "2차"
                elif "T3" in turret_id: lane = "억제기 포탑"
                entry = {"time": time_str, "icon": "🏰", "title": "포탑 파괴", "desc": f"{lane} 포탑 철거 (+골드 획득)"}

            elif ev_name == "InhibKilled":
                killer = ev.get("KillerName", "")
                entry = {"time": time_str, "icon": "💎", "title": "억제기 파괴", "desc": f"슈퍼 미니언 생성 개시"}

            elif ev_name == "Ace":
                team_acer = ev.get("Acer", "팀")
                entry = {"time": time_str, "icon": "⚡", "title": "에이스 (전원 처치)", "desc": f"{team_acer} 적 전원 소멸"}

            if entry:
                timeline_entries.append(entry)

        # 최신 순 정렬하여 상위 7개 항목 반환
        return timeline_entries[-7:]
