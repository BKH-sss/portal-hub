"""
local_fact_checker.py
------------------------------------------------------------
Gemini API 없이, 로컬 LLM(Ollama) + DuckDuckGo 검색만으로
  1) 검증 가능한 주장(claim) 추출
  2) 인터넷 검색으로 팩트체크
  3) 점수화 (0~100)
  4) 챕터 단위 청킹
을 수행합니다. brain_server.py의 check_and_chunk_knowledge()를 대체하는 용도입니다.

주의(정직하게):
  로컬 8B급 모델은 Gemini 2.5 Flash보다 판단력이 떨어집니다. 완전 무료/오프라인이
  중요하면 이걸 쓰고, 대신 MIN_SCORE_TO_KEEP을 보수적으로 잡거나 애매한 점수는
  사람이 다시 검토하는 큐로 빼는 걸 권장합니다.

사용법 (brain_server.py에서):
    from local_fact_checker import local_check_and_chunk_knowledge
    chunks = local_check_and_chunk_knowledge(content, title, category="lol")
    # 반환 형식은 기존 check_and_chunk_knowledge와 동일합니다:
    # [{"content": str, "metadata": dict, "id_suffix": str}, ...]
"""
from ollama_utils import ollama_generate, safe_json_parse

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

CLAIM_MODEL = "llama3.1"
MIN_SCORE_TO_KEEP = 75  # 로컬 판단은 보수적으로. 너무 자주 걸러지면 65~70으로 낮추세요.


def _extract_claims(content: str, title: str, max_claims: int = 5) -> list[str]:
    """본문에서 검색으로 검증 가능한 핵심 주장(사실 진술)을 뽑아낸다."""
    prompt = f"""다음은 '{title}'에 대한 게임 공략/정보 텍스트입니다.
이 안에서 사실 여부를 검색으로 확인할 수 있는 핵심 주장을 최대 {max_claims}개 뽑아주세요.
(예: "14.13 패치에서 아리 W 쿨타임이 감소했다", "이 아이템은 3800골드다")
너무 애매하거나 주관적인 문장(예: "이 챔피언은 재밌다")은 제외하세요.

반드시 아래 JSON 배열 형식으로만 답하세요. 다른 설명 없이 순수 JSON만 출력하세요.
["주장1", "주장2"]

[텍스트]
{content[:3000]}
"""
    raw = ollama_generate(prompt, model=CLAIM_MODEL, temperature=0.0, num_predict=400)
    data = safe_json_parse(raw, default=[])
    if isinstance(data, list):
        return [str(c) for c in data if isinstance(c, str)][:max_claims]
    return []


def _search_claim(claim: str, max_results: int = 3) -> str:
    """DuckDuckGo로 주장을 검색해서 스니펫을 모아 반환."""
    if DDGS is None:
        print("[local_fact_checker] duckduckgo_search 미설치 - 검증 불가")
        return ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(claim, max_results=max_results, region="kr-kr"))
        snippets = []
        for r in results:
            body = r.get("body", "")
            href = r.get("href", "")
            if body:
                snippets.append(f"- {body} (출처: {href})")
        return "\n".join(snippets)
    except Exception as e:
        print(f"[local_fact_checker] 검색 실패 ('{claim}'): {e}")
        return ""


def _judge_claim(claim: str, search_snippets: str) -> dict:
    """검색 결과와 주장을 비교해서 신뢰도(0~100)를 판단."""
    if not search_snippets:
        # 검색 결과가 없으면 검증 불가 -> 중간값(보수적)으로 처리
        return {"score": 50, "reason": "검색 결과 없음 (검증 불가)"}

    prompt = f"""아래 [주장]이 [검색 결과]와 얼마나 일치하는지 판단하세요.
반드시 검색 결과에 실제로 있는 내용에만 근거해서 판단하고, 검색 결과에 없는 내용은 추측하지 마세요.

아래 JSON 형식으로만 출력하세요:
{{"score": 85, "reason": "검색 결과 다수가 동일한 수치를 언급함"}}

[주장]
{claim}

[검색 결과]
{search_snippets}
"""
    raw = ollama_generate(prompt, model=CLAIM_MODEL, temperature=0.0, num_predict=200)
    data = safe_json_parse(raw, default={"score": 50, "reason": "판단 실패"})
    try:
        score = int(data.get("score", 50))
    except (TypeError, ValueError):
        score = 50
    return {"score": max(0, min(100, score)), "reason": data.get("reason", "")}


def _chunk_into_chapters(content: str, title: str) -> list[dict]:
    """본문을 논리적 챕터 단위로 분할. LLM이 실패하면 기계적 분할로 폴백."""
    prompt = f"""다음 텍스트를 2~4개의 논리적인 챕터(예: 라인전, 한타, 템트리, 운영)로 나누세요.
각 챕터의 제목과 해당 부분의 원문 내용을 그대로 포함해서 아래 JSON으로만 답하세요.

{{"chunks": [{{"chapter": "템트리", "content": "..."}}, {{"chapter": "운영", "content": "..."}}]}}

[제목: {title}]
{content[:6000]}
"""
    raw = ollama_generate(prompt, model=CLAIM_MODEL, temperature=0.1, num_predict=2000)
    data = safe_json_parse(raw, default={})
    chunks = data.get("chunks", [])
    if chunks:
        return chunks

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=120)
        parts = splitter.split_text(content)
        return [{"chapter": f"섹션{i + 1}", "content": t} for i, t in enumerate(parts)]
    except ImportError:
        return [{"chapter": "전체", "content": content}]


def local_check_and_chunk_knowledge(content: str, title: str, category: str = "general") -> list[dict]:
    """
    check_and_chunk_knowledge()의 로컬(Gemini-free) 버전.
    반환 형식은 기존 함수와 동일: [{"content", "metadata", "id_suffix"}, ...]
    """
    claims = _extract_claims(content, title)

    if not claims:
        overall_score = 70  # 검증할 사실 주장이 없는 서술형 텍스트는 중립 점수로 통과
        judged = []
    else:
        judged = []
        for claim in claims:
            snippets = _search_claim(claim)
            verdict = _judge_claim(claim, snippets)
            judged.append({"claim": claim, **verdict})
        scores = [j["score"] for j in judged]
        overall_score = sum(scores) // len(scores) if scores else 50

    print(f"[로컬 팩트체커] '{title}' 종합 점수: {overall_score}점")
    for j in judged:
        print(f"   - {j.get('claim', '')}: {j.get('score')}점 ({j.get('reason', '')})")

    if overall_score < MIN_SCORE_TO_KEEP:
        print(f"[경고] [로컬 Fact Check 실패] 점수 {overall_score} < {MIN_SCORE_TO_KEEP}, 저장 거부")
        return []

    chapters = _chunk_into_chapters(content, title)

    result_chunks = []
    for idx, c in enumerate(chapters):
        meta = {
            "chapter": c.get("chapter", "일반"),
            "game": category,
            "score": overall_score,
            "fact_check_method": "local",  # Gemini 버전과 구분하기 위한 표시
        }
        result_chunks.append({
            "content": c.get("content", ""),
            "metadata": meta,
            "id_suffix": f"_chunk_{idx}",
        })
    return result_chunks
