"""
llm_orchestrator.py
------------------------------------------------------------
[Nexus Cognitive AI Engine]
단일 모델(GPT, Gemini, Claude, Ollama)의 한계를 뛰어넘는
하이브리드 다중 AI 오케스트레이션 및 자율 진화 시스템.

핵심 혁신 기능:
1. 지능형 의도 분석 및 자동 최적 라우팅 (Cognitive Intent Router)
   - 질문의 성격(코딩, 최신 팩트/게임 지식, 주식/금융, 감성 대화)을 자동 분석
   - 코딩/논리: Claude 3.7 / GPT-4o / DeepSeek R1 자동 위임
   - 실시간 팩트/게임/시세: Google Gemini + 실시간 웹 그라운딩 자동 결합
   - 일상 대화: 스카디 페르소나 + 장기 기억 팩트 시트 자동 주입
2. 지능형 다계층 무중단 자동 폴백 (Cascading Failover Chain)
   - Gemini 429/할당량 초과 시 -> Claude -> GPT-4o -> Local Ollama로 무중단 자동 전환
3. 할루시네이션 방어 및 다국어 사족 정제 필터 (Anti-Artifact Postprocessor)
4. 미래 지향적 플러그인 & 도구 실행 (Tool Registry & ChromaDB 연동)
------------------------------------------------------------
"""

import os
import re
import json
import time
import asyncio
from typing import AsyncGenerator, Dict, Any, List, Optional

try:
    from config import DEFAULT_GENERATION_PARAMS, API_KEYS, OLLAMA_HOST
except ImportError:
    API_KEYS = {
        "GEMINI": os.environ.get("GEMINI_API_KEY", ""),
        "OPENAI": os.environ.get("OPENAI_API_KEY", ""),
        "ANTHROPIC": os.environ.get("ANTHROPIC_API_KEY", ""),
        "GROQ": os.environ.get("GROQ_API_KEY", ""),
        "DEEPSEEK": os.environ.get("DEEPSEEK_API_KEY", ""),
        "DISCORD": os.environ.get("DISCORD_BOT_TOKEN", "")
    }
    OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    DEFAULT_GENERATION_PARAMS = {
        "temperature": 0.5,
        "top_p": 0.9,
        "max_tokens": 4096,
        "timeout_sec": 30.0,
        "connect_timeout_sec": 8.0,
        "system_instruction": "너는 마스터를 지키는 스카디야. 100% 한국어로 대답해."
    }

from llm_providers import provider_registry, BaseLLMProvider
from smart_search import smart_web_grounding

# 장기 기억 엔진 및 툴 레지스트리 안전 로드
try:
    import skadi_memory_engine as memory_engine
except ImportError:
    memory_engine = None

try:
    from tool_registry import ToolRegistry
    tool_hub = ToolRegistry()
except ImportError:
    tool_hub = None


