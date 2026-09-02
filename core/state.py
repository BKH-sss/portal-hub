"""
core/state.py
------------------------------------------------------------
JARVIS 시스템 전역 상태(State) 및 싱글톤 인스턴스 관리 모듈.
- WebSocket 연결 관리자 (ConnectionManager)
- 게임 연동 싱글톤 (RiotLCU, NexonAPI)
- 백그라운드 프로세스 핸들 (YOLO, 비전 모니터, 드림 엔진)
- 실시간 게임/유저 상태 변수
------------------------------------------------------------
"""

import os
from typing import List, Optional, Dict, Any
from fastapi import WebSocket

from riot_lcu import RiotLCU
from nexon_api import NexonAPI

# ============================================================
# 1. 실시간 WebSocket 연결 관리자
# ============================================================
class ConnectionManager:
    """
    웹 브라우저 클라이언트들과의 실시간 WebSocket 연결을 관리하고,
    인게임 브리핑, 상태 알림, 자동 학습 이벤트 등을 브로드캐스트합니다.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """새 클라이언트 WebSocket 연결 수락 및 등록"""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """연결 끊긴 WebSocket 제거"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """모든 활성 클라이언트에게 JSON 메시지 전송"""
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

# 전역 싱글톤 WebSocket 매니저 인스턴스
manager = ConnectionManager()

# ============================================================
# 2. 게임 연동 싱글톤 인스턴스
# ============================================================
# 롤 라이브 클라이언트(LCU) 연동 인스턴스
riot_lcu = RiotLCU()

# 넥슨 메이플스토리 Open API 연동 인스턴스
nexon_api = NexonAPI()

# ============================================================
# 3. 실시간 런타임 상태 변수 (Shared Memory State)
# ============================================================
# 현재 연동된 메이플스토리 캐릭터 닉네임
linked_maple_character: Optional[str] = None

# 현재 감지된 롤(LoL) 소환사명, 게임 모드, 플레이 중인 챔피언
current_summoner: str = "Unknown"
current_game_mode: str = "Unknown"
current_champion: str = "Unknown"

# 백그라운드 비전/YOLO 서브프로세스 핸들
yolo_process = None
vision_process = None

# Gemini API 누적 호출 카운터
gemini_api_calls: int = 0

# 관리자 실시간 토글 및 자동 기능 플래그
admin_flags: Dict[str, bool] = {
    "auto_learning": True,
    "vision_monitor": False,
    "lol_feedback": True,
    "obsidian_sync": True,
}
