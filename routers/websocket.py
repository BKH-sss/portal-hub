"""
routers/websocket.py
------------------------------------------------------------
⚡ JARVIS 실시간 WebSocket 양방향 통신 라우터.
- 웹 브라우저 클라이언트 연결 관리 (/ws)
- 인게임 이벤트, TTS 대사, RAG 지식 학습 알림 브로드캐스트
------------------------------------------------------------
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.state import manager

router = APIRouter(tags=["WebSocket"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    클라이언트 웹 브라우저와 영구 WebSocket 연결을 맺고,
    실시간 브리핑, 게임 이벤트, 인게임 음성 트리거를 수신 대기합니다.
    """
    await manager.connect(websocket)
    try:
        while True:
            # 클라이언트로부터 수신된 메시지를 대기 (핑/퐁 유지)
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
