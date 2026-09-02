"""
routers/websocket.py
==============================================================================
⚡ JARVIS 실시간 WebSocket 양방향 브로드캐스트 라우터
==============================================================================
이 모듈은 웹 브라우저(chatbot.html, portal.html, skadi_chess.html)와
백엔드 서버 간의 영구 지속 실시간 WebSocket 양방향 통신 채널(/ws)을 제공합니다.

주요 역할:
  - 롤(LoL) 실시간 킬/데스/용 획득 이벤트 즉각 브로드캐스트
  - 비전 감시 상태 알림 및 자율 학습 완료 이벤트 알림
  - 클라이언트 핑-퐁 연결 생존 확인
==============================================================================
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.state import manager

router = APIRouter(tags=["WebSocket"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    ⚡ [WebSocket 핸들러]
    1) 클라이언트 접속 시 연결을 수락(accept)하고 전역 ConnectionManager 활성 목록에 등록합니다.
    2) 클라이언트가 보낸 텍스트를 수신 대기하며 연결을 유지합니다.
    3) 브라우저 탭을 닫거나 네트워크가 끊기면 안전하게 목록에서 제거(disconnect)합니다.
    """
    await manager.connect(websocket)
    try:
        while True:
            # 클라이언트로부터 메시지 수신 (Keep-Alive 유지)
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
