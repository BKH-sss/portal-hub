# -*- coding: utf-8 -*-
"""
자동 실시간 화면 감시 & 선제 브리핑 모듈 (Auto Proactive Vision Monitor)
- 코딩애플 영상처럼 N초마다 마스터의 화면을 자동 캡처하여
- 게임 시작, 데스(죽음), 딴짓/집중 저하 발생 시 마스터가 먼저 말을 걸지 않아도
- 스카디 AI가 선제적으로 호통 및 전술 브리핑을 출력하도록 지원합니다.
"""

import time
import threading
import mss
import mss.tools
import os
import base64
import requests

class AutoProactiveVisionMonitor:
    def __init__(self, interval_seconds=15, server_url="http://localhost:8000/api/proactive_briefing"):
        self.interval_seconds = interval_seconds
        self.server_url = server_url
        self.is_running = False
        self.monitor_thread = None
        self.sct = None

    def capture_screen_base64(self):
        """현재 마스터의 전체 화면을 스크린샷 캡처하여 base64 코드로 변환합니다."""
        try:
            with mss.mss() as sct:
                if len(sct.monitors) > 1:
                    monitor = sct.monitors[1]
                else:
                    monitor = sct.monitors[0]
                sct_img = sct.grab(monitor)
                img_bytes = mss.tools.to_png(sct_img.rgb, sct_img.size)
                return base64.b64encode(img_bytes).decode('utf-8')
        except Exception:
            return None

    def _monitor_loop(self):
        print(f"[AutoVisionMonitor] 실시간 선제 화면 감시 시작 (감시 주기: {self.interval_seconds}초)")
        while self.is_running:
            try:
                img_b64 = self.capture_screen_base64()
                if img_b64:
                    payload = {
                        "image_b64": img_b64,
                        "event_type": "auto_check"
                    }
                    response = requests.post(self.server_url, json=payload, timeout=5)
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("spoken"):
                            print(f"[AutoVisionMonitor] 선제 브리핑 발화: {result.get('briefing')}")
            except Exception:
                pass
            
            time.sleep(max(self.interval_seconds, 5))

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            return True
        return False

    def stop(self):
        self.is_running = False
        print("[AutoVisionMonitor] 실시간 선제 화면 감시 종료")

# 싱글톤 인스턴스
auto_monitor = AutoProactiveVisionMonitor(interval_seconds=15)
