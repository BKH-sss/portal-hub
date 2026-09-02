"""
routers/__init__.py
------------------------------------------------------------
JARVIS Brain Server의 도메인별 APIRouter 모듈 패키지.
- portal: 포털, 뉴스, 날씨, 축구, 주식 라우터
- chat: 대화 스트리밍, LLM 오케스트레이션, 도구 실행 라우터
- tts: 음성 합성(GPT-SoVITS & Edge-TTS) 라우터
- lol: 리그 오브 레전드 LCU 연동 & 브라이어 피드백 라우터
- maple: 넥슨 메이플스토리 Open API 라우터
- memory: ChromaDB RAG, 장기 기억, 옵시디언, 수면학습 라우터
- vision: 화면 공유 및 비전 모니터링 라우터
- chess: 스카디 체스 AI 게임 라우터
- websocket: 실시간 WebSocket 통신 라우터
------------------------------------------------------------
"""

from routers.portal import router as portal_router
from routers.chat import router as chat_router
from routers.tts import router as tts_router
from routers.lol import router as lol_router
from routers.maple import router as maple_router
from routers.memory import router as memory_router
from routers.vision import router as vision_router
from routers.chess import router as chess_router
from routers.websocket import router as websocket_router

__all__ = [
    "portal_router",
    "chat_router",
    "tts_router",
    "lol_router",
    "maple_router",
    "memory_router",
    "vision_router",
    "chess_router",
    "websocket_router",
]
