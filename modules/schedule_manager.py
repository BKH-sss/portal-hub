"""
schedule_manager.py
=============================================================================
📅 JARVIS 스마트 캘린더, 일정 및 할 일(Todo) 관리 모듈
=============================================================================
- 기능:
    1. 로컬 SQLite (`data/schedule.db`) 기반의 초경량 영구 저장소
    2. 일정(Events) 및 할 일(Todos) 등록, 수정, 완료, 삭제
    3. D-Day 계산 및 오늘/이번 주 일정 자동 필터링
    4. 24/7 디스코드 봇 및 모닝 브리핑 연동용 요약 텍스트 생성기 내장
    5. FastAPI APIRouter 내장으로 REST API 제공
=============================================================================
"""

import os
import sqlite3
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# =============================================================================
# 🚀 1. FastAPI APIRouter 및 DB 경로 설정
# =============================================================================
router = APIRouter(prefix="/api/schedule", tags=["Schedule & Tasks"])

# 데이터베이스 저장 디렉토리 및 파일 경로
MODULE_DIR = Path(__file__).parent
DATA_DIR = MODULE_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "schedule.db"


# =============================================================================
# 📦 2. Pydantic 요청 모델 정의
# =============================================================================
class ScheduleCreateRequest(BaseModel):
    title: str = Field(..., description="일정 또는 할 일 제목")
    category: str = Field("default", description="카테고리 (예: work, study, gaming, personal)")
    start_time: str = Field(..., description="시작 일시 (YYYY-MM-DD 또는 YYYY-MM-DD HH:MM)")
    end_time: Optional[str] = Field(None, description="종료 일시 (선택)")
    description: Optional[str] = Field("", description="상세 메모")
    is_todo: bool = Field(False, description="True일 경우 체크 가능한 할 일(Todo)로 등록")
    priority: int = Field(2, ge=1, le=3, description="우선순위 (1: 낮음, 2: 보통, 3: 중요/긴급)")

class ScheduleUpdateRequest(BaseModel):
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    description: Optional[str] = None
    is_completed: Optional[bool] = None
    priority: Optional[int] = None


# =============================================================================
# 🗄️ 3. SQLite 데이터베이스 관리 클래스
# =============================================================================
class ScheduleDatabase:
    """일정 및 할 일 데이터를 관리하는 SQLite DB 헬퍼"""

    @staticmethod
    def get_connection():
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        """데이터베이스 테이블 초기화 (테이블이 없을 시 자동 생성)"""
        with cls.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    category TEXT DEFAULT 'default',
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    description TEXT,
                    is_todo INTEGER DEFAULT 0,
                    is_completed INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 2,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

# 모듈 로드 시 DB 초기화 실행
ScheduleDatabase.init_db()


