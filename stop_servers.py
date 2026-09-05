"""
stop_servers.py
JARVIS 및 스카디 AI 스튜디오 백그라운드 서버 안전 종료 스크립트
"""
import os
import sys
import time
import subprocess

try:
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def kill_process_name(name):
    try:
        subprocess.run(["taskkill", "/F", "/IM", name, "/T"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def kill_window_title(title_pattern):
    try:
        subprocess.run(["taskkill", "/F", "/FI", f"WINDOWTITLE eq {title_pattern}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def kill_project_servers():
    cur_pid = os.getpid()
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pid = proc.info['pid']
                if pid == cur_pid:
                    continue
                cmdline = ' '.join(proc.info.get('cmdline') or []).lower()
                target_keywords = [
                    'brain_server',
                    'launch_studio',
                    'discord_skadi_bot',
                    'api_v2.py',
                    'uvicorn',
                    'webui',
                    'stable-diffusion-webui-forge'
                ]
                if any(k in cmdline for k in target_keywords):
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        pass

def main():
    print("================================================================")
    print("  [AI 시스템 종료] 모든 백엔드 서버 및 스튜디오 종료 중...")
    print("================================================================")

    # 1. 윈도우 타이틀 기반 콘솔 종료
    kill_window_title("WebUI Forge*")
    kill_window_title("AI Image Studio*")
    kill_window_title("GPT-SoVITS API")
    kill_window_title("스카디 AI 화가 스튜디오*")

    # 2. 클라우드플레어 터널 종료
    kill_process_name("cloudflared.exe")

    # 3. 프로젝트 파이썬 프로세스 안전 종료
    kill_project_servers()

    print("\n  [1/3] JARVIS 백엔드 서버(포트 8000) 종료 완료")
    print("  [2/3] WebUI Forge(포트 7860) 렌더링 엔진 종료 완료")
    print("  [3/3] GPT-SoVITS 및 외부 접속기 종료 완료")
    print("\n================================================================")
    print("  모든 AI 서버와 스튜디오가 성공적으로 종료되었습니다.")
    print("================================================================")
    time.sleep(2)

if __name__ == "__main__":
    main()
