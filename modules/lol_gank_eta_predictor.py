"""
lol_gank_eta_predictor.py
=============================================================================
⏳ JARVIS / SKADI: 롤(LoL) 적 이동 동선 벡터 예측 & 갱킹 도착 타이머 (ETA) 엔진
=============================================================================
- 역할:
    1. 연속된 미니맵 프레임 간 적 챔피언 위치 시계열 추적
    2. 2D 속도 벡터(Velocity Vector, dx/dt, dy/dt) 및 이동 방향(Heading) 산출
    3. 협곡 주요 타깃 라인(Mid, Bot, Top Lane)으로 향하는 갱킹 경로 판별
    4. 챔피언 기본 이속(평균 345 units/s) 기반 남은 도달 시간(ETA, 초) 실시간 카운트다운
    5. 조기경보 발행: "적 정글러 미드 방향 이동 중, 약 8초 후 도달 예상!"
=============================================================================
"""

import math
import time
from typing import Dict, Any, List, Optional, Tuple

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

# =============================================================================
# 🚀 1. FastAPI APIRouter
# =============================================================================
router = APIRouter(prefix="/api/lol/eta", tags=["LoL Predictive Gank & ETA Engine"])


# =============================================================================
# 🎯 2. 소환사의 협곡 주요 목표 거점 (정규화 좌표 0.0 ~ 1.0)
# =============================================================================
LANE_TARGETS = {
    "탑 라인 (Top)": (0.18, 0.20),
    "미드 라인 (Mid)": (0.50, 0.50),
    "바텀 라인 (Bot)": (0.82, 0.80),
    "용 둥지 (Dragon)": (0.64, 0.58),
    "바론 둥지 (Baron)": (0.36, 0.42),
}


