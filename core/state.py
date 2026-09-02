"""
core/state.py
==============================================================================
JARVIS 시스템 전역 상태(State) 및 싱글톤 인스턴스 관리 모듈
==============================================================================
이 모듈은 여러 APIRouter(chat, lol, maple, vision, websocket 등)에서 공통으로
참조하고 공유해야 하는 WebSocket 연결 매니저, 게임 클라이언트 연동 인스턴스,
백그라운드 서브프로세스 핸들 및 런타임 캐시 상태를 한곳에서 안전하게 관리합니다.
==============================================================================
"""

import os
from typing import List, Optional, Dict, Any
from fastapi import WebSocket

from riot_lcu import RiotLCU
from nexon_api import NexonAPI

# ==============================================================================
# 1. 실시간 WebSocket 연결 관리자 (ConnectionManager)
# ==============================================================================
class ConnectionManager:
    """
    웹 브라우저 클라이언트들과의 실시간 WebSocket 연결 풀(Pool)을 관리하고,
    인게임 브리핑, 롤 이벤트, 자율 학습 알림을 전체 접속자에게 브로드캐스트합니다.
    """
    def __init__(self):
        # 현재 연결된 WebSocket 클라이언트 객체 목록
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """새 클라이언트 WebSocket 연결을 수락하고 풀에 등록합니다."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """연결이 종료된 WebSocket을 풀에서 안전하게 제거합니다."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """접속 중인 모든 클라이언트에게 JSON 페이로드를 일괄 전송합니다."""
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

# 전역 싱글톤 WebSocket 매니저 인스턴스 (모든 라우터에서 공용 import)
manager = ConnectionManager()

# ==============================================================================
# 2. 게임 연동 싱글톤 인스턴스
# ==============================================================================
# 롤 라이브 클라이언트(LCU) 연동 인스턴스 (LeagueClientUx.exe 감지 및 매치 조회)
riot_lcu = RiotLCU()

# 넥슨 메이플스토리 Open API 연동 인스턴스 (캐릭터 스펙, 전투력, 장비 조회)
nexon_api = NexonAPI()

# ==============================================================================
# 3. 실시간 런타임 공유 상태 변수 (Shared Memory State)
# ==============================================================================
# 현재 연동된 메이플스토리 캐릭터 상세 데이터 딕셔너리
linked_maple_character: Optional[Dict[str, Any]] = None

# 현재 감지된 롤(LoL) 소환사명, 게임 모드, 플레이 중인 챔피언
current_summoner: str = "Unknown"
current_game_mode: str = "Unknown"
current_champion: str = "Unknown"

# 백그라운드 비전/YOLO 및 화면 감시 서브프로세스 핸들
yolo_process = None
vision_process = None

# Gemini API 누적 호출 카운터 (성능 모니터링용)
gemini_api_calls: int = 0

# 시스템 기능 실시간 토글 플래그
admin_flags: Dict[str, bool] = {
    "auto_learning": True,
    "vision_monitor": False,
    "lol_feedback": True,
    "obsidian_sync": True,
}
