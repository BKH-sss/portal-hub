"""
autonomous_learner.py
------------------------------------------------------------
"AI가 스스로 뭘 모르는지 판단하고, 스스로 검색 계획을 세워서 학습한다"는
체감을 만들기 위한 자율학습 루프.

정직한 전제: 이건 모델 가중치를 바꾸는 게 아닙니다. ChromaDB 지식 베이스를
AI가 스스로 계획을 세워 넓혀가는 방식(RAG 확장형 자율학습)입니다.
"모델 자체가 똑똑해지는 것"과는 다르다는 걸 설계할 때 꼭 염두에 두세요.

사용법 (brain_server.py에서):
    from autonomous_learner import log_unanswered_question, run_autonomous_learning_cycle

    # chat()에서 ChromaDB 검색 결과가 비어있어 "모른다"로 답한 경우:
    if not docs:
        log_unanswered_question(req.agent, last_msg)

    # 자율학습 사이클 (스케줄러 또는 /admin/toggle 확장에서 주기적으로 호출):
    run_autonomous_learning_cycle(
        collection_lol,
        category="lol",
        search_fn=my_search_fn,       # 쿼리 -> URL 리스트를 반환하는 함수 (직접 구현)
        analyze_video_fn=my_learn_fn, # URL -> 학습 결과 dict를 반환하는 함수 (기존 analyze_video 재사용)
    )
"""
import os
import json
import datetime

from ollama_utils import ollama_generate, safe_json_parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = r"B:\AI_Brain" if os.path.exists(r"B:") else os.path.join(BASE_DIR, "AI_Brain")
try:
    os.makedirs(MEMORY_DIR, exist_ok=True)
except Exception:
    pass
GAP_QUEUE_FILE = os.path.join(MEMORY_DIR, "learning_gap_queue.json")
JOURNAL_FILE = os.path.join(MEMORY_DIR, "self_growth_journal.md")


def _load_queue() -> list[dict]:
    if not os.path.exists(GAP_QUEUE_FILE):
        return []
    try:
        with open(GAP_QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_queue(queue: list[dict]):
    os.makedirs(os.path.dirname(GAP_QUEUE_FILE), exist_ok=True)
    with open(GAP_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def log_unanswered_question(agent: str, question: str):
    """근거 데이터가 없어서 답을 못했던(혹은 불확실했던) 질문을 학습 큐에 쌓는다."""
    queue = _load_queue()
    queue.append({
        "agent": agent,
        "question": question,
        "logged_at": datetime.datetime.now().isoformat(),
        "status": "pending",
    })
    _save_queue(queue)
    print(f"[자율학습] 학습 큐에 추가됨: {question}")


def _propose_search_queries_from_gaps(collection, category: str, n: int = 5) -> list[str]:
    """
    1) 사람에게 못 답한 질문들 + 2) 기존 지식 베이스 커버리지 샘플을 LLM에게 보여주고
    스스로 다음에 검색해서 채울 만한 쿼리를 제안하게 한다.
    """
    queue = _load_queue()
    pending = [q for q in queue if q.get("status") == "pending"][:10]
    pending_text = "\n".join(f"- {q['question']}" for q in pending) if pending else "(없음)"

    try:
        sample = collection.peek(limit=15)
        known_titles = set()
        for meta in sample.get("metadatas", []) or []:
            if meta and meta.get("title"):
                known_titles.add(meta["title"])
        known_text = "\n".join(f"- {t}" for t in list(known_titles)[:15]) or "(아직 지식 없음)"
    except Exception as e:
        known_text = f"(조회 실패: {e})"

    prompt = f"""너는 '{category}' 분야를 스스로 공부하는 AI야.
아래는 1) 유저가 물어봤지만 네가 근거가 없어서 답 못한 질문들, 2) 네가 이미 알고 있는 문서 제목들이야.

[답 못한 질문들]
{pending_text}

[이미 알고 있는 것]
{known_text}

이 정보를 바탕으로, 지금 네 지식에서 비어 있어서 검색으로 채워야 할 만한
유튜브/웹 검색 쿼리를 {n}개 제안해줘. 이미 아는 내용은 제외하고,
답 못한 질문과 관련된 것을 우선해줘.

반드시 아래 JSON 배열로만 답해. ["쿼리1", "쿼리2"]
"""
    raw = ollama_generate(prompt, model="llama3.1", temperature=0.3, num_predict=300)
    data = safe_json_parse(raw, default=[])
    if isinstance(data, list):
        return [str(q) for q in data if isinstance(q, str)][:n]
    return []


def _write_journal_entry(category: str, queries: list[str], learned_count: int):
    os.makedirs(os.path.dirname(JOURNAL_FILE), exist_ok=True)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n## {now} - {category} 자율학습 사이클\n")
        f.write(f"- 스스로 세운 검색 계획: {', '.join(queries) if queries else '(없음)'}\n")
        f.write(f"- 새로 학습한 문서 수: {learned_count}\n")


def get_journal_text(max_chars: int = 3000) -> str:
    """최근 자율학습 일지를 읽어온다 (대화 중 '요즘 뭐 배웠어?' 같은 질문에 활용 가능)."""
    if not os.path.exists(JOURNAL_FILE):
        return "아직 자율학습 기록이 없습니다."
    with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    return text[-max_chars:]


def run_autonomous_learning_cycle(collection, category: str = "general",
                                   analyze_video_fn=None, search_fn=None,
                                   max_new_items: int = 3) -> dict:
    """
    자율학습 한 사이클 실행:
    1. 스스로 검색 쿼리 계획 세움 (지식 공백 + 못 답한 질문 기반)
    2. 각 쿼리로 실제 검색(search_fn) 수행
    3. 새 자료를 분석/저장 (analyze_video_fn - 기존 analyze_video 로직 재사용 권장)
    4. 성찰 일지 기록, 학습 큐 status 갱신

    이 모듈은 "무엇을 배울지 계획을 세우는 것"에만 집중하고, "어떻게 배우는지"는
    기존에 이미 만들어둔 검증된 파이프라인(check_and_chunk_knowledge 등)을
    그대로 재사용하도록 설계했습니다. 학습 로직을 두 곳에서 따로 관리하지 않기 위함입니다.
    """
    queries = _propose_search_queries_from_gaps(collection, category)
    print(f"[자율학습] 이번 사이클 계획: {queries}")

    learned_count = 0
    if search_fn and queries:
        for q in queries[:max_new_items]:
            try:
                urls = search_fn(q)  # 쿼리 -> URL 리스트
                for url in (urls or [])[:1]:  # 쿼리당 1개만 우선 학습 (과도 학습 방지)
                    if analyze_video_fn:
                        result = analyze_video_fn(url, category)
                        if result and result.get("status") == "success":
                            learned_count += 1
            except Exception as e:
                print(f"[자율학습] '{q}' 처리 중 오류: {e}")

    queue = _load_queue()
    for item in queue:
        if item.get("status") == "pending":
            item["status"] = "reviewed"
    _save_queue(queue)

    _write_journal_entry(category, queries, learned_count)
    print(f"[자율학습] 사이클 완료. 새로 학습: {learned_count}건")
    return {"queries": queries, "learned_count": learned_count}
