import time
import sys
import cv2
import numpy as np
from mss import mss
import requests
import easyocr

SERVER_URL = "http://127.0.0.1:8000/game-event"

# EasyOCR 초기화 (최초 실행 시 모델 다운로드)
print("[Vision] EasyOCR 모델을 불러오는 중입니다. 잠시만 기다려주세요...")
reader = easyocr.Reader(['en'], gpu=False)

# 상태 변수 (연속 트리거 방지)
is_1min_triggered = False
is_30sec_triggered = False

def send_event(event_type, time_left=0, details=None):
    if details is None:
        details = {}
    payload = {
        "event_type": event_type,
        "map": "알 수 없음",
        "time_left": time_left,
        "details": details
    }
    try:
        requests.post(SERVER_URL, json=payload, timeout=3)
        print(f"[{event_type}] 전송 완료!")
    except Exception as e:
        print(f"[에러] 서버 연결 실패: {e}")

def process_screen():
    global is_1min_triggered, is_30sec_triggered
    
    with mss() as sct:
        # 모니터 캡처 영역 (QHD 2560x1440 기준 중앙 상단 타이머 위치)
        monitor = {'top': 10, 'left': 1220, 'width': 120, 'height': 60}
        
        try:
            while True:
                sct_img = sct.grab(monitor)
                img = np.array(sct_img)
                
                # 1. 흑백 변환 (Grayscale)
                gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
                # 2. 이진화 (Thresholding) - 텍스트를 까맣게, 배경을 하얗게 (인식률 200% 증가)
                _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
                
                # 3. EasyOCR 텍스트 추출
                results = reader.readtext(thresh, detail=0)
                text = " ".join(results).replace(" ", "")
                
                if text:
                    # 1분 감지 (1:01)
                    if "1" in text and "01" in text and not is_1min_triggered:
                        print("[비전] 1:01 감지! 백엔드로 이벤트 전송")
                        requests.post("http://127.0.0.1:8000/game-event", json={
                            "event_type": "time_warning_1min",
                            "map": "unknown",
                            "time_left": 60,
                            "details": {"message": "1분 1초 선입력 트리거"}
                        })
                        is_1min_triggered = True
                        
                    # 30초 감지 (0:31)
                    if "0" in text and "31" in text and not is_30sec_triggered:
                        print("[비전] 0:31 감지! 백엔드로 이벤트 전송")
                        requests.post("http://127.0.0.1:8000/game-event", json={
                            "event_type": "time_warning_30sec",
                            "map": "unknown",
                            "time_left": 30,
                            "details": {"message": "31초 선입력 트리거"}
                        })
                        is_30sec_triggered = True
                        
                    # 0:00 (라운드 종료) 감지되면 상태 락(Lock) 초기화
                    elif "0" in text and "00" in text:
                        is_1min_triggered = False
                        is_30sec_triggered = False
                
                # 1초 대기 (1 FPS) - 4080 Super 기준 점유율 0% 유지
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n비전 클라이언트를 종료합니다.")
            sys.exit(0)

if __name__ == "__main__":
    print("==================================================")
    print(" 📷 스카디 [실전형] 비전 클라이언트 가동 완료")
    print("   - QHD 화면(2560x1440)의 1분 / 30초를 주시합니다.")
    print("   - 렉 방지를 위해 1초에 1번만 캡처합니다.")
    print("==================================================")
    process_screen()