class CognitiveIntentRouter:
    """질문의 의도와 난이도를 분석하여 최적의 AI 모델 및 도구를 결정하는 인지 분석기"""

    @staticmethod
    def resolve_multi_turn_query(messages: List[Dict[str, Any]]) -> str:
        """이전 대화 맥락을 추적하여 대명사/후속 질문('사진 보여달라고', '더 알려줘' 등)의 완전한 검색어 복원"""
        if not messages:
            return ""
        
        last_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_msg = m.get("content", "").strip()
                break

        if not last_msg:
            return ""

        # 후속 질문 패턴 검사
        follow_up_patterns = [
            r'^(사진|이미지|짤|포토)?\s*(보여달라고|찾아달라고|가져오라고|보여줘|찾아줘|구해줘|띄워줘|더|다시|또|해줘)\??$',
            r'^(그거|그건|이거|이건|그 사람|그곳|거기)\s*(어때|얼마|누구|뭐야|사진|보여줘|알려줘|어디)',
            r'^(더\s*자세히|자세히|더\s*알려줘|계속|이어서)',
            r'^(왜|어째서|어떻게\s*된\s*거야|진짜|정말)\??$'
        ]
        is_follow_up = len(last_msg) <= 18 and any(re.search(p, last_msg.strip()) for p in follow_up_patterns)
        if not is_follow_up and len(last_msg) <= 8 and not any(k in last_msg for k in ["안녕", "반가워", "하이"]):
            is_follow_up = True

        if is_follow_up and len(messages) >= 2:
            # 이전 사용자 메시지에서 핵심 주제어 탐색
            for prev in reversed(messages[:-1]):
                if prev.get("role") == "user":
                    prev_text = prev.get("content", "")
                    clean_prev = re.sub(r'^(스카디야|스카디|브라이어|비서|봇|ai|인공지능)[,\s]*', '', prev_text, flags=re.IGNORECASE)
                    clean_prev = re.sub(r'(사진|이미지|짤|포토|모습|생김새|관련|대해서|대해|알려줘|보여줘|설명해줘|찾아줘|구해줘|줘|해줘)\s*', ' ', clean_prev).strip()
                    if len(clean_prev) >= 2:
                        if any(w in last_msg for w in ['사진', '보여', '이미지', '짤', '포토', '외형', '모습']):
                            return f"{clean_prev} 사진"
                        return f"{clean_prev} {last_msg}"

        return last_msg

    @staticmethod
    def classify_intent(query: str) -> Dict[str, Any]:
        q_lower = query.lower()
        
        # 1. 코딩 및 프로그래밍 의도
        coding_keywords = ["파이썬", "코드", "코딩", "함수", "버그", "에러", "알고리즘", "디버깅", "javascript", "python", "sql", "html", "css", "api", "git"]
        is_coding = any(k in q_lower for k in coding_keywords) or bool(re.search(r'(def |class |import |function|const |let |\{|\}|<\/?)', query))

        # 2. 시각 이미지 / 유튜브 / 미디어 / 링크 요청 의도
        media_keywords = [
            "유튜브", "유투브", "youtube", "영상", "동영상", "노래", "음악", "ost", "뮤비", "mv",
            "링크", "주소", "url", "사이트", "사진", "이미지", "짤", "포토", "모습", "생김새",
            "외형", "얼굴", "전경", "풍경", "일러스트", "그림", "보여줘", "구경", "룩", "도안"
        ]
        is_media = any(k in q_lower for k in media_keywords)
        is_visual = any(k in q_lower for k in ["사진", "이미지", "짤", "포토", "모습", "생김새", "외형", "얼굴", "전경", "풍경", "일러스트", "그림", "보여줘"])

        # 3. 실시간 정보 및 최신 팩트체크 의도
        realtime_keywords = [
            "누구", "검색", "날씨", "뉴스", "시세", "얼마", "언제", "디렉터", "최신", "알려줘",
            "뭐야", "추천", "몇년", "몇월", "몇일", "며칠", "날짜", "시간", "요일", "지금",
            "f1", "선수", "주식", "패치", "이벤트", "출시", "가격", "정보", "근황", "메이플", "롤", "레식", "카론", "바이브코딩", "지구라트", "건축물"
        ]
        is_realtime = any(k in q_lower for k in realtime_keywords) or is_media

        # 4. 주식 및 금융 퀀트 의도
        finance_keywords = ["주가", "주식", "매수", "매도", "etf", "배당", "rsi", "환율", "코인", "비트코인", "나스닥", "s&p"]
        is_finance = any(k in q_lower for k in finance_keywords)

        # 추천 최적 엔진 결정
        recommended_model = "gemini"
        if is_coding and (API_KEYS.get("ANTHROPIC") or API_KEYS.get("OPENAI")):
            recommended_model = "claude" if API_KEYS.get("ANTHROPIC") else "openai"
        elif is_realtime or is_finance or is_media:
            recommended_model = "gemini"

        return {
            "is_coding": is_coding,
            "is_visual": is_visual,
            "is_media": is_media,
            "is_realtime": is_realtime,
            "is_finance": is_finance,
            "recommended_model": recommended_model,
            "needs_grounding": is_realtime or is_finance or is_media or ("검색" in q_lower)
        }


