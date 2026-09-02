"""
routers/memory.py
------------------------------------------------------------
🧠 JARVIS 영구 메모리(Memory) & 지식(RAG) & 옵시디언 & 수면학습 라우터.
- 유저 팩트 시트 및 장기 기억 관리 (/api/skadi/memory, /api/skadi/memory/add)
- RAG 지식 보관소 조회/업로드/AI 요약 (/knowledge/list, /knowledge/upload, /knowledge/summarize)
- 자율 성장 일기 및 학습 사이클 (/admin/journal, /admin/learn_cycle)
- 웹 크롤링 기반 옵시디언(Obsidian) 지식 자동 생성 (/admin/crawl_to_obsidian)
- 수면 학습 엔진 (Dream Engine) 원격 제어 (/api/dream/status, /api/dream/start, /api/dream/stop, /api/dream/kill)
- 관리자 관측성(Observability) 및 시스템 상태 (/admin/status, /admin/observability)
------------------------------------------------------------
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

# ============================================================
# 1. ChromaDB 벡터 데이터베이스 초기화
# ============================================================
CHROMA_DATA_DIR = os.path.join(str(MEMORY_DIR), "chroma_db")
os.makedirs(CHROMA_DATA_DIR, exist_ok=True)

chroma_client = chromadb.PersistentClient(path=CHROMA_DATA_DIR)
default_ef = embedding_functions.DefaultEmbeddingFunction()

collection_general = chroma_client.get_or_create_collection(name="general_knowledge", embedding_function=default_ef)
collection_lol = chroma_client.get_or_create_collection(name="lol_knowledge", embedding_function=default_ef)
collection_maple = chroma_client.get_or_create_collection(name="maple_knowledge", embedding_function=default_ef)
collection_r6s = chroma_client.get_or_create_collection(name="r6s_knowledge", embedding_function=default_ef)
collection_coding = chroma_client.get_or_create_collection(name="coding_knowledge", embedding_function=default_ef)
collection_hacking = chroma_client.get_or_create_collection(name="hacking_knowledge", embedding_function=default_ef)

# ============================================================
# 2. Pydantic 요청 스키마 정의
# ============================================================
class AddMemoryRequest(BaseModel):
    memory_text: str
    category: str = "general"

class UploadKnowledgeRequest(BaseModel):
    content: str
    title: str

class CrawlToObsidianRequest(BaseModel):
    query: str
    category: str = "general"
    vault_path: str = os.path.join(str(MEMORY_DIR), "Obsidian_Knowledge")
    max_results: int = 5
    use_fact_check: bool = True

class WriteRequest(BaseModel):
    topic: str
    agent: str = "skadi"

# 수면 학습 엔진 프로세스 맵
dream_processes: Dict[str, Optional[subprocess.Popen]] = {
    "r6s": None,
    "lol": None,
    "coding": None,
    "hacking": None
}

# ============================================================
# 3. 유저 장기 기억 & 팩트 시트 API
# ============================================================
@router.get("/api/skadi/memory", summary="스카디 유저 장기 기억 조회")
def get_skadi_memory():
    """스카디가 학습하고 누적한 유저의 성향, 취향, 팩트 정보를 반환합니다."""
    facts = load_user_facts()
    return {"status": "success", "facts": facts}

@router.post("/api/skadi/memory/add", summary="유저 장기 기억 명시적 주입")
def add_skadi_memory_endpoint(req: AddMemoryRequest):
    """스카디의 영구 메모리 DB에 새로운 사실이나 기억을 명시적으로 주입합니다."""
    success = add_explicit_memory(req.memory_text, req.category)
    return {
        "status": "success" if success else "duplicate",
        "message": f"기억 저장 완료: {req.memory_text}"
    }

@router.post("/api/proactive_talk", summary="AI 선제 발화 한마디")
async def proactive_talk(agent: str = "skadi"):
    """일정 시간 침묵 시 캐릭터별로 유저에게 먼저 말을 건네는 멘트를 반환합니다."""
    talks = {
        "skadi": "마스터, 무슨 일 있어? 말이 없네...",
        "briar": "배고파아아! 우리 언제 싸우러 가?!",
        "angelic": "매니저님~ 집중 안 하고 딴생각하시는 거 아니죠?!"
    }
    msg = talks.get(agent, "마스터, 도움이 필요한가요?")
    return {"status": "success", "message": msg}

# ============================================================
# 4. RAG 지식 보관소(Knowledge Base) API
# ============================================================
@router.get("/knowledge/list", summary="지식 보관소 문서 목록")
def list_knowledge_items():
    """ChromaDB에 등록된 모든 카테고리별 지식 조각들을 반환합니다."""
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

# ============================================================
# 5. 자율 학습 & 옵시디언 & 관측성 API
# ============================================================
@router.get("/admin/journal", summary="AI 자기성장 일기 조회")
def get_learning_journal():
    """자율 학습 엔진이 밤사이 기록한 자아성찰 및 학습 일기 전문을 반환합니다."""
    return {"journal": get_journal_text()}

@router.get("/admin/observability", summary="관리자 관측성 지표 조회")
def get_observability(event_type: str = "chat_rag_query_timing", limit: int = 30):
    """RAG 검색 지연시간, 팩트체크 정확도 등 실시간 관측성 로그를 반환합니다."""
    return {"event_type": event_type, "events": summarize_recent(event_type, limit)}

@router.post("/admin/crawl_to_obsidian", summary="웹 검색 지식 -> 옵시디언 노트 자동 생성")
def crawl_to_obsidian(req: CrawlToObsidianRequest):
    """DDG 검색 기반으로 웹 문서를 자동 크롤링하고 팩트 체크 후 옵시디언 마크다운으로 저장합니다."""
    return crawl_search_and_save(
        query=req.query,
        vault_path=req.vault_path,
        category=req.category,
        max_results=req.max_results,
        use_fact_check=req.use_fact_check,
    )

@router.post("/write", summary="근거 기반(Grounded) 고품질 보고서 작성")
async def write_grounded_article(req: WriteRequest):
    """ChromaDB 지식을 근거(Grounding)로 삼아 할루시네이션 없는 전문 보고서를 작성합니다."""
    collection_map = {
        "angelic": collection_maple, "skadi_r6s": collection_r6s,
        "coder": collection_coding, "lucy": collection_hacking,
    }
    target_collection = collection_map.get(req.agent, collection_lol)
    return generate_grounded_writing(req.topic, target_collection)

# ============================================================
# 6. 수면 학습 엔진 (Dream Engine) 원격 제어
# ============================================================
@router.get("/api/dream/status", summary="수면 학습 엔진 가동 상태")
def get_dream_status(game: str = "r6s"):
    proc = dream_processes.get(game)
    is_running = proc is not None and proc.poll() is None
    return {"status": "running" if is_running else "stopped", "game": game}

@router.post("/api/dream/start", summary="수면 학습 엔진 시작")
def start_dream_engine(game: str = "r6s"):
    proc = dream_processes.get(game)
    if proc is None or proc.poll() is not None:
        script_name = f"dream_engine_{game}.py"
        if os.path.exists(script_name):
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            dream_processes[game] = subprocess.Popen(["python", script_name], env=env)
            return {"status": "started", "game": game}
        return {"status": "error", "message": f"{script_name} 스크립트를 찾을 수 없습니다."}
    return {"status": "already_running", "game": game}

@router.post("/api/dream/stop", summary="수면 학습 엔진 안전 종료")
def stop_dream_engine(game: str = "r6s"):
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
    proc = dream_processes.get(game)
    if proc and proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass
        return {"status": "killed", "game": game}
    return {"status": "already_stopped", "game": game}
