"""
routers/chat.py
------------------------------------------------------------
💬 JARVIS 메인 대화(Chat) & LLM 오케스트레이션 & 도구 실행 라우터.
- 멀티 에이전트 스트리밍 대화 (/chat)
- 웹 실시간 검색 기반 RAG 자동 완성 (/auto-search, /auto-search-stream)
- 확장 도구 및 Python 샌드박스 실행 (/api/tools/execute, /api/python/execute)
- 에이전트/도구/프로바이더 카탈로그 (/api/agents, /api/tools, /api/providers)
- 대화 내보내기 및 영구 스토리지 백업 (/api/chat/export, /api/storage/save, /api/storage/load)
------------------------------------------------------------
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

# ============================================================
# 1. Pydantic 요청 스키마 정의
# ============================================================
class Message(BaseModel):
    role: str
    content: str
    images: Optional[List[str]] = None

class ChatRequest(BaseModel):
    messages: List[Message]
    agent: str = "skadi"
    model: str = "gemini"
    game_mode: bool = False

class AutoSearchRequest(BaseModel):
    query: str
    agent: str = "skadi"

class ToolExecuteRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}

class PythonExecuteRequest(BaseModel):
    code: str

class SearchGroundingRequest(BaseModel):
    query: str
    max_sources: int = 4

class ChatExportRequest(BaseModel):
    title: str
    messages: List[Dict[str, Any]]

class StorageSaveRequest(BaseModel):
    key: str
    data: Any

STORAGE_FILE = os.path.join(str(MEMORY_DIR), "app_storage_data.json")

def load_user_profile(agent: str = "general") -> str:
    """에이전트별 축적된 유저 프로필 마크다운 로드"""
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

# ============================================================
# 2. 메인 스트리밍 대화 엔드포인트 (/chat)
# ============================================================
@router.post("/chat", summary="멀티 에이전트 실시간 스트리밍 대화")
async def chat(req: ChatRequest):
    """
    1) 유저 질의를 분석하여 LoL, 메이플, 코딩, R6S 등 적절한 ChromaDB 지식 컬렉션을 자동 라우팅합니다.
    2) 유저 프로필과 장기 기억 팩트 시트를 프롬프트에 주입합니다.
    3) LLM 오케스트레이터를 가동하여 SSE(Server-Sent Events) 스트림으로 토큰을 실시간 전송합니다.
    """
    try:
        last_msg = req.messages[-1].content or "" if req.messages else ""
        clean_last_msg = last_msg.strip()
        context_str = ""

        # 지능형 타겟 컬렉션 자동 판별
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

        # RAG 지식 고속 검색 (단순 인사가 아닐 때만)
        is_greeting = len(clean_last_msg) < 3 or clean_last_msg in ["안녕", "ㅎㅇ", "응", "어", "아니", "그래", "ㅋㅋ", "ㅎㅎ"]
        if clean_last_msg and not is_greeting:
            try:
                def _rag_search():
                    res = target_collection.query(query_texts=[clean_last_msg], n_results=3)
                    if res and res.get("documents") and len(res["documents"][0]) > 0:
                        return res["documents"][0]
                    return []
                docs = await asyncio.wait_for(asyncio.to_thread(_rag_search), timeout=0.8)
                if docs:
                    context_str += f"\n\n[데이터베이스 연동 지식]\n" + "\n---\n".join(docs)
            except Exception:
                pass

        # 유저 프로필 주입
        u_profile = load_user_profile(req.agent)
        if u_profile != "현재 분석된 유저 프로필이 없습니다.":
            context_str += f"\n\n[주인 맞춤형 프로필]\n{u_profile}"

        # 스카디 장기 기억 주입
        if req.agent.startswith("skadi") or req.agent in ["general", "default"]:
            try:
                fact_sheet = get_fact_sheet_prompt()
                if fact_sheet:
                    context_str += f"\n\n{fact_sheet}"
                if any(k in clean_last_msg for k in ["기억해", "내 이름은", "내가 좋아하는", "내 취향은"]):
                    add_explicit_memory(clean_last_msg)
            except Exception:
                pass

        # 시스템 프롬프트 조합
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
        async def fallback():
            yield "data: " + json.dumps({'content': f'잠시 연결 동기화 중 오류가 발생했어: {str(e)}'}) + "\n\n"
        return StreamingResponse(fallback(), media_type="text/event-stream")

# ============================================================
# 3. 도구 & 샌드박스 & 메타데이터 API
# ============================================================
@router.get("/api/agents", summary="등록된 모든 에이전트 프로필 목록")
def get_agents():
    return {"agents": agent_registry.list_agents()}

@router.get("/api/tools", summary="등록된 확장 도구 목록")
def get_tools():
    return {"tools": tool_registry.list_tools()}

@router.get("/api/providers", summary="가용 LLM 엔진 및 모델 목록")
def get_providers():
    available = [
        {"id": p.provider_id, "name": p.display_name, "available": p.is_available()}
        for p in provider_registry.get_available_providers()
    ]
    return {"providers": available, "models": MODEL_REGISTRY}

@router.post("/api/tools/execute", summary="도구 동적 실행")
async def execute_tool(req: ToolExecuteRequest):
    return await tool_registry.execute(req.tool_name, **req.arguments)

@router.post("/api/python/execute", summary="안전한 Python 연산 샌드박스")
async def execute_python(req: PythonExecuteRequest):
    return run_safe_python(req.code)

@router.post("/api/search/grounding", summary="실시간 웹 검색 및 팩트 추출")
async def search_grounding(req: SearchGroundingRequest):
    return await smart_web_grounding(req.query, max_sources=req.max_sources)

@router.post("/api/chat/export", summary="대화 세션 마크다운 내보내기")
async def export_chat(req: ChatExportRequest):
    lines = [f"# {req.title}\n", f"> 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n"]
    for msg in req.messages:
        role = "사용자" if msg.get("role") == "user" else "AI"
        lines.append(f"### 👤 {role}\n\n{msg.get('content', '')}\n\n---\n")
    return {"markdown": "\n".join(lines)}

# ============================================================
# 4. 앱 스토리지 영구 백업 API
# ============================================================
@router.post("/api/storage/save", summary="앱 설정 및 상태 디스크 저장")
async def save_storage(req: StorageSaveRequest):
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
    try:
        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, "r", encoding="utf-8") as f:
                return {"status": "success", "data": json.load(f)}
        return {"status": "success", "data": {}}
    except Exception as e:
        return {"status": "error", "message": str(e)}
