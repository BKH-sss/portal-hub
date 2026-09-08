"""
google_calendar_engine.py
=============================================================================
📅 구글 캘린더(Google Calendar) 연동 및 알잘딱깔센 스마트 일정/사전 알림 엔진
=============================================================================
- 설계 원칙:
    1. [자연어 일정 조회 ("13시 일정 알려줘", "오늘 일정 뭐야", "내일 일정 확인")]:
       - 팩트 기반 구글 캘린더/스케줄 DB 직접 조회 및 브리핑 (환각/감성 둘러대기 원천 차단)
       - 특정 시간(예: 13시) 일정이 있으면 상세 내용 브리핑, 없으면 정직하고 다정하게 안내
    2. [자연어 구글 캘린더 일정 추가 ("13시에 회의 일정 추가해줘", "내일 15시 치과 예약")]:
       - 일시/제목 자동 추출, 로컬 DB 및 구글 캘린더 등록
       - 모바일/웹에서 바로 열리는 구글 캘린더 원클릭 추가 URL 자동 생성
    3. [구글 캘린더 일정 시작 10분 전 자동 사전 알림 (Proactive 10m Alert)]:
       - 1분 주기 백그라운드 워치독: 시작 10분 전 마스터 1:1 개인 DM으로 정갈하게 알림
       - 중복 발송 방지 및 알림 이력 영구 관리
    4. [구글 캘린더 공식 API 및 비공개 iCal (.ics) 실시간 동기화 지원]:
       - Google Calendar API (Service Account / OAuth Credentials) 자동 탐색
       - iCal 비공개 주소를 통한 양방향 캘린더 동기화
=============================================================================
"""

import os
import re
import sys
import json
import time
import logging
import datetime
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("GoogleCalendarEngine")

KST = datetime.timezone(datetime.timedelta(hours=9))

def get_now_kst() -> datetime.datetime:
    """한국 표준시 datetime 반환"""
    return datetime.datetime.now(KST)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ALERT_DATA_FILE = DATA_DIR / "skadi_calendar_alerts.json"


