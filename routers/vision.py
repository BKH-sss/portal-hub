"""
routers/vision.py
------------------------------------------------------------
👁️ PC 화면 공유 및 비전(YOLO/Vision Agent) 모니터링 라우터.
- 실시간 화면 캡처 수신 및 선제적 브리핑 (/api/proactive_briefing)
- 화면 공유 감시 주기 설정 (/api/screen_share/config)
- 레인보우 식스 시즈(R6S) 비전 에이전트 수동 토글 (/api/vision/toggle)
------------------------------------------------------------
"""

import subprocess
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from core.state import manager
import core.state as state
from auto_proactive_vision_monitor import auto_monitor

router = APIRouter(tags=["Vision & Screen Monitoring"])

# ============================================================
# 1. Pydantic 요청 스키마 정의
# ============================================================
class ProactiveBriefingRequest(BaseModel):
    """실시간 화면 캡처 데이터 모델"""
    image_b64: Optional[str] = None
    event_type: str = "auto_check"

class ScreenShareConfigRequest(BaseModel):
    """화면 공유 감시 설정 모델"""
    interval: int = 15
    enabled: bool = True

class ToggleVisionRequest(BaseModel):
    """비전 에이전트 토글 요청 모델"""
    enabled: bool

# ============================================================
# 2. 비전 모니터링 엔드포인트
# ============================================================
@router.post("/api/proactive_briefing", summary="15초 주기 실시간 화면 관찰 브리핑")
async def proactive_briefing(req: ProactiveBriefingRequest):
    """
    15초마다 클라이언트 웹에서 전송되는 PC 메인 화면 스크린샷을 수신하여 
    게임, 코딩, 웹서핑 상태를 AI가 선제적으로 인지하고 브리핑을 준비합니다.
    """
    if req.image_b64:
        img_len = len(req.image_b64)
        return {"status": "success", "spoken": False, "briefing": "화면 관찰 정상 진행 중", "received_size": img_len}
    return {"status": "warning", "spoken": False, "briefing": "이미지 데이터 없음"}

@router.post("/api/screen_share/config", summary="화면 공유 감시 엔진 설정")
def config_screen_share(req: ScreenShareConfigRequest):
    """실시간 PC 화면 캡처 엔진의 작동 주기(초)와 활성화 여부를 설정합니다."""
    auto_monitor.interval_seconds = req.interval
    if req.enabled:
        auto_monitor.start()
        msg = f"실시간 PC 화면 캡처 엔진 가동됨 ({req.interval}초 주기)"
    else:
        auto_monitor.stop()
        msg = "실시간 PC 화면 캡처 엔진 중지됨"
    return {
        "status": "success",
        "message": msg,
        "is_running": auto_monitor.is_running,
        "interval": auto_monitor.interval_seconds
    }

@router.post("/api/vision/toggle", summary="R6S 비전 클라이언트 수동 가동/중지")
async def toggle_vision(req: ToggleVisionRequest):
    """레인보우 식스 시즈 전용 실시간 화면 분석 프로세스(vision_agent_real.py)를 토글합니다."""
    if req.enabled:
        if state.vision_process is None or state.vision_process.poll() is not None:
            state.vision_process = subprocess.Popen(["python", "vision_agent_real.py"])
            await manager.broadcast({'content': '\n\n[시스템] 스카디(레식) 비전 클라이언트가 수동으로 활성화되었습니다.\n\n'})
            return {"status": "started"}
    else:
        if state.vision_process and state.vision_process.poll() is None:
            state.vision_process.terminate()
            state.vision_process = None
            await manager.broadcast({'content': '\n\n[시스템] 스카디(레식) 비전 클라이언트가 수동으로 비활성화되었습니다.\n\n'})
            return {"status": "stopped"}
    return {"status": "no_change"}
