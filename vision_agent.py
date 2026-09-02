import keyboard
import requests
import time
import sys

SERVER_URL = "http://127.0.0.1:8000/game-event"

def send_event(event_type, time_left=0, details=None):
    if details is None:
        details = {}
        
    payload = {
        "event_type": event_type,
        "map": "오리건",  # 임시
        "time_left": time_left,
        "details": details
    }
    
    try:
        res = requests.post(SERVER_URL, json=payload, timeout=3)
        if res.status_code == 200:
            print(f"[전송성공] {event_type}")
        else:
            print(f"[전송실패] {res.status_code}")
    except Exception as e:
        print(f"[연결에러] {e}")

print("========================================")
print(" 📷 스카디 비전 클라이언트 가동 완료")
print("   - F1: 사망 이벤트 테스트")
print("   - F2: 시간 부족(15초) 테스트")
print("========================================")

# 단축키 설정
keyboard.add_hotkey('F1', lambda: send_event("player_death", details={"cause": "총격", "location": "진입로"}))
keyboard.add_hotkey('F2', lambda: send_event("time_warning", time_left=15))
keyboard.add_hotkey('F3', lambda: send_event("defuser_drop", details={"location": "폭탄 B 구역 근처"}))

print("   - F3: 디퓨저 드랍 테스트 추가됨!")

# 프로그램 유지 (무한 루프)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("종료합니다.")
    sys.exit(0)
