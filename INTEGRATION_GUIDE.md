# brain_server.py 통합 가이드

새로 만든 5개 파일(`ollama_utils.py`, `local_fact_checker.py`, `local_video_analyzer.py`,
`autonomous_learner.py`, `grounded_writer.py`)을 `brain_server.py`와 **같은 폴더**에 넣고,
아래 순서대로 연결하세요.

## 0. 사전 설치

```bash
pip install duckduckgo_search yt-dlp langchain-text-splitters --break-system-packages
ollama pull qwen3-vl:8b      # VRAM 8GB 기준. 4GB면 qwen3-vl:2b
ollama pull llama3.1         # 이미 쓰고 계셔서 아마 있을 겁니다
```
ffmpeg/ffprobe는 GPT-SoVITS/SD 세팅에 보통 이미 PATH에 잡혀 있을 거예요. `ffmpeg -version`으로 확인하세요.

## 1. import 추가 (파일 상단, 기존 `import chromadb` 근처)

```python
from local_fact_checker import local_check_and_chunk_knowledge
from local_video_analyzer import analyze_video_visually
from autonomous_learner import log_unanswered_question, run_autonomous_learning_cycle, get_journal_text
from grounded_writer import generate_grounded_writing
```

## 2. Gemini 없이 팩트체크 (선택적 전환)

기존 `check_and_chunk_knowledge()` 함수를 통째로 바꾸지 말고, **맨 앞에 분기 하나만 추가**하세요.
이렇게 하면 환경변수 하나로 Gemini/로컬을 즉시 스위칭할 수 있습니다.

```python
def check_and_chunk_knowledge(content: str, title: str) -> list[dict]:
    # [추가] USE_LOCAL_FACT_CHECK=true 면 Gemini 없이 로컬로 처리
    if os.environ.get("USE_LOCAL_FACT_CHECK", "false").lower() == "true":
        return local_check_and_chunk_knowledge(content, title, category="general")

    # ↓ 기존 Gemini 코드는 그대로 둡니다
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    ...
```

`analyze_video()` 안에서 호출하는 `check_and_chunk_knowledge(script, title)`도 그대로 재사용되니
따로 손댈 필요 없습니다.

## 3. 영상을 "실제로 보고" 분석 (analyze_video 함수 안)

`/analyze` 엔드포인트에서 자막 추출(`extract_transcript`) 직후에 한 줄만 추가하면 됩니다.

```python
@app.post("/analyze")
def analyze_video(req: AnalyzeRequest):
    ...
    script = extract_transcript(video_id)
    if not script:
        return {"status": "error", "message": "..."}

    # [추가] 화면도 실제로 분석해서 자막과 융합 (무거우니 옵션으로)
    if os.environ.get("USE_VISUAL_ANALYSIS", "false").lower() == "true":
        visual_result = analyze_video_visually(url, script, title=video_id)
        if visual_result.get("visual_ok"):
            script = visual_result["fused_summary"] + "\n\n[원본 자막]\n" + script

    # 이후 게이트키퍼/팩트체크는 기존 로직 그대로
    if not local_ai_gatekeeper(script):
        ...
```

**주의**: 영상 다운로드 + 프레임 6장 VLM 분석은 자막 추출(0.1초)과 비교가 안 될 만큼 느립니다
(영상당 수십 초~몇 분). 기본은 꺼두고, 자막이 아예 없는 영상이거나 화면 정보가 중요한 영상에만
`USE_VISUAL_ANALYSIS=true`로 켜는 걸 권장합니다.

## 4. 자율학습 - 막힌 질문 로깅 (chat() 함수 안)

ChromaDB 검색 결과가 비어있을 때(=답을 못 찾았을 때) 딱 한 줄 추가하면 됩니다.

```python
results = target_collection.query(query_texts=[last_msg], n_results=20)
context_str = ""
if results and results["documents"] and len(results["documents"][0]) > 0:
    ...
else:
    # [추가] 근거를 못 찾은 질문은 자율학습 큐에 쌓아둠
    log_unanswered_question(req.agent, last_msg)
```

## 5. 자율학습 사이클을 실제로 도는 엔드포인트 추가 (파일 아무 곳이나, 다른 @app.post 근처)

기존 `/admin/toggle`이 `auto_scraper.py`를 켜고 끄는 구조인데, 거기에 훅을 걸거나
별도 엔드포인트로 수동/스케줄 트리거하세요.

