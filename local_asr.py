# -*- coding: utf-8 -*-
"""
local_asr.py
------------
faster-whisper 기반 완전 로컬 음성인식(STT) 모듈.

기존 문제점:
- chatbot.html은 브라우저 내장 webkitSpeechRecognition(Web Speech API)에 의존.
  -> 크롬 계열 브라우저에서만 동작
  -> 음성 데이터가 구글 서버로 전송됨 (로컬/무검열 지향 프로젝트 취지와 안 맞음)

이 모듈은 그 대안으로, 브라우저에서 녹음한 오디오 블롭을 서버로 올리면
로컬 GPU(RTX 4080 Super)에서 faster-whisper로 텍스트 변환해서 돌려줍니다.

설치:
    pip install faster-whisper

brain_server.py 쪽 연동:
    from local_asr import router as asr_router
    app.include_router(asr_router)

프론트엔드(chatbot.html) 쪽 연동 예시는 파일 하단 주석 참고.
"""

import os
import io
import tempfile
import time
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

router = APIRouter()

# 지연 로딩: faster-whisper는 무겁기 때문에 서버 부팅 시가 아니라
# 첫 요청이 들어올 때 로드합니다. (import 실패해도 서버 전체가 죽지 않도록 방어)
_model = None
_model_load_error = None

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")  # tiny/base/small/medium/large-v3
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cuda")  # 4080 Super면 cuda 권장
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "float16")


def _get_model():
    global _model, _model_load_error
    if _model is not None:
        return _model
    if _model_load_error is not None:
        raise RuntimeError(_model_load_error)
    try:
        from faster_whisper import WhisperModel
        print(f"[ASR] faster-whisper 모델 로딩 중... ({WHISPER_MODEL_SIZE}, {WHISPER_DEVICE}/{WHISPER_COMPUTE_TYPE})")
        _model = WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
        print("[ASR] faster-whisper 모델 로딩 완료!")
        return _model
    except Exception as e:
        # CUDA 관련 실패 시 CPU로 1회 자동 폴백 시도
        if WHISPER_DEVICE == "cuda":
            try:
                from faster_whisper import WhisperModel
                print(f"[ASR] CUDA 로딩 실패({e}), CPU로 폴백 시도...")
                _model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
                print("[ASR] CPU 폴백 로딩 완료!")
                return _model
            except Exception as e2:
                _model_load_error = f"faster-whisper 로딩 실패: {e2}"
                raise RuntimeError(_model_load_error)
        _model_load_error = f"faster-whisper 로딩 실패: {e}"
        raise RuntimeError(_model_load_error)


class ASRResponse(BaseModel):
    text: str
    language: str
    duration_sec: float
    processing_ms: float


@router.post("/api/asr", response_model=ASRResponse)
async def transcribe_audio(file: UploadFile = File(...), language: str = "ko"):
    """
    브라우저에서 녹음한 오디오(webm/wav/mp3 등)를 업로드하면 텍스트로 변환합니다.
    STT를 완전히 로컬에서 처리하므로 외부로 음성 데이터가 나가지 않습니다.
    """
    try:
        model = _get_model()
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))

    suffix = os.path.splitext(file.filename or "")[1] or ".webm"
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="빈 오디오 파일입니다.")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        start = time.time()
        segments, info = model.transcribe(
            tmp_path,
            language=language if language else None,
            vad_filter=True,  # 침묵 구간 자동 제거
            beam_size=5,
        )
        text = "".join(seg.text for seg in segments).strip()
        elapsed_ms = round((time.time() - start) * 1000, 1)

        return ASRResponse(
            text=text,
            language=info.language if info else (language or "unknown"),
            duration_sec=round(info.duration, 2) if info else 0.0,
            processing_ms=elapsed_ms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"음성 인식 실패: {e}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@router.get("/api/asr/status")
def asr_status():
    """ASR 모델이 로딩 가능한 상태인지 미리 확인하는 헬스체크 엔드포인트"""
    try:
        _get_model()
        return {"status": "ready", "model_size": WHISPER_MODEL_SIZE, "device": WHISPER_DEVICE}
    except RuntimeError as e:
        return {"status": "unavailable", "reason": str(e)}


# -----------------------------------------------------------------------
# 프론트엔드(chatbot.html) 연동 예시 - JS (MediaRecorder로 녹음 후 업로드)
# -----------------------------------------------------------------------
"""
async function transcribeWithLocalASR(audioBlob) {
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');
    const res = await fetch(`${SERVER_URL}/api/asr?language=ko`, {
        method: 'POST',
        body: formData
    });
    if (!res.ok) throw new Error('ASR 실패');
    const data = await res.json();
    return data.text;
}

// VAD 기반 자동 녹음 종료와 결합하려면 vad_barge_in.js 참고
"""
