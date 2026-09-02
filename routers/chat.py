"""
routers/chat.py
==============================================================================
💬 JARVIS 메인 대화(Chat) & LLM 오케스트레이션 & 도구 실행 라우터
==============================================================================
이 모듈은 챗봇과의 모든 실시간 텍스트/이미지 대화, RAG 지식 검색, 확장 도구 실행,
Python 샌드박스 연산 및 대화 기록 저장을 전담하는 핵심 라우터입니다.

주요 엔드포인트:
  1) POST /chat                : 멀티 에이전트 SSE(Server-Sent Events) 스트리밍 대화
  2) GET  /api/agents          : 등록된 에이전트(스카디, 브라이어, 코더, 루시 등) 목록
  3) GET  /api/tools           : 사용 가능한 AI 확장 도구 목록 조회
  4) GET  /api/providers       : 가용 LLM 제공자(Gemini, OpenAI, Claude, Ollama) 조회
  5) POST /api/tools/execute   : AI 도구 동적 실행
  6) POST /api/python/execute  : 안전한 Python 샌드박스 연산 실행
  7) POST /api/search/grounding: DuckDuckGo 실시간 웹 검색 및 팩트 추출
  8) POST /api/chat/export     : 대화 내역 마크다운 문서로 내보내기
  9) POST/GET /api/storage/*   : 브라우저 로컬 스토리지 데이터 디스크 영구 백업
==============================================================================
"""

import os
import json
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import MEMORY_DIR, BASE_DIR, MODEL_REGISTRY
from core.utils import get_cached_file_content
from llm_orchestrator import orchestrator
from agent_registry import agent_registry
from tool_registry import tool_registry
from llm_providers import provider_registry
from python_sandbox import run_safe_python
from smart_search import smart_web_grounding, search_duckduckgo
from skadi_memory_engine import get_fact_sheet_prompt, add_explicit_memory, get_growth_journal
from routers.memory import (
    collection_general, collection_lol, collection_maple,
    collection_r6s, collection_coding, collection_hacking
)

router = APIRouter(tags=["Chat & LLM Orchestration"])

# ==============================================================================
# 1. Pydantic 요청/응답 스키마 정의 (데이터 유효성 검증용)
# ==============================================================================
class Message(BaseModel):
    """단일 대화 메시지 모델 (역할, 내용, 선택적 base64 이미지)"""
    role: str                       # "user" (사용자) 또는 "assistant" (AI 비서)
    content: str                    # 메시지 텍스트 본문
    images: Optional[List[str]] = None  # 비전 모델 전달용 base64 이미지 목록

class ChatRequest(BaseModel):
    """/chat 엔드포인트 대화 요청 페이로드"""
    messages: List[Message]         # 이전 대화 기록을 포함한 전체 메시지 배열
    agent: str = "skadi"            # 대화할 캐릭터 ID (skadi, briar, coder, lucy, angelic 등)
    model: str = "gemini"           # 사용할 LLM 엔진 (gemini, openai, claude, ollama 등)
    game_mode: bool = False         # 저사양 게임 모드 플래그 (True 시 초경량 로컬 모델 사용)

class ToolExecuteRequest(BaseModel):
    """확장 도구 동적 실행 요청 모델"""
    tool_name: str                  # 실행할 도구 이름 (예: ddg_search, get_time 등)
    arguments: Dict[str, Any] = {}  # 도구에 전달할 파라미터 딕셔너리

class PythonExecuteRequest(BaseModel):
    """Python 샌드박스 연산 요청 모델"""
    code: str                       # 안전하게 실행할 파이썬 소스코드

class SearchGroundingRequest(BaseModel):
    """웹 검색 기반 팩트 그라운딩 요청 모델"""
    query: str                      # 검색 질의어
    max_sources: int = 4            # 수집할 최대 웹 문서 수

class ChatExportRequest(BaseModel):
    """대화 세션 내보내기 요청 모델"""
    title: str                      # 저장할 마크다운 문서 제목
    messages: List[Dict[str, Any]]  # 내보낼 대화 메시지 배열

class StorageSaveRequest(BaseModel):
    """앱 상태 디스크 저장 요청 모델"""
    key: str                        # 저장 키 식별자
    data: Any                       # 저장할 임의의 JSON 직렬화 가능 데이터

# 앱 상태 및 유저 설정 영구 저장 파일 경로
STORAGE_FILE = os.path.join(str(MEMORY_DIR), "app_storage_data.json")

