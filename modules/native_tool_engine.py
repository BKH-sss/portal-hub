"""
native_tool_engine.py
=============================================================================
🛠️ JARVIS 네이티브 도구(Function Calling) & 디스패치 통합 엔진
=============================================================================
- 기능:
    1. 정규식 문자열 태그('[검색요청]', '[SDDRAW:]')를 완전히 대체하는 표준 Tool Schema
    2. OpenAI, Google Gemini, Anthropic Claude, Ollama 공용 도구 스펙 제공
    3. LLM의 Function Call 요청을 감지하고 해당 모듈의 함수를 비동기 실행 및 결과 반환
    4. 시스템 제어, 일정, 웹검색, 게임 API, 파이썬 코드 실행 단일 디스패처
=============================================================================
"""

import json
import asyncio
from typing import Dict, Any, List, Callable, Optional
try:
    from modules._safe_router import (
        APIRouter, HTTPException, Response, HTMLResponse, FileResponse,
        JSONResponse, Request, WebSocket, WebSocketDisconnect, FastAPI,
        CORSMiddleware, BaseModel, Field
    )
except ImportError:
    try:
        from _safe_router import (
            APIRouter, HTTPException, Response, HTMLResponse, FileResponse,
            JSONResponse, Request, WebSocket, WebSocketDisconnect, FastAPI,
            CORSMiddleware, BaseModel, Field
        )
    except ImportError:
        pass

