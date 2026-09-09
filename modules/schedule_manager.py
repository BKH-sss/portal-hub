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
import re
import sqlite3
import logging
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger("ScheduleManager")

KST = timezone(timedelta(hours=9))

def get_now_kst() -> datetime:
    return datetime.now(KST)

try:
    from modules._safe_router import get_safe_router, APIRouter, HTTPException, BaseModel, Field
except ImportError:
    try:
        from _safe_router import get_safe_router, APIRouter, HTTPException, BaseModel, Field
    except ImportError:
        class DummyRouter:
            def __init__(self, *args, **kwargs): pass
            def get(self, *args, **kwargs): return lambda f: f
            def post(self, *args, **kwargs): return lambda f: f
            def put(self, *args, **kwargs): return lambda f: f
            def delete(self, *args, **kwargs): return lambda f: f
            def patch(self, *args, **kwargs): return lambda f: f
            def include_router(self, *args, **kwargs): pass
        APIRouter = DummyRouter
        def get_safe_router(*args, **kwargs): return DummyRouter()
        class HTTPException(Exception):
            def __init__(self, status_code: int = 400, detail: str = ""):
                self.status_code = status_code
                self.detail = detail
                super().__init__(detail)
        class BaseModel:
            def __init__(self, **kwargs):
                for k, v in kwargs.items(): setattr(self, k, v)
            def dict(self, *args, **kwargs): return self.__dict__.copy()
            def model_dump(self, *args, **kwargs): return self.__dict__.copy()
        def Field(default=None, **kwargs): return None if default is Ellipsis else default

# =============================================================================
# 🚀 1. FastAPI APIRouter 및 DB 경로 설정
# =============================================================================
router = get_safe_router(prefix="/api/schedule", tags=["Schedule & Tasks"])

# 데이터베이스 저장 디렉토리 및 파일 경로
MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR.parent / "data" if (MODULE_DIR.parent / "data").exists() or MODULE_DIR.name == "modules" else MODULE_DIR
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    DATA_DIR = MODULE_DIR
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
        """데이터베이스 테이블 초기화 및 스키마 자동 마이그레이션"""
        with cls.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT,
                    title TEXT NOT NULL,
                    category TEXT DEFAULT 'default',
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    description TEXT,
                    is_todo INTEGER DEFAULT 0,
                    is_completed INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 2,
                    last_synced_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 기존 테이블에 uid 및 last_synced_at 컬럼 무중단 안전 마이그레이션
            for col_def in ["uid TEXT", "last_synced_at TEXT"]:
                try:
                    cursor.execute(f"ALTER TABLE schedules ADD COLUMN {col_def}")
                except Exception:
                    pass
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedules_uid ON schedules(uid)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_schedules_start ON schedules(start_time)")
            except Exception:
                pass
            conn.commit()

# 모듈 로드 시 DB 초기화 실행
ScheduleDatabase.init_db()