def load_user_profile(agent: str = "general") -> str:
    """
    [헬퍼 함수] 캐릭터별로 영구 축적된 유저 프로필 마크다운 파일 내용을 로드합니다.
    - 예: skadi -> user_profile.md, coder -> user_profile_coding.md
    """
    profile_map = {
        "skadi": "user_profile.md",
        "coder": "user_profile_coding.md",
        "skadi_r6s": "user_profile_r6s.md",
        "lucy": "user_profile_hacking.md",
        "briar": "user_profile_lol.md"
    }
    filename = profile_map.get(agent, "user_profile.md")
    user_profile_path = os.path.join(str(MEMORY_DIR), filename)
    if os.path.exists(user_profile_path):
        try:
            with open(user_profile_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return "현재 분석된 유저 프로필이 없습니다."

# ==============================================================================
# 2. 메인 실시간 스트리밍 대화 엔드포인트 (/chat)
# ==============================================================================
@router.post("/chat", summary="멀티 에이전트 실시간 스트리밍 대화")
async def chat(req: ChatRequest):
    """
    🎯 [대화 처리 메커니즘]
    1) 질문 분석 및 ChromaDB 컬렉션 자동 선택:
       - 롤 관련 키워드 ➔ collection_lol
       - 메이플 관련 키워드 ➔ collection_maple
       - 코딩/해킹 ➔ collection_coding / collection_hacking
    2) RAG 지식 검색:
       - 단순 인사가 아닐 때 ChromaDB에서 유사도가 가장 높은 상위 문서 3개를 추출하여 프롬프트에 주입.
    3) 유저 프로필 및 장기 기억 주입:
       - 유저의 취향, 생일, 성향 팩트 시트와 자기성장 일지를 컨텍스트에 포함.
    4) LLM 스트리밍 생성:
       - 선택된 모델(Gemini, OpenAI, Claude, Ollama)로 SSE(Server-Sent Events) 스트림을 가동하여
         0.1초 단위로 실시간 답변 토큰을 프론트엔드로 전송.
    """
    try:
        last_msg = req.messages[-1].content or "" if req.messages else ""
        clean_last_msg = last_msg.strip()
        context_str = ""

        # ----------------------------------------------------
        # 1단계: 유저 질문 키워드 기반 ChromaDB 컬렉션 라우팅
        # ----------------------------------------------------
        is_lol = any(k in clean_last_msg for k in ["롤", "리그오브", "도란", "아이템", "챔피언", "템트리", "브라이어", "정글"])
        is_maple = any(k in clean_last_msg for k in ["메이플", "엔버", "엔젤릭", "보스", "메소", "스타포스", "심볼", "유니온"])

        if req.agent == "angelic" or is_maple:
            target_collection = collection_maple
        elif req.agent == "skadi_r6s":
            target_collection = collection_r6s
        elif req.agent == "coder":
            target_collection = collection_coding
        elif is_lol or req.agent == "briar":
            target_collection = collection_lol
        elif req.agent == "lucy":
            target_collection = collection_hacking
        else:
            target_collection = collection_general

        # ----------------------------------------------------
        # 2단계: RAG 벡터 검색 (불필요한 인사말 I/O 필터링)
        # ----------------------------------------------------
        is_greeting = len(clean_last_msg) < 3 or clean_last_msg in ["안녕", "ㅎㅇ", "응", "어", "아니", "그래", "ㅋㅋ", "ㅎㅎ"]
        if clean_last_msg and not is_greeting:
            try:
                def _rag_search():
                    res = target_collection.query(query_texts=[clean_last_msg], n_results=3)
                    if res and res.get("documents") and len(res["documents"][0]) > 0:
                        return res["documents"][0]
                    return []
                # 0.8초 타임아웃으로 UI 멈춤 방지
                docs = await asyncio.wait_for(asyncio.to_thread(_rag_search), timeout=0.8)
                if docs:
                    context_str += f"\n\n[데이터베이스 연동 지식]\n" + "\n---\n".join(docs)
            except Exception:
                pass

        # ----------------------------------------------------
        # 3단계: 유저 맞춤 프로필 및 장기 기억 주입
        # ----------------------------------------------------
        u_profile = load_user_profile(req.agent)
        if u_profile != "현재 분석된 유저 프로필이 없습니다.":
            context_str += f"\n\n[주인 맞춤형 프로필]\n{u_profile}"

        if req.agent.startswith("skadi") or req.agent in ["general", "default"]:
            try:
                fact_sheet = get_fact_sheet_prompt()
                if fact_sheet:
                    context_str += f"\n\n{fact_sheet}"
                # 명시적 기억 키워드 감지 시 영구 저장
                if any(k in clean_last_msg for k in ["기억해", "내 이름은", "내가 좋아하는", "내 취향은"]):
                    add_explicit_memory(clean_last_msg)
            except Exception:
                pass

        # ----------------------------------------------------
        # 4단계: 에이전트 시스템 프롬프트 조립 & LLM 스트리밍 가동
        # ----------------------------------------------------
        agent_profile = agent_registry.get(req.agent)
        system_content = agent_profile.assemble_system_prompt(context_str=context_str)

        target_model = req.model if req.model in ["gemini", "openai", "claude", "ollama"] else "gemini"
        msg_dicts = [m.dict(exclude_none=True) for m in req.messages]

        stream_gen = orchestrator.stream_chat(
            messages=msg_dicts,
            system_prompt=system_content,
            agent_name=agent_profile.display_name,
            target_model=target_model,
            enable_grounding=True,
            enable_reasoning=True,
            temperature=0.5
        )
        return StreamingResponse(stream_gen, media_type="text/event-stream")

    except Exception as e:
        # 에러 발생 시 부드러운 Fallback 메시지 스트리밍
        async def fallback():
            yield "data: " + json.dumps({'content': f'잠시 연결 동기화 중 오류가 발생했어: {str(e)}'}) + "\n\n"
        return StreamingResponse(fallback(), media_type="text/event-stream")

# ==============================================================================
# 3. 확장 도구 & Python 샌드박스 & 메타데이터 엔드포인트
# ==============================================================================
@router.get("/api/agents", summary="등록된 모든 에이전트 프로필 목록")
def get_agents():
    """스카디, 브라이어, 코더, 루시 등 시스템에 등록된 모든 캐릭터 에이전트 프로필을 반환합니다."""
    return {"agents": agent_registry.list_agents()}

@router.get("/api/tools", summary="등록된 확장 도구 목록")
def get_tools():
    """웹 검색, 계산기, 시스템 도구 등 AI가 호출 가능한 도구 목록을 반환합니다."""
    return {"tools": tool_registry.list_tools()}

@router.get("/api/providers", summary="가용 LLM 엔진 및 모델 목록")
def get_providers():
    """현재 API 키가 등록되어 가용 상태인 LLM 엔진(Gemini, Claude, GPT, Ollama)을 반환합니다."""
    available = [
        {"id": p.provider_id, "name": p.display_name, "available": p.is_available()}
        for p in provider_registry.get_available_providers()
    ]
    return {"providers": available, "models": MODEL_REGISTRY}

@router.post("/api/tools/execute", summary="도구 동적 실행")
async def execute_tool(req: ToolExecuteRequest):
    """지정된 AI 도구(tool_name)를 비동기로 실행하고 그 결과를 반환합니다."""
    return await tool_registry.execute(req.tool_name, **req.arguments)

@router.post("/api/python/execute", summary="안전한 Python 연산 샌드박스")
async def execute_python(req: PythonExecuteRequest):
    """격리된 환경에서 수학 계산, 데이터 조작 등 파이썬 코드를 안전하게 실행합니다."""
    return run_safe_python(req.code)

@router.post("/api/search/grounding", summary="실시간 웹 검색 및 팩트 추출")
async def search_grounding(req: SearchGroundingRequest):
    """DuckDuckGo를 통해 웹 검색을 수행하고 신뢰도 높은 최신 팩트를 추출합니다."""
    return await smart_web_grounding(req.query, max_sources=req.max_sources)

@router.post("/api/chat/export", summary="대화 세션 마크다운 내보내기")
async def export_chat(req: ChatExportRequest):
    """현재 대화방의 전체 세션을 깔끔하게 정돈된 마크다운(.md) 텍스트로 변환합니다."""
    lines = [f"# {req.title}\n", f"> 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n"]
    for msg in req.messages:
        role = "사용자" if msg.get("role") == "user" else "AI"
        lines.append(f"### 👤 {role}\n\n{msg.get('content', '')}\n\n---\n")
    return {"markdown": "\n".join(lines)}

# ==============================================================================
# 4. 앱 스토리지 영구 디스크 백업 API
# ==============================================================================
@router.post("/api/storage/save", summary="앱 설정 및 상태 디스크 저장")
async def save_storage(req: StorageSaveRequest):
    """웹 브라우저의 localStorage 설정 및 데이터를 서버 디스크 파일(app_storage_data.json)에 영구 백업합니다."""
    try:
        storage = {}
        if os.path.exists(STORAGE_FILE):
            try:
                with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                    storage = json.load(f)
            except Exception:
                storage = {}
        storage[req.key] = req.data
        with open(STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(storage, f, ensure_ascii=False, indent=2)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/storage/load", summary="앱 설정 및 상태 디스크 로드")
async def load_storage():
    """서버 디스크에 영구 백업된 앱 설정 및 데이터를 조회하여 브라우저로 불러옵니다."""
    try:
        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                return {"status": "success", "data": json.load(f)}
        return {"status": "success", "data": {}}
    except Exception as e:
        return {"status": "error", "message": str(e)}
