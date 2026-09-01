"""
llm_providers.py
------------------------------------------------------------
GPT, Gemini, Claude, Ollama 등 모든 주요 LLM 엔진을 단일 인터페이스로
통합하는 다형성(Polymorphic) Provider 아키텍처.

구조:
- BaseLLMProvider (추상 기반 클래스)
  - GeminiProvider (Google GenAI SDK 기반, 검색 그라운딩 및 다계층 폴백 지원)
  - OpenAIProvider (OpenAI API / GPT-4o, o3, o1, GPT-4.5 비동기 스트리밍)
  - ClaudeProvider (Anthropic Claude 3.7 Sonnet / 3.5 Sonnet / Haiku 및 Thinking 모드)
  - OllamaProvider (로컬 Llama 3.1, DeepSeek-R1, Qwen 2.5, Gemma 2 고속 스트리밍)
  - ProviderRegistry (플러그 앤 플레이 방식의 프로바이더 자동 등록 및 탐색기)
------------------------------------------------------------
"""

import os
import json
import time
import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx

from config import API_KEYS, OLLAMA_HOST, DEFAULT_GENERATION_PARAMS


# 공용 비동기 HTTP 클라이언트 관리자 (싱글톤)
_SHARED_HTTP_CLIENT: Optional[httpx.AsyncClient] = None

def get_shared_http_client() -> httpx.AsyncClient:
    global _SHARED_HTTP_CLIENT
    if _SHARED_HTTP_CLIENT is None or _SHARED_HTTP_CLIENT.is_closed:
        _SHARED_HTTP_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_GENERATION_PARAMS["timeout_sec"], connect=DEFAULT_GENERATION_PARAMS["connect_timeout_sec"]),
            limits=httpx.Limits(max_keepalive_connections=30, max_connections=60)
        )
    return _SHARED_HTTP_CLIENT


# ==========================================
# 1. Abstract Base Provider
# ==========================================
class BaseLLMProvider(ABC):
    """모든 LLM 공급자의 공통 추상 클래스"""
    
    @property
    @abstractmethod
    def provider_id(self) -> str:
        """프로바이더 고유 식별자 (예: 'gemini', 'openai', 'claude', 'ollama')"""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """UI 표기용 프로바이더 이름"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """API 키 존재 여부 또는 로컬 인프라 연결 가능 여부 반환"""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        model_name: Optional[str] = None,
        temperature: float = 0.5,
        enable_grounding: bool = False,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        통일된 딕셔너리 스트림 생성:
        - {"status": "thinking", "label": "..."}
        - {"status": "reasoning", "thought": "..."}
        - {"content": "토큰 텍스트"}
        """
        pass


# ==========================================
# 2. Google Gemini Provider
# ==========================================
class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        self._client = None

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

    def is_available(self) -> bool:
        key = API_KEYS.get("GEMINI") or os.environ.get("GEMINI_API_KEY")
        return bool(key and key.strip())

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                key = API_KEYS.get("GEMINI") or os.environ.get("GEMINI_API_KEY")
                self._client = genai.Client(api_key=key)
            except Exception as e:
                print(f"[GeminiProvider Client Error] {e}")
        return self._client

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        model_name: Optional[str] = None,
        temperature: float = 0.5,
        enable_grounding: bool = False,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        client = self._get_client()
        if not client:
            raise RuntimeError("Gemini Client 초기화 실패")

        from google.genai import types
        
        candidate_models = [model_name] if model_name else ['gemini-flash-latest', 'gemini-3.5-flash', 'gemini-2.5-flash']
        
        # 마지막 유저 메시지 추출
        last_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_msg = m.get("content", "")
                break

        full_prompt = f"{system_prompt}\n\n질문: {last_msg}"

        # 1차: 검색 그라운딩 시도 (활성화된 경우)
        if enable_grounding:
            for m in candidate_models:
                try:
                    tools = [types.Tool(google_search=types.GoogleSearch())]
                    config = types.GenerateContentConfig(temperature=temperature, tools=tools)
                    has_yielded = False
                    async for chunk in await client.aio.models.generate_content_stream(
                        model=m,
                        contents=full_prompt,
                        config=config
                    ):
                        if chunk.text:
                            has_yielded = True
                            yield {"content": chunk.text}
                    if has_yielded:
                        return
                except Exception as e:
                    print(f"[Gemini Search Fail - {m}] {e}")

        # 2차: 일반 생성 시도 (검색 실패 시 또는 그라운딩 비활성화 시)
        for m in candidate_models:
            try:
                config = types.GenerateContentConfig(temperature=temperature)
                has_yielded = False
                async for chunk in await client.aio.models.generate_content_stream(
                    model=m,
                    contents=full_prompt,
                    config=config
                ):
                    if chunk.text:
                        has_yielded = True
                        yield {"content": chunk.text}
                if has_yielded:
                    return
            except Exception as e:
                print(f"[Gemini Direct Fail - {m}] {e}")

        raise RuntimeError("모든 Gemini 모델 스트리밍 호출 실패")


