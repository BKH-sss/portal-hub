import os
import time
import uuid
import chromadb
from chromadb.utils import embedding_functions
import requests
import json
import sys
import signal
import argparse
from datetime import datetime

# brain_server.py와 반드시 동일한 임베딩 모델을 사용해야 합니다.
# 다르면 같은 컬렉션에 upsert 시 임베딩 차원(dimension) 불일치 에러가 발생합니다.
try:
    _bge_m3_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-m3")
except Exception as _e:
    print(f"[경고] BGE-M3 임베딩 모델 로딩 실패, 기본 임베딩으로 대체됩니다: {_e}")
    _bge_m3_ef = None

# ==========================================
# ⚙️ 설정 (Configuration)
# ==========================================
MEMORY_DIR = r"B:\AI_Brain"

# [중요] brain_server.py가 실제로 읽는 것과 100% 동일한 경로를 사용해야
# 수면 학습 엔진의 결과물이 실전 코치(브라이어/스카디)에게 실제로 전달됩니다.
# brain_server.py: CHROMADB_DIR = os.path.join(MEMORY_DIR, "chroma_db")
CHROMADB_DIR = os.path.join(MEMORY_DIR, "chroma_db")

OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma4:e4b"

# Graceful Shutdown 플래그
is_running = True
is_learning = False # 현재 학습 중인지 여부

GAME_MODE = "r6s"
PROFILE_PATH = ""
LOG_FILE_PATH = ""
COLLECTION_NAME = ""

# [중요] brain_server.py의 chat 라우트가 agent별로 조회하는 실제 컬렉션명과
# 반드시 일치해야 합니다 (brain_server.py 상단 collection_* 정의 참고).
#   - skadi_r6s 에이전트 → collection_r6s → "r6s_knowledge"
#   - briar(기본/롤) 에이전트 → collection_lol → "lol_knowledge"
GAME_TO_COLLECTION = {
    "r6s": "r6s_knowledge",
    "lol": "lol_knowledge",
}

def init_config(game_mode):
    global GAME_MODE, PROFILE_PATH, LOG_FILE_PATH, COLLECTION_NAME
    GAME_MODE = game_mode
    PROFILE_PATH = os.path.join(MEMORY_DIR, f"user_profile_{game_mode}.md")
    LOG_FILE_PATH = os.path.join(MEMORY_DIR, f"dream_engine_{game_mode}.log")
    COLLECTION_NAME = GAME_TO_COLLECTION.get(game_mode, f"{game_mode}_knowledge")
    os.makedirs(CHROMADB_DIR, exist_ok=True)

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
    너는 최고의 E-sports 전술 분석가이자 데이터 사이언티스트야.
    아래는 마스터(유저)가 오늘 플레이하며 남긴 데스 및 플레이 기록이야.

    [오늘의 데스 및 플레이 기록]
    {profile_data}

    [분석 및 섀도우 복싱 규칙]
    1. 모드 감지: 프로필에서 [모드: OOO] 태그를 확인하고, 아래 기준에 맞춰 뇌구조를 전환하라.
       - [소환사의 협곡]: 라인전 상성, 정글 동선, 오브젝트(용/바론) 시야 통제 위주로 팩폭 분석.
       - [칼바람 나락 / 아수라장]: 라인전 개념 배제. 5v5 좁은 길목 한타, 포킹 구도, 이니시에이팅 타이밍 위주로 분석.
       - [아레나]: 3인 콤보 조합, 증강(Augment) 시너지, 피지컬 좁은 교전 위주로 분석.
       - (모드가 없으면 소환사의 협곡으로 간주)
    2. 원인 분석: 마스터가 오늘 왜 연패했는지, 어떤 포지션이나 상황에서 주로 죽었는지 공통된 패턴을 찾아라.
    3. 가설 설정: 내일 똑같은 맵, 똑같은 상황이 주어졌을 때 적을 압도할 수 있는 최적의 카운터 전술을 생각해라.
    4. 데이터 각인: 분석한 내용을 바탕으로, 내일 마스터가 게임을 켤 때 즉각적으로 쏴줄 수 있는 '한 줄짜리 행동 지침'을 생성하라.

    [출력 형식]
    결과는 반드시 아래 포맷의 텍스트로만 출력하라. (다른 군더더기 말은 절대 금지)
    분석 결과: [어떤 모드에서 어떤 상황에 취약했는지 요약]. 
    실전 지침: [내일 게임에서 바로 써먹을 구체적이고 거친 피드백 1~2줄]
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
    write_log(f"💾 ChromaDB({CHROMADB_DIR} / {COLLECTION_NAME})에 깨달음을 각인합니다...")
    try:
        # brain_server.py와 동일한 경로를 사용해야 실전 코치가 이 기억을 조회할 수 있습니다.
        client = chromadb.PersistentClient(path=CHROMADB_DIR)
        collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=_bge_m3_ef)

        doc_id = f"dream_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        collection.upsert(
            documents=[strategy],
            metadatas=[{"source": "dream_engine", "type": "counter_strategy", "mode": GAME_MODE, "timestamp": datetime.now().isoformat()}],
            ids=[doc_id]
        )
        write_log(f"✨ 기억 각인 성공! (ID: {doc_id}, 컬렉션: {COLLECTION_NAME})")

    except Exception as e:
        write_log(f"❌ 기억 각인 실패: {e}")

def run_learning_cycle():
    profile_data = read_user_profile()
    if profile_data and len(profile_data.strip()) > 10:
        strategy = dream_and_reflect(profile_data)
        if strategy:
            save_to_chromadb(strategy)
    else:
        write_log("💤 학습할 내용이 부족하여 건너뜁니다.")

def run_scheduler():
    write_log("========================================")
    write_log("🌙 AI 수면 학습 엔진(Dream Engine) 연속 가동 시작")
    write_log("========================================")
    
    while is_running:
        run_learning_cycle()
        
        # 관리자 요청: 1사이클당 30초 휴식 후 끌 때까지 반복
        wait_seconds = 30
        write_log(f"💤 다음 수면 주기까지 {wait_seconds}초 휴식합니다...")
        
        for _ in range(wait_seconds):
            if not is_running:
                break
            time.sleep(1)
            
    write_log("🛑 수면 학습 엔진이 안전하게 종료되었습니다. (Graceful Shutdown 완료)")
    sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=str, default="r6s", choices=["r6s", "lol"], help="학습할 게임 모드")
    parser.add_argument("--run-once", action="store_true", help="주기 대기 없이 1회 학습 후 즉시 종료")
    args = parser.parse_args()

    os.makedirs(MEMORY_DIR, exist_ok=True)
    init_config(args.game)
    
    if args.run_once:
        write_log(f"⚡ [강제 실행 모드] 수면 학습 ({args.game}) 1회 즉시 실행")
        run_learning_cycle()
        write_log("✅ 강제 실행 완료.")
    else:
        run_scheduler()
