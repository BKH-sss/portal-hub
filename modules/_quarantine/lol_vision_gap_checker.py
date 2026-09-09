"""
lol_vision_gap_checker.py
=============================================================================
🐉 JARVIS / SKADI: 롤(LoL) 오브젝트 출현 1분 전 '시야 공백(Fog of War)' 선제 감지기
=============================================================================
- 역할:
    1. 인게임 타이머와 결합하여 드래곤 / 내셔 남작(바론) 리젠 60초 전 카운트다운 추적
    2. 미니맵 상의 용 둥지 및 바론 둥지 관심영역(ROI)의 밝기/색도 히스토그램 분석
    3. 전장 안개(Fog of War: 평균 밝기 45 미만, 와드/아군 부재) 상태 자동 판정
    4. 선제적 시야 확보 경고 발행:
       - "용 출현 50초 전인데 용 둥지 시야가 비어있어요! 서포터와 함께 와드 설치 추천해요."
    5. 스카디 음성 알림 엔진(`lol_voice_alert_engine`)과 즉시 연동
=============================================================================
"""

import time
from typing import Dict, Any, Optional

try:
    from modules._safe_router import (
        APIRouter, HTTPException, Response, HTMLResponse, FileResponse,
        JSONResponse, Request, WebSocket, WebSocketDisconnect, FastAPI,
        CORSMiddleware, BaseModel, Field
    )
except ImportError:
    try:
        from _safe_router import (
            APIRouter, HTTPException, Response, HTMLResponse, FileResponse,
            JSONResponse, Request, WebSocket, WebSocketDisconnect, FastAPI,
            CORSMiddleware, BaseModel, Field
        )
    except ImportError:
        pass

try:
    import numpy as np
except ImportError:
    np = None

# =============================================================================
# 🚀 1. FastAPI APIRouter
# =============================================================================
router = APIRouter(prefix="/api/lol/vision", tags=["LoL Objective Vision Gap Checker"])


