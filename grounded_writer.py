"""
grounded_writer.py
------------------------------------------------------------
환각(hallucination)을 줄이면서도 "짧게 자르지 않고" 긴 글을 쓰기 위한 모듈.

기존 /chat의 "1~2문장 강제, 마크다운 금지" 규칙은 실시간 게임 브리핑에는 맞지만
장문 글쓰기에는 애초에 맞지 않습니다. 그렇다고 제한을 풀면 환각이 늘어나니,
이 모듈은 아래 3단계로 "길게 써도 안전하게" 만듭니다.

    1. 근거 자료(ChromaDB 청크)만 보고 목차(섹션)를 설계 - 근거 없는 섹션은 아예 안 만듦
    2. 섹션마다 배정된 근거 자료만 사용해서 문단 생성 - 근거 부족하면 짧게 끝냄
    3. 완성된 초안을 근거 자료와 다시 대조해서 미근거 문장을 찾아내 경고로 반환

사용법 (brain_server.py에 새 엔드포인트로 추가):
    from grounded_writer import generate_grounded_writing

    class WriteRequest(BaseModel):
        topic: str
        agent: str = "skadi_writer"

    @app.post("/write")
    async def write(req: WriteRequest):
        target_collection = ...  # 기존 /chat과 동일한 방식으로 agent -> collection 매핑
        result = generate_grounded_writing(req.topic, target_collection)
        return result
"""
from ollama_utils import ollama_generate, safe_json_parse

WRITER_MODEL = "llama3.1"


def _retrieve_chunks(collection, topic: str, n_results: int = 10) -> list[dict]:
    results = collection.query(query_texts=[topic], n_results=n_results)
    chunks = []
    if results and results.get("documents") and results["documents"][0]:
        docs = results["documents"][0]
        ids = (results.get("ids") or [[]])[0]
        for i, doc in enumerate(docs):
            chunks.append({"id": ids[i] if i < len(ids) else f"chunk_{i}", "content": doc})
    return chunks


def _build_outline(topic: str, chunks: list[dict]) -> list[dict]:
    """근거 청크들을 보고, 실제로 뒷받침 가능한 섹션만 설계."""
    chunk_list_text = "\n".join(f"[{c['id']}] {c['content'][:200]}" for c in chunks)
    prompt = f"""주제: "{topic}"

아래는 이 주제에 대해 실제로 확보하고 있는 근거 자료 목록이다(각 앞에 ID가 붙어 있음).
이 자료들만 활용해서 쓸 수 있는 글의 목차(섹션)를 3~6개 설계해라.
근거가 부족한 섹션은 만들지 마라. 반드시 실제 자료에 있는 내용만으로 구성 가능한 섹션만 만들어라.

[근거 자료 목록]
{chunk_list_text if chunk_list_text else "(자료 없음)"}

아래 JSON 형식으로만 답해라:
{{"sections": [{{"title": "섹션 제목", "supporting_chunk_ids": ["id1", "id2"]}}]}}
"""
    raw = ollama_generate(prompt, model=WRITER_MODEL, temperature=0.2, num_predict=500)
    data = safe_json_parse(raw, default={"sections": []})
    return data.get("sections", [])


def _write_section(topic: str, section_title: str, supporting_chunks: list[str]) -> str:
    context = "\n---\n".join(supporting_chunks) if supporting_chunks else ""
    prompt = f"""주제: "{topic}"
지금 쓰는 섹션: "{section_title}"

아래 근거 자료에 있는 내용만 사용해서 이 섹션을 3~6문단으로 서술해라.
근거 자료에 없는 사실, 숫자, 이름은 절대 지어내지 마라.
근거가 부족해서 이어가기 어려우면 그 지점에서 문단을 마무리하고 더 확장하지 마라.
마크다운 헤더 없이 본문만 써라.

[근거 자료]
{context if context else "(근거 자료 없음 - 아주 짧게, 일반적으로 알려진 사실 범위 내에서만)"}
"""
    return ollama_generate(prompt, model=WRITER_MODEL, temperature=0.35, num_predict=900)


def _verify_draft(draft: str, all_chunks_text: str) -> dict:
    """초안 전체를 근거 자료와 대조해서, 근거 없는 구체적 사실이 있는지 검증."""
    prompt = f"""아래 [초안]의 문장들이 [근거 자료]로 뒷받침되는지 검토해라.
근거 자료에 없는 구체적 사실(숫자, 고유명사, 수치 등)이 있으면 찾아내서 목록으로 알려줘.
일반적인 설명/연결 문장은 문제 삼지 마라.

[근거 자료]
{all_chunks_text[:4000]}

[초안]
{draft}

아래 JSON 형식으로만 답해라:
{{"unsupported_claims": ["문장 또는 표현1"], "confidence": "high|medium|low"}}
"""
    raw = ollama_generate(prompt, model=WRITER_MODEL, temperature=0.0, num_predict=400)
    return safe_json_parse(raw, default={"unsupported_claims": [], "confidence": "low"})


def generate_grounded_writing(topic: str, collection, min_chunks: int = 1) -> dict:
    """
    근거 기반 장문 생성 파이프라인의 진입점.
    반환: {"text": 최종 글, "warnings": 검증에서 걸러진 미근거 표현 목록,
           "confidence": "high|medium|low", "grounded": bool}
    """
    chunks = _retrieve_chunks(collection, topic)
    if len(chunks) < min_chunks:
        return {
            "text": f"'{topic}'에 대해 확보한 자료가 없어서 근거 있는 글을 쓸 수 없어. 먼저 관련 자료를 학습시켜줘.",
            "warnings": [],
            "confidence": "low",
            "grounded": False,
        }

    chunk_map = {c["id"]: c["content"] for c in chunks}
    outline = _build_outline(topic, chunks)

    if not outline:
        return {
            "text": f"'{topic}'에 대한 자료는 있지만 목차를 구성할 만큼 충분하지 않아.",
            "warnings": [],
            "confidence": "low",
            "grounded": False,
        }

    sections_text = []
    for sec in outline:
        supporting = [chunk_map[cid] for cid in sec.get("supporting_chunk_ids", []) if cid in chunk_map]
        body = _write_section(topic, sec.get("title", ""), supporting)
        sections_text.append(f"## {sec.get('title', '')}\n\n{body}")

    draft = "\n\n".join(sections_text)
    all_chunks_text = "\n---\n".join(chunk_map.values())
    verification = _verify_draft(draft, all_chunks_text)

    return {
        "text": draft,
        "warnings": verification.get("unsupported_claims", []),
        "confidence": verification.get("confidence", "medium"),
        "grounded": True,
    }
