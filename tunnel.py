import subprocess
import re
import sys
import threading
import os
import urllib.request

print("=========================================================")
print("    🚀 [관제탑 웜홀 개방] OpenClaw 외부 접속 시스템")
print("    스카디 / 알파 / 루시 3대장 외부 접속기 가동 중...")
print("=========================================================\n")

# 클라우드플레어 파일 확인 및 다운로드
CLOUDFLARED_EXE = "cloudflared.exe"
if not os.path.exists(CLOUDFLARED_EXE):
    print("🚀 최초 실행 중입니다. 안전한 터널링 프로그램을 다운로드합니다...")
    try:
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        urllib.request.urlretrieve(url, CLOUDFLARED_EXE)
        print("✅ 다운로드 완료!\n")
    except Exception as e:
        print("다운로드 실패:", e)
        sys.exit(1)

print("터널을 개방 중입니다... (3~5초 소요)\n")

# Cloudflared 실행
process = subprocess.Popen(
    [CLOUDFLARED_EXE, "tunnel", "--url", "http://localhost:8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT, # cloudflared는 stderr에 출력함
    text=True,
    encoding="utf-8",
    errors="ignore"
)

url_found = False

def read_output():
    global url_found
    for line in process.stdout:
        clean_line = line.strip()
        
        match = re.search(r"(https://[a-zA-Z0-9-]+\.trycloudflare\.com)", clean_line)
        if match and not url_found:
            url_found = True
            base_tunnel_url = match.group(1)
            portal_url = base_tunnel_url + "/portal"
            chatbot_url = base_tunnel_url + "/chatbot.html"
            print("\n" + "="*60)
            print("🎉 [성공] 전 세계 어디서나 접속 가능한 외부 링크가 발급되었습니다!")
            print(f"👉 4차산업 포털 링크 : {portal_url}")
            print(f"👉 AI 비서 챗봇 링크 : {chatbot_url}")
            print("="*60)
            
            # 클립보드에 포털 링크 우선 자동 복사
            try:
                subprocess.run("clip", input=portal_url.encode("utf-16le"), check=True)
                print("\n✅ 포털 링크가 [클립보드에 자동 복사] 되었습니다!")
                print("✅ 스마트폰 브라우저나 카톡 등에 바로 '붙여넣기(Ctrl+V)' 하시면 열립니다!\n")
            except Exception as e:
                print("클립보드 복사 실패:", e)

thread = threading.Thread(target=read_output)
thread.daemon = True
thread.start()

try:
    process.wait()
except KeyboardInterrupt:
    print("\n종료합니다.")
    process.terminate()
