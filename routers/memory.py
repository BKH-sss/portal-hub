"""
routers/memory.py
==============================================================================
🧠 JARVIS 영구 메모리(Memory) & 지식(RAG) & 옵시디언 & 수면학습 라우터
==============================================================================
이 모듈은 AI 비서의 장기 기억(Long-term Memory), ChromaDB 벡터 지식베이스,
옵시디언(Obsidian) 지식 자동 동기화, 수면 자율 학습 엔진(Dream Engine) 및
시스템 관측성(Observability)을 관리하는 지능형 메모리 컨트롤러입니다.

주요 엔드포인트:
  1) GET  /api/skadi/memory          : 유저 팩트 시트 및 축적된 장기 기억 조회
  2) POST /api/skadi/memory/add      : 명시적 기억(이름, 취향, 관심사 등) 강제 주입
  3) POST /api/proactive_talk        : 침묵 시 AI 캐릭터별 선제 발화 멘트 생성
  4) GET  /knowledge/list            : ChromaDB 컬렉션별 누적 지식 조각 수 조회
  5) GET  /admin/journal             : 밤사이 기록된 자율 성장 및 자아성찰 일기 조회
  6) GET  /admin/observability       : RAG 검색 지연시간 및 시스템 이벤트 관측
  7) POST /admin/crawl_to_obsidian   : 웹 검색 지식을 옵시디언 마크다운으로 자동 정리
  8) POST /write                     : ChromaDB 근거 기반(Grounded) 고품질 보고서 작성
  9) POST/GET /api/dream/*           : 수면 학습 엔진 (LoL, R6S, 코딩) 원격 가동/중지
==============================================================================
"""

import os
import time
import json
import subprocess
import signal
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions

from config import MEMORY_DIR, API_KEYS
import core.state as state
from skadi_memory_engine import (
    load_user_facts, add_explicit_memory, get_growth_journal
)
from autonomous_learner import get_journal_text, run_autonomous_learning_cycle
from obsidian_writer import crawl_search_and_save
from observability import summarize_recent, observe_learning
from grounded_writer import generate_grounded_writing

router = APIRouter(tags=["Memory & Knowledge & Admin"])

# ==============================================================================
# 1. ChromaDB 벡터 데이터베이스 초기화 (카테고리별 컬렉션 분리)
# ==============================================================================
CHROMA_DATA_DIR = os.path.join(str(MEMORY_DIR), "chroma_db")
os.makedirs(CHROMA_DATA_DIR, exist_ok=True)

# 영구 디스크 기반 ChromaDB 클라이언트 및 기본 임베딩 모델 로드
chroma_client = chromadb.PersistentClient(path=CHROMA_DATA_DIR)
default_ef = embedding_functions.DefaultEmbeddingFunction()

# 도메인별 6대 지식 컬렉션 생성/연결
collection_general = chroma_client.get_or_create_collection(name="general_knowledge", embedding_function=default_ef)
collection_lol = chroma_client.get_or_create_collection(name="lol_knowledge", embedding_function=default_ef)
collection_maple = chroma_client.get_or_create_collection(name="maple_knowledge", embedding_function=default_ef)
collection_r6s = chroma_client.get_or_create_collection(name="r6s_knowledge", embedding_function=default_ef)
collection_coding = chroma_client.get_or_create_collection(name="coding_knowledge", embedding_function=default_ef)
collection_hacking = chroma_client.get_or_create_collection(name="hacking_knowledge", embedding_function=default_ef)

# ==============================================================================
# 2. Pydantic 요청 스키마 정의
# ==============================================================================
class AddMemoryRequest(BaseModel):
    """장기 기억 명시적 주입 요청 모델"""
    memory_text: str                # 저장할 기억 문장 (예: "마스터는 민초를 좋아해")
    category: str = "general"       # 기억 카테고리 (general, lol, coding 등)

class CrawlToObsidianRequest(BaseModel):
    """옵시디언 자동 크롤링 요청 모델"""
    query: str                      # 검색할 주제 키워드
    category: str = "general"       # 분류 카테고리
    vault_path: str = os.path.join(str(MEMORY_DIR), "Obsidian_Knowledge")
    max_results: int = 5            # 수집할 최대 웹 문서 수
    use_fact_check: bool = True     # AI 팩트체크 및 청킹 적용 여부

