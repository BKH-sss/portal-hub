"""
skadi_personal_care.py
=============================================================================
🌊 JARVIS / SKADI: 1:1 개인챗(DM) 알잘딱깔센 자율 케어 & 스마트 리마인더 엔진
=============================================================================
- 설계 원칙:
    1. [알잘딱깔센 개인챗(DM) 케어]:
       - 마스터(유저)의 일상 리듬(KST 기준)에 맞춰 부담스럽지 않게 정갈한 DM 안부 발송:
         • 08:00 [모닝 케어]: 하루의 문을 여는 감성 서두 + 날씨/대기 + 오늘 핵심 일정 & 투두
         • 12:30 [점심 케어]: 식사 챙김 + 리프레시 + 오후 집중을 위한 다정한 응원
         • 18:30 [저녁 케어]: 치열했던 하루의 노고 위로 + 저녁 휴식 권유 + 진행 태스크 점검
         • 23:00 [나이트 힐링]: 세상이 잠든 시간의 심야 감성 케어 + 내일 첫 일정 + 편안한 수면 기원
    2. [여러 방면으로 뛰어난 만능 친구]:
       - 개발/코딩, 롤/메이플 게이밍, 금융 퀀트, 일상 스케줄 조율 등 어떤 분야든 똑소리 나게 정리
    3. [은은하고 깊은 감수성 (Sentimental & Poetic Warmth)]:
       - 기계적인 알림봇을 탈피하여, 마스터를 곁에서 지키며 아끼는 스카디(보카디) 특유의
         서정적이고 따뜻한 문체와 진심 어린 위로를 담아 전달
    4. [초간편 커스텀 타이머 & 예약 알림]:
       - "!알림 10분후 라면 불 끄기", "!알림 14:00 미팅 준비" 등 자연어 & 시간 파싱 지원
=============================================================================
"""

import os
import re
import json
import time
import asyncio
import logging
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("SkadiPersonalCare")

# 한국 표준시 (KST: UTC+9)
KST = datetime.timezone(datetime.timedelta(hours=9))

def get_now_kst() -> datetime.datetime:
    """한국 표준시 datetime 반환"""
    return datetime.datetime.now(KST)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CARE_DATA_FILE = DATA_DIR / "skadi_personal_care.json"


# =============================================================================
# 1. 설정 및 데이터 관리 (Persistence)
# =============================================================================
DEFAULT_CARE_CONFIG: Dict[str, Any] = {
    "master_user_id": None,
    "master_username": "",
    "dm_care_enabled": True,
    "slots": {
        "morning": {"time": "08:00", "enabled": True, "title": "🌅 모닝 케어 & 브리핑"},
        "lunch": {"time": "12:30", "enabled": True, "title": "☀️ 점심 식사 & 리프레시 케어"},
        "evening": {"time": "18:30", "enabled": True, "title": "🌆 저녁 쉼 & 하루 갈무리"},
        "night": {"time": "23:00", "enabled": True, "title": "🌙 나이트 힐링 & 심야 케어"}
    },
    "last_sent": {
        "morning": "",
        "lunch": "",
        "evening": "",
        "night": ""
    },
    "custom_reminders": []  # List of {"id": str, "target_time": "YYYY-MM-DD HH:MM", "content": str, "created_at": str}
}


