"""
routers/tts.py
==============================================================================
🔊 JARVIS 고성능 음성 합성(TTS) 라우터
==============================================================================
이 모듈은 AI 비서의 답변 텍스트를 사람의 목소리로 실시간 합성하는 음성 엔진 라우터입니다.
- 스카디(보카디)/브라이어: 로컬 그래픽카드를 활용하는 GPT-SoVITS AI 음성 복제 모델(9880 포트)
- 기타 에이전트/일반 대화: 0.1초 만에 응답하는 Microsoft Edge-TTS 신경망 고속 음성 합성

주요 엔드포인트:
  1) POST /tts                : 실시간 텍스트 음성 변환 (WAV/MP3 스트리밍)
  2) GET  /api/sovits_status  : 로컬 GPT-SoVITS 음성 복제 서버 가동 여부 점검
==============================================================================
"""

import io
import re
import os
import time
import tempfile
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
import edge_tts
from config import GPT_SOVITS_URL, BASE_DIR

router = APIRouter(tags=["TTS Voice Engine"])

# ==============================================================================
# 1. Pydantic 요청 스키마 정의
# ==============================================================================
class TTSRequest(BaseModel):
    """음성 합성 요청 모델"""
    text: str                       # 음성으로 읽어줄 텍스트 본문
    agent: str = "skadi"            # 발화할 캐릭터 ID (skadi, briar, angelic, coder, lucy 등)

# 캐릭터별 Microsoft Edge-TTS 고품질 한국어 뉴럴 보이스 매핑
EDGE_VOICE_MAP = {
    "angelic": "ko-KR-SunHiNeural",   # 밝고 활기찬 아이돌 보이스
    "briar": "ko-KR-InJoonNeural",    # 개구쟁이 목소리
    "lucy": "ko-KR-JiMinNeural",      # 차분하고 시크한 사이버펑크 톤
    "coder": "ko-KR-InJoonNeural",    # 정확하고 명쾌한 개발자 톤
    "assistant": "ko-KR-SunHiNeural", # 부드러운 기본 안내 비서
    "stock": "ko-KR-InJoonNeural",    # 냉철하고 신뢰도 높은 금융 분석 톤
}

# ==============================================================================
# 2. TTS 음성 생성 엔드포인트 (/tts)
# ==============================================================================
@router.post("/tts", summary="실시간 텍스트 음성 변환 (TTS)")
async def generate_tts(req: TTSRequest):
    """
    🎯 [음성 합성 파이프라인]
    1) 지문 기호 정제: 대괄호 [], 괄호 (), 별표 ** 등 AI의 속마음/지문 텍스트를 깔끔하게 제거.
    2) 로컬 GPT-SoVITS 호출 (우선순위 1):
       - 'skadi' 계열이나 'briar'는 로컬 AI 보이스 엔진(http://127.0.0.1:9880)으로 합성.
    3) Microsoft Edge-TTS 고속 생성 (우선순위 2 / Fallback):
       - 로컬 SoVITS가 꺼져있거나 다른 캐릭터인 경우 0.1초 만에 MP3 스트림으로 전송.
    """
    # --------------------------------------------------------
    # 1단계: 불필요한 시스템 지문/기호 필터링
    # --------------------------------------------------------
    clean_text = re.sub(r'\[.*?\]', '', req.text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text)
    clean_text = re.sub(r'\*.*?\*', '', clean_text)
    clean_text = clean_text.strip()
    
    if not clean_text:
        return {"status": "skipped", "message": "발화할 유효한 텍스트가 없습니다."}

    # --------------------------------------------------------
    # 2단계: 로컬 GPT-SoVITS AI 음성 합성 시도
    # --------------------------------------------------------
    if req.agent.startswith("skadi") or req.agent == "briar":
        try:
            def _call_sovits():
                payload = {
                    "text": clean_text,
                    "text_lang": "ko",
                    "ref_audio_path": "",
                    "prompt_text": "",
                    "prompt_lang": "ko",
                    "top_k": 5,
                    "top_p": 1,
                    "temperature": 1,
                    "speed": 1.0
                }
                res = requests.post(f"{GPT_SOVITS_URL}/tts", json=payload, timeout=5.0)
                if res.status_code == 200:
                    return res.content
                return None

            wav_bytes = await run_in_threadpool(_call_sovits)
            if wav_bytes:
                return StreamingResponse(io.BytesIO(wav_bytes), media_type="audio/wav")
        except Exception:
            # GPT-SoVITS 가동 실패 시 자동으로 Edge-TTS로 우아하게 전환(Fallback)
            pass

    # --------------------------------------------------------
    # 3단계: Microsoft Edge-TTS 초고속 클라우드 뉴럴 보이스 스트리밍
    # --------------------------------------------------------
    voice_name = EDGE_VOICE_MAP.get(req.agent, "ko-KR-SunHiNeural")
    communicate = edge_tts.Communicate(clean_text, voice_name)
    
    audio_stream = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_stream.write(chunk["data"])
            
    audio_stream.seek(0)
    return StreamingResponse(audio_stream, media_type="audio/mpeg")

# ==============================================================================
# 3. 음성 엔진 상태 점검 API
# ==============================================================================
@router.get("/api/sovits_status", summary="GPT-SoVITS 엔진 상태 확인")
def get_sovits_status():
    """로컬 GPT-SoVITS 음성 복제 서버(127.0.0.1:9880)의 활성화 여부를 조회합니다."""
    try:
        r = requests.get(f"{GPT_SOVITS_URL}/", timeout=1.0)
        return {"online": r.status_code == 200, "url": GPT_SOVITS_URL}
    except Exception:
        return {"online": False, "url": GPT_SOVITS_URL}
