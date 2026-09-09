"""
lol_snapshot_reviewer.py
=============================================================================
📸 JARVIS / SKADI: 롤(LoL) 전술 하이라이트 스냅샷 & 협곡 오답노트 복기 엔진
=============================================================================
- 역할:
    1. 타워 다이브, 용/바론 버스트, 기습 갱킹 등 전술 위협 발생 순간의 미니맵 자동 캡처
    2. `memory/lol_matches/{날짜}/` 폴더에 시각 스냅샷(.jpg) 및 전술 메타데이터(.json) 자동 보관
    3. 경기 종료 후 또는 야간 수면 학습(`dream_engine_lol.py`) 주기에서
       당일 발생한 위협과 데스 위치를 자동 집계하여 마크다운 "협곡 전술 오답노트" 생성
    4. 옵시디언(Obsidian) 지식 베이스와 자동 동기화
=============================================================================
"""

import os
import io
import time
import json
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

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
from PIL import Image, ImageDraw

try:
    import cv2
except ImportError:
    cv2 = None

from config import MEMORY_DIR

# =============================================================================
# 🚀 1. FastAPI APIRouter
# =============================================================================
router = APIRouter(prefix="/api/lol/review", tags=["LoL Tactical Snapshot & Reviewer"])


# =============================================================================
# 📸 2. 전술 스냅샷 및 복기 코어 엔진
# =============================================================================
class TacticalSnapshotReviewer:
    def __init__(self):
        self.base_dir = Path(MEMORY_DIR) / "lol_matches"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_cooldown: float = 8.0  # 연속 스냅샷 최소 간격(초)
        self.last_snapshot_time: float = 0.0
        self.current_session_events: List[Dict[str, Any]] = []

    def _get_today_dir(self) -> Path:
        today_str = datetime.now().strftime("%Y-%m-%d")
        d = self.base_dir / today_str
        d.mkdir(parents=True, exist_ok=True)
        return d

    def record_tactical_moment(
        self,
        event_type: str,
        enemies: List[Dict[str, Any]],
        allies: List[Dict[str, Any]],
        raw_bgra: Any,
        message: str
    ) -> Optional[Dict[str, Any]]:
        """
        위협 발생 시점의 미니맵 영상을 JPEG 스냅샷으로 저장하고 메타데이터를 비동기(Background Thread)로 즉시 기록합니다.
        """
        now = time.time()
        if (now - self.last_snapshot_time) < self.snapshot_cooldown:
            return None  # 쿨타임 미경과

        self.last_snapshot_time = now
        today_dir = self._get_today_dir()
        ts_str = datetime.now().strftime("%H%M%S")
        filename_base = f"{ts_str}_{event_type.lower()}"

        img_path = today_dir / f"{filename_base}.jpg"
        meta_path = today_dir / f"{filename_base}.json"

        # 메타데이터 사전 구성
        meta = {
            "timestamp": now,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": event_type,
            "message": message,
            "enemies_count": len(enemies),
            "enemy_zones": [e.get("zone", "") for e in enemies],
            "allies_count": len(allies),
            "image_file": str(img_path.name)
        }
        self.current_session_events.append(meta)

        # 백그라운드 비동기 디스크 저장 (스캔 루프 지연 0.0ms 보장)
        def _save_worker(bgra_copy, enemies_copy, allies_copy, m_dict, i_path, m_path):
            try:
                if bgra_copy is not None:
                    if cv2 is not None:
                        canvas = bgra_copy[:, :, :3].copy()
                        for e in enemies_copy:
                            x, y = int(e.get("x", 0)), int(e.get("y", 0))
                            cv2.circle(canvas, (x, y), 12, (68, 23, 255), 2)
                        for a in allies_copy:
                            x, y = int(a.get("x", 0)), int(a.get("y", 0))
                            cv2.circle(canvas, (x, y), 12, (255, 229, 0), 2)
                        cv2.imwrite(str(i_path), canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    else:
                        rgb_arr = bgra_copy[:, :, [2, 1, 0]]
                        img = Image.fromarray(rgb_arr, mode="RGB")
                        draw = ImageDraw.Draw(img)
                        for e in enemies_copy:
                            x, y = e.get("x", 0), e.get("y", 0)
                            draw.ellipse([x - 12, y - 12, x + 12, y + 12], outline="#ff1744", width=2)
                        for a in allies_copy:
                            x, y = a.get("x", 0), a.get("y", 0)
                            draw.ellipse([x - 12, y - 12, x + 12, y + 12], outline="#00e5ff", width=2)
                        img.save(str(i_path), format="JPEG", quality=85)
            except Exception:
                pass

            try:
                with open(m_path, "w", encoding="utf-8") as f:
                    json.dump(m_dict, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        threading.Thread(
            target=_save_worker,
            args=(raw_bgra.copy() if raw_bgra is not None else None, enemies, allies, meta, img_path, meta_path),
            daemon=True,
            name="SnapshotSaveWorker"
        ).start()

        return meta

    def generate_daily_review_markdown(self) -> str:
        """
        당일 기록된 모든 위험 상황 스냅샷을 종합하여 마크다운 전술 오답노트를 생성합니다.
        """
        today_dir = self._get_today_dir()
        date_str = datetime.now().strftime("%Y년 %m월 %d일")

        md = []
        md.append(f"# 🛡️ 스카디의 소환사의 협곡 전술 오답노트 ({date_str})")
        md.append("> *Modern DeepLeague 실시간 비전 레이더가 기록한 주요 위협 및 한타 복기 리포트입니다.*\n")

        # 저장된 JSON 파일 목록 검색
        meta_files = sorted(today_dir.glob("*.json"))
        if not meta_files:
            md.append("오늘 기록된 특이 전술 위협 상황이 없습니다. 완벽한 게임이었습니다, 마스터!")
            return "\n".join(md)

        md.append(f"**총 감지된 위협 이벤트 수**: `{len(meta_files)}회`\n")
        md.append("---")

        for idx, mf in enumerate(meta_files, 1):
            try:
                with open(mf, "r", encoding="utf-8") as f:
                    data = json.load(f)

                time_str = data.get("datetime", "").split(" ")[-1]
                ev_type = data.get("event_type", "위협")
                msg = data.get("message", "")
                e_zones = ", ".join(data.get("enemy_zones", [])) or "미상"
                img_name = data.get("image_file", "")

                md.append(f"### {idx}. [{time_str}] {ev_type} ({msg})")
                md.append(f"- **적군 출현 구역**: `{e_zones}` (총 {data.get('enemies_count', 0)}명)")
                if img_name:
                    md.append(f"- **미니맵 캡처**: `![스냅샷]({img_name})`")
                md.append(f"- **스카디의 전술 피드백**: 다음번 유사 상황에서는 즉시 와드를 지우고 라인을 사리는 판단이 유리합니다.\n")
            except Exception:
                continue

        # 파일로 저장
        report_file = today_dir / "Tactical_Review_Report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(md))

        return "\n".join(md)


# 전역 싱글톤 인스턴스
snapshot_reviewer = TacticalSnapshotReviewer()


# =============================================================================
# 🌐 3. REST API 엔드포인트
# =============================================================================
@router.get("/status", summary="전술 스냅샷 상태 조회")
def get_snapshot_status():
    """당일 저장된 전술 스냅샷 개수 및 저장 경로를 반환합니다."""
    today_dir = snapshot_reviewer._get_today_dir()
    count = len(list(today_dir.glob("*.json"))) if today_dir.exists() else 0
    return {
        "today_snapshots_count": count,
        "storage_dir": str(today_dir)
    }


@router.get("/latest", summary="최근 기록된 전술 스냅샷 목록 조회")
def get_latest_snapshots(limit: int = 10):
    """오늘 저장된 최근 미니맵 전술 스냅샷 메타데이터 목록을 반환합니다."""
    today_dir = snapshot_reviewer._get_today_dir()
    meta_files = sorted(today_dir.glob("*.json"), reverse=True)[:limit]

    results = []
    for mf in meta_files:
        try:
            with open(mf, "r", encoding="utf-8") as f:
                results.append(json.load(f))
        except Exception:
            pass

    return {
        "count": len(results),
        "snapshots": results
    }


@router.post("/generate-report", summary="오늘의 협곡 전술 오답노트 마크다운 리포트 생성")
def generate_review_report():
    """당일 수집된 모든 전술 스냅샷을 종합하여 오답노트 Markdown을 생성합니다."""
    report_text = snapshot_reviewer.generate_daily_review_markdown()
    return {
        "status": "success",
        "message": "오늘의 협곡 전술 오답노트가 성공적으로 생성되었습니다.",
        "report_preview": report_text[:500] + "..." if len(report_text) > 500 else report_text
    }


@router.post("/capture-now", summary="1회 즉시 전술 스냅샷 수동 기록")
def manual_capture_snapshot(event_name: str = "MANUAL_BOOKMARK"):
    """현재 화면 상태를 즉시 전술 오답노트에 스냅샷으로 저장합니다."""
    try:
        from modules.lol_minimap_tracker import minimap_tracker
        with minimap_tracker.lock:
            meta = snapshot_reviewer.record_tactical_moment(
                event_type=event_name,
                enemies=minimap_tracker.last_enemies,
                allies=minimap_tracker.last_allies,
                raw_bgra=minimap_tracker.last_raw_bgra,
                message="유저 수동 전술 북마크"
            )
        return {"status": "success", "saved": meta}
    except Exception as e:
        return {"status": "error", "message": str(e)}
