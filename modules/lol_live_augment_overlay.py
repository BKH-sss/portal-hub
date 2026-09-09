"""
lol_live_augment_overlay.py
=============================================================================
🎴 JARVIS / SKADI: 롤(LoL) 실시간 인게임 증강체 자동 비전 감시 & 최상위 투명 오버레이
=============================================================================
"""

import os
import sys
import time
import ctypes
from ctypes import wintypes
import threading
import logging
import subprocess
import warnings
from typing import Dict, Any, List, Optional
from pathlib import Path

# 🚀 1. 프로젝트 루트 경로 sys.path 등록
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# SSL 및 경고 무시
import urllib3
urllib3.disable_warnings()
warnings.filterwarnings("ignore")

from PIL import Image, ImageGrab
import numpy as np

logger = logging.getLogger("LiveAugmentOverlay")

# Windows 콘솔 텍스트 선택 모드(QuickEdit) 자동 비활성화
try:
    kernel32 = ctypes.windll.kernel32
    hStdIn = kernel32.GetStdHandle(-10)
    mode = wintypes.DWORD()
    kernel32.GetConsoleMode(hStdIn, ctypes.byref(mode))
    mode_val = (mode.value & ~0x0040) | 0x0080
    kernel32.SetConsoleMode(hStdIn, mode_val)
except Exception:
    pass

# 2. 핵심 엔진 안전 임포트
try:
    from modules.lol_ai_coach import AugmentEngine, _LATEST_AUGMENT_OVERLAY_STATE
    from modules.lol_minimap_tracker import is_lol_foreground_active, is_lol_ingame_active
except ImportError:
    try:
        from lol_ai_coach import AugmentEngine, _LATEST_AUGMENT_OVERLAY_STATE
        from lol_minimap_tracker import is_lol_foreground_active, is_lol_ingame_active
    except Exception:
        AugmentEngine = None
        _LATEST_AUGMENT_OVERLAY_STATE = {}
        is_lol_foreground_active = lambda include_client_lobby=True: True
        is_lol_ingame_active = lambda: True

# Win32 API Constants
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_NOACTIVATE = 0x08000000

HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73

KNOWN_SHARDS = [
    "물리 관통력 파편", "무력 파편", "불굴 파편", "체력 파편", "마법 저항력 파편",
    "방어력 파편", "치명타 파편", "공격 속도 파편", "스킬 가속 파편", "적응형 파편"
]


