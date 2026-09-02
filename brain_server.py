"""
brain_server.py
==============================================================================
🤖 JARVIS / NEXT PULSE 통합 AI 백엔드 서버 (FastAPI Main Entrypoint)
==============================================================================
- 아키텍처: 모듈형 마이크로 라우팅 구조 (FastAPI APIRouter 기반)
- 주요 기능:
    ├── 🏛️ routers/portal.py    : 4차 산업 포털, 실시간 날씨, 맨유 축구, 주식 퀀트 리포트
    ├── 💬 routers/chat.py      : 멀티 에이전트 스트리밍 대화, LLM 오케스트레이션, 도구 실행
    ├── 🔊 routers/tts.py       : 로컬 GPT-SoVITS 및 MS Edge-TTS 고성능 음성 합성
    ├── ⚔️ routers/lol.py       : 롤(LoL) 실시간 LCU 연동 & 브라이어 인게임 피드백
    ├── 🍁 routers/maple.py     : 넥슨 메이플스토리 공식 Open API 캐릭터/장비 연동
    ├── 🧠 routers/memory.py    : ChromaDB RAG 벡터 지식, 장기 기억, 옵시디언 자동화, 수면학습
    ├── 👁️ routers/vision.py    : 실시간 PC 화면 캡처 및 YOLO/비전 모니터링
    ├── ♟️ routers/chess.py     : 스카디 체스 AI 자율 대전 및 오프닝 기보 분석
    └── ⚡ routers/websocket.py : 실시간 양방향 WebSocket 브로드캐스트
==============================================================================
"""

import os
import sys
import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# 1. 전역 설정 및 환경 변수 로드
from config import BASE_DIR, MEMORY_DIR, API_KEYS
from core.utils import safe_static_path
from local_asr import router as asr_router

# 2. 도메인별 분리된 API 라우터 임포트
from routers import (
    portal_router,
    chat_router,
    tts_router,
    lol_router,
    maple_router,
    memory_router,
    vision_router,
    chess_router,
    websocket_router
)

# ==============================================================================
# 🚀 3. FastAPI 메인 애플리케이션 생성 및 미들웨어 설정
# ==============================================================================
app = FastAPI(
    title="JARVIS / NEXT PULSE Brain Server",
    description="지능형 멀티 에이전트 & 실시간 포털 허브 통합 백엔드",
    version="3.0.0"
)

# CORS (Cross-Origin Resource Sharing) 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 🧩 4. 기능별 APIRouter 등록 (Include Routers)
# ==============================================================================
app.include_router(portal_router)     # 🏛️ 포털, 날씨, 축구, 뉴스, 주식
app.include_router(chat_router)       # 💬 멀티 에이전트 대화, LLM, 도구 실행
app.include_router(tts_router)        # 🔊 GPT-SoVITS & Edge-TTS 음성 합성
app.include_router(lol_router)        # ⚔️ 롤 LCU 연동 & 인게임 브리핑
app.include_router(maple_router)      # 🍁 넥슨 메이플스토리 Open API
app.include_router(memory_router)     # 🧠 ChromaDB RAG 지식 & 수면학습
app.include_router(vision_router)     # 👁️ PC 화면 공유 & 비전 감시
app.include_router(chess_router)      # ♟️ 체스 AI 자율 대전 & 기보
app.include_router(websocket_router)  # ⚡ 실시간 웹소켓 통신
app.include_router(asr_router)        # 🎙️ 로컬 음성 인식 (Whisper ASR)

# ==============================================================================
# 📁 5. 정적 리소스 디렉터리 마운트
# ==============================================================================
# 1) 기본 이미지 폴더
if os.path.exists("images"):
    app.mount("/images", StaticFiles(directory="images"), name="images")

# 2) Stable Diffusion 생성 이미지 폴더
SD_IMAGES_DIR = os.path.join(str(MEMORY_DIR), "images")
os.makedirs(SD_IMAGES_DIR, exist_ok=True)
app.mount("/sd_images", StaticFiles(directory=SD_IMAGES_DIR), name="sd_images")

# ==============================================================================
# 🌐 6. 프론트엔드 핵심 웹페이지 라우트
# ==============================================================================
@app.get("/api/health", summary="서버 헬스 체크")
async def health_check():
    """서버 가동 및 신경망 준비 상태 확인 엔드포인트"""
    return {"status": "ok", "ready": True, "version": "3.0.0"}

@app.get("/chatbot.html", summary="챗봇 UI 서빙")
def read_chatbot():
    return FileResponse("chatbot.html")

@app.get("/global", summary="ORBIS 해외 외신 포털 서빙")
@app.get("/global/", summary="ORBIS 해외 외신 포털 서빙 (슬래시)")
def read_global_portal():
    global_index = os.path.join("global", "index.html")
    if os.path.exists(global_index):
        return FileResponse(global_index)
    if os.path.exists("global.html"):
        return FileResponse("global.html")
    return FileResponse("index.html")

@app.get("/{filename}", summary="안전한 정적 파일 서빙")
def read_static_file(filename: str):
    """HTML, CSS, JS, 이미지 등 정적 웹 에셋을 안전하게 서빙합니다."""
    path = safe_static_path(".", filename)
    if path:
        return FileResponse(path)

    path = safe_static_path("images", filename)
    if path:
        return FileResponse(path)

    if os.path.exists(filename) and os.path.isfile(filename):
        return FileResponse(filename)

    return FileResponse("index.html")

# ==============================================================================
# ⚡ 7. 서버 라이프사이클 이벤트 (Startup & Shutdown)
# ==============================================================================
@app.on_event("startup")
async def on_server_startup():
    print("=" * 60)
    print("🚀 [JARVIS Brain Server 3.0] 모듈형 아키텍처 가동 완료!")
    print("   • 포털 메인:  http://127.0.0.1:8000/portal")
    print("   • AI 챗봇:    http://127.0.0.1:8000/chatbot.html")
    print("   • 외신(ORBIS): http://127.0.0.1:8000/global/")
    print("   • API 문서:   http://127.0.0.1:8000/docs (Swagger UI)")
    print("=" * 60)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("brain_server:app", host="0.0.0.0", port=8000, reload=True)