class WriteRequest(BaseModel):
    """근거 기반 보고서 작성 요청 모델"""
    topic: str                      # 보고서 주제
    agent: str = "skadi"            # 작성할 AI 에이전트

# 수면 학습 엔진 (Dream Engine) 서브프로세스 핸들 딕셔너리
dream_processes: Dict[str, Optional[subprocess.Popen]] = {
    "r6s": None,
    "lol": None,
    "coding": None,
    "hacking": None
}

# ==============================================================================
# 3. 유저 장기 기억 & 팩트 시트 API
# ==============================================================================
@router.get("/api/skadi/memory", summary="스카디 유저 장기 기억 조회")
def get_skadi_memory():
    """
    스카디가 대화를 통해 자율적으로 추출하고 축적한 유저의 성향, 취향, 
    개인 팩트 정보(skadi_profile_facts.json)를 반환합니다.
    """
    facts = load_user_facts()
    return {"status": "success", "facts": facts}

@router.post("/api/skadi/memory/add", summary="유저 장기 기억 명시적 주입")
def add_skadi_memory_endpoint(req: AddMemoryRequest):
    """
    유저가 직접 "이거 꼭 기억해!"라고 입력한 중요한 정보나 규칙을 
    스카디의 영구 메모리 DB에 즉시 등록합니다.
    """
    success = add_explicit_memory(req.memory_text, req.category)
    return {
        "status": "success" if success else "duplicate",
        "message": f"기억 저장 완료: {req.memory_text}"
    }

@router.post("/api/proactive_talk", summary="AI 선제 발화 한마디")
async def proactive_talk(agent: str = "skadi"):
    """
    일정 시간 유저의 입력이 없을 때(침묵 상태), 캐릭터별 고유 성격에 맞춰 
    먼저 말을 건네는 상황별 선제 멘트를 생성합니다.
    """
    talks = {
        "skadi": "마스터, 무슨 일 있어? 말이 없네...",
        "briar": "배고파아아! 우리 언제 싸우러 가?!",
        "angelic": "매니저님~ 집중 안 하고 딴생각하시는 거 아니죠?!"
    }
    msg = talks.get(agent, "마스터, 도움이 필요한가요?")
    return {"status": "success", "message": msg}