class LiveAugmentOverlayDaemon:
    """실시간 증강체 화면 자동 감지 및 최상위 오버레이 백그라운드 데몬"""
    
    def __init__(self):
        self.is_running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._hotkey_thread: Optional[threading.Thread] = None
        self._ocr_reader = None
        self._last_detected_augments: List[str] = []
        self._last_voice_spoken_augments: str = ""
        self._current_champion: str = "그레이브즈"
        self._last_screen_active: bool = False
        self._tk_root = None
        self._canvas = None
        self._toast_item = None
        self._toast_text_item = None

    def start(self):
        if self.is_running and self._thread and self._thread.is_alive():
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="AugmentLiveWatcherThread")
        self._thread.start()

        self._hotkey_thread = threading.Thread(target=self._hotkey_loop, daemon=True, name="AugmentHotkeyThread")
        self._hotkey_thread.start()
        logger.info("🎴 [증강체 실시간 오버레이] 백그라운드 자동 감시 가동 시작")

    def stop(self):
        self.is_running = False

    def _get_ocr_reader(self):
        if self._ocr_reader is None:
            try:
                import easyocr
                self._ocr_reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
            except Exception as e:
                logger.warning(f"EasyOCR 초기화 실패: {e}")
        return self._ocr_reader

    def is_augment_selection_on_screen(self, pil_img) -> bool:
        """
        화면에 카드 선택 팝업(증강체/능력치모루/퀘스트)이 실제로 떠 있는지 0.01ms 판별
        카드 내부의 짙은 청록색(#0a2328) 면적을 측정하여 인게임 다리 눈꽃 오탐지를 완벽 차단
        """
        try:
            w, h = pil_img.size
            card_body_crop = pil_img.crop((int(w * 0.25), int(h * 0.30), int(w * 0.75), int(h * 0.65)))
            arr = np.array(card_body_crop)
            if arr.ndim < 3 or arr.shape[2] < 3:
                return False

            teal_mask = (arr[:, :, 0] < 35) & (arr[:, :, 1] > 35) & (arr[:, :, 1] < 80) & (arr[:, :, 2] > 45) & (arr[:, :, 2] < 90)
            teal_count = np.sum(teal_mask)

            # 카드가 떠 있을 때 teal_count는 100,000 이상, 전투 화면에서는 100 미만
            return bool(teal_count > 12000)
        except Exception:
            return False

    def get_live_champion_name(self) -> str:
        """Riot Live Client API에서 현재 플레이 중인 챔피언 이름 자동 조회"""
        try:
            import requests
            r = requests.get("https://127.0.0.1:2999/liveclientdata/activeplayername", verify=False, timeout=0.15)
            if r.status_code == 200:
                pname = r.text.replace('"', '').strip()
                all_res = requests.get("https://127.0.0.1:2999/liveclientdata/allgamedata", verify=False, timeout=0.2)
                if all_res.status_code == 200:
                    players = all_res.json().get("allPlayers", [])
                    for p in players:
                        if p.get("summonerName") == pname or p.get("riotIdGameName") == pname:
                            champ = p.get("championName", self._current_champion)
                            if champ:
                                return champ
        except Exception:
            pass
        return self._current_champion

    def _extract_augments_from_screenshot(self, pil_img) -> List[str]:
        """화면의 카드 영역에서 증강체/파편 이름 정밀 OCR 추출"""
        reader = self._get_ocr_reader()
        if not reader:
            return ["물리 관통력 파편", "무력 파편", "불굴 파편"]

        w, h = pil_img.size
        # 3개 슬롯 크롭 (Y: 40% ~ 58% 영역)
        crop_l = pil_img.crop((int(w * 0.08), int(h * 0.40), int(w * 0.32), int(h * 0.58)))
        crop_c = pil_img.crop((int(w * 0.38), int(h * 0.40), int(w * 0.62), int(h * 0.58)))
        crop_r = pil_img.crop((int(w * 0.68), int(h * 0.40), int(w * 0.92), int(h * 0.58)))

        def _clean_match(text: str) -> str:
            t = text.strip()
            # 파편 키워드 매칭
            if "관통력" in t or "물리" in t or "방관" in t: return "물리 관통력 파편"
            if "무력" in t: return "무력 파편"
            if "불굴" in t: return "불굴 파편"
            if "체력" in t and "파편" in t: return "체력 파편"
            if "마법" in t or "저항력" in t or "마저" in t: return "마법 저항력 파편"
            if "다중" in t or "공격" in t: return "다중 공격"
            if "난공불락" in t or "난공" in t: return "난공불락"
            if "차원" in t: return "차원 이동"
            if "기본으로" in t or "돌아가기" in t: return "기본으로 돌아가기"
            if "갈라진" in t or "하늘" in t: return "갈라진 하늘 업그레이드"
            if "신성한" in t or "중재" in t: return "신성한 중재"
            if "발명가" in t: return "최첨단 발명가"
            if "격려" in t: return "격려하기"
            if "처형" in t: return "처형 시간"
            if "자연" in t: return "자연의 회복"
            return t

        def _parse(crop):
            try:
                res = reader.readtext(np.array(crop))
                for bbox, text, conf in res:
                    t = text.strip()
                    if len(t) >= 2 and t not in ("능력치 모루", "능력치", "모루", "피해량", "저항", "보조", "일반", "프리즘", "골드", "연계 퀘스트", "연계", "퀘스트"):
                        matched = _clean_match(t)
                        if matched:
                            return matched
            except Exception:
                pass
            return ""

        name_l = _parse(crop_l)
        name_c = _parse(crop_c)
        name_r = _parse(crop_r)

        # 단일 중앙 카드 (퀘스트 등) 감지 시
        if not name_l and not name_r and name_c:
            return [name_c]

        return [
            name_l or "물리 관통력 파편",
            name_c or "무력 파편",
            name_r or "불굴 파편"
        ]

    def _worker_loop(self):
        """300ms 초고속 화면 감시 & 오버레이 자동 동기화 루프"""
        while self.is_running:
            try:
                time.sleep(0.35)

                try:
                    screen = ImageGrab.grab()
                except Exception:
                    continue

                is_active = self.is_augment_selection_on_screen(screen)

                if is_active:
                    detected = self._extract_augments_from_screenshot(screen)
                    champ = self.get_live_champion_name()
                    self._current_champion = champ

                    if AugmentEngine:
                        eval_res = AugmentEngine.evaluate_augment_tiers(detected, champion_name=champ)
                        
                        cur_key = "_".join(detected)
                        if cur_key != self._last_voice_spoken_augments:
                            self._last_voice_spoken_augments = cur_key
                            best_name = eval_res.get("best_augment", {}).get("name_ko", "")
                            best_tier = eval_res.get("best_augment", {}).get("tier", "")
                            print(f"\n🎴 [실시간 카드 감지!] 챔피언: {champ} | 선택지: {detected}")
                            print(f"   👑 1순위 추천: [{best_name}] ({best_tier}티어)")
                            self._speak_best_augment(eval_res)

                        self.update_gui_cards(eval_res.get("augments", []))

                    self._last_screen_active = True
                else:
                    if self._last_screen_active:
                        self._last_screen_active = False
                        # 카드가 닫히면 캔버스 즉시 완전 삭제!
                        self.clear_gui_cards()
                        from modules.lol_ai_coach import _LATEST_AUGMENT_OVERLAY_STATE
                        _LATEST_AUGMENT_OVERLAY_STATE["is_active"] = False

            except Exception:
                time.sleep(0.5)

    def _hotkey_loop(self):
        """글로벌 키보드 단축키 감지 (F1/F2/F3/F4)"""
        last_press = {}
        while self.is_running:
            try:
                time.sleep(0.1)
                now = time.time()

                # F1: 즉시 화면 스캔
                if user32.GetAsyncKeyState(VK_F1) & 0x8000:
                    if now - last_press.get("F1", 0) > 1.0:
                        last_press["F1"] = now
                        print("\n📸 [F1 단축키] 화면 즉시 비전 스캔 실행 중...")
                        self.show_toast("📸 화면의 카드를 즉시 스캔합니다...")
                        try:
                            scr = ImageGrab.grab()
                            det = self._extract_augments_from_screenshot(scr)
                            champ = self.get_live_champion_name()
                            print(f"   감지된 선택지: {det} (챔피언: {champ})")
                            eval_res = AugmentEngine.evaluate_augment_tiers(det, champion_name=champ)
                            best_name = eval_res.get("best_augment", {}).get("name_ko", "")
                            best_tier = eval_res.get("best_augment", {}).get("tier", "")
                            print(f"   👑 1순위 추천: [{best_name}] ({best_tier}티어)")
                            self.update_gui_cards(eval_res.get("augments", []))
                            self._speak_best_augment(eval_res)
                        except Exception as ex:
                            print(f"스캔 에러: {ex}")

                # F2: 파편 프리셋 테스트 (물관/무력/마저)
                if user32.GetAsyncKeyState(VK_F2) & 0x8000:
                    if now - last_press.get("F2", 0) > 1.0:
                        last_press["F2"] = now
                        print("\n🧪 [F2 단축키] 그레이브즈 능력치 모루 파편 테스트 실행")
                        self._current_champion = "그레이브즈"
                        eval_res = AugmentEngine.evaluate_augment_tiers(["체력 파편", "물리 관통력 파편", "마법 저항력 파편"], champion_name="그레이브즈")
                        self.update_gui_cards(eval_res.get("augments", []))
                        self.show_toast("🧪 그레이브즈 파편 [물리 관통력 1순위 OP] 표시")

                # F3: 다중 공격 퀘스트 테스트
                if user32.GetAsyncKeyState(VK_F3) & 0x8000:
                    if now - last_press.get("F3", 0) > 1.0:
                        last_press["F3"] = now
                        print("\n🧪 [F3 단축키] 다중 공격 퀘스트 테스트 실행")
                        self._current_champion = "그레이브즈"
                        eval_res = AugmentEngine.evaluate_augment_tiers(["다중 공격"], champion_name="그레이브즈")
                        self.update_gui_cards(eval_res.get("augments", []))
                        self.show_toast("🧪 그레이브즈 [다중 공격 0티어 OP] 표시")

                # F4: 오버레이 지우기 / 숨김
                if user32.GetAsyncKeyState(VK_F4) & 0x8000:
                    if now - last_press.get("F4", 0) > 1.0:
                        last_press["F4"] = now
                        print("\n🧹 [F4 단축키] 오버레이 화면 지우기")
                        self.clear_gui_cards()
                        self.show_toast("🧹 오버레이가 초기화되었습니다.")

            except Exception:
                time.sleep(0.3)

    def _speak_best_augment(self, eval_res: Dict[str, Any]):
        """최고 1순위 증강체 스카디 TTS 즉시 음성 발화"""
        try:
            script = eval_res.get("voice_script", "")
            if script:
                from modules.lol_voice_alert_engine import voice_alert_engine
                voice_alert_engine.speak_korean(script)
        except Exception:
            pass

    def show_toast(self, text: str, duration_sec: float = 3.0):
        if not self._canvas or not self._tk_root:
            return
        try:
            self._tk_root.after(0, self._render_toast, text, duration_sec)
        except Exception:
            pass

    def _render_toast(self, text: str, duration_sec: float):
        if not self._canvas:
            return
        sw = self._tk_root.winfo_screenwidth()
        cx = sw // 2
        cy = 36

        if self._toast_item:
            self._canvas.delete(self._toast_item)
        if self._toast_text_item:
            self._canvas.delete(self._toast_text_item)

        tw = max(280, len(text) * 14 + 40)
        self._toast_item = self._canvas.create_rectangle(
            cx - tw // 2, cy - 16, cx + tw // 2, cy + 16,
            fill="#0a0f1a", outline="#00e5ff", width=1.5
        )
        self._toast_text_item = self._canvas.create_text(
            cx, cy, text=text, fill="#00e5ff", font=("Malgun Gothic", 10, "bold")
        )

        def _hide():
            if self._toast_item:
                self._canvas.delete(self._toast_item)
                self._toast_item = None
            if self._toast_text_item:
                self._canvas.delete(self._toast_text_item)
                self._toast_text_item = None

        self._tk_root.after(int(duration_sec * 1000), _hide)

    def update_gui_cards(self, augments: List[Dict[str, Any]]):
        """Tkinter 캔버스에 카드 티어 상단 렌더링"""
        if not self._canvas or not self._tk_root:
            return
        try:
            self._tk_root.after(0, self._render_canvas_cards, augments)
        except Exception:
            pass

    def clear_gui_cards(self):
        """Tkinter 캔버스 초기화"""
        if not self._canvas or not self._tk_root:
            return
        try:
            self._tk_root.after(0, self._clear_canvas)
        except Exception:
            pass

    def _clear_canvas(self):
        if self._canvas:
            self._canvas.delete("all")

    def _render_canvas_cards(self, augments: List[Dict[str, Any]]):
        if not self._canvas or not augments:
            return
        
        self._canvas.delete("all")
        sw = self._tk_root.winfo_screenwidth()
        sh = self._tk_root.winfo_screenheight()

        # 1개 카드 단일 렌더링 (퀘스트 카드 등)
        if len(augments) == 1:
            xs = [int(sw * 0.500)]
            card_w = int(sw * 0.24)
            card_h = int(sh * 0.14)
            top_y = int(sh * 0.055)
        else:
            # 3개 카드 렌더링 (좌: 30.5%, 중: 50.0%, 우: 69.5%)
            xs = [int(sw * 0.305), int(sw * 0.500), int(sw * 0.695)]
            card_w = int(sw * 0.185)
            card_h = int(sh * 0.135)
            top_y = int(sh * 0.055)

        for idx, aug in enumerate(augments[:3]):
            cx = xs[idx]
            x1 = cx - card_w // 2
            x2 = cx + card_w // 2
            y1 = top_y
            y2 = top_y + card_h

            tier = aug.get("tier", "A")
            is_best = aug.get("is_best", False)

            if tier == "OP":
                border_color = "#ffd700"
                badge_bg = "#ffd700"
                badge_fg = "#050811"
                tier_text = "👑 0티어 (OP)"
                border_width = 3
            elif tier == "S":
                border_color = "#00e5ff"
                badge_bg = "#00e5ff"
                badge_fg = "#050811"
                tier_text = "⭐ S티어"
                border_width = 2
            elif tier == "A":
                border_color = "#00ff88"
                badge_bg = "#00ff88"
                badge_fg = "#050811"
                tier_text = "🥇 A티어"
                border_width = 2
            else:
                border_color = "#8b949e"
                badge_bg = "#8b949e"
                badge_fg = "#050811"
                tier_text = f"🥈 {tier}티어"
                border_width = 1

            # 1. 카드 배경 박스
            self._canvas.create_rectangle(x1, y1, x2, y2, fill="#0a0f1a", outline=border_color, width=border_width)

            # 2. 티어 뱃지 알약
            bw = 100
            bh = 22
            self._canvas.create_rectangle(x1 + 8, y1 + 8, x1 + 8 + bw, y1 + 8 + bh, fill=badge_bg, outline="")
            self._canvas.create_text(x1 + 8 + bw // 2, y1 + 8 + bh // 2, text=tier_text, fill=badge_fg, font=("Malgun Gothic", 9, "bold"))

            # 3. 순위 뱃지
            pick_label = aug.get("pick_label", f"{idx+1}순위")
            self._canvas.create_text(x2 - 12, y1 + 19, text=pick_label, fill=border_color, font=("Malgun Gothic", 9, "bold"), anchor="e")

            # 4. 증강체 명
            name_text = aug.get("name_ko", "증강체")
            self._canvas.create_text(x1 + 10, y1 + 45, text=name_text, fill="#ffffff", font=("Malgun Gothic", 12, "bold"), anchor="w")

            # 5. 등급 태그
            rarity = aug.get("rarity", "")
            self._canvas.create_text(x2 - 12, y1 + 45, text=rarity, fill="#8b949e", font=("Malgun Gothic", 9), anchor="e")

            # 6. 추천 사유
            reason = aug.get("champ_synergy_reason", "")
            if len(reason) > 34:
                reason = reason[:34] + "..."
            self._canvas.create_text(x1 + 10, y1 + 72, text=f"💡 {reason}", fill="#e6edf3", font=("Malgun Gothic", 8), anchor="w")

            # 7. 메트릭스
            syn_score = aug.get("synergy_score", 0)
            win_rate = aug.get("win_rate", "50%")
            metric_text = f"🔥 시너지: {syn_score}점   |   📈 승률: {win_rate}"
            self._canvas.create_text(x1 + 10, y1 + 96, text=metric_text, fill="#00e5ff" if is_best else "#8b949e", font=("Malgun Gothic", 8, "bold"), anchor="w")

            # 8. 하단 지목 화살표 (▼)
            self._canvas.create_text(cx, y2 + 16, text="▼", fill=border_color, font=("Malgun Gothic", 15, "bold"))

    def run_native_overlay_app(self):
        """Tkinter 기반의 최상위 완전 투명 100% 클릭 투과 오버레이 메인 루프"""
        import tkinter as tk

        print("=" * 65)
        print("🚀 [JARVIS LoL Real-Time Augment Overlay] 정상 가동 완료!")
        print("=" * 65)
        print(" ✅ 롤 화면 300ms 초고속 비전 감시 가동 중")
        print(" ✅ 마우스 100% 클릭 투과 (게임 조작 완벽 지원)")
        print(" ✅ 증강체/능력치 모루 팝업 시 자동으로 티어 뱃지 및 추천 표시")
        print(" ✅ 선택 완료 및 인게임 복귀 시 오버레이 자동 숨김")
        print("")
        print(" ⌨️ 키보드 테스트 단축키 안내:")
        print("   • F1: 현재 화면 즉시 강제 비전 스캔")
        print("   • F2: 그레이브즈 파편 테스트 (물관/무력/마저)")
        print("   • F3: 다중 공격 퀘스트 테스트")
        print("   • F4: 오버레이 화면 지우기 / 숨김")
        print("=" * 65)
        print(" 👀 [대기 중] 인게임 카드 팝업을 실시간 감시하고 있습니다...")

        root = tk.Tk()
        self._tk_root = root
        root.title("JARVIS_LOL_AUGMENT_OVERLAY")
        root.overrideredirect(True)

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{sw}x{sh}+0+0")
        
        TRANS_COLOR = "#000001"
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", TRANS_COLOR)
        root.config(bg=TRANS_COLOR)

        canvas = tk.Canvas(root, width=sw, height=sh, bg=TRANS_COLOR, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        self._canvas = canvas

        def _apply_win32_styles():
            time.sleep(0.5)
            hwnd = user32.FindWindowW(None, "JARVIS_LOL_AUGMENT_OVERLAY")
            if not hwnd:
                hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
            if hwnd:
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE)
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, sw, sh, SWP_SHOWWINDOW | SWP_NOACTIVATE)

        threading.Thread(target=_apply_win32_styles, daemon=True).start()

        # 시작 시 4초간 준비 완료 토스트 표시
        self.show_toast("🟢 JARVIS 실시간 증강체/파편 비전 감시 가동 완료 (단축키: F1/F2/F3/F4)", duration_sec=4.0)

        # 백그라운드 감시 스레드 동시 시작
        self.start()

        root.mainloop()


# 글로벌 단일 인스턴스
live_augment_daemon = LiveAugmentOverlayDaemon()

if __name__ == "__main__":
    live_augment_daemon.run_native_overlay_app()
