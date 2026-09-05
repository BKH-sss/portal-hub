"""
launch_portal.py
4차 산업 포털 (ERECHTHEION) 전용 런처
- JARVIS 백엔드 서버(포트 8000)를 독립 백그라운드 프로세스로 안전 가동
- 브라우저로 http://127.0.0.1:8000/portal 자동 오픈
"""
import os
import sys
import time
import socket
import subprocess
import webbrowser

try:
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def is_port_open(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def get_python_exe() -> str:
    candidates = [
        sys.executable,
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
    ]
    for c in candidates:
        if c and os.path.exists(c) and "pythonw.exe" not in c.lower():
            return c
    return "python"


def main():
    print("================================================================")
    print(" 🏛️ [4차 산업 포털 · ERECHTHEION] 포털 허브 가동 중...")
    print("================================================================")

    py_exe = get_python_exe()

    # 1. Brain Server (포트 8000) 확인 및 백그라운드 구동
    if not is_port_open(8000):
        print("\n[1/2] 🚀 JARVIS 백엔드 서버(brain_server:8000) 가동 시작...")
        creation_flags = 0
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creation_flags |= subprocess.CREATE_NEW_PROCESS_GROUP
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creation_flags |= subprocess.DETACHED_PROCESS

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        subprocess.Popen(
            [py_exe, "-c", "import uvicorn; uvicorn.run('brain_server:app', host='0.0.0.0', port=8000)"],
            cwd=PROJECT_ROOT,
            creationflags=creation_flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            close_fds=True
        )

        for _ in range(24):
            if is_port_open(8000):
                print("      ✅ 백엔드 서버 정상 가동 완료!")
                break
            time.sleep(0.25)
    else:
        print("\n[1/2] ✅ JARVIS 백엔드 서버가 이미 작동 중입니다 (포트 8000).")

    # 2. 포털 웹 브라우저 열기
    portal_url = "http://127.0.0.1:8000/portal"
    print(f"\n[2/2] 🌐 브라우저에서 포털 페이지를 엽니다: {portal_url}")
    time.sleep(0.5)
    webbrowser.open(portal_url)

    print("\n✨ 포털 웹사이트가 열렸습니다! (3초 후 창이 자동으로 닫힙니다)")
    time.sleep(3)


if __name__ == "__main__":
    main()
