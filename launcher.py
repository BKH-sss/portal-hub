import subprocess
import os
import sys
import time
import threading
import urllib.request
import psutil
import webview

def get_project_root():
    # 1. 현재 작업 폴더 확인
    if os.path.exists("chatbot.html") and os.path.exists("brain_server.py"):
        return os.path.abspath(".")
    
    # 2. 실행 파일 위치 기반 탐색
    candidates = []
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.extend([exe_dir, os.path.dirname(exe_dir), os.path.dirname(os.path.dirname(exe_dir))])
    
    file_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.extend([file_dir, os.path.dirname(file_dir), os.path.dirname(os.path.dirname(file_dir))])
    
    for cand in candidates:
        if os.path.exists(os.path.join(cand, "chatbot.html")) and os.path.exists(os.path.join(cand, "brain_server.py")):
            return os.path.abspath(cand)
            
    return os.path.abspath(".")

PROJECT_ROOT = get_project_root()
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 환경 변수 설정
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'
try:
    from config import API_KEYS
except Exception:
    pass

tts_process = None
brain_process = None
discord_process = None

def get_python_exe():
    # 1. 시스템에 설치된 실제 파이썬 경로 탐색
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\python3.11.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
        r"C:\Program Files\Python311\python.exe",
        r"C:\Program Files\Python312\python.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
            
    if not getattr(sys, 'frozen', False):
        exe = sys.executable
        if "pythonw.exe" in exe.lower():
            cand = exe.lower().replace("pythonw.exe", "python.exe")
            if os.path.exists(cand):
                return cand
        return exe

    import shutil
    which_py = shutil.which("python.exe") or shutil.which("python")
    if which_py:
        return which_py
    return "python"

def kill_process_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass

def stop_servers():
    global tts_process, brain_process, discord_process
    if tts_process:
        kill_process_tree(tts_process.pid)
    if brain_process:
        kill_process_tree(brain_process.pid)
    if discord_process:
        kill_process_tree(discord_process.pid)
    try:
        os.system('taskkill /f /im python.exe 2>nul')
        os.system('taskkill /f /im python3.11.exe 2>nul')
        os.system('taskkill /f /im pythonw.exe 2>nul')
    except:
        pass

def start_servers():
    global tts_process, brain_process, discord_process
    base_dir = PROJECT_ROOT
    python_exe = get_python_exe()
    
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

    # 1. TTS 서버 시작 (창 숨김)
    tts_dir = os.path.join(base_dir, "tts_engine_sovits", "GPT-SoVITS-main")
    tts_python = os.path.join(tts_dir, "venv_sovits", "Scripts", "python.exe")
    
    if os.path.exists(tts_python):
        try:
            tts_process = subprocess.Popen(
                [tts_python, "api_v2.py", "-a", "127.0.0.1", "-p", "9880", "-c", "GPT_SoVITS/configs/tts_infer.yaml"],
                cwd=tts_dir,
                startupinfo=startupinfo,
                creationflags=creation_flags
            )
        except Exception as te:
            print(f"[TTS Launch Error] {te}")

    # 2. Brain 서버 백그라운드 시작 (창 숨김)
    try:
        brain_process = subprocess.Popen(
            [python_exe, "-m", "uvicorn", "brain_server:app", "--port", "8000"],
            cwd=base_dir,
            startupinfo=startupinfo,
            creationflags=creation_flags
        )
    except Exception as be:
        print(f"[Brain Launch Error] {be}")

    # 3. 스카디 디스코드 봇 백그라운드 시작 (창 숨김)
    discord_script = os.path.join(base_dir, "discord_bot", "discord_skadi_bot.py")
    if os.path.exists(discord_script):
        try:
            discord_process = subprocess.Popen(
                [python_exe, "discord_skadi_bot.py"],
                cwd=os.path.join(base_dir, "discord_bot"),
                startupinfo=startupinfo,
                creationflags=creation_flags
            )
            print("[Discord Bot] 스카디 디스코드 봇 백그라운드 가동 완료")
        except Exception as de:
            print(f"[Discord Launch Error] {de}")

def check_and_redirect(window):
    health_url = "http://127.0.0.1:8000/api/health"
    target_url = "http://127.0.0.1:8000/chatbot.html"
    max_wait = 35
    start = time.time()
    is_ready = False
    
    while time.time() - start < max_wait:
        try:
            req = urllib.request.Request(health_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    is_ready = True
                    break
        except Exception:
            pass
        time.sleep(0.25)
    
    # 서버 응답 200이 확인된 경우 즉시 매끄럽게 전환
    if is_ready:
        time.sleep(0.2)
        try:
            window.evaluate_js(f"if (typeof window.onServerReady === 'function') {{ window.onServerReady(); }} else {{ window.location.href = '{target_url}'; }}")
        except Exception:
            try:
                window.load_url(target_url)
            except Exception:
                pass

if __name__ == "__main__":
    base_dir = PROJECT_ROOT
    loading_page = os.path.join(base_dir, "loading.html")
    loading_url = f"file:///{loading_page.replace(chr(92), '/')}"

    # 서버 프로세스 백그라운드 시작
    start_servers()
    
    # 데스크탑 앱(웹뷰) 생성 - 텍스트 마우스 드래그 선택 및 우클릭 복사 완전 허용
    window = webview.create_window(
        'J.A.R.V.I.S Assistant',
        loading_url,
        width=1280,
        height=800,
        min_size=(800, 600),
        easy_drag=False,
        text_select=True
    )
    
    # 백그라운드 스레드에서 서버 상태 감시 후 자동 전환
    watcher = threading.Thread(target=check_and_redirect, args=(window,), daemon=True)
    watcher.start()
    
    # 앱 실행 (영구 캐시 및 localStorage 유지 모드로 구동)
    storage_dir = os.path.join(base_dir, ".webview_data")
    os.makedirs(storage_dir, exist_ok=True)
    webview.start(private_mode=False, storage_path=storage_dir)
    
    # 창이 꺼지면 서버 자동 정리
    stop_servers()