# =============================================================================
# 🧠 4. 일정 & 할 일 핵심 비즈니스 로직
# =============================================================================
class ScheduleManager:
    """일정 및 할 일 CRUD 및 모닝 브리핑 포맷팅 엔진"""

    @staticmethod
    def add_item(data: ScheduleCreateRequest) -> Dict[str, Any]:
        """새로운 일정 또는 할 일을 데이터베이스에 등록"""
        with ScheduleDatabase.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO schedules (title, category, start_time, end_time, description, is_todo, is_completed, priority)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """, (
                data.title,
                data.category,
                data.start_time,
                data.end_time,
                data.description,
                1 if data.is_todo else 0,
                data.priority
            ))
            conn.commit()
            item_id = cursor.lastrowid
            return {"status": "success", "id": item_id, "message": f"'{data.title}' 등록 완료"}

    @staticmethod
    def get_items(target_date: Optional[str] = None, only_todos: bool = False, include_completed: bool = False) -> List[Dict[str, Any]]:
        """조건에 맞는 일정 및 할 일 목록 반환"""
        with ScheduleDatabase.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM schedules WHERE 1=1"
            params = []

            if target_date:
                # YYYY-MM-DD 매칭
                query += " AND start_time LIKE ?"
                params.append(f"{target_date}%")

            if only_todos:
                query += " AND is_todo = 1"

            if not include_completed:
                query += " AND is_completed = 0"

            query += " ORDER BY start_time ASC, priority DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def toggle_complete(item_id: int) -> Dict[str, Any]:
        """할 일의 완료 상태 토글 (완료 <-> 미완료)"""
        with ScheduleDatabase.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_completed FROM schedules WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="해당 일정을 찾을 수 없습니다.")

            new_status = 0 if row["is_completed"] == 1 else 1
            cursor.execute("UPDATE schedules SET is_completed = ? WHERE id = ?", (new_status, item_id))
            conn.commit()
            return {"status": "success", "id": item_id, "is_completed": bool(new_status)}

    @staticmethod
    def delete_item(item_id: int) -> Dict[str, Any]:
        """일정 또는 할 일 삭제"""
        with ScheduleDatabase.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM schedules WHERE id = ?", (item_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="삭제할 항목을 찾을 수 없습니다.")
            return {"status": "success", "message": f"ID {item_id} 삭제 완료"}

    @staticmethod
    def get_morning_briefing_summary() -> str:
        """
        🌅 자율 모닝 브리핑용 일정 & 할 일 요약 문자열 생성
        - 오늘 예정된 일정 목록
        - 마감되지 않은 긴급/중요 Todo 목록을 포맷팅하여 반환
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_items = ScheduleManager.get_items(target_date=today_str, include_completed=False)
        pending_todos = ScheduleManager.get_items(only_todos=True, include_completed=False)

        lines = [f"📅 **[{today_str} 오늘의 스케줄 & 브리핑]**"]

        # 1. 오늘의 일정
        events = [item for item in today_items if not item["is_todo"]]
        if events:
            lines.append("📌 **오늘의 일정:**")
            for ev in events:
                time_part = ev["start_time"].split(" ")[1] if " " in ev["start_time"] else "종일"
                lines.append(f"  • `{time_part}` {ev['title']}")
        else:
            lines.append("📌 **오늘의 일정:** 예정된 일정이 없습니다. (자유 시간)")

        # 2. 미완료 중요 할 일
        important_todos = [t for t in pending_todos if t["priority"] >= 2]
        if important_todos:
            lines.append("\n✅ **진행 중인 주요 태스크:**")
            for todo in important_todos[:5]:
                priority_mark = "🔥" if todo["priority"] == 3 else "⚡"
                lines.append(f"  • {priority_mark} {todo['title']} (마감: {todo['start_time']})")
        else:
            lines.append("\n✅ **할 일:** 모든 주요 태스크가 완료되었습니다.")

        return "\n".join(lines)


# =============================================================================
# 🌐 5. FastAPI 라우터 엔드포인트 정의
# =============================================================================

@router.get("/list", summary="일정 및 할 일 목록 조회")
async def list_schedules(target_date: Optional[str] = None, only_todos: bool = False, include_completed: bool = False):
    """지정한 날짜(YYYY-MM-DD) 또는 조건에 맞는 일정을 가져옵니다."""
    return {"status": "success", "items": ScheduleManager.get_items(target_date, only_todos, include_completed)}


@router.post("/add", summary="새 일정/할 일 등록")
async def add_schedule(req: ScheduleCreateRequest):
    """새로운 일정 또는 Todo를 생성합니다."""
    return ScheduleManager.add_item(req)


@router.post("/toggle/{item_id}", summary="할 일 완료 여부 토글")
async def toggle_schedule_complete(item_id: int):
    """할 일의 완료/미완료 상태를 반전시킵니다."""
    return ScheduleManager.toggle_complete(item_id)


@router.delete("/delete/{item_id}", summary="일정 삭제")
async def delete_schedule(item_id: int):
    """지정한 ID의 일정을 삭제합니다."""
    return ScheduleManager.delete_item(item_id)


@router.get("/briefing-text", summary="모닝 브리핑용 텍스트 생성")
async def get_briefing_text():
    """디스코드 봇이나 음성 비서가 읽어줄 오늘의 브리핑 텍스트를 반환합니다."""
    return {"status": "success", "briefing": ScheduleManager.get_morning_briefing_summary()}