# =============================================================================
# 🧠 3. 동선 벡터 & 갱킹 ETA 예측 코어 엔진
# =============================================================================
class GankETAPredictor:
    """
    미니맵 챔피언 좌표를 바탕으로 2D 이동 궤적을 추적하고 갱 도착 예상 시간을 계산합니다.
    """

    def __init__(self):
        # 챔피언별 위치 히스토리: tracker_id -> list of (x, y, timestamp)
        self.track_history: Dict[int, List[Tuple[float, float, float]]] = {}
        self.max_history_len: int = 8
        self.active_ganks: List[Dict[str, Any]] = []
        self.last_update_time: float = time.time()

    def update_positions(self, enemies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        새로운 프레임의 적 챔피언 목록(정규화 좌표 norm_x, norm_y)을 수신하여
        이동 벡터를 계산하고 위협적인 갱킹 이동을 감지합니다.
        """
        now = time.time()
        detected_ganks = []

        # 1. 간단한 최근접 이웃(Nearest Neighbor) 매칭으로 적 트랙 연관
        updated_tracks = {}
        unmatched_enemies = list(enemies)

        for track_id, history in self.track_history.items():
            if not history:
                continue
            last_x, last_y, last_t = history[-1]
            
            # 3초 이상 끊겼으면 트랙 만료
            if (now - last_t) > 3.0:
                continue

            # 가장 가까운 새 좌표 찾기
            best_idx = -1
            best_dist = 0.15 # 정규화 거리 최대 반경 (약 40px)
            for i, e in enumerate(unmatched_enemies):
                dx = e["norm_x"] - last_x
                dy = e["norm_y"] - last_y
                dist = math.hypot(dx, dy)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i

            if best_idx >= 0:
                e = unmatched_enemies.pop(best_idx)
                new_history = history + [(e["norm_x"], e["norm_y"], now)]
                updated_tracks[track_id] = new_history[-self.max_history_len:]
                
                # 벡터 및 ETA 계산
                gank_info = self._analyze_vector_eta(track_id, updated_tracks[track_id], e["zone"])
                if gank_info:
                    detected_ganks.append(gank_info)

        # 매칭되지 않은 새로운 적 챔피언 새 트랙 생성
        next_id = max(updated_tracks.keys(), default=0) + 1
        for e in unmatched_enemies:
            updated_tracks[next_id] = [(e["norm_x"], e["norm_y"], now)]
            next_id += 1

        self.track_history = updated_tracks
        self.active_ganks = detected_ganks
        self.last_update_time = now
        return detected_ganks

    def _analyze_vector_eta(
        self, track_id: int, history: List[Tuple[float, float, float]], current_zone: str
    ) -> Optional[Dict[str, Any]]:
        """이동 벡터를 산출하여 주요 라인 방향인지 검사하고 ETA(초)를 도출"""
        if len(history) < 3:
            return None

        # 최근 3프레임 기준 이동 벡터
        p_old = history[-3]
        p_new = history[-1]
        dt = p_new[2] - p_old[2]
        if dt <= 0.1:
            return None

        vx = (p_new[0] - p_old[0]) / dt  # norm_x per sec
        vy = (p_new[1] - p_old[1]) / dt  # norm_y per sec
        speed = math.hypot(vx, vy)

        # 거의 정지 상태(미니언 막타, 파밍 중)이면 갱킹 아님
        if speed < 0.015:  # 초당 1.5% 미만 이동
            return None

        cur_x, cur_y = p_new[0], p_new[1]

        # 각 거점(탑, 미드, 바텀)과의 벡터 내적(Dot Product) 검사
        for target_name, (tx, ty) in LANE_TARGETS.items():
            to_tx = tx - cur_x
            to_ty = ty - cur_y
            dist_to_target = math.hypot(to_tx, to_ty)

            # 이미 해당 라인에 도착해 있으면 제외
            if dist_to_target < 0.08:
                continue

            # 방향 일치도 (코사인 유사도)
            dot = (vx * to_tx + vy * to_ty) / (speed * dist_to_target)

            # 대상 거점을 향해 70도 이내로 돌진 중일 때 (cos > 0.35)
            if dot > 0.4:
                # 롤 협곡 기준 정규화 1.0 단위 이동 시간: 약 35초
                # 현재 속도 또는 평균 이동 속도 기준 ETA 도출
                eta_seconds = round(dist_to_target / max(speed, 0.028), 1)

                # 현실적인 갱킹 사정거리 내 (3~18초 이내 도착 예상)
                if 3.0 <= eta_seconds <= 18.0:
                    return {
                        "track_id": track_id,
                        "target_lane": target_name,
                        "from_zone": current_zone,
                        "eta_seconds": eta_seconds,
                        "speed_rating": "FAST" if speed > 0.04 else "NORMAL",
                        "direction_dot": round(dot, 2),
                        "timestamp": time.time(),
                        "alert_message": f"🚨 [{current_zone}]에서 [{target_name}] 방향 급습 감지! (도착 예상: 약 {int(eta_seconds)}초)"
                    }

        return None


# 전역 싱글톤 인스턴스
gank_predictor = GankETAPredictor()


# =============================================================================
# 🌐 4. REST API 엔드포인트
# =============================================================================
@router.get("/active", summary="현재 활성화된 적 동선 갱킹 ETA 목록 조회")
def get_active_ganks():
    """현재 미니맵에서 감지된 주요 라인 급습 벡터와 도착 예상 카운트다운을 반환합니다."""
    return {
        "count": len(gank_predictor.active_ganks),
        "ganks": gank_predictor.active_ganks,
        "last_updated": round(time.time() - gank_predictor.last_update_time, 1)
    }


@router.post("/simulate", summary="가상 적군 이동 갱킹 시뮬레이션")
def simulate_gank_vector(target: str = "미드 라인 (Mid)", steps: int = 3):
    """테스트용 가상 강가 이동 시퀀스를 주입하여 ETA 계산 결과를 검증합니다."""
    # 상단 강가 (0.35, 0.42) -> 미드 (0.50, 0.50) 방향으로 시뮬레이션
    now = time.time()
    for i in range(steps):
        t = now - (steps - i) * 0.5
        x = 0.35 + (i * 0.04)
        y = 0.42 + (i * 0.025)
        enemies = [{"norm_x": x, "norm_y": y, "zone": "상단 강가 (River Top)"}]
        gank_predictor.update_positions(enemies)

    return {
        "status": "success",
        "result": gank_predictor.active_ganks
    }
