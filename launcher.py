import subprocess
import os
import sys
import time
import threading
import urllib.request
import ctypes
import psutil
import webview

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def ensure_admin():
    """J.A.R.V.I.S Assistant 실행 시 관리자 권한으로 자동 승격 실행"""
    if not is_admin():
        try:
            if getattr(sys, 'frozen', False):
                exe = sys.executable
                params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
                ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
            else:
                exe = sys.executable
                script = f'"{os.path.abspath(sys.argv[0])}"'
                params = f'{script} ' + " ".join([f'"{arg}"' for arg in sys.argv[1:]])
                ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)
            if ret > 32:
                sys.exit(0)
        except Exception as e:
            print(f"[Admin Elevation Error]: {e}")

ensure_admin()

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

def is_server_ready():
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/api/health", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False

def kill_process_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except Exception:
                pass
        parent.kill()
    except (psutil.NoSuchProcess, Exception):
        pass

def stop_servers():
    global tts_process, brain_process, discord_process
    if tts_process:
        try: kill_process_tree(tts_process.pid)
        except: pass
    if brain_process:
        try: kill_process_tree(brain_process.pid)
        except: pass
    if discord_process:
        try: kill_process_tree(discord_process.pid)
        except: pass

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

    # 2. Brain 서버 백그라운드 시작 (이미 실행 중이지 않을 때만 실행)
    if not is_server_ready():
        try:
            brain_process = subprocess.Popen(
                [python_exe, "-m", "uvicorn", "brain_server:app", "--host", "0.0.0.0", "--port", "8000"],
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
    target_url = "http://127.0.0.1:8000/chatbot.html"
    max_wait = 40
    start = time.time()
    
    while time.time() - start < max_wait:
        if is_server_ready():
            time.sleep(0.3)
            try:
                window.load_url(target_url)
            except Exception:
                try:
                    window.evaluate_js(f"window.location.href = '{target_url}';")
                except Exception:
                    pass
            return
        time.sleep(0.2)
    
    # 타임아웃 시 강제 로드
    try:
        window.load_url(target_url)
    except Exception:
        pass

if __name__ == "__main__":
    base_dir = PROJECT_ROOT
    loading_page = os.path.join(base_dir, "loading.html")
    loading_url = f"file:///{loading_page.replace(chr(92), '/')}"
    target_url = "http://127.0.0.1:8000/chatbot.html"

    # 서버 프로세스 백그라운드 시작
    start_servers()
    
    # 이미 서버가 켜져 있으면 로딩 없이 즉시 챗봇 화면으로 실행
    initial_url = target_url if is_server_ready() else loading_url

    # 데스크탑 앱(웹뷰) 생성 - 텍스트 마우스 드래그 선택 및 우클릭 복사 완전 허용
    window = webview.create_window(
        'J.A.R.V.I.S Assistant',
        initial_url,
        width=1280,
        height=800,
        min_size=(800, 600),
        easy_drag=False,
        text_select=True
    )
    
    # 로딩 화면으로 시작된 경우에만 백그라운드 스레드로 전환 감시
    if initial_url == loading_url:
        watcher = threading.Thread(target=check_and_redirect, args=(window,), daemon=True)
        watcher.start()
    
    # 앱 실행 (영구 캐시 및 localStorage 유지 모드로 구동)
    storage_dir = os.path.join(base_dir, ".webview_data")
    os.makedirs(storage_dir, exist_ok=True)
    webview.start(private_mode=False, storage_path=storage_dir)
    
    # 창이 꺼지면 서버 정리
    stop_servers()
