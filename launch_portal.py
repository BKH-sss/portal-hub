"""
launch_portal.py
==============================================================================
ERECHTHEION KOREA & ORBIS GLOBAL & SKADI CHESS 웹 포털 로컬 실행기
==============================================================================
- 포트 8080에서 경량 HTTP 정적 웹 서버를 구동합니다.
- 기본 브라우저로 http://127.0.0.1:8080/ (메인 포털)을 자동 실행합니다.
- 국내 포털, 글로벌 외신(/global/), 스카디 체스(skadi_chess.html)를 즉시 이용할 수 있습니다.
==============================================================================
"""

import os
import sys
import time
import socket
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def run_server(port: int):
    os.chdir(PROJECT_ROOT)
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
    httpd.serve_forever()

def main():
    print("================================================================")
    print(" [ERECHTHEION KOREA · ORBIS GLOBAL · SKADI CHESS] 포털 가동 중")
    print("================================================================")
    
    port = 8080
    if not is_port_in_use(port):
        server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
        server_thread.start()
        time.sleep(0.5)
        print(f" 로컬 웹 서버 가동 완료: http://127.0.0.1:{port}/")
    else:
        print(f" 로컬 웹 서버가 이미 작동 중입니다: http://127.0.0.1:{port}/")

    portal_url = f"http://127.0.0.1:{port}/"
    print(f" 브라우저를 엽니다: {portal_url}")
    print("    - 국내 포털: http://127.0.0.1:8080/")
    print("    - 글로벌 외신: http://127.0.0.1:8080/global/")
    print("    - 스카디 체스: http://127.0.0.1:8080/skadi_chess.html")
    print("================================================================")
    webbrowser.open(portal_url)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n포털 웹 서버를 종료합니다.")

if __name__ == "__main__":
    main()