# ==============================================================================
# 4. RAG 지식 보관소(Knowledge Base) API
# ==============================================================================
@router.get("/knowledge/list", summary="지식 보관소 문서 목록")
def list_knowledge_items():
    """ChromaDB에 등록된 카테고리별 누적 지식 조각(Document) 개수를 집계하여 반환합니다."""
    try:
        results = {}
        collections = {
            "lol": collection_lol, "maple": collection_maple,
            "r6s": collection_r6s, "coding": collection_coding,
            "general": collection_general
        }
        for name, col in collections.items():
            results[name] = col.count()
        return {"status": "success", "knowledge_counts": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/admin/status", summary="서버 및 자율학습 상태 조회")
def get_admin_status():
    """
    챗봇 UI 상단의 게임 특화 보조 AI 상태 뱃지(ONLINE / OFFLINE / 자율학습 ON)를 갱신하는 헬스체크 API입니다.
    """
    is_dream_running = any(p is not None and p.poll() is None for p in dream_processes.values())
    return {
        "status": "online",
        "auto_learning_active": is_dream_running,
        "vision_monitor": state.admin_flags.get("vision_monitor", False),
        "lol_feedback": state.admin_flags.get("lol_feedback", True),
        "active_connections": len(state.manager.active_connections),
    }

@router.get("/admin/journal", summary="AI 자기성장 일기 조회")
def get_learning_journal():
    """자율 학습 엔진이 유튜브나 웹 문서를 공부하고 남긴 자기성찰 및 학습 일기 전문을 반환합니다."""
    return {"journal": get_journal_text()}

@router.get("/admin/observability", summary="관리자 관측성 지표 조회")
def get_observability(event_type: str = "chat_rag_query_timing", limit: int = 30):
    """RAG 벡터 검색 소요 시간, 팩트체크 정확도 등 실시간 시스템 성능 관측 로그를 반환합니다."""
    return {"event_type": event_type, "events": summarize_recent(event_type, limit)}

@router.post("/admin/crawl_to_obsidian", summary="웹 검색 지식 -> 옵시디언 노트 자동 생성")
def crawl_to_obsidian(req: CrawlToObsidianRequest):
    """
    DuckDuckGo 검색 결과 문서를 웹 크롤링한 뒤, 로컬 AI가 팩트체크를 거쳐 
    옵시디언(Obsidian) 마크다운 볼트에 자동으로 인덱싱 노트를 작성합니다.
    """
    return crawl_search_and_save(
        query=req.query,
        vault_path=req.vault_path,
        category=req.category,
        max_results=req.max_results,
        use_fact_check=req.use_fact_check,
    )

@router.post("/write", summary="근거 기반(Grounded) 고품질 보고서 작성")
async def write_grounded_article(req: WriteRequest):
    """ChromaDB에 저장된 공식 문서를 근거(Grounding)로 삼아 할루시네이션(거짓 답변) 없는 전문 보고서를 생성합니다."""
    collection_map = {
        "angelic": collection_maple, "skadi_r6s": collection_r6s,
        "coder": collection_coding, "lucy": collection_hacking,
    }
    target_collection = collection_map.get(req.agent, collection_lol)
    return generate_grounded_writing(req.topic, target_collection)

# ==============================================================================
# 6. 수면 학습 엔진 (Dream Engine) 원격 제어
# ==============================================================================
ALLOWED_DREAM_GAMES = {"r6s", "lol", "coding", "hacking"}

@router.get("/api/dream/status", summary="수면 학습 엔진 가동 상태")
def get_dream_status(game: str = "r6s"):
    """수면 학습 엔진(백그라운드 지식 심층 학습기)의 현재 실행 여부를 반환합니다."""
    if game not in ALLOWED_DREAM_GAMES:
        return {"status": "error", "message": f"허용되지 않은 게임 유형입니다: {game}"}
    proc = dream_processes.get(game)
    is_running = proc is not None and proc.poll() is None
    return {"status": "running" if is_running else "stopped", "game": game}

@router.post("/api/dream/start", summary="수면 학습 엔진 시작")
def start_dream_engine(game: str = "r6s"):
    """사용자가 잠든 사이 유튜브/웹 지식을 자동으로 크롤링하여 벡터 DB에 주입하는 학습기를 백그라운드로 실행합니다."""
    if game not in ALLOWED_DREAM_GAMES:
        return {"status": "error", "message": f"허용되지 않은 게임 유형입니다: {game}"}
    proc = dream_processes.get(game)
    if proc is None or proc.poll() is not None:
        script_name = f"dream_engine_{game}.py"
        if os.path.exists(script_name):
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            dream_processes[game] = subprocess.Popen([sys.executable, script_name], env=env)
            return {"status": "started", "game": game}
        return {"status": "error", "message": f"{script_name} 스크립트를 찾을 수 없습니다."}
    return {"status": "already_running", "game": game}

@router.post("/api/dream/stop", summary="수면 학습 엔진 안전 종료")
def stop_dream_engine(game: str = "r6s"):
    """현재 실행 중인 수면 학습 프로세스에 SIGTERM 신호를 전달하여 안전하게 정리 종료합니다."""
    proc = dream_processes.get(game)
    if proc and proc.poll() is None:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except Exception:
            proc.terminate()
        return {"status": "stop_signal_sent", "game": game}
    return {"status": "already_stopped", "game": game}

@router.post("/api/dream/kill", summary="수면 학습 엔진 강제 종료")
def kill_dream_engine(game: str = "r6s"):
    """비정상 작동 중인 수면 학습 프로세스를 즉시 강제 종료합니다."""
    proc = dream_processes.get(game)
    if proc and proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass
        return {"status": "killed", "game": game}
    return {"status": "already_stopped", "game": game}
