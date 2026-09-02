# -*- coding: utf-8 -*-
"""
observability.py
-----------------
외부 서비스(Langfuse 등) 없이 로컬에서 돌아가는 초경량 관측성(Observability) 모듈.

왜 필요한가:
- reranker가 변수명 오타 때문에 몇 달간 조용히 미적용된 것처럼, "로그만 있고 구조화된
  추적이 없는" 상태에서는 이런 버그를 알아채기가 매우 어렵습니다.
- 이 모듈은 RAG 검색/리랭크 결과, 팩트체크 판정, 자율학습 판단 근거를
  B:\AI_Brain\observability\*.jsonl 에 append-only로 기록합니다.
- 각 줄이 독립된 JSON이라(JSONL) `tail -f`로 실시간 확인하거나,
  pandas.read_json(lines=True)로 바로 분석할 수 있습니다.

사용법 (brain_server.py에서):
    from observability import observe_rerank, observe_fact_check, observe_learning, obs_timer

    with obs_timer("chat_rag_query", agent=req.agent):
        results = target_collection.query(...)

나중에 실제 Langfuse/Phoenix 등으로 옮기고 싶다면, 이 모듈의 함수 시그니처만
유지한 채 내부 구현을 REST 호출로 바꾸면 되므로 브레이킹 체인지가 없습니다.
"""

import os
import json
import time
import threading
from contextlib import contextmanager
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = r"B:\AI_Brain" if os.path.exists(r"B:") else os.path.join(BASE_DIR, "AI_Brain")
OBS_DIR = os.path.join(MEMORY_DIR, "observability")
try:
    os.makedirs(OBS_DIR, exist_ok=True)
except Exception:
    pass

_lock = threading.Lock()


def _write(event_type: str, payload: dict):
    """이벤트 타입별로 별도 .jsonl 파일에 append. 실패해도 서버 동작에는 영향 없음."""
    try:
        record = {
            "ts": datetime.now().isoformat(),
            "type": event_type,
            **payload,
        }
        path = os.path.join(OBS_DIR, f"{event_type}.jsonl")
        with _lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        # 관측성 로깅 실패가 실제 서비스를 망가뜨리면 안 됨 - 조용히 무시하되 콘솔엔 남김
        print(f"[Observability] 로그 기록 실패({event_type}): {e}")


def observe_rag_query(agent: str, query: str, n_results: int, retrieved_ids: list):
    """RAG 1차 검색(reranker 이전) 결과 기록"""
    _write("rag_query", {
        "agent": agent,
        "query": query[:300],
        "n_results": n_results,
        "retrieved_ids": retrieved_ids,
    })


def observe_rerank(query: str, ranked_docs: list, top_k: int = 3):
    """reranker가 실제로 몇 개를 어떤 순서로 골랐는지 기록.
    이게 있었다면 'reranker_model vs bge_reranker' 변수명 버그도
    '항상 로그가 비어있다'는 신호로 훨씬 빨리 잡혔을 것."""
    _write("rerank", {
        "query": query[:300],
        "selected_count": min(top_k, len(ranked_docs)),
        "total_candidates": len(ranked_docs),
        "top_docs_preview": [d[:120] for d in ranked_docs[:top_k]],
    })


def observe_fact_check(title: str, score: int, accepted: bool, reason: str = ""):
    """Gemini/로컬 fact-checker의 채택/거부 판정 기록"""
    _write("fact_check", {
        "title": title,
        "score": score,
        "accepted": accepted,
        "reason": reason[:300],
    })


def observe_learning(category: str, action: str, detail: dict = None):
    """자율학습(autonomous_learner, dream_engine) 사이클의 판단 근거 기록"""
    _write("learning", {
        "category": category,
        "action": action,
        "detail": detail or {},
    })


def observe_gemini_call(purpose: str, agent: str = ""):
    """Gemini API 실제 호출 시점 기록 (쿼터 추적용, gemini_api_calls 카운터 보조)"""
    _write("gemini_call", {
        "purpose": purpose,
        "agent": agent,
    })


@contextmanager
def obs_timer(event_type: str, **extra_fields):
    """구간 소요시간 측정 컨텍스트 매니저.

    사용 예:
        with obs_timer("chat_rag_query", agent=req.agent, query=last_msg[:80]):
            results = target_collection.query(query_texts=[last_msg], n_results=20)
    """
    start = time.time()
    error = None
    try:
        yield
    except Exception as e:
        error = str(e)
        raise
    finally:
        elapsed_ms = round((time.time() - start) * 1000, 1)
        _write(f"{event_type}_timing", {
            "elapsed_ms": elapsed_ms,
            "error": error,
            **extra_fields,
        })


def summarize_recent(event_type: str, limit: int = 20):
    """최근 N개 이벤트를 리스트로 반환 (관리자 대시보드에서 조회용)"""
    path = os.path.join(OBS_DIR, f"{event_type}.jsonl")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
        return [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return []
