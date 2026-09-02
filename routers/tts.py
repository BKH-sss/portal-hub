"""
routers/tts.py
------------------------------------------------------------
🔊 JARVIS 고성능 음성 합성(TTS) 라우터.
- GPT-SoVITS 로컬 AI 음성 복제 엔진 (스카디/브라이어 보이스)
- Microsoft Edge-TTS 초고속 신경망 음성 스트리밍 (0.1초 반응속도)
- 지문/태그 필터링 및 텍스트 정제
------------------------------------------------------------
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

# ============================================================
# 1. Pydantic 요청 스키마 정의
# ============================================================
class TTSRequest(BaseModel):
    """음성 합성 요청 모델"""
    text: str
    agent: str = "skadi"

# 캐릭터별 Edge-TTS 음성 매핑
EDGE_VOICE_MAP = {
    "angelic": "ko-KR-SunHiNeural",
    "briar": "ko-KR-InJoonNeural",
    "lucy": "ko-KR-JiMinNeural",
    "coder": "ko-KR-InJoonNeural",
    "assistant": "ko-KR-SunHiNeural",
    "stock": "ko-KR-InJoonNeural",
}

# ============================================================
# 2. TTS 생성 엔드포인트 (/tts)
# ============================================================
@router.post("/tts", summary="실시간 텍스트 음성 변환 (TTS)")
async def generate_tts(req: TTSRequest):
    """
    1) 대괄호[], 괄호(), 별표* 등 지문 및 내부 생각을 필터링합니다.
    2) 'skadi', 'briar' 등 고유 캐릭터는 로컬 GPT-SoVITS(127.0.0.1:9880)로 실시간 합성합니다.
    3) 그 외 에이전트는 Microsoft Edge-TTS로 0.1초 만에 MP3 스트리밍합니다.
    """
    # 불필요한 시스템 지문/기호 정제
    clean_text = re.sub(r'\[.*?\]', '', req.text)
    clean_text = re.sub(r'\(.*?\)', '', clean_text)
    clean_text = re.sub(r'\*.*?\*', '', clean_text)
    clean_text = clean_text.strip()
    
    if not clean_text:
        raise HTTPException(status_code=204, detail="No speakable text")

    # 1순위: 로컬 GPT-SoVITS 캐릭터 보이스 (스카디 / 브라이어)
    if req.agent in ["skadi", "skadi_r6s", "briar"]:
        try:
            ref_audio = str(BASE_DIR / "korean_skadi_voice" / "kor_skadi_ref_000.wav")
            payload = {
                "text": clean_text,
                "text_lang": "ko",
                "ref_audio_path": ref_audio,
                "prompt_text": "바닷물에서 떨어지면 우리 같은 건 살아남지 못할 줄 알았어?",
                "prompt_lang": "ko"
            }
            res = await run_in_threadpool(requests.post, f"{GPT_SOVITS_URL}/tts", json=payload, timeout=60)
            if res.status_code == 200:
                temp_path = os.path.join(tempfile.gettempdir(), f"gptsovits_skadi_{int(time.time()*1000)}.wav")
                with open(temp_path, "wb") as f:
                    f.write(res.content)
                return FileResponse(temp_path, media_type="audio/wav")
        except Exception:
            # SoVITS 서버가 꺼져있을 경우 Edge-TTS로 부드럽게 Fallback
            pass

    # 2순위 / 기본값: Microsoft Edge-TTS 신경망 고속 음성
    voice = EDGE_VOICE_MAP.get(req.agent, "ko-KR-SunHiNeural")
    try:
        communicate = edge_tts.Communicate(clean_text, voice, rate="+15%")
        byte_io = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                byte_io.write(chunk["data"])
        
        byte_io.seek(0)
        return StreamingResponse(byte_io, media_type="audio/mp3")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Edge-TTS 오류: {str(e)}")

@router.get("/api/sovits_status", summary="GPT-SoVITS 로컬 서버 상태 확인")
def get_sovits_status():
    """로컬 GPT-SoVITS 서버(127.0.0.1:9880)의 온라인 여부를 반환합니다."""
    try:
        r = requests.get(f"{GPT_SOVITS_URL}/", timeout=1)
        return {"online": True, "url": GPT_SOVITS_URL}
    except Exception:
        return {"online": False, "url": GPT_SOVITS_URL}
