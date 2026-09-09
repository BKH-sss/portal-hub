"""
desktop_overlay/riot_live_client.py
-----------------------------------------------------------------------------
🎮 Riot Games Official Live Client Data API Communication Client
-----------------------------------------------------------------------------
- 로컬 포트 127.0.0.1:2999 HTTPS 통신
- 자체 서명 SSL 인증서 안전 처리 (verify=False, 경고 억제)
- 빠른 연결 타임아웃 및 게임 미실행 무부하 감지
-----------------------------------------------------------------------------
"""

import time
import logging
from typing import Dict, List, Any, Optional, Tuple

import requests
import urllib3

# 자체 서명 인증서 경고 숨김 처리
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from . import config
except ImportError:
    import config

logger = logging.getLogger("RiotLiveClient")


class RiotLiveClient:
    """Riot Live Client Data API 통신 엔진"""

    def __init__(self, base_url: str = config.LIVE_CLIENT_URL, timeout: float = config.REQUEST_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = False

    def is_game_active(self) -> bool:
        """인게임 라이브 서버 응답 여부 확인 (빠른 핑)"""
        try:
            url = f"{self.base_url}/gamestats"
            resp = self.session.get(url, timeout=self.timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def get_all_game_data(self) -> Optional[Dict[str, Any]]:
        """전체 게임 데이터 덤프 획득 (/allgamedata)"""
        try:
            url = f"{self.base_url}/allgamedata"
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_active_player(self) -> Optional[Dict[str, Any]]:
        """플레이어 본인 데이터 획득 (/activeplayer)"""
        try:
            url = f"{self.base_url}/activeplayer"
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_all_players(self) -> Optional[List[Dict[str, Any]]]:
        """양 팀 10명 플레이어 데이터 획득 (/allplayers)"""
        try:
            url = f"{self.base_url}/allplayers"
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def get_event_data(self) -> Optional[List[Dict[str, Any]]]:
        """인게임 발생 이벤트 리스트 획득 (/eventdata)"""
        try:
            url = f"{self.base_url}/eventdata"
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "Events" in data:
                    return data["Events"]
                elif isinstance(data, list):
                    return data
        except Exception:
            pass
        return None

    def get_game_stats(self) -> Optional[Dict[str, Any]]:
        """게임 시간 및 모드 통계 획득 (/gamestats)"""
        try:
            url = f"{self.base_url}/gamestats"
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None
