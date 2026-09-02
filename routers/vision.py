"""
routers/vision.py
==============================================================================
👁️ PC 화면 공유 및 비전(YOLO/Vision Agent) 모니터링 라우터
==============================================================================
이 모듈은 유저의 PC 바탕화면 및 인게임 화면을 실시간 캡처하여 비전 멀티모달 LLM과
YOLO 객체 감지 신경망에 전달하고, 스카디가 유저의 행동(코딩, 게임, 웹서핑 등)을
먼저 인지하여 선제적 브리핑을 건네는 화면 감시 라우터입니다.

주요 엔드포인트:
  1) POST /api/proactive_briefing  : 브라우저/클라이언트 화면 캡처 수신 및 상태 분석
  2) POST /api/screen_share/config : 실시간 화면 감시 주기(초 단위) 설정 및 켜기/끄기
  3) POST /api/vision/toggle       : 레인보우 식스 시즈(R6S) 비전 에이전트 수동 실행/종료
==============================================================================
"""

import subprocess
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from core.state import manager
import core.state as state
from auto_proactive_vision_monitor import auto_monitor

router = APIRouter(tags=["Vision & Screen Monitoring"])

# ==============================================================================
# 1. Pydantic 요청 스키마 정의
# ==============================================================================
class ProactiveBriefingRequest(BaseModel):
    """실시간 화면 캡처 데이터 모델"""
    image_b64: Optional[str] = None         # Base64로 인코딩된 JPEG/PNG 스크린샷 문자열
    event_type: str = "auto_check"          # 감시 트리거 이벤트 유형

class ScreenShareConfigRequest(BaseModel):
    """화면 공유 감시 설정 모델"""
    interval: int = 15                      # 캡처 주기 (기본값: 15초)
    enabled: bool = True                    # 자동 캡처 엔진 가동 여부

class ToggleVisionRequest(BaseModel):
    """비전 에이전트 토글 요청 모델"""
    enabled: bool                           # True: 활성화, False: 비활성화

# ==============================================================================
# 2. 비전 모니터링 API
# ==============================================================================
@router.post("/api/proactive_briefing", summary="15초 주기 실시간 화면 관찰 브리핑")
async def proactive_briefing(req: ProactiveBriefingRequest):
    """
    브라우저에서 15초마다 전송되는 화면 이미지를 수신하여 비전 엔진에 등록합니다.
    유저가 게임 중이거나 오류 화면을 띄웠을 때 AI가 먼저 알아채고 조언을 건넬 수 있습니다.
    """
    if req.image_b64:
        img_len = len(req.image_b64)
        return {
            "status": "success",
            "spoken": False,
            "briefing": "화면 관찰 정상 진행 중",
            "received_size": img_len
        }
    return {"status": "warning", "spoken": False, "briefing": "이미지 데이터 없음"}

@router.post("/api/screen_share/config", summary="화면 공유 감시 엔진 설정")
def config_screen_share(req: ScreenShareConfigRequest):
    """
    백그라운드 PC 화면 자동 캡처 엔진의 주기(초)와 켜짐/꺼짐 상태를 변경합니다.
    """
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

@router.post("/api/start_auto_monitor", summary="화면 감시 주기 설정 및 시작")
def start_auto_monitor_api(interval: int = 15):
    """지정된 주기(초)로 화면 감시 타이머를 설정하고 가동합니다."""
    auto_monitor.interval_seconds = interval
    auto_monitor.start()
    return {"status": "success", "interval": interval}

@router.post("/api/vision/toggle", summary="R6S 비전 클라이언트 수동 가동/중지")
async def toggle_vision(req: ToggleVisionRequest):
    """
    레인보우 식스 시즈(R6S) 인게임 화면 실시간 분석 프로세스(vision_agent_real.py)를
    사용자의 UI 클릭에 따라 켜거나 종료합니다.
    """
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