def parse_ical_datetime_to_kst(raw_val: str) -> Tuple[str, bool]:
    """
    iCal 날짜/시각 문자열을 정확한 대한민국 표준시(KST: UTC+9)로 변환
    반환값: (start_time_str: 'YYYY-MM-DD HH:MM' 또는 'YYYY-MM-DD', is_all_day: bool)
    """
    clean_val = raw_val.strip()
    if ":" in clean_val:
        clean_val = clean_val.split(":")[-1].strip()

    # 1. UTC 날짜-시각 (예: 20260909T010000Z 또는 20260909T0100Z)
    if "T" in clean_val and clean_val.endswith("Z"):
        core = clean_val.rstrip("Z")
        if len(core) >= 15:
            utc_dt = datetime.strptime(core[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        elif len(core) >= 13:
            utc_dt = datetime.strptime(core[:13], "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
        else:
            return clean_val[:8], True
        kst_dt = utc_dt.astimezone(KST)
        return kst_dt.strftime("%Y-%m-%d %H:%M"), False

    # 2. 로컬 날짜-시각 (예: 20260909T100000)
    if "T" in clean_val:
        core = clean_val.split("T")
        d_part = core[0]
        t_part = core[1]
        date_str = f"{d_part[:4]}-{d_part[4:6]}-{d_part[6:8]}"
        time_str = f"{t_part[:2]}:{t_part[2:4]}"
        return f"{date_str} {time_str}", False

    # 3. 종일 일정 (예: 20260909)
    if len(clean_val) >= 8 and clean_val[:8].isdigit():
        return f"{clean_val[:4]}-{clean_val[4:6]}-{clean_val[6:8]}", True

    return clean_val, False


# =============================================================================
# 🧠 4. 일정 & 할 일 핵심 비즈니스 로직
# =============================================================================
class ScheduleManager:
    """일정 및 할 일 CRUD 및 모닝 브리핑 포맷팅 엔진"""

    _last_sync_time: Optional[str] = None
    _last_sync_status: str = "미동기화"
    _last_sync_count: int = 0
    _total_feed_events: int = 0

    @classmethod
    def get_total_count(cls) -> int:
        try:
            with ScheduleDatabase.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as cnt FROM schedules")
                row = cursor.fetchone()
                return row["cnt"] if row else 0
        except Exception:
            return 0

    @classmethod
    def get_sync_status(cls) -> Dict[str, Any]:
        return {
            "last_sync_time": cls._last_sync_time or "동기화 이력 없음",
            "last_sync_status": cls._last_sync_status,
            "last_sync_count": cls._last_sync_count,
            "total_feed_events": cls._total_feed_events,
            "total_db_schedules": cls.get_total_count()
        }

    @staticmethod
    def get_configured_ical_url() -> Optional[str]:
        """환경변수 및 설정 파일에서 구글 캘린더 iCal 비공개 URL 탐색"""
        url = os.environ.get("GOOGLE_CALENDAR_ICAL_URL")
        if url and url.strip().startswith("http"):
            return url.strip()
        try:
            from config import GOOGLE_CALENDAR_ICAL_URL
            if GOOGLE_CALENDAR_ICAL_URL and GOOGLE_CALENDAR_ICAL_URL.strip().startswith("http"):
                return GOOGLE_CALENDAR_ICAL_URL.strip()
        except Exception:
            pass
        return None

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

    @classmethod
    def get_morning_briefing_summary(cls, target_date: Optional[str] = None) -> str:
        """
        🌅 자율 모닝 브리핑용 일정 & 할 일 요약 문자열 생성
        - 오늘 예정된 일정 목록
        - 마감되지 않은 긴급/중요 Todo 목록을 포맷팅하여 반환
        """
        # 0. 구글 캘린더 최신 자동 동기화 보장
        ical_url = cls.get_configured_ical_url()
        if ical_url:
            try:
                sync_res = cls.sync_from_google_calendar_ical(ical_url)
                logger.info(f"🌅 [모닝 브리핑] 캘린더 자동 동기화 완료: {sync_res.get('message')}")
            except Exception as e:
                logger.warning(f"🌅 [모닝 브리핑] 캘린더 자동 동기화 경고: {e}")

        now_kst = get_now_kst()
        today_str = target_date or now_kst.strftime("%Y-%m-%d")
        today_items = cls.get_items(target_date=today_str, include_completed=False)
        pending_todos = cls.get_items(only_todos=True, include_completed=False)

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

    @staticmethod
    def generate_google_calendar_url(title: str, start_time_str: str, end_time_str: Optional[str] = None, description: str = "") -> str:
        """구글 캘린더 원클릭 등록 URL 템플릿 생성"""
        import urllib.parse
        clean_title = urllib.parse.quote(title.strip())
        clean_desc = urllib.parse.quote((description or "스카디 AI 비서가 등록한 일정입니다.").strip())

        # 날짜 파싱
        try:
            if " " in start_time_str:
                dt_start = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
                dt_end = dt_start + timedelta(hours=1) if not end_time_str else datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")
                dates_str = f"{dt_start.strftime('%Y%m%dT%H%M00')}/{dt_end.strftime('%Y%m%dT%H%M00')}"
            else:
                dt_start = datetime.strptime(start_time_str, "%Y-%m-%d")
                dt_end = dt_start + timedelta(days=1)
                dates_str = f"{dt_start.strftime('%Y%m%d')}/{dt_end.strftime('%Y%m%d')}"
        except Exception:
            dates_str = datetime.now().strftime("%Y%m%d/%Y%m%d")

        return f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={clean_title}&dates={dates_str}&details={clean_desc}"

    @staticmethod
    def generate_ical_feed() -> str:
        """
        🌐 표준 iCalendar (.ics / RFC 5545) 포맷 텍스트 생성
        - 구글 캘린더, 삼성 캘린더(Galaxy), 애플 캘린더, 아웃룩 100% 호환
        """
        items = ScheduleManager.get_items(include_completed=True)
        now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//JARVIS Assistant//Skadi Scheduler 2.0//KO",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:스카디 캘린더 (JARVIS)",
            "X-WR-CALDESC:J.A.R.V.I.S / 스카디 AI 비서 스마트 캘린더 실시간 피드",
            "X-WR-TIMEZONE:Asia/Seoul",
            "REFRESH-INTERVAL;VALUE=DURATION:PT15M",
            "X-PUBLISHED-TTL:PT15M"
        ]

        for item in items:
            item_id = item["id"]
            title = item["title"].replace("\n", " ").replace(",", "\\,")
            desc = (item.get("description") or "").replace("\n", "\\n").replace(",", "\\,")
            is_todo = bool(item.get("is_todo"))
            is_done = bool(item.get("is_completed"))
            start_str = item["start_time"].strip()

            if is_todo:
                status_prefix = "[완료] " if is_done else "[할일] "
                title = status_prefix + title

            # 시간 포맷 계산
            try:
                if " " in start_str:
                    # YYYY-MM-DD HH:MM
                    dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M")
                    dt_end = dt + timedelta(hours=1)
                    dt_start_fmt = f"DTSTART;TZID=Asia/Seoul:{dt.strftime('%Y%m%dT%H%M00')}"
                    dt_end_fmt = f"DTEND;TZID=Asia/Seoul:{dt_end.strftime('%Y%m%dT%H%M00')}"
                else:
                    # YYYY-MM-DD (종일 일정)
                    dt = datetime.strptime(start_str, "%Y-%m-%d")
                    dt_end = dt + timedelta(days=1)
                    dt_start_fmt = f"DTSTART;VALUE=DATE:{dt.strftime('%Y%m%d')}"
                    dt_end_fmt = f"DTEND;VALUE=DATE:{dt_end.strftime('%Y%m%d')}"
            except Exception:
                continue

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:skadi-item-{item_id}@jarvis-assistant",
                f"DTSTAMP:{now_utc}",
                dt_start_fmt,
                dt_end_fmt,
                f"SUMMARY:{title}",
                f"DESCRIPTION:{desc}",
                "STATUS:CONFIRMED" if not is_done else "CANCELLED",
                "END:VEVENT"
            ])

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)



    @staticmethod
    def _mask_url(url: str) -> str:
        """민감한 URL 로그 마스킹 (앞 15자만 노출하고 나머지는 *** 처리)"""
        if not url:
            return ""
        return url[:15] + "***" if len(url) > 15 else "***"

    @classmethod
    def sync_from_google_calendar_ical(cls, ical_url: Optional[str] = None, ical_content: Optional[str] = None) -> Dict[str, Any]:
        """
        🌐 외부 구글 캘린더 iCal (basic.ics) URL을 읽어와서 로컬 schedule.db에 자동 동기화 (RFC 5545 준수)
        - RFC 5545 Line Folding 자동 언폴딩 처리
        - UTC(Z) -> 대한민국 표준시(KST: UTC+9) 정확한 시차 변환 (오전/새벽 일정 날짜 누락 원천 방지)
        - UID 기준 upsert (중복 저장 방지 및 일정 일시 변경 시 자동 업데이트)
        - CANCELLED 취소 일정 자동 필터링
        - 동기화 메트릭(최종 시각, 피드 개수, 갱신 개수) 자동 갱신
        """
        raw_content = ical_content
        target_url = ical_url or os.environ.get("GOOGLE_CALENDAR_ICAL_URL", "")

        if raw_content is None:
            if not target_url or not target_url.startswith("http"):
                return {"status": "error", "message": "유효한 구글 캘린더 iCal URL이 설정되지 않았습니다."}

            try:
                import urllib.request
                req = urllib.request.Request(
                    target_url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Skadi-Calendar/3.8'}
                )
                with urllib.request.urlopen(req, timeout=12.0) as resp:
                    raw_content = resp.read().decode('utf-8', errors='replace')
            except Exception as e:
                masked = cls._mask_url(target_url)
                logger.error(f"구글 캘린더 iCal 다운로드 실패 ({masked}): {e}")
                return {"status": "error", "message": f"구글 캘린더 다운로드 실패 ({masked})"}

        # 1. RFC 5545 Line Folding 언폴딩
        unfolded_content = re.sub(r"\r?\n[ \t]", "", raw_content)

        # 2. VEVENT 추출
        events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded_content, flags=re.DOTALL)
        if not events:
            return {"status": "warning", "message": "가져올 캘린더 일정이 없습니다.", "count": 0}

        now_sync_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        added_count = 0
        updated_count = 0
        cancelled_count = 0

        for ev in events:
            # STATUS: CANCELLED 확인
            status_m = re.search(r"^STATUS:\s*(.*?)$", ev, flags=re.MULTILINE)
            if status_m and status_m.group(1).strip().upper() == "CANCELLED":
                cancelled_count += 1
                continue

            # UID 확인
            uid_m = re.search(r"^UID:\s*(.*?)$", ev, flags=re.MULTILINE)
            uid = uid_m.group(1).strip() if uid_m else None

            # SUMMARY 확인
            summary_m = re.search(r"^SUMMARY:\s*(.*?)$", ev, flags=re.MULTILINE)
            summary = summary_m.group(1).strip().replace("\\,", ",").replace("\\;", ";") if summary_m else "구글 캘린더 일정"

            # DTSTART 확인 및 KST 변환
            dtstart_m = re.search(r"^DTSTART(?:;[^:\r\n]+)?:\s*([^\r\n]+)", ev, flags=re.MULTILINE)
            if not dtstart_m:
                continue
            start_time_str, is_all_day = parse_ical_datetime_to_kst(dtstart_m.group(1))

            # DTEND 확인 및 KST 변환
            dtend_m = re.search(r"^DTEND(?:;[^:\r\n]+)?:\s*([^\r\n]+)", ev, flags=re.MULTILINE)
            end_time_str = parse_ical_datetime_to_kst(dtend_m.group(1))[0] if dtend_m else None

            # DESCRIPTION 확인
            desc_m = re.search(r"^DESCRIPTION:\s*(.*?)$", ev, flags=re.MULTILINE)
            desc = desc_m.group(1).strip().replace("\\n", "\n").replace("\\,", ",") if desc_m else "구글 캘린더 동기화"

            # 3. UID 기반 upsert 처리
            try:
                with ScheduleDatabase.get_connection() as conn:
                    cursor = conn.cursor()
                    row = None
                    if uid:
                        cursor.execute("SELECT id, start_time, title FROM schedules WHERE uid = ?", (uid,))
                        row = cursor.fetchone()
                    if not row:
                        cursor.execute("SELECT id, start_time, title FROM schedules WHERE title = ? AND start_time = ?", (summary, start_time_str))
                        row = cursor.fetchone()

                    if row:
                        item_id = row["id"]
                        cursor.execute("""
                            UPDATE schedules
                            SET uid = ?, title = ?, category = 'google', start_time = ?, end_time = ?, description = ?, last_synced_at = ?
                            WHERE id = ?
                        """, (uid, summary, start_time_str, end_time_str, desc, now_sync_str, item_id))
                        conn.commit()
                        updated_count += 1
                    else:
                        cursor.execute("""
                            INSERT INTO schedules (uid, title, category, start_time, end_time, description, is_todo, is_completed, priority, last_synced_at)
                            VALUES (?, ?, 'google', ?, ?, ?, 0, 0, 2, ?)
                        """, (uid, summary, start_time_str, end_time_str, desc, now_sync_str))
                        conn.commit()
                        inserted_count += 1
            except Exception as db_e:
                logger.error(f"스케줄 DB upsert 오류 ({summary}): {db_e}")

        total_synced = inserted_count + updated_count
        cls._last_sync_time = now_sync_str
        cls._last_sync_status = "SUCCESS"
        cls._last_sync_count = total_synced
        cls._total_feed_events = len(events)

        succ_msg = f"구글 캘린더에서 {len(events)}개 일정을 분석하여 {total_synced}개 동기화 완료 (신규 {inserted_count}, 갱신 {updated_count})"
        logger.info(f"📅 [구글 캘린더 동기화 성공] {succ_msg}")

        return {
            "status": "success",
            "total_events_in_feed": len(events),
            "total_events": len(events),
            "newly_synced_count": inserted_count,
            "updated_count": updated_count,
            "total_synced": total_synced,
            "synced_count": total_synced,
            "cancelled_count": cancelled_count,
            "last_sync_time": now_sync_str,
            "message": succ_msg
        }


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
    res = ScheduleManager.add_item(req)
    google_url = ScheduleManager.generate_google_calendar_url(req.title, req.start_time, req.end_time, req.description)
    res["google_calendar_url"] = google_url
    return res


@router.post("/sync/google", summary="구글 캘린더 비공개 iCal URL로부터 일정 가져오기")
@router.get("/sync/google", summary="구글 캘린더 비공개 iCal URL로부터 일정 가져오기")
async def api_sync_google_calendar(ical_url: str):
    return ScheduleManager.sync_from_google_calendar_ical(ical_url)


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


@router.get("/calendar.ics", summary="구글/삼성/애플 캘린더 실시간 iCal 피드 구독")
async def get_ical_calendar():
    """
    구글 캘린더 및 삼성 캘린더에서 'URL로 캘린더 추가'를 통해 실시간 자동 동기화할 수 있는
    표준 iCalendar (.ics) 피드를 제공합니다.
    """
    from fastapi.responses import Response
    ics_content = ScheduleManager.generate_ical_feed()
    return Response(
        content=ics_content,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": "inline; filename=skadi_calendar.ics",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )
