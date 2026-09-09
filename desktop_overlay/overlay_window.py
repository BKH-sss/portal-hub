"""
desktop_overlay/overlay_window.py
-----------------------------------------------------------------------------
🖥️ Transparent Always-on-Top Click-Through Gaming HUD Overlay Window
-----------------------------------------------------------------------------
- Tkinter Canvas 기반의 초경량 고성능 다크 HUD 렌더러 (0 외부 의존성)
- Windows API (ctypes user32)를 사용한 완벽한 Click-Through (게임 입력 무방해)
- 상단 딜교 팁, 중단 아이템/복귀 알림, 하단 이벤트 타임라인 3단 레이아웃
-----------------------------------------------------------------------------
"""

import sys
import ctypes
import tkinter as tk
from typing import Dict, List, Any, Optional

try:
    from . import config
except ImportError:
    import config


class OverlayWindow:
    """투명 게임 오버레이 윈도우"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LoL Desktop Intelligence Overlay")
        self.root.overrideredirect(True)                # 윈도우 프레임/타이틀바 제거
        self.root.attributes("-topmost", config.ALWAYS_ON_TOP)
        self.root.attributes("-alpha", config.OVERLAY_OPACITY)
        
        # 윈도우 위치 및 크기 설정
        geo_str = f"{config.OVERLAY_WIDTH}x{config.OVERLAY_HEIGHT}+{config.OVERLAY_POS_X}+{config.OVERLAY_POS_Y}"
        self.root.geometry(geo_str)
        self.root.configure(bg=config.COLOR_BG)

        # 캔버스 위젯 생성
        self.canvas = tk.Canvas(
            self.root,
            width=config.OVERLAY_WIDTH,
            height=config.OVERLAY_HEIGHT,
            bg=config.COLOR_BG,
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 윈도우 투명 클릭 관통 (Click-Through) 설정
        if sys.platform == "win32" and config.ENABLE_CLICK_THROUGH:
            self._apply_click_through()

        # 현재 렌더링 상태 캐시
        self._is_visible = False
        self._current_state: Dict[str, Any] = {}

    def _apply_click_through(self):
        """Windows API를 활용하여 게임 클릭을 가로채지 않는 투명 레이어 설정"""
        try:
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            WS_EX_TOOLWINDOW = 0x80

            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                hwnd,
                GWL_EXSTYLE,
                style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
            )
        except Exception as e:
            print(f"Click-through 적용 경고: {e}")

    def show(self):
        if not self._is_visible:
            self.root.deiconify()
            self._is_visible = True

    def hide(self):
        if self._is_visible:
            self.root.withdraw()
            self._is_visible = False

    def update_data(self, state: Dict[str, Any]):
        """새로운 게임 상태를 캔버스에 렌더링 (메인 UI 스레드 안전 호출)"""
        self._current_state = state
        self._render()

    def _draw_rounded_rect(self, x1, y1, x2, y2, radius=8, **kwargs):
        """둥근 사각 컨테이너 박스 그리기"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _render(self):
        """HUD 전체 요소 실시간 렌더링"""
        self.canvas.delete("all")

        w = config.OVERLAY_WIDTH
        h = config.OVERLAY_HEIGHT

        # 1. 외곽 메인 컨테이너
        self._draw_rounded_rect(4, 4, w - 4, h - 4, radius=12, fill=config.COLOR_BG, outline=config.COLOR_BORDER, width=1.5)

        # 2. 헤더 바 (상태 및 킬 스위치 배지)
        is_in_game = self._current_state.get("is_in_game", False)
        game_time_str = self._current_state.get("game_time_str", "00:00")
        my_champ = self._current_state.get("my_champion", "LoL Overlay")

        status_color = config.COLOR_GREEN if is_in_game else config.COLOR_TEXT_MUTED
        status_text = f"🟢 LIVE [{game_time_str}] • {my_champ}" if is_in_game else "⚪ STANDBY (대기 중)"

        self._draw_rounded_rect(12, 12, w - 12, 44, radius=6, fill=config.COLOR_CARD_BG, outline=config.COLOR_BORDER)
        self.canvas.create_text(24, 28, text=status_text, fill=status_color, font=("Malgun Gothic", 10, "bold"), anchor="w")
        self.canvas.create_text(w - 24, 28, text="YOUR.GG Style", fill=config.COLOR_ACCENT, font=("Segoe UI", 9, "bold"), anchor="e")

        curr_y = 52

        # 3. [섹션 1] 초반 라인 딜 교환 팁 (Feature 1)
        lane_tip = self._current_state.get("lane_tip")
        if config.ENABLE_EARLY_LANE_TIPS and lane_tip and lane_tip.get("is_active"):
            card_h = 135
            self._draw_rounded_rect(12, curr_y, w - 12, curr_y + card_h, radius=8, fill=config.COLOR_CARD_BG, outline=config.COLOR_ACCENT, width=1.2)
            
            # 섹션 타이틀
            title = f"⚔️ 초반 라인 딜교 팁 ({lane_tip['my_name_ko']} vs {lane_tip['enemy_name_ko']})"
            self.canvas.create_text(22, curr_y + 16, text=title, fill=config.COLOR_ACCENT, font=("Malgun Gothic", 10, "bold"), anchor="w")
            
            # 팁 내용
            t1 = f"• 스파이크: {lane_tip['spike_level']}레벨 ({lane_tip['my_style']})"
            t2 = f"• 권장: {lane_tip['my_advantage_tip'][:24]}..."
            t3 = f"• 주의: {lane_tip['enemy_counter_tip'][:24]}..."

            self.canvas.create_text(22, curr_y + 40, text=t1, fill=config.COLOR_GOLD, font=("Malgun Gothic", 9), anchor="w")
            self.canvas.create_text(22, curr_y + 65, text=t2, fill=config.COLOR_TEXT_WHITE, font=("Malgun Gothic", 9), anchor="w")
            self.canvas.create_text(22, curr_y + 90, text=t3, fill=config.COLOR_ALERT_RED, font=("Malgun Gothic", 9), anchor="w")

            curr_y += card_h + 10

        # 4. [섹션 2] 복귀 타이밍 예측 & 아이템 알림 (Feature 2 & 3)
        ret_pred = self._current_state.get("return_prediction")
        item_alerts = self._current_state.get("item_alerts", [])

        # A. 상대 복귀 타이밍 추정치 카드
        if config.ENABLE_RETURN_PREDICTION and ret_pred:
            card_h = 75
            border_c = config.COLOR_GOLD if ret_pred.get("is_dead") else config.COLOR_BORDER
            self._draw_rounded_rect(12, curr_y, w - 12, curr_y + card_h, radius=8, fill=config.COLOR_CARD_BG, outline=border_c, width=1.2)

            self.canvas.create_text(22, curr_y + 16, text=ret_pred.get("label", "상대 복귀 예상"), fill=config.COLOR_GOLD, font=("Malgun Gothic", 9, "bold"), anchor="w")
            if ret_pred.get("is_dead"):
                sub_txt = f"• {ret_pred['champion']} 약 {ret_pred['estimated_time_str']} 후 복귀 예상"
                self.canvas.create_text(22, curr_y + 38, text=sub_txt, fill=config.COLOR_TEXT_WHITE, font=("Malgun Gothic", 9, "bold"), anchor="w")
                self.canvas.create_text(22, curr_y + 56, text=f"👉 {ret_pred['action_advice']}", fill=config.COLOR_GREEN, font=("Malgun Gothic", 8), anchor="w")
            else:
                self.canvas.create_text(22, curr_y + 38, text=f"• {ret_pred['champion']} 라인전 진행 중 (막타 딜교 노리기)", fill=config.COLOR_TEXT_MUTED, font=("Malgun Gothic", 9), anchor="w")

            curr_y += card_h + 10

        # B. 핵심 아이템 완성 알림 배너
        if config.ENABLE_CORE_ITEM_ALERT and item_alerts:
            for alert in item_alerts[-2:]:   # 최근 최대 2개 표시
                banner_h = 55
                self._draw_rounded_rect(12, curr_y, w - 12, curr_y + banner_h, radius=6, fill="#2c1517", outline=config.COLOR_ALERT_RED, width=1.5)
                self.canvas.create_text(22, curr_y + 16, text=f"🚨 [{alert['champion']}] {alert['item_name']} 완성!", fill=config.COLOR_ALERT_RED, font=("Malgun Gothic", 9, "bold"), anchor="w")
                self.canvas.create_text(22, curr_y + 36, text=f"💡 {alert['alert_msg']}", fill=config.COLOR_TEXT_WHITE, font=("Malgun Gothic", 8), anchor="w")
                curr_y += banner_h + 8

        # 5. [섹션 3] 골드/오브젝트 이벤트 타임라인 (Feature 4)
        if config.ENABLE_EVENT_TIMELINE:
            timeline = self._current_state.get("timeline", [])
            rem_h = h - curr_y - 12
            if rem_h > 80:
                self._draw_rounded_rect(12, curr_y, w - 12, h - 12, radius=8, fill=config.COLOR_CARD_BG, outline=config.COLOR_BORDER)
                self.canvas.create_text(22, curr_y + 16, text="⏱️ 경기 이벤트 타임라인", fill=config.COLOR_ACCENT, font=("Malgun Gothic", 9, "bold"), anchor="w")

                line_y = curr_y + 36
                for ev in reversed(timeline[-5:]):   # 최신 5개
                    if line_y + 20 > h - 16:
                        break
                    icon_time = f"{ev['icon']} [{ev['time']}] {ev['title']}"
                    self.canvas.create_text(22, line_y, text=icon_time, fill=config.COLOR_TEXT_WHITE, font=("Malgun Gothic", 8, "bold"), anchor="w")
                    self.canvas.create_text(180, line_y, text=ev['desc'][:16], fill=config.COLOR_TEXT_MUTED, font=("Malgun Gothic", 8), anchor="w")
                    line_y += 22

    def run_loop(self):
        """메인 Tkinter 이벤트 루프 시작"""
        self.root.mainloop()