# =============================================================================
# 🔍 2. 오브젝트 시야 공백 검사 엔진
# =============================================================================
class ObjectiveVisionGapChecker:
    def __init__(self):
        # 둥지 정규화 좌표 (x_min, x_max, y_min, y_max)
        self.dragon_pit_roi = (0.58, 0.70, 0.52, 0.65)
        self.baron_pit_roi = (0.30, 0.42, 0.35, 0.48)

        # 상태 추적
        self.last_check_time: float = 0.0
        self.dragon_status: Dict[str, Any] = {"has_vision": True, "brightness": 100.0, "time_to_spawn": 120}
        self.baron_status: Dict[str, Any] = {"has_vision": True, "brightness": 100.0, "time_to_spawn": 300}
        self.last_alert_time: Dict[str, float] = {}

    def analyze_pit_vision(
        self,
        bgra: Any,
        dragon_spawn_sec: Optional[int] = None,
        baron_spawn_sec: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        미니맵 BGRA 영상에서 용 둥지와 바론 둥지 영역의 픽셀 휘도(Luminance)를 측정하여
        시야 확보 여부(와드 설치됨 vs 전장 안개 속)를 판정합니다.
        """
        now = time.time()
        self.last_check_time = now

        if np is None or bgra is None:
            return {"status": "skipped", "reason": "No image or numpy"}

        h, w = bgra.shape[:2]

        # 1. 용 둥지 휘도 계산
        dx1, dx2 = int(w * self.dragon_pit_roi[0]), int(w * self.dragon_pit_roi[1])
        dy1, dy2 = int(h * self.dragon_pit_roi[2]), int(h * self.dragon_pit_roi[3])
        dragon_crop = bgra[dy1:dy2, dx1:dx2]

        # R, G, B 평균 밝기 (인간 시각 가중치)
        # 롤 미니맵 전장 안개는 어두운 흑갈색(평균 휘도 < 50)
        d_b, d_g, d_r = dragon_crop[:, :, 0], dragon_crop[:, :, 1], dragon_crop[:, :, 2]
        dragon_brightness = float(np.mean(0.299 * d_r + 0.587 * d_g + 0.114 * d_b))
        dragon_has_vision = dragon_brightness > 55.0

        # 2. 바론 둥지 휘도 계산
        bx1, bx2 = int(w * self.baron_pit_roi[0]), int(w * self.baron_pit_roi[1])
        by1, by2 = int(h * self.baron_pit_roi[2]), int(h * self.baron_pit_roi[3])
        baron_crop = bgra[by1:by2, bx1:bx2]

        b_b, b_g, b_r = baron_crop[:, :, 0], baron_crop[:, :, 1], baron_crop[:, :, 2]
        baron_brightness = float(np.mean(0.299 * b_r + 0.587 * b_g + 0.114 * b_r))
        baron_has_vision = baron_brightness > 55.0

        alerts = []

        # 3. 드래곤 출현 60초 전 시야 공백 경고 판정
        d_sec = dragon_spawn_sec if dragon_spawn_sec is not None else 45  # 기본 예시 45초 전
        if d_sec <= 65 and not dragon_has_vision:
            if (now - self.last_alert_time.get("dragon_fog", 0.0)) > 30.0:
                self.last_alert_time["dragon_fog"] = now
                alerts.append({
                    "type": "VISION_GAP",
                    "priority": "HIGH",
                    "pit": "용 둥지",
                    "time_left": d_sec,
                    "message": f"🐉 드래곤 출현 약 {d_sec}초 전인데 용 둥지 시야가 비어있어요! 와드 설치 권장!"
                })

        # 4. 바론 출현 60초 전 시야 공백 경고 판정
        b_sec = baron_spawn_sec if baron_spawn_sec is not None else 180
        if b_sec <= 65 and not baron_has_vision:
            if (now - self.last_alert_time.get("baron_fog", 0.0)) > 30.0:
                self.last_alert_time["baron_fog"] = now
                alerts.append({
                    "type": "VISION_GAP",
                    "priority": "HIGH",
                    "pit": "바론 둥지",
                    "time_left": b_sec,
                    "message": f"👾 바론 출현 약 {b_sec}초 전인데 바론 둥지 시야가 비어있어요! 와드 확보 필요!"
                })

        self.dragon_status = {
            "has_vision": dragon_has_vision,
            "brightness": round(dragon_brightness, 1),
            "spawn_in_sec": d_sec
        }
        self.baron_status = {
            "has_vision": baron_has_vision,
            "brightness": round(baron_brightness, 1),
            "spawn_in_sec": b_sec
        }

        return {
            "dragon": self.dragon_status,
            "baron": self.baron_status,
            "alerts": alerts
        }


# 전역 싱글톤 인스턴스
vision_gap_checker = ObjectiveVisionGapChecker()


# =============================================================================
# 🌐 3. REST API 엔드포인트
# =============================================================================
@router.get("/status", summary="용 및 바론 둥지 실시간 시야 상태 조회")
def get_pit_vision_status():
    """용과 바론 둥지 주변의 시야 확보 여부(와드 설치됨/안개 속)를 반환합니다."""
    return {
        "dragon": vision_gap_checker.dragon_status,
        "baron": vision_gap_checker.baron_status,
        "last_check": round(time.time() - vision_gap_checker.last_check_time, 1)
    }


@router.post("/test-alert", summary="오브젝트 시야 공백 경고 테스트")
def test_vision_alert(pit: str = "용 둥지"):
    """가상 시야 공백 경고를 음성 엔진에 전달하여 테스트합니다."""
    try:
        from modules.lol_voice_alert_engine import voice_alert_engine
        voice_alert_engine.trigger_alert("VISION_GAP", {"pit": pit})
        return {"status": "success", "message": f"[{pit}] 시야 공백 경고가 음성 엔진에 전달되었습니다."}
    except Exception as e:
        return {"status": "error", "message": str(e)}
