"""
modules/candidates/voice_pitch_tuner.py
=============================================================================
🎙️ [후보 모듈 1] 에이전트 음성(TTS) 피치 & 속도 실시간 튜너 모듈
=============================================================================
- 설명: 각 AI 캐릭터(스카디, 브라이어, 루시, 엔버 등)의 TTS 보이스 속도(Rate),
        음높이(Pitch), 볼륨(Volume)을 개별 맞춤 튜닝하고 프로필을 저장/불러옵니다.
- 연동 방식: brain_server에 마운트 시 /api/voice/tune 엔드포인트 제공.
- 상태: [후보군 - 마스터 검토 및 승인 대기]
=============================================================================
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_PATH = Path("data/voice_tuning_profiles.json")

DEFAULT_PROFILES = {
    "skadi": {"voice": "ko-KR-SunHiNeural", "rate": "+0%", "pitch": "-2Hz", "volume": "+0%"},
    "briar": {"voice": "ko-KR-SunHiNeural", "rate": "+15%", "pitch": "+5Hz", "volume": "+10%"},
    "lucy": {"voice": "ko-KR-SunHiNeural", "rate": "-5%", "pitch": "-4Hz", "volume": "+0%"},
    "angelic": {"voice": "ko-KR-JiMinNeural", "rate": "+10%", "pitch": "+8Hz", "volume": "+5%"},
    "coder": {"voice": "ko-KR-InJoonNeural", "rate": "+0%", "pitch": "-1Hz", "volume": "+0%"}
}

class VoicePitchTuner:
    """캐릭터별 보이스 파라미터 프로필 매니저"""
    
    @classmethod
    def load_profiles(cls) -> Dict[str, Any]:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return DEFAULT_PROFILES.copy()

    @classmethod
    def save_profiles(cls, profiles: Dict[str, Any]):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)

    @classmethod
    def get_agent_voice_params(cls, agent_id: str) -> Dict[str, str]:
        profs = cls.load_profiles()
        return profs.get(agent_id, DEFAULT_PROFILES.get("skadi", {}))

    @classmethod
    def update_agent_voice(cls, agent_id: str, rate: Optional[str] = None, pitch: Optional[str] = None, volume: Optional[str] = None):
        profs = cls.load_profiles()
        if agent_id not in profs:
            profs[agent_id] = DEFAULT_PROFILES.get(agent_id, DEFAULT_PROFILES["skadi"]).copy()
        if rate: profs[agent_id]["rate"] = rate
        if pitch: profs[agent_id]["pitch"] = pitch
        if volume: profs[agent_id]["volume"] = volume
        cls.save_profiles(profs)
        return profs[agent_id]