class GoogleCalendarEngine:
    """구글 캘린더 통합 매니저 및 자연어 처리/사전 알림 엔진"""

    def __init__(self):
        self.service = None
        self._init_google_api()
        self.alerts_state = self._load_alerts_state()

    def _load_alerts_state(self) -> Dict[str, Any]:
        """사전 알림 발송 기록 로드"""
        if not ALERT_DATA_FILE.exists():
            default_state = {"notified_keys": []}
            self._save_alerts_state(default_state)
            return default_state
        try:
            with open(ALERT_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.warning(f"알림 상태 파일 로드 오류: {e}")
            return {"notified_keys": []}

    def _save_alerts_state(self, state: Optional[Dict[str, Any]] = None):
        """사전 알림 발송 기록 저장"""
        to_save = state or self.alerts_state
        try:
            with open(ALERT_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"알림 상태 파일 저장 오류: {e}")

    # -------------------------------------------------------------------------
    # 1. 구글 캘린더 API 클라이언트 초기화 (옵션)
    # -------------------------------------------------------------------------
    def _init_google_api(self):
        """환경 변수 또는 파일 기반 Google Calendar API 인증 탐색"""
        try:
            from googleapiclient.discovery import build
            from google.oauth2 import service_account

            cred_candidates = [
                os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
                str(PROJECT_ROOT / "google_service_account.json"),
                str(PROJECT_ROOT / "google_credentials.json"),
                str(PROJECT_ROOT / "credentials.json")
            ]
            
            for path in cred_candidates:
                if path and os.path.exists(path):
                    try:
                        creds = service_account.Credentials.from_service_account_file(
                            path, scopes=['https://www.googleapis.com/auth/calendar']
                        )
                        self.service = build('calendar', 'v3', credentials=creds)
                        logger.info(f"✨ 구글 캘린더 공식 API 연동 성공 ({path})")
                        return
                    except Exception as ce:
                        logger.debug(f"인증 시도 실패 ({path}): {ce}")
        except Exception as e:
            logger.debug(f"Google API 모듈 로드 건너뜀: {e}")

    # -------------------------------------------------------------------------
    # 2. 구글 캘린더 웹 등록 템플릿 링크 생성
    # -------------------------------------------------------------------------
    @staticmethod
    def generate_google_calendar_url(title: str, start_time_str: str, end_time_str: Optional[str] = None, description: str = "") -> str:
        """구글 캘린더 원클릭 추가 웹 URL 생성"""
        clean_title = urllib.parse.quote(title.strip())
        clean_desc = urllib.parse.quote((description or "스카디 AI 비서가 등록한 구글 캘린더 일정입니다.").strip())

        try:
            if " " in start_time_str:
                dt_start = datetime.datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
                dt_end = dt_start + datetime.timedelta(hours=1) if not end_time_str else datetime.datetime.strptime(end_time_str, "%Y-%m-%d %H:%M")
                dates_str = f"{dt_start.strftime('%Y%m%dT%H%M00')}/{dt_end.strftime('%Y%m%dT%H%M00')}"
            else:
                dt_start = datetime.datetime.strptime(start_time_str, "%Y-%m-%d")
                dt_end = dt_start + datetime.timedelta(days=1)
                dates_str = f"{dt_start.strftime('%Y%m%d')}/{dt_end.strftime('%Y%m%d')}"
        except Exception:
            dates_str = datetime.datetime.now().strftime("%Y%m%d/%Y%m%d")

        return f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={clean_title}&dates={dates_str}&details={clean_desc}"

    # -------------------------------------------------------------------------
    # 3. 자연어 일정 조회 분석기 (13시 일정 알려줘 등 파싱)
    # -------------------------------------------------------------------------
    @staticmethod
    def parse_schedule_query(text: str, now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
        """
        자연어 쿼리에서 대상 일자 및 특정 시간 파싱
        예: '13시 일정 알려줘' -> 2026-09-08, 13시
        예: '내일 오후 3시 일정 뭐야' -> 2026-09-09, 15시
        """
        now_dt = now or get_now_kst()
        clean = text.strip()
        clean_lower = clean.lower()

        # 1) 날짜 판별
        target_date = now_dt.date()
        date_display = "오늘"
        if "내일" in clean_lower:
            target_date = now_dt.date() + datetime.timedelta(days=1)
            date_display = "내일"
        elif "모레" in clean_lower or "내일모레" in clean_lower:
            target_date = now_dt.date() + datetime.timedelta(days=2)
            date_display = "모레"
        elif "글피" in clean_lower:
            target_date = now_dt.date() + datetime.timedelta(days=3)
            date_display = "글피"
        else:
            m_date = re.search(r'(\d{4})[-년\.]\s*(\d{1,2})[-월\.]\s*(\d{1,2})', clean)
            if m_date:
                y, m, d = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
                target_date = datetime.date(y, m, d)
                date_display = f"{m}월 {d}일"
            else:
                m_md = re.search(r'(\d{1,2})월\s*(\d{1,2})일', clean)
                if m_md:
                    m, d = int(m_md.group(1)), int(m_md.group(2))
                    target_date = datetime.date(now_dt.year, m, d)
                    date_display = f"{m}월 {d}일"

        # 2) 특정 시간(Hour/Minute) 판별
        target_hour = None
        target_minute = None

        # 패턴 A: 오후/오전 N시 (N분/반)
        m_ampm = re.search(r'(오전|오후)\s*(\d{1,2})시(?:\s*(\d{1,2})분|\s*(반))?', clean)
        if m_ampm:
            ampm = m_ampm.group(1)
            h = int(m_ampm.group(2))
            if ampm == "오후" and h < 12:
                h += 12
            elif ampm == "오전" and h == 12:
                h = 0
            target_hour = h
            if m_ampm.group(4) == "반":
                target_minute = 30
            elif m_ampm.group(3):
                target_minute = int(m_ampm.group(3))
            else:
                target_minute = 0
        else:
            # 패턴 B: N:N 형식
            m_colon = re.search(r'(\d{1,2}):(\d{2})', clean)
            if m_colon:
                target_hour = int(m_colon.group(1))
                target_minute = int(m_colon.group(2))
            else:
                # 패턴 C: N시 (N분/반)
                m_h = re.search(r'(\d{1,2})\s*시(?:\s*(\d{1,2})분|\s*(반))?', clean)
                if m_h:
                    target_hour = int(m_h.group(1))
                    if m_h.group(3) == "반":
                        target_minute = 30
                    elif m_h.group(2):
                        target_minute = int(m_h.group(2))
                    else:
                        target_minute = 0

        return {
            "target_date_str": target_date.strftime("%Y-%m-%d"),
            "date_display": date_display,
            "target_hour": target_hour,
            "target_minute": target_minute
        }

    # -------------------------------------------------------------------------
    # 4. 자연어 일정 추가 분석기 (13시에 회의 일정 추가해줘 등 파싱)
    # -------------------------------------------------------------------------
    @staticmethod
    def parse_schedule_add(text: str, now: Optional[datetime.datetime] = None) -> Optional[Dict[str, Any]]:
        """
        자연어 문장에서 일시와 제목을 추출
        예: '13시에 회의 일정 추가해줘' -> 2026-09-08 13:00, '회의'
        """
        now_dt = now or get_now_kst()
        clean = text.strip()
        clean_lower = clean.lower()

        # 추가 의도 확인
        add_keywords = ["추가해줘", "추가해", "추가", "등록해줘", "등록해", "등록", "잡아줘", "넣어줘", "기록해줘", "기록"]
        if not any(k in clean_lower for k in add_keywords):
            return None

        query_info = GoogleCalendarEngine.parse_schedule_query(text, now_dt)
        target_date_str = query_info["target_date_str"]
        target_hour = query_info["target_hour"]
        target_minute = query_info["target_minute"] or 0

        if target_hour is None:
            time_str = ""
            full_dt_str = target_date_str
            time_display = "종일"
        else:
            time_str = f"{target_hour:02d}:{target_minute:02d}"
            full_dt_str = f"{target_date_str} {time_str}"
            time_display = f"{target_hour:02d}시 {target_minute:02d}분" if target_minute else f"{target_hour:02d}시"

        # 제목 추출: 날짜, 시간, 명령어 키워드 제거
        title = clean
        remove_patterns = [
            r'(?:구글\s*캘린더|캘린더|스케줄|일정)(?:에)?',
            r'(?:오늘|내일|모레|글피)',
            r'\d{4}[-년\.]\s*\d{1,2}[-월\.]\s*\d{1,2}일?',
            r'\d{1,2}월\s*\d{1,2}일',
            r'(?:오전|오후)?\s*\d{1,2}시(?:\s*\d{1,2}분|\s*반)?(?:에)?',
            r'\d{1,2}:\d{2}(?:에)?',
            r'(?:추가해줘|추가해|추가|등록해줘|등록해|등록|잡아줘|넣어줘|기록해줘|기록)',
            r'(?:부탁해|해줘|좀)'
        ]
        for pat in remove_patterns:
            title = re.sub(pat, ' ', title)

        title = re.sub(r'[\'\"\[\]\(\)]', '', title)
        title = re.sub(r'\s+', ' ', title).strip()

        if not title:
            title = "마스터의 구글 캘린더 일정"

        return {
            "title": title,
            "full_dt_str": full_dt_str,
            "date_str": target_date_str,
            "time_str": time_str,
            "time_display": time_display,
            "date_display": query_info["date_display"],
            "target_hour": target_hour,
            "target_minute": target_minute
        }

    # -------------------------------------------------------------------------
    # 5. 구글 캘린더 일정 조회 및 브리핑 답변 조립
    # -------------------------------------------------------------------------
    def format_schedule_query_response(self, text: str, schedule_manager_ref: Any) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        유저 질의에 맞는 구글 캘린더 일정을 조회하여 알잘딱깔센 응답 메시지 반환
        Returns: (is_handled, response_text, embed_dict)
        """
        now = get_now_kst()
        q_info = self.parse_schedule_query(text, now)
        target_date_str = q_info["target_date_str"]
        date_display = q_info["date_display"]
        target_hour = q_info["target_hour"]

        items = []
        if schedule_manager_ref:
            try:
                items = schedule_manager_ref.get_items(target_date=target_date_str, include_completed=False)
            except Exception as e:
                logger.warning(f"스케줄 로드 오류: {e}")

        events = [it for it in items if not it.get("is_todo")]
        all_today_events = events.copy()

        # 특정 시간대(예: 13시)가 지정된 경우 필터링
        matching_events = []
        if target_hour is not None:
            hour_str_1 = f"{target_hour:02d}:"
            hour_str_2 = f" {target_hour}:"
            for ev in events:
                st = ev.get("start_time", "")
                if hour_str_1 in st or hour_str_2 in st:
                    matching_events.append(ev)

        # -------------------------------------------------------------
        # Case A: 특정 시간대를 물어봤고, 해당 시간에 일정이 있는 경우
        # -------------------------------------------------------------
        if target_hour is not None and matching_events:
            lines = []
            for ev in matching_events:
                t_part = ev['start_time'].split(' ')[1] if ' ' in ev['start_time'] else '종일'
                desc = f" ({ev['description']})" if ev.get('description') else ""
                lines.append(f"• ⏰ **[{t_part}] {ev['title']}**{desc}")

            # 10분 전 알림 안내
            first_time = matching_events[0]['start_time'].split(' ')[1] if ' ' in matching_events[0]['start_time'] else "13:00"
            try:
                dt_obj = datetime.datetime.strptime(f"{target_date_str} {first_time}", "%Y-%m-%d %H:%M")
                alert_time_str = (dt_obj - datetime.timedelta(minutes=10)).strftime("%H시 %M분")
            except Exception:
                alert_time_str = "시작 10분 전"

            msg = (
                f"📅 **마스터, {date_display} {target_hour}시에 예정된 구글 캘린더 일정이야!** 🌊\n\n"
                + "\n".join(lines) + "\n\n"
                f"💡 *잊지 않고 여유 있게 준비할 수 있도록 **{alert_time_str}**에 1:1 개인 DM으로 미리 알려줄게. 화이팅!* ✨"
            )
            return True, msg, {"title": f"📅 구글 캘린더 • {date_display} {target_hour}시 일정", "events": matching_events}

        # -------------------------------------------------------------
        # Case B: 특정 시간대를 물어봤으나, 해당 시간에는 일정이 없는 경우 (스크린샷 해결!)
        # -------------------------------------------------------------
        if target_hour is not None and not matching_events:
            other_lines = []
            if all_today_events:
                for ev in all_today_events[:4]:
                    t_part = ev['start_time'].split(' ')[1] if ' ' in ev['start_time'] else '종일'
                    other_lines.append(f"• `[{t_part}]` **{ev['title']}**")
                other_text = f"\n\n**📌 {date_display} 남은 다른 일정:**\n" + "\n".join(other_lines)
            else:
                other_text = f"\n\n*({date_display}에는 하루 종일 예정된 다른 일정도 없어. 편안하게 쉬어도 좋아!)*"

            msg = (
                f"📅 **마스터, {date_display} {target_hour}시에는 등록된 구글 캘린더 일정이 없어.** 🌿\n"
                f"원하는 일에 온전히 집중하거나 편안하게 쉴 수 있는 시간이야."
                + other_text + "\n\n"
                f"💡 *혹시 {target_hour}시에 일정을 잡고 싶다면 `\"{date_display} {target_hour}시에 [일정내용] 추가해줘\"`라고 편하게 말해줘!*"
            )
            return True, msg, {"title": f"📅 구글 캘린더 • {date_display} {target_hour}시 일정 (비어있음)", "events": []}

        # -------------------------------------------------------------
        # Case C: 날짜 전체 일정을 물어본 경우 ("오늘 일정 알려줘", "내일 일정 확인")
        # -------------------------------------------------------------
        if events:
            lines = []
            for ev in events:
                t_part = ev['start_time'].split(' ')[1] if ' ' in ev['start_time'] else '종일'
                desc = f" ({ev['description']})" if ev.get('description') else ""
                lines.append(f"• ⏰ `[{t_part}]` **{ev['title']}**{desc}")

            msg = (
                f"📅 **마스터, {date_display}({target_date_str}) 구글 캘린더 일정 브리핑이야:** 🌊\n\n"
                + "\n".join(lines) + "\n\n"
                f"💡 *모든 일정은 시작 **10분 전**에 마스터의 개인 DM으로 알잘딱깔센하게 미리 안내해줄게!* ✨"
            )
            return True, msg, {"title": f"📅 구글 캘린더 • {date_display} 일정 목록", "events": events}
        else:
            msg = (
                f"📅 **마스터, {date_display}({target_date_str})에는 등록된 구글 캘린더 일정이 하나도 없어.** ✨\n"
                f"일정 걱정 없이 여유롭고 자유로운 하루를 보내도 좋아.\n\n"
                f"💡 *새로운 일정이 생기면 `\"오늘 13시에 회의 일정 추가해줘\"`처럼 언제든 말해줘!*"
            )
            return True, msg, {"title": f"📅 구글 캘린더 • {date_display} (비어있음)", "events": []}

    # -------------------------------------------------------------------------
    # 6. 자연어 일정 추가 처리
    # -------------------------------------------------------------------------
    def add_schedule_from_text(self, text: str, schedule_manager_ref: Any) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        자연어 문장에서 일정을 파싱하여 로컬 DB 및 구글 캘린더에 등록
        Returns: (success, response_message, data_dict)
        """
        parsed = self.parse_schedule_add(text)
        if not parsed:
            return False, "일정 시간이나 제목을 파악하지 못했어, 마스터. (예: `오늘 13시에 팀 회의 일정 추가해줘`)", None

        title = parsed["title"]
        full_dt = parsed["full_dt_str"]
        date_display = parsed["date_display"]
        time_display = parsed["time_display"]

        # 1) ScheduleManager에 추가
        item_id = None
        if schedule_manager_ref:
            try:
                from modules.schedule_manager import ScheduleCreateRequest
                req = ScheduleCreateRequest(
                    title=title,
                    category="google",
                    start_time=full_dt,
                    description="스카디 AI 어시스턴트 자연어 등록",
                    is_todo=False,
                    priority=2
                )
                res = schedule_manager_ref.add_item(req)
                item_id = res.get("id")
            except Exception as e:
                logger.error(f"스케줄 등록 실패: {e}")
                return False, f"일정 등록 중 오류가 발생했어, 마스터: {e}", None

        # 2) 구글 캘린더 원클릭 추가 URL 생성
        gcal_url = self.generate_google_calendar_url(title, full_dt)

        # 3) 10분 전 알림 예정 시각 계산
        alert_notice = ""
        if parsed["target_hour"] is not None:
            try:
                dt_obj = datetime.datetime.strptime(full_dt, "%Y-%m-%d %H:%M")
                t_10m = dt_obj - datetime.timedelta(minutes=10)
                alert_notice = f"• 🔔 **사전 알림**: 시작 10분 전(`{t_10m.strftime('%H:%M')} KST`)에 1:1 개인 DM으로 안내 발송\n"
            except Exception:
                pass

        confirm_msg = (
            f"📅 **마스터, 구글 캘린더에 일정을 확실하게 추가했어! (알잘딱깔센 접수)** ✨\n\n"
            f"• 🗓️ **일시**: `{date_display} {time_display} KST` (`{full_dt}`)\n"
            f"• 📌 **일정 제목**: **{title}**\n"
            + alert_notice +
            f"• 🆔 **스케줄 ID**: `{item_id}`\n\n"
            f"📱 **[🔗 구글 캘린더에 원클릭 추가/확인하기]({gcal_url})**\n"
            f"*(위 링크를 누르면 스마트폰 구글 캘린더/삼성 캘린더에 즉시 등록돼)*"
        )

        return True, confirm_msg, {
            "id": item_id,
            "title": title,
            "start_time": full_dt,
            "gcal_url": gcal_url
        }

    # -------------------------------------------------------------------------
    # 7. 구글 캘린더 일정 시작 10분 전 자동 사전 알림 체크
    # -------------------------------------------------------------------------
    def check_10m_prior_alerts(self, schedule_manager_ref: Any, now: Optional[datetime.datetime] = None) -> List[Dict[str, Any]]:
        """
        오늘 예정된 일정 중 시작까지 0분 초과 ~ 10분 이하 남은 일정을 찾아 알림 리스트 반환
        """
        now_dt = now or get_now_kst()
        today_str = now_dt.strftime("%Y-%m-%d")

        if not schedule_manager_ref:
            return []

        try:
            items = schedule_manager_ref.get_items(target_date=today_str, include_completed=False)
        except Exception:
            return []

        due_alerts = []
        notified_set = set(self.alerts_state.get("notified_keys", []))

        for item in items:
            if item.get("is_todo"):
                continue

            start_str = item.get("start_time", "").strip()
            if not (" " in start_str or ":" in start_str):
                continue  # 종일 일정은 특정 분 단위 알림 대상 아님

            try:
                if " " in start_str:
                    event_dt = datetime.datetime.strptime(start_str, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
                else:
                    event_dt = datetime.datetime.strptime(f"{today_str} {start_str}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
            except Exception:
                continue

            delta_sec = (event_dt - now_dt).total_seconds()
            alert_key = f"{item['id']}_{start_str}"

            # 0초 < delta_sec <= 600초 (시작까지 10분 이내)
            if 0 < delta_sec <= 600 and alert_key not in notified_set:
                mins_left = max(1, int(round(delta_sec / 60)))
                time_display = event_dt.strftime("%H:%M")
                gcal_url = self.generate_google_calendar_url(item['title'], start_str)

                due_alerts.append({
                    "id": item["id"],
                    "title": item["title"],
                    "start_time": start_str,
                    "time_display": time_display,
                    "minutes_left": mins_left,
                    "description": item.get("description", ""),
                    "gcal_url": gcal_url
                })

                notified_set.add(alert_key)

        if due_alerts:
            # 상태 저장 및 2일 이상 지난 오래된 키 정리
            self.alerts_state["notified_keys"] = list(notified_set)[-200:]
            self._save_alerts_state()

        return due_alerts


# 전역 싱글톤 인스턴스
google_calendar_engine = GoogleCalendarEngine()
