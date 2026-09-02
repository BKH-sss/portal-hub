"""
modules/candidates/game_sound_effect_pack.py
=============================================================================
🔔 [후보 모듈 3] LoL/메이플 인게임 알림 효과음 팩 모듈
=============================================================================
- 설명: 3000G 골드 달성, 힐팩 10초 전 리젠, 메이플 스킬 쿨타임 완료 시
        시각/청각적 만족감을 극대화하는 인게임 효과음 사운드 트리거.
- 상태: [후보군 - 마스터 검토 및 승인 대기]
=============================================================================
"""

import os
from pathlib import Path
from typing import Dict, Any

class GameSoundEffectPack:
    """게임 트리거별 사운드 효과음 라우팅 매니저"""

    SOUND_MAP = {
        "lol_gold_reach": "sounds/lol_gold_ding.wav",
        "lol_relic_soon": "sounds/lol_heal_ping.wav",
        "lol_snowball": "sounds/lol_snowball_whoosh.wav",
        "maple_skill_ready": "sounds/maple_buff_ready.wav",
        "system_alert": "sounds/jarvis_notify.wav"
    }

    @classmethod
    def get_sound_event(cls, event_name: str) -> Dict[str, Any]:
        sound_rel = cls.SOUND_MAP.get(event_name, "")
        return {
            "event": event_name,
            "sound_file": sound_rel,
            "available": Path(sound_rel).exists() if sound_rel else False
        }