```python
class SearchAndLearnRequest(BaseModel):
    query: str

def _simple_youtube_search(query: str) -> list[str]:
    """DDGS로 유튜브 URL만 골라서 반환하는 간단한 검색 함수 예시."""
    from duckduckgo_search import DDGS
    urls = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(f"{query} site:youtube.com", max_results=5):
                href = r.get("href", "")
                if "youtube.com/watch" in href or "youtu.be" in href:
                    urls.append(href)
    except Exception as e:
        print(f"[자율학습] 검색 실패: {e}")
    return urls

def _learn_from_url(url: str, category: str) -> dict:
    """analyze_video()의 핵심 로직을 재사용해서 URL 하나를 학습시키는 헬퍼."""
    fake_req = AnalyzeRequest(url=url, category=category)
    return analyze_video(fake_req)

@app.post("/admin/learn_cycle")
def trigger_learning_cycle(category: str = "lol"):
    collection_map = {
        "lol": collection_lol, "maplestory": collection_maple,
        "r6s": collection_r6s, "general": collection_general,
    }
    target = collection_map.get(category, collection_general)
    result = run_autonomous_learning_cycle(
        target, category=category,
        search_fn=_simple_youtube_search,
        analyze_video_fn=_learn_from_url,
    )
    return result

@app.get("/admin/journal")
def get_learning_journal():
    return {"journal": get_journal_text()}
```

이렇게 해두면 `POST /admin/learn_cycle`을 호출할 때마다 AI가 스스로 "지금 뭐가 부족한지" 판단하고
검색 쿼리를 세우고 학습한 뒤 일지에 기록합니다. 이걸 `APScheduler`나 Windows 작업 스케줄러로
하루 1~2회 자동 호출하게 하면 "혼자 알아서 공부하는" 흐름이 완성됩니다.

```python
# 스케줄러 예시 (startup_event 안에 추가)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(lambda: trigger_learning_cycle("lol"), "interval", hours=12)
scheduler.start()
```

## 6. 환각 줄인 장문 글쓰기 엔드포인트 추가

```python
class WriteRequest(BaseModel):
    topic: str
    agent: str = "skadi"

@app.post("/write")
async def write(req: WriteRequest):
    collection_map = {
        "angelic": collection_maple, "skadi_r6s": collection_r6s,
        "coder": collection_coding, "lucy": collection_hacking,
    }
    target_collection = collection_map.get(req.agent, collection_lol)
    result = generate_grounded_writing(req.topic, target_collection)
    return result
```

이건 기존 `/chat`(1~2문장 강제, 브리핑용)과는 완전히 분리된 별도 엔드포인트입니다.
프론트엔드(`chatbot.html`)에 "글쓰기 모드" 버튼을 하나 추가해서 이 엔드포인트를 호출하게
만들면, 실시간 브리핑용 짧은 말투는 그대로 유지하면서 장문 글쓰기만 근거 기반으로 분리할 수 있습니다.

---

## 정리: 무엇이 바뀌는가

| 요청하신 것 | 담당 파일 | 통합 방식 |
|---|---|---|
| Gemini 없이 팩트체크 | `local_fact_checker.py` | 환경변수 분기로 기존 함수에 끼워 넣기 |
| 영상을 실제로 보고 분석 | `local_video_analyzer.py` | `/analyze`에 한 줄 추가 (옵션으로 켜고 끔) |
| 스스로 생각하고 발전 | `autonomous_learner.py` | `/chat`에 로깅 한 줄 + 새 엔드포인트 2개 |
| 환각 줄인 글쓰기 | `grounded_writer.py` | 완전히 새로운 `/write` 엔드포인트 |

모두 **기존 코드를 삭제/치환하지 않고 옆에 추가**하는 방식으로 설계했습니다. 문제가 생기면
환경변수(`USE_LOCAL_FACT_CHECK`, `USE_VISUAL_ANALYSIS`)를 꺼서 즉시 기존 동작으로 되돌릴 수 있습니다.

실제로 붙여넣고 돌려보시면서 에러 메시지나 예상과 다르게 동작하는 부분 있으면 그대로 붙여넣어 주세요 -
로그/에러 메시지 기준으로 같이 고쳐나가면 됩니다. (이 환경엔 GPU/Ollama가 없어서 제가 직접
실행 테스트는 못 했다는 점 감안해주세요.)