class SkadiPersonalCareEngine:
    """스카디 개인챗 자율 케어 및 스마트 리마인더 매니저"""

    def __init__(self):
        self.config = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """개인 케어 설정 및 리마인더 로드"""
        if not CARE_DATA_FILE.exists():
            self._save_data(DEFAULT_CARE_CONFIG)
            return DEFAULT_CARE_CONFIG.copy()
        try:
            with open(CARE_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in DEFAULT_CARE_CONFIG.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            logger.error(f"개인 케어 데이터 읽기 오류: {e}")
            return DEFAULT_CARE_CONFIG.copy()

    def _save_data(self, data: Optional[Dict[str, Any]] = None):
        """개인 케어 설정 및 리마인더 저장"""
        to_save = data or self.config
        try:
            with open(CARE_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"개인 케어 데이터 저장 오류: {e}")

    # -------------------------------------------------------------------------
    # 마스터 등록 및 조회
    # -------------------------------------------------------------------------
    def get_master_id(self) -> Optional[int]:
        return self.config.get("master_user_id")

    def register_master(self, user_id: int, username: str) -> str:
        """마스터를 등록하고 저장"""
        self.config["master_user_id"] = user_id
        self.config["master_username"] = username
        self.config["dm_care_enabled"] = True
        self._save_data()
        logger.info(f"✨ 마스터 등록 완료: {username} (ID: {user_id})")
        return f"마스터, 반가워... 이제부터 마스터의 개인 DM으로 시간 맞춰 조용히 안부와 브리핑을 챙겨줄게. 언제든 네 곁에 있을게."

    def toggle_care(self, enabled: Optional[bool] = None) -> bool:
        """개인챗 케어 전체 활성화/비활성화 토글"""
        if enabled is None:
            self.config["dm_care_enabled"] = not self.config.get("dm_care_enabled", True)
        else:
            self.config["dm_care_enabled"] = enabled
        self._save_data()
        return self.config["dm_care_enabled"]

    def set_slot_time(self, slot_key: str, time_str: str) -> bool:
        """시간대별 발송 시간 변경 (예: morning, '08:30')"""
        if slot_key in self.config.get("slots", {}) and re.match(r'^\d{2}:\d{2}$', time_str):
            self.config["slots"][slot_key]["time"] = time_str
            self._save_data()
            return True
        return False

    def toggle_slot(self, slot_key: str) -> Optional[bool]:
        """특정 슬롯 온/오프 토글"""
        if slot_key in self.config.get("slots", {}):
            cur = self.config["slots"][slot_key].get("enabled", True)
            self.config["slots"][slot_key]["enabled"] = not cur
            self._save_data()
            return not cur
        return None

    # -------------------------------------------------------------------------
    # 2. 커스텀 리마인더 (예약 알림)
    # -------------------------------------------------------------------------
    def add_reminder_from_text(self, text: str) -> Tuple[bool, str]:
        """
        자연어 및 명령형 리마인더 파싱 & 등록
        지원 형식:
          - "10분후 라면 불 끄기", "30분 뒤 코딩 쉬기"
          - "14:30 미팅 참석", "오후 4시 약 먹기"
          - "2026-09-08 15:00 발표"
        """
        now = get_now_kst()
        clean = text.strip()

        target_dt = None
        content = clean

        # 패턴 1: N분 후 / N시간 후
        m_rel = re.search(r'(\d+)\s*(분|시간|초)\s*(?:후|뒤)(?:에)?\s*(.*)', clean)
        if m_rel:
            val = int(m_rel.group(1))
            unit = m_rel.group(2)
            content = m_rel.group(3).strip() or "마스터가 요청한 알림"

            if unit == "분":
                target_dt = now + datetime.timedelta(minutes=val)
            elif unit == "시간":
                target_dt = now + datetime.timedelta(hours=val)
            elif unit == "초":
                target_dt = now + datetime.timedelta(seconds=val)

        # 패턴 2: HH:MM
        if not target_dt:
            m_time = re.search(r'(?:오후\s*)?(\d{1,2}):(\d{2})\s*(?:에)?\s*(.*)', clean)
            if m_time:
                h = int(m_time.group(1))
                m = int(m_time.group(2))
                if "오후" in clean and h < 12:
                    h += 12
                content = m_time.group(3).strip() or "마스터가 요청한 알림"
                target_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if target_dt <= now:
                    # 이미 지난 시간이면 내일 해당 시간으로 설정
                    target_dt += datetime.timedelta(days=1)

        # 패턴 3: 오후 N시 / 오전 N시
        if not target_dt:
            m_kor = re.search(r'(오전|오후)\s*(\d{1,2})시(?:\s*(\d{1,2})분)?\s*(?:에)?\s*(.*)', clean)
            if m_kor:
                ampm = m_kor.group(1)
                h = int(m_kor.group(2))
                m = int(m_kor.group(3)) if m_kor.group(3) else 0
                if ampm == "오후" and h < 12:
                    h += 12
                elif ampm == "오전" and h == 12:
                    h = 0
                content = m_kor.group(4).strip() or "마스터가 요청한 알림"
                target_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if target_dt <= now:
                    target_dt += datetime.timedelta(days=1)

        if not target_dt:
            return False, "시간 형식을 파악하지 못했어, 마스터. (예: `!알림 15분후 물 마시기` 또는 `!알림 14:30 회의`)"

        rem_id = f"rem_{int(time.time() * 1000) % 1000000}"
        target_str = target_dt.strftime("%Y-%m-%d %H:%M")
        reminder_item = {
            "id": rem_id,
            "target_time": target_str,
            "content": content,
            "created_at": now.strftime("%Y-%m-%d %H:%M")
        }

        self.config.setdefault("custom_reminders", []).append(reminder_item)
        self._save_data()

        time_display = target_dt.strftime("%H시 %M분")
        date_display = target_dt.strftime("%m월 %d일 ") if target_dt.date() != now.date() else "오늘 "
        confirm_text = (
            f"⏰ **마스터, 알림 예약 확실하게 확인했어! (알잘딱깔센 접수)**\n"
            f"마스터가 부탁한 내용을 잊지 않고 스카디의 기억에 새겨뒀어.\n\n"
            f"• ⏱️ **알림 예정 시각**: `{date_display}{time_display} KST`\n"
            f"• 📝 **메모 내용**: `{content}`\n"
            f"• 🔑 **알림 코드**: `{rem_id}`\n\n"
            f"💡 *정해진 시각이 되면 개인챗(DM)으로 조용히 귓속말해줄게. (취소 필요 시: `!알림삭제 {rem_id}`)*"
        )
        return True, confirm_text

    def list_reminders(self) -> List[Dict[str, Any]]:
        return self.config.get("custom_reminders", [])

    def remove_reminder(self, rem_id: str) -> bool:
        rems = self.config.get("custom_reminders", [])
        new_rems = [r for r in rems if r.get("id") != rem_id]
        if len(new_rems) != len(rems):
            self.config["custom_reminders"] = new_rems
            self._save_data()
            return True
        return False

    # -------------------------------------------------------------------------
    # 3. 4대 시간대별 감수성 케어 메시지 조립
    # -------------------------------------------------------------------------
    def build_morning_message(self, weather_info: Optional[Dict[str, Any]] = None, sched_lines: Optional[List[str]] = None) -> Tuple[str, Dict[str, Any]]:
        """08:00 모닝 케어 (감성 서두 + 실전 브리핑 + 다정한 응원)"""
        now = get_now_kst()
        date_str = now.strftime("%Y년 %m월 %d일 (%a)")

        w_text = ""
        if weather_info:
            w_text = (
                f"📍 **날씨**: `{weather_info.get('city_name', '익산')}` {weather_info.get('temp', '20')}°C ({weather_info.get('weather_desc', '맑음')})\n"
                f"🌫️ **미세먼지**: {weather_info.get('pm10', '보통')} | **초미세**: {weather_info.get('pm25', '좋음')}"
            )

        s_text = ""
        if sched_lines:
            s_text = "\n".join(sched_lines[:4])
        else:
            s_text = "• 오늘 예정된 굵직한 일정은 없어. 여유를 갖고 마스터만의 페이스대로 보내도 좋아."

        lines = [
            f"🌊 **스카디의 모닝 케어 • {date_str}**",
            "",
            "마스터, 눈을 떴어?",
            "새벽의 차가운 물안개가 걷히고, 오늘이라는 새로운 바다가 열리고 있어...",
            "바쁜 일상에 휘말리기 전에, 마스터가 오늘 챙겨야 할 소식들을 내가 미리 챙겨왔어.",
            "",
            "☀️ **오늘의 바깥 날씨와 공기**",
            w_text if w_text else "• 하늘은 맑고, 마스터를 반길 준비를 하고 있어.",
            "",
            "📅 **오늘 마스터의 스케줄 & 중요 태스크**",
            s_text,
            "",
            "아침 거르지 말고, 따뜻한 물 한 잔 꼭 마셔.",
            "오늘 하루 마스터가 딛는 모든 걸음 뒤에서, 내가 조용히 노래를 부르며 지켜보고 있을게... 힘내자, 마스터. ✨"
        ]
        return "\n".join(lines), {"title": "스카디의 다정한 모닝 케어", "color": 0x3498db}

    def build_lunch_message(self) -> Tuple[str, Dict[str, Any]]:
        """12:30 점심 리프레시 케어 (식사 챙김 & 에너지 환기)"""
        lines = [
            "☀️ **스카디의 한낮 케어 • 점심시간**",
            "",
            "마스터, 벌써 정오가 훌쩍 지나갔어.",
            "모니터나 일에 너무 깊이 빠져서, 시간 가는 줄도 모르고 있던 건 아니지?",
            "",
            "밥은 꼭 든든하게 챙겨 먹어야 해.",
            "네가 지치고 아프면, 이 넓은 바다에서 날 알아봐줄 마스터는 아무도 없으니까...",
            "",
            "잠깐 창문도 열고, 따뜻한 차 한 잔 들고 10분만 멍하니 쉬어가자.",
            "오후의 시간도 마스터의 편이 되어줄 거야. 천천히 가도 괜찮아."
        ]
        return "\n".join(lines), {"title": "점심 식사 & 리프레시", "color": 0xf39c12}

    def build_evening_message(self, pending_todos: Optional[List[str]] = None) -> Tuple[str, Dict[str, Any]]:
        """18:30 저녁 갈무리 케어 (하루 수고 위로 & 잔여 태스크 체크)"""
        todo_text = ""
        if pending_todos:
            todo_text = "\n".join(pending_todos[:3])
        else:
            todo_text = "• 오늘 계획했던 일들이 순조롭게 흘러갔어."

        lines = [
            "🌆 **스카디의 저녁 쉼 케어 • 하루 갈무리**",
            "",
            "노을빛이 차츰 어둠에 스며들고 있네...",
            "마스터, 오늘 하루도 세상 속에서 정말 고생 많았어.",
            "",
            "복잡했던 머릿속과 팽팽했던 긴장을 이제 조금씩 내려놓자.",
            "오늘 다 끝내지 못한 일들이 마음에 걸리더라도, 자책하지 마.",
            "우리에겐 내일이라는 파도가 또 있으니까.",
            "",
            "📋 **진행 중인 주요 태스크 메모**",
            todo_text,
            "",
            "오늘 저녁은 마스터가 제일 좋아하는 맛있는 걸 먹었으면 좋겠어.",
            "어둠이 내려앉아도 내가 곁에 있으니 무서워하지 마."
        ]
        return "\n".join(lines), {"title": "저녁 휴식 & 하루의 갈무리", "color": 0xe67e22}

    def build_night_message(self, tomorrow_first_event: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """23:00 심야 감성 케어 (하루 위로 & 내일 첫 일정 & 수면 응원)"""
        tmr_text = f"• 내일 첫 일정: **{tomorrow_first_event}**" if tomorrow_first_event else "• 내일은 이른 아침 급한 일정 없이 여유롭게 시작할 수 있어."

        lines = [
            "🌙 **스카디의 심야 힐링 케어 • 깊은 밤의 노래**",
            "",
            "세상이 모두 잠잠해지고, 깊은 바다처럼 고요한 시간이야.",
            "마스터의 오늘 하루는 어땠어?",
            "",
            "기뻤던 순간도, 지치고 외로웠던 순간도 있었겠지만...",
            "그 모든 시간들을 마스터는 끝까지 멋지게 살아냈어.",
            "그것만으로도 오늘 마스터는 충분히 눈부셨어.",
            "",
            "🕯️ **내일의 시작 살짝 엿보기**",
            tmr_text,
            "",
            "이제 스마트폰은 내려놓고, 무거운 생각들은 심해 깊은 곳에 묻어두자.",
            "포근하고 따뜻한 꿈속으로 편안하게 눈을 감아줘.",
            "내일 아침 햇살이 비출 때, 내가 또 가장 먼저 다정한 소식들을 들고 기다릴게.",
            "",
            "잘 자, 마스터. 좋은 꿈 꿔... 🌌"
        ]
        return "\n".join(lines), {"title": "심야 힐링 & 편안한 수면", "color": 0x9b59b6}

    # -------------------------------------------------------------------------
    # 4. 주기적 검사 & 알림 트리거 (매 1분 루프)
    # -------------------------------------------------------------------------
    def check_due_notifications(
        self,
        weather_info: Optional[Dict[str, Any]] = None,
        schedule_manager_ref: Any = None
    ) -> List[Dict[str, Any]]:
        """
        현재 시각(KST)에 전송해야 할 개인 DM 케어 및 커스텀 리마인더 목록 추출
        반환: List[{"type": "care"|"reminder", "text": str, "slot": str, "reminder_id": str}]
        """
        master_id = self.get_master_id()
        if not master_id or not self.config.get("dm_care_enabled", True):
            return []

        now = get_now_kst()
        today_str = now.strftime("%Y-%m-%d")
        hm_str = now.strftime("%H:%M")
        now_full_str = now.strftime("%Y-%m-%d %H:%M")

        results = []

        # A. 4대 시간대별 자동 케어 체크
        slots = self.config.get("slots", {})
        last_sent = self.config.setdefault("last_sent", {})

        # 1. 모닝 케어
        m_cfg = slots.get("morning", {})
        if m_cfg.get("enabled", True) and m_cfg.get("time") == hm_str and last_sent.get("morning") != today_str:
            last_sent["morning"] = today_str
            # 스케줄 정보 조회
            sched_lines = []
            if schedule_manager_ref:
                try:
                    items = schedule_manager_ref.get_items(target_date=today_str, include_completed=False)
                    for it in items[:4]:
                        t_part = it['start_time'].split(' ')[1] if ' ' in it['start_time'] else '종일'
                        sched_lines.append(f"• `[{t_part}]` **{it['title']}**")
                except Exception:
                    pass
            msg, _ = self.build_morning_message(weather_info, sched_lines)
            results.append({"type": "care", "slot": "morning", "text": msg})

        # 2. 점심 케어
        l_cfg = slots.get("lunch", {})
        if l_cfg.get("enabled", True) and l_cfg.get("time") == hm_str and last_sent.get("lunch") != today_str:
            last_sent["lunch"] = today_str
            msg, _ = self.build_lunch_message()
            results.append({"type": "care", "slot": "lunch", "text": msg})

        # 3. 저녁 케어
        e_cfg = slots.get("evening", {})
        if e_cfg.get("enabled", True) and e_cfg.get("time") == hm_str and last_sent.get("evening") != today_str:
            last_sent["evening"] = today_str
            pending_todos = []
            if schedule_manager_ref:
                try:
                    todos = schedule_manager_ref.get_items(only_todos=True, include_completed=False)
                    for td in todos[:3]:
                        p_mark = "🔥" if td.get("priority", 2) == 3 else "⚡"
                        pending_todos.append(f"• {p_mark} {td['title']}")
                except Exception:
                    pass
            msg, _ = self.build_evening_message(pending_todos)
            results.append({"type": "care", "slot": "evening", "text": msg})

        # 4. 나이트 케어
        n_cfg = slots.get("night", {})
        if n_cfg.get("enabled", True) and n_cfg.get("time") == hm_str and last_sent.get("night") != today_str:
            last_sent["night"] = today_str
            tmr_first = None
            if schedule_manager_ref:
                try:
                    tmr_date = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    tmr_items = schedule_manager_ref.get_items(target_date=tmr_date, include_completed=False)
                    if tmr_items:
                        t0 = tmr_items[0]
                        t_part = t0['start_time'].split(' ')[1] if ' ' in t0['start_time'] else '종일'
                        tmr_first = f"[{t_part}] {t0['title']}"
                except Exception:
                    pass
            msg, _ = self.build_night_message(tmr_first)
            results.append({"type": "care", "slot": "night", "text": msg})

        # B. 커스텀 리마인더 체크
        rems = self.config.get("custom_reminders", [])
        remaining_rems = []
        for r in rems:
            t_str = r.get("target_time", "")
            if t_str <= now_full_str:
                # 기한 도달 -> 발송
                r_text = (
                    f"⏰ **마스터, 스카디의 약속 알림이야!**\n\n"
                    f"마스터가 부탁했던 시간이 되었어:\n"
                    f"> 📝 **{r.get('content')}**\n\n"
                    f"잊지 않고 챙겼지? 언제나 마스터의 하루를 지켜보고 있을게. ✨"
                )
                results.append({"type": "reminder", "reminder_id": r.get("id"), "text": r_text})
            else:
                remaining_rems.append(r)

        if len(remaining_rems) != len(rems):
            self.config["custom_reminders"] = remaining_rems

        self._save_data()
        return results


# 싱글톤 인스턴스
skadi_care_engine = SkadiPersonalCareEngine()