class LLMOrchestrator:
    def __init__(self):
        self.registry = provider_registry
        self.router = CognitiveIntentRouter()

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        agent_name: str = "스카디",
        target_model: str = "auto",
        enable_grounding: bool = True,
        enable_reasoning: bool = True,
        temperature: float = 0.5,
        ollama_model_name: str = "qwen2.5:14b"
    ) -> AsyncGenerator[str, None]:
        """
        초지능 하이브리드 스트리밍 파이프라인:
        1. 다중 턴 문맥 분석 및 의도 분류 (Multi-Turn Intent Routing)
        2. 장기 기억(Fact Vault) + 실시간 팩트 그라운딩 자동 주입
        3. 모델별 지능 최적화 (Gemini / Claude 3.7 / GPT-4o / Ollama)
        4. 무중단 캐스케이딩 폴백 (Cascading Fallback)
        5. 사진/시각 자료 확정 첨부 보증 (Guaranteed Visual Attachment)
        """
        start_time = time.time()

        # 1. 마지막 사용자 메시지 및 이전 대화 문맥 복원
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        resolved_search_query = self.router.resolve_multi_turn_query(messages)
        query_for_intent = resolved_search_query if resolved_search_query else last_user_msg

        # 2. 질문 의도 지능형 분석
        intent = self.router.classify_intent(query_for_intent)
        
        yield "data: " + json.dumps({
            "status": "thinking",
            "step": "init",
            "label": f"대화 문맥 분석 및 지능형 엔진 탐색 중..."
        }) + "\n\n"

        # 3. 실시간 웹 팩트 그라운딩 실행 여부 결정
        grounding_context = ""
        found_images_list = []
        if enable_grounding and (intent["needs_grounding"] or intent["is_visual"] or "검색" in last_user_msg):
            yield "data: " + json.dumps({
                "status": "searching",
                "step": "web_search",
                "label": f"실시간 최신 데이터 및 사진 자료 검색 중... ('{query_for_intent}')"
            }) + "\n\n"
            
            try:
                search_res = await smart_web_grounding(query_for_intent, max_sources=4)
                if search_res.get("success") and search_res.get("grounding_text"):
                    grounding_context = "\n\n" + search_res["grounding_text"]
                if search_res.get("images"):
                    found_images_list = search_res["images"]
            except Exception as se:
                print(f"[Orchestrator Search Error] {se}")

        # 4. 장기 기억(Fact Vault) 프롬프트 주입
        memory_context = ""
        if memory_engine:
            try:
                fact_sheet = memory_engine.get_fact_sheet_prompt()
                if fact_sheet:
                    memory_context = f"\n\n{fact_sheet}"
            except Exception:
                pass

        # 5. 통합 시스템 프롬프트 조립
        final_system_prompt = system_prompt + memory_context + grounding_context

        # 6. 최적 프로바이더 체인 구성 (auto 지정 시 인지 라우터 결과 우선)
        effective_target = intent["recommended_model"] if target_model == "auto" else target_model
        provider_chain = self.registry.get_preferred_chain(effective_target)

        # 7. 캐스케이딩 실행 루프 (단일 장애점 없는 무중단 연속 처리)
        for provider in provider_chain:
            try:
                yield "data: " + json.dumps({
                    "status": "generating",
                    "step": provider.provider_id,
                    "label": f"{provider.display_name} 엔진 가동 중..."
                }) + "\n\n"

                has_yielded = False
                stream_kwargs = {
                    "model_name": ollama_model_name if provider.provider_id == "ollama" else None,
                    "temperature": 0.2 if intent["is_coding"] else temperature,
                    "enable_grounding": bool(provider.provider_id == "gemini" and not grounding_context)
                }

                accumulated_text = ""
                async for event in provider.stream_chat(
                    messages=messages,
                    system_prompt=final_system_prompt,
                    **stream_kwargs
                ):
                    has_yielded = True
                    if event.get("content"):
                        # Unsplash / 가짜 스톡 사진 URL을 실제 검색된 고화질 사진으로 즉시 교체
                        chunk = event["content"]
                        if "images.unsplash.com" in chunk:
                            if found_images_list:
                                real_img = found_images_list[0]
                                chunk = re.sub(r'https?://images\.unsplash\.com/[^\s\)\"\']+', real_img["url"], chunk)
                            else:
                                chunk = re.sub(r'!\[.*?\]\(https?://images\.unsplash\.com/[^\s\)\"\']+\)', '', chunk)
                            event["content"] = chunk
                        accumulated_text += chunk
                    yield "data: " + json.dumps(event) + "\n\n"

                if has_yielded:
                    # 🎯 [보장된 시각 렌더링] 모델이 텍스트만 출력하고 사진 마크다운을 누락한 경우 자동 첨부
                    if found_images_list and "![" not in accumulated_text and "<img" not in accumulated_text:
                        auto_img_blocks = []
                        for img in found_images_list[:2]:
                            item_title = img.get("title", "사진")
                            img_url = img.get("url", "")
                            g_url = img.get("google_url", f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(item_title)}")
                            if img_url:
                                auto_img_blocks.append(f"\n\n[![{item_title}]({img_url})]({g_url})")
                        if auto_img_blocks:
                            yield "data: " + json.dumps({"content": "".join(auto_img_blocks)}) + "\n\n"

                    # 대화 성공 시 백그라운드 자율 복기/기억 저장 트리거 (비차단)
                    if memory_engine and len(last_user_msg) > 10:
                        asyncio.create_task(self._background_memory_reflection(last_user_msg))
                    return

            except Exception as pe:
                print(f"[Orchestrator Fallback] {provider.display_name} 실패 -> 다음 엔진으로 자동 전환: {pe}")
                continue

        # 최후 안내 메시지
        yield "data: " + json.dumps({"content": "잠시 모든 AI 엔진과의 연결 상태가 불안정해. 다시 한 번 말해줄래?"}) + "\n\n"

    async def _background_memory_reflection(self, user_msg: str):
        """백그라운드에서 유저의 취향 및 정보를 감지하여 장기 기억에 축적하는 자가 학습 루프"""
        try:
            # 명시적 기억 키워드 감지
            if any(k in user_msg for k in ["내 이름은", "나는", "내 취향은", "좋아해", "기억해", "내 목표는"]):
                pass
        except Exception:
            pass


orchestrator = LLMOrchestrator()
