import os
import time
import uuid
import chromadb
import requests
import json
import sys
import signal
import argparse
from datetime import datetime

# ==========================================
# ⚙️ 설정 (Configuration)
# ==========================================
MEMORY_DIR = r"B:\AI_Brain"

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma4:e4b"

# Graceful Shutdown 플래그
is_running = True
is_learning = False # 현재 학습 중인지 여부

GAME_MODE = "hacking"
PROFILE_PATH = ""
LOG_FILE_PATH = ""
COLLECTION_NAME = ""

def init_config(game_mode):
    global GAME_MODE, PROFILE_PATH, LOG_FILE_PATH, COLLECTION_NAME
    GAME_MODE = game_mode
    PROFILE_PATH = os.path.join(MEMORY_DIR, f"user_profile_{game_mode}.md")
    LOG_FILE_PATH = os.path.join(MEMORY_DIR, f"dream_engine_{game_mode}.log")
    COLLECTION_NAME = f"gaming_memory_{game_mode}"

def write_log(msg):
    """콘솔 출력과 동시에 B드라이브 로그 파일에 기록"""
    timestamped_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(timestamped_msg, flush=True)
    try:
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(timestamped_msg + "\n")
    except Exception as e:
        print(f"로그 기록 실패: {e}")

def signal_handler(signum, frame):
    """강제 종료 신호 감지 (Graceful Shutdown)"""
    global is_running, is_learning
    if is_running:
        write_log("⚠️ 강제 종료 신호(SIGTERM/SIGINT) 수신됨. '우아한 종료'를 준비합니다...")
        is_running = False
        if is_learning:
            write_log("⏳ 현재 진행 중인 섀도우 복싱 연산이 있습니다. 연산과 B드라이브 기록이 끝날 때까지 대기합니다...")
        else:
            write_log("✅ 진행 중인 연산이 없어 즉시 종료합니다.")
            sys.exit(0)

# 윈도우 환경을 위한 SIGINT/SIGTERM 감지
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def read_user_profile():
    if not os.path.exists(PROFILE_PATH):
        write_log(f"💤 수면 학습 대기 중: 프로필 파일이 없습니다. ({PROFILE_PATH})")
        return None
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return f.read()

def dream_and_reflect(profile_data):
    global is_learning
    is_learning = True
    write_log("🧠 AI가 수면 학습(섀도우 복싱)을 시작합니다...")
    
    prompt = f"""
    너는 천재 해커 '루시'야.
    아래는 마스터(유저)가 오늘 남긴 모의해킹 및 보안 로그 기록이야.

    [오늘의 보안 로그]
    {profile_data}

    [분석 규칙]
    1. 원인 분석: 마스터가 어떤 보안 취약점을 놓쳤거나 공격 패턴에 실패했는지 분석해라.
    2. 실전 지침: 내일 시스템 방어나 공격을 수행할 때 쓸 수 있는 핵심 지침을 거칠고 직설적인 반말로 생성하라.

    [출력 형식]
    분석 결과: [취약점 요약].
    실전 지침: [내일 해킹/보안에 바로 써먹을 거친 피드백 1~2줄]
    """
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7}
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        strategy = response.json().get("response", "").strip()
        write_log(f"💡 깨달음 도출 완료:\n{strategy}")
        return strategy
    except Exception as e:
        write_log(f"❌ 수면 중 악몽(에러) 발생: {e}")
        return None
    finally:
        is_learning = False

def save_to_chromadb(strategy):
    write_log(f"💾 ChromaDB(B드라이브 장기 기억 - {COLLECTION_NAME})에 깨달음을 각인합니다...")
    try:
        client = chromadb.PersistentClient(path=MEMORY_DIR)
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
        
        doc_id = f"dream_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        collection.upsert(
            documents=[strategy],
            metadatas=[{"source": "dream_engine", "type": "counter_strategy", "timestamp": datetime.now().isoformat()}],
            ids=[doc_id]
        )
        write_log(f"✨ 기억 각인 성공! (ID: {doc_id})")
        
    except Exception as e:
        write_log(f"❌ 기억 각인 실패: {e}")

def run_learning_cycle():
    profile_data = read_user_profile()
    if profile_data and len(profile_data.strip()) > 10:
        strategy = dream_and_reflect(profile_data)
        if strategy:
            save_to_chromadb(strategy)
            # 학습 완료 후 프로필 초기화 (중복 학습 방지)
            try:
                open(PROFILE_PATH, "w", encoding="utf-8").close()
                write_log("🧹 학습 완료된 프로필 데이터를 초기화했습니다.")
            except Exception as e:
                write_log(f"❌ 프로필 초기화 실패: {e}")
    else:
        write_log("⚡ 타겟 로그가 비었잖아. 똑바로 안 긁어와? (분석할 취약점 없음)")

def run_scheduler():
    write_log("========================================")
    write_log("🌙 AI 수면 학습 엔진(Dream Engine) 연속 가동 시작")
    write_log("========================================")
    
    while is_running:
        run_learning_cycle()
        
        # 관리자 요청: 1사이클당 30초 휴식 후 끌 때까지 반복
        wait_seconds = 30
        write_log(f"⚡ 다음 타겟 찾을 때까지 {wait_seconds}초만 시스템 절전한다...")
        
        for _ in range(wait_seconds):
            if not is_running:
                break
            time.sleep(1)
            
    write_log("🛑 수면 학습 엔진이 안전하게 종료되었습니다. (Graceful Shutdown 완료)")
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-once", action="store_true", help="주기 대기 없이 1회 학습 후 즉시 종료")
    args = parser.parse_args()

    os.makedirs(MEMORY_DIR, exist_ok=True)
    init_config("hacking")
    
    if args.run_once:
        write_log(f"⚡ [강제 실행 모드] 수면 학습 (hacking) 1회 즉시 실행")
        run_learning_cycle()
        write_log("✅ 강제 실행 완료.")
    else:
        run_scheduler()