# =============================================================================
# 📋 1. 표준 Tool Definitions (JSON Schema 규격)
# =============================================================================
JARVIS_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "system_control",
            "description": "PC의 볼륨 조절, 음소거, 미디어 재생/일시정지, 화면 잠금 등 OS 제어를 수행합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["set_volume", "toggle_mute", "play_pause", "next_track", "prev_track", "lock_screen"],
                        "description": "실행할 시스템 동작"
                    },
                    "volume_level": {
                        "type": "integer",
                        "description": "set_volume 동작 시 목표 볼륨 (0~100)"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_hardware_metrics",
            "description": "GPU(온도, VRAM 사용량), CPU 점유율, RAM 사용량 등 PC 하드웨어 상태를 조회합니다.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_schedule",
            "description": "일정 및 할 일(Todo)을 등록, 조회, 완료 처리합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "add", "toggle_complete", "get_briefing"],
                        "description": "수행할 작업 (list: 조회, add: 등록, toggle_complete: 완료 토글, get_briefing: 모닝브리핑)"
                    },
                    "title": {"type": "string", "description": "일정/할일 제목"},
                    "start_time": {"type": "string", "description": "시작 날짜/시간 (YYYY-MM-DD 또는 YYYY-MM-DD HH:MM)"},
                    "is_todo": {"type": "boolean", "description": "할 일(Todo) 여부"},
                    "priority": {"type": "integer", "enum": [1, 2, 3], "description": "우선순위 (1: 낮음, 2: 보통, 3: 긴급)"},
                    "item_id": {"type": "integer", "description": "토글/삭제할 항목 ID"}
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "최신 뉴스, 실시간 정보, 웹 검색, 유튜브 영상을 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색 키워드"},
                    "search_type": {
                        "type": "string",
                        "enum": ["general", "news", "youtube", "image"],
                        "description": "검색 유형 (기본값: general)"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# =============================================================================
# 🚀 2. 도구 디스패처 (Tool Dispatcher)
# =============================================================================
class NativeToolEngine:
    """LLM의 도구 호출(Tool Calling) 요청을 라우팅하고 실행하는 중앙 엔진"""

    _registry: Dict[str, Callable] = {}

    @classmethod
    def register_tool(cls, name: str, handler: Callable):
        """커스텀 도구 핸들러 등록"""
        cls._registry[name] = handler

    @classmethod
    async def execute_tool(cls, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        도구 이름과 인자를 받아 실제 로직을 실행하고 결과를 JSON-직렬화 가능한 딕셔너리로 반환
        """
        try:
            # 1. 커스텀 등록 핸들러가 있는 경우 우선 실행
            if tool_name in cls._registry:
                handler = cls._registry[tool_name]
                if asyncio.iscoroutinefunction(handler):
                    return await handler(**arguments)
                return handler(**arguments)

            # 2. 내장 도구 디스패칭
            if tool_name == "system_control":
                return await cls._handle_system_control(arguments)

            elif tool_name == "get_hardware_metrics":
                return await cls._handle_hardware_metrics()

            elif tool_name == "manage_schedule":
                return await cls._handle_manage_schedule(arguments)

            elif tool_name == "web_search":
                return await cls._handle_web_search(arguments)

            else:
                return {"error": f"알 수 없는 도구: '{tool_name}'"}

        except Exception as e:
            return {"error": f"도구 실행 중 오류 발생 ({tool_name}): {str(e)}"}

    # -------------------------------------------------------------------------
    # 🛠️ 개별 내장 도구 핸들러 구현
    # -------------------------------------------------------------------------
    @staticmethod
    async def _handle_system_control(args: Dict[str, Any]) -> Dict[str, Any]:
        """시스템 제어 실행 핸들러"""
        from modules.system_os_controller import WindowsNativeController
        action = args.get("action")

        if action == "set_volume":
            vol = args.get("volume_level", 50)
            WindowsNativeController.set_volume_powershell(vol)
            return {"status": "success", "message": f"볼륨을 {vol}%로 조정했습니다."}

        elif action == "toggle_mute":
            WindowsNativeController.send_key_event(WindowsNativeController.VK_VOLUME_MUTE)
            return {"status": "success", "message": "음소거를 토글했습니다."}

        elif action == "play_pause":
            WindowsNativeController.send_key_event(WindowsNativeController.VK_MEDIA_PLAY_PAUSE)
            return {"status": "success", "message": "미디어 재생/일시정지를 실행했습니다."}

        elif action == "next_track":
            WindowsNativeController.send_key_event(WindowsNativeController.VK_MEDIA_NEXT_TRACK)
            return {"status": "success", "message": "다음 곡으로 넘겼습니다."}

        elif action == "prev_track":
            WindowsNativeController.send_key_event(WindowsNativeController.VK_MEDIA_PREV_TRACK)
            return {"status": "success", "message": "이전 곡으로 돌아갔습니다."}

        elif action == "lock_screen":
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return {"status": "success", "message": "화면을 잠갔습니다."}

        return {"status": "error", "message": f"알 수 없는 시스템 동작: {action}"}

    @staticmethod
    async def _handle_hardware_metrics() -> Dict[str, Any]:
        """하드웨어 상태 핸들러"""
        from modules.system_os_controller import HardwareMonitor
        return HardwareMonitor.get_system_metrics()

    @staticmethod
    async def _handle_manage_schedule(args: Dict[str, Any]) -> Dict[str, Any]:
        """일정 관리 핸들러"""
        from modules.schedule_manager import ScheduleManager, ScheduleCreateRequest
        action = args.get("action")

        if action == "list":
            date_filter = args.get("start_time")
            items = ScheduleManager.get_items(target_date=date_filter)
            return {"status": "success", "items": items}

        elif action == "add":
            req = ScheduleCreateRequest(
                title=args.get("title", "제목 없음"),
                start_time=args.get("start_time", ""),
                is_todo=args.get("is_todo", False),
                priority=args.get("priority", 2)
            )
            return ScheduleManager.add_item(req)

        elif action == "toggle_complete":
            item_id = args.get("item_id")
            if not item_id:
                return {"error": "완료 처리할 item_id가 누락되었습니다."}
            return ScheduleManager.toggle_complete(item_id)

        elif action == "get_briefing":
            summary = ScheduleManager.get_morning_briefing_summary()
            return {"status": "success", "summary": summary}

        return {"status": "error", "message": f"알 수 없는 스케줄 동작: {action}"}

    @staticmethod
    async def _handle_web_search(args: Dict[str, Any]) -> Dict[str, Any]:
        """웹 검색 핸들러 (DuckDuckGo Search 기반 경량 처리)"""
        query = args.get("query", "")
        search_type = args.get("search_type", "general")
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                if search_type == "news":
                    results = list(ddgs.news(query, max_results=5))
                elif search_type == "youtube" or "유튜브" in query:
                    results = list(ddgs.videos(query, max_results=3))
                else:
                    results = list(ddgs.text(query, max_results=5))
                return {"status": "success", "query": query, "results": results}
        except Exception as e:
            return {"status": "error", "message": f"검색 실패: {str(e)}"}