# ==========================================
# 3. OpenAI GPT Provider (GPT-4o, o3, o1, GPT-4.5)
# ==========================================
class OpenAIProvider(BaseLLMProvider):
    @property
    def provider_id(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return "OpenAI GPT-4o / o3"

    def is_available(self) -> bool:
        key = API_KEYS.get("OPENAI") or os.environ.get("OPENAI_API_KEY")
        return bool(key and key.strip())

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        model_name: Optional[str] = None,
        temperature: float = 0.5,
        enable_grounding: bool = False,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        api_key = API_KEYS.get("OPENAI") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 미설정")

        target_model = model_name or "gpt-4o"
        http_client = get_shared_http_client()

        # 메시지 조립
        formatted_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            if m.get("role") != "system":
                formatted_messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

        payload = {
            "model": target_model,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": True
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        async with http_client.stream("POST", "https://api.openai.com/v1/chat/completions", json=payload, headers=headers) as res:
            if res.status_code != 200:
                err_text = await res.aread()
                raise RuntimeError(f"OpenAI API Error ({res.status_code}): {err_text.decode('utf-8')}")

            async for line in res.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choice = data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield {"content": content}
                except Exception:
                    pass


# ==========================================
# 4. Anthropic Claude Provider (Claude 3.7 / 3.5 Sonnet / Haiku)
# ==========================================
class ClaudeProvider(BaseLLMProvider):
    @property
    def provider_id(self) -> str:
        return "claude"

    @property
    def display_name(self) -> str:
        return "Anthropic Claude 3.7"

    def is_available(self) -> bool:
        key = API_KEYS.get("ANTHROPIC") or os.environ.get("ANTHROPIC_API_KEY")
        return bool(key and key.strip())

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        model_name: Optional[str] = None,
        temperature: float = 0.5,
        enable_grounding: bool = False,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        api_key = API_KEYS.get("ANTHROPIC") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY 미설정")

        target_model = model_name or "claude-3-7-sonnet-latest"
        http_client = get_shared_http_client()

        # Claude 형식 메시지 조립
        formatted_messages = []
        for m in messages:
            if m.get("role") in ["user", "assistant"]:
                formatted_messages.append({"role": m["role"], "content": m.get("content", "")})

        payload = {
            "model": target_model,
            "system": system_prompt,
            "messages": formatted_messages,
            "max_tokens": 4096,
            "temperature": temperature,
            "stream": True
        }

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        async with http_client.stream("POST", "https://api.anthropic.com/v1/messages", json=payload, headers=headers) as res:
            if res.status_code != 200:
                err_text = await res.aread()
                raise RuntimeError(f"Claude API Error ({res.status_code}): {err_text.decode('utf-8')}")

            async for line in res.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                try:
                    event_data = json.loads(data_str)
                    event_type = event_data.get("type", "")

                    # 1. Thinking / Reasoning 블록
                    if event_type == "content_block_delta":
                        delta = event_data.get("delta", {})
                        if delta.get("type") == "thinking_delta":
                            yield {"status": "reasoning_chunk", "chunk": delta.get("thinking", "")}
                        elif delta.get("type") == "text_delta":
                            yield {"content": delta.get("text", "")}
                except Exception:
                    pass


# ==========================================
# 5. Local Ollama Provider (Llama 3.1, DeepSeek-R1, Qwen, Gemma)
# ==========================================
class OllamaProvider(BaseLLMProvider):
    def __init__(self, host: str = OLLAMA_HOST):
        self.host = host

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def display_name(self) -> str:
        return "Local Ollama"

    def is_available(self) -> bool:
        return True  # 로컬 서버 기본 가용

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        model_name: Optional[str] = None,
        temperature: float = 0.5,
        enable_grounding: bool = False,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        target_model = model_name or "llama3.1"
        http_client = get_shared_http_client()

        # 최근 대화 메시지 추출
        non_system = [m for m in messages if m.get("role") != "system"]
        recent = non_system[-6:] if len(non_system) > 6 else non_system

        ollama_messages = [{"role": "system", "content": system_prompt}]
        for m in recent:
            m_dict = {"role": m.get("role", "user"), "content": m.get("content", "")}
            if m.get("images"):
                m_dict["images"] = [img.split(',', 1)[1] if ',' in img else img for img in m["images"]]
            ollama_messages.append(m_dict)

        payload = {
            "model": target_model,
            "messages": ollama_messages,
            "stream": True,
            "keep_alive": "2h",
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": 4096,
                "num_ctx": 8192,
                "num_thread": 12
            }
        }

        in_think_mode = False
        think_buffer = ""

        async with http_client.stream("POST", f"{self.host}/api/chat", json=payload) as res:
            if res.status_code != 200:
                raise RuntimeError(f"Ollama 연결 실패 (HTTP {res.status_code})")

            async for line in res.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "error" in data:
                        break
                    chunk = data.get("message", {}).get("content", "")
                    if not chunk:
                        continue

                    # <think> 태그 파싱 (DeepSeek R1 / Qwen Reasoning 지원)
                    if "<think>" in chunk and not in_think_mode:
                        in_think_mode = True
                        parts = chunk.split("<think>", 1)
                        if parts[0]:
                            yield {"content": parts[0]}
                        chunk = parts[1]

                    if in_think_mode:
                        if "</think>" in chunk:
                            in_think_mode = False
                            parts = chunk.split("</think>", 1)
                            think_buffer += parts[0]
                            yield {"status": "reasoning", "thought": think_buffer}
                            if parts[1]:
                                yield {"content": parts[1]}
                        else:
                            think_buffer += chunk
                            yield {"status": "reasoning_chunk", "chunk": chunk}
                    else:
                        yield {"content": chunk}

                except Exception:
                    pass


# ==========================================
# 6. Unified Provider Registry
# ==========================================
class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
        self.register(GeminiProvider())
        self.register(OpenAIProvider())
        self.register(ClaudeProvider())
        self.register(OllamaProvider())

    def register(self, provider: BaseLLMProvider):
        """새로운 프로바이더 등록 (플러그 앤 플레이)"""
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> Optional[BaseLLMProvider]:
        return self._providers.get(provider_id)

    def get_available_providers(self) -> List[BaseLLMProvider]:
        return [p for p in self._providers.values() if p.is_available()]

    def get_preferred_chain(self, target_provider: Optional[str] = None) -> List[BaseLLMProvider]:
        """
        우선순위 체인 구성:
        - 특정 프로바이더 지정 시 해당 프로바이더 최우선
        - 사용 가능한 클라우드(Gemini/OpenAI/Claude) -> 로컬 Ollama 순서로 탄력적 체인 구성
        """
        chain = []
        if target_provider and target_provider in self._providers:
            chain.append(self._providers[target_provider])

        # 기본 자동 폴백 순서
        for pid in ["gemini", "claude", "openai", "ollama"]:
            p = self._providers.get(pid)
            if p and p not in chain and p.is_available():
                chain.append(p)
                
        # 만약 아무것도 없으면 로컬 Ollama 보장
        if not chain and "ollama" in self._providers:
            chain.append(self._providers["ollama"])
            
        return chain


provider_registry = ProviderRegistry()
