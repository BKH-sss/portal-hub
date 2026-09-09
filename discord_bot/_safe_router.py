"""
modules/_safe_router.py
=============================================================================
Universal Safe Router and Dependency Fallback Provider
=============================================================================
"""

import sys
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("SafeRouter")

# 1. FastAPI
try:
    from fastapi import APIRouter as _RealAPIRouter, HTTPException as _RealHTTPException, Response as _RealResponse, Request as _RealRequest, WebSocket as _RealWebSocket, WebSocketDisconnect as _RealWebSocketDisconnect, FastAPI as _RealFastAPI
    try:
        from fastapi.responses import HTMLResponse as _RealHTMLResponse, FileResponse as _RealFileResponse, JSONResponse as _RealJSONResponse
    except ImportError:
        _RealHTMLResponse = _RealResponse
        _RealFileResponse = _RealResponse
        _RealJSONResponse = _RealResponse
    try:
        from fastapi.middleware.cors import CORSMiddleware as _RealCORSMiddleware
    except ImportError:
        _RealCORSMiddleware = None
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    _RealAPIRouter = None
    _RealHTTPException = None
    _RealResponse = None
    _RealRequest = None
    _RealHTMLResponse = None
    _RealFileResponse = None
    _RealJSONResponse = None
    _RealWebSocket = None
    _RealWebSocketDisconnect = None
    _RealFastAPI = None
    _RealCORSMiddleware = None

# 2. Pydantic
try:
    from pydantic import BaseModel as _RealBaseModel, Field as _RealField
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False
    _RealBaseModel = None
    _RealField = None


# Safe Dummy Classes
class SafeDummyRouter:
    """Dummy router that safely absorbs all decorators as no-op functions"""
    def __init__(self, *args, **kwargs):
        self.prefix = kwargs.get("prefix", "")
        self.tags = kwargs.get("tags", [])
        self.routes = []

    def _decorator(self, *args, **kwargs) -> Callable:
        return lambda func: func

    def get(self, *args, **kwargs): return self._decorator(*args, **kwargs)
    def post(self, *args, **kwargs): return self._decorator(*args, **kwargs)
    def put(self, *args, **kwargs): return self._decorator(*args, **kwargs)
    def delete(self, *args, **kwargs): return self._decorator(*args, **kwargs)
    def patch(self, *args, **kwargs): return self._decorator(*args, **kwargs)
    def options(self, *args, **kwargs): return self._decorator(*args, **kwargs)
    def head(self, *args, **kwargs): return self._decorator(*args, **kwargs)
    def api_route(self, *args, **kwargs): return self._decorator(*args, **kwargs)
    def websocket(self, *args, **kwargs): return self._decorator(*args, **kwargs)

    def include_router(self, *args, **kwargs): pass
    def add_api_route(self, *args, **kwargs): pass


class SafeDummyHTTPException(Exception):
    def __init__(self, status_code: int = 400, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class SafeDummyBaseModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def dict(self, *args, **kwargs) -> Dict[str, Any]:
        return self.__dict__.copy()

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:
        return self.__dict__.copy()


def safe_dummy_field(default: Any = None, **kwargs) -> Any:
    if default is Ellipsis:
        return None
    return default


class SafeDummyResponse:
    def __init__(self, content: Any = None, status_code: int = 200, **kwargs):
        self.content = content
        self.status_code = status_code


class SafeDummyRequest:
    def __init__(self, *args, **kwargs):
        pass


class SafeDummyWebSocket:
    async def accept(self): pass
    async def send_text(self, text: str): pass
    async def send_json(self, data: Any): pass
    async def receive_text(self) -> str: return ""
    async def close(self, code: int = 1000): pass


class SafeDummyWebSocketDisconnect(Exception):
    pass


class SafeDummyFastAPI:
    def __init__(self, *args, **kwargs): pass
    def include_router(self, *args, **kwargs): pass
    def add_middleware(self, *args, **kwargs): pass
    def mount(self, *args, **kwargs): pass
    def get(self, *args, **kwargs): return lambda f: f
    def post(self, *args, **kwargs): return lambda f: f
    def put(self, *args, **kwargs): return lambda f: f
    def delete(self, *args, **kwargs): return lambda f: f


class SafeDummyCORSMiddleware:
    pass


HTTPException = _RealHTTPException if HAS_FASTAPI else SafeDummyHTTPException
Response = _RealResponse if HAS_FASTAPI else SafeDummyResponse
HTMLResponse = _RealHTMLResponse if HAS_FASTAPI else SafeDummyResponse
FileResponse = _RealFileResponse if HAS_FASTAPI else SafeDummyResponse
JSONResponse = _RealJSONResponse if HAS_FASTAPI else SafeDummyResponse
Request = _RealRequest if HAS_FASTAPI else SafeDummyRequest
WebSocket = _RealWebSocket if HAS_FASTAPI else SafeDummyWebSocket
WebSocketDisconnect = _RealWebSocketDisconnect if HAS_FASTAPI else SafeDummyWebSocketDisconnect
FastAPI = _RealFastAPI if HAS_FASTAPI else SafeDummyFastAPI
CORSMiddleware = _RealCORSMiddleware if HAS_FASTAPI else SafeDummyCORSMiddleware
BaseModel = _RealBaseModel if HAS_PYDANTIC else SafeDummyBaseModel
Field = _RealField if HAS_PYDANTIC else safe_dummy_field


def get_safe_router(prefix: str = "", tags: Optional[List[str]] = None, **kwargs) -> Any:
    if HAS_FASTAPI and _RealAPIRouter is not None:
        try:
            return _RealAPIRouter(prefix=prefix, tags=tags or [], **kwargs)
        except Exception as e:
            logger.debug(f"APIRouter fallback to dummy: {e}")
            return SafeDummyRouter(prefix=prefix, tags=tags or [], **kwargs)
    return SafeDummyRouter(prefix=prefix, tags=tags or [], **kwargs)


APIRouter = _RealAPIRouter if HAS_FASTAPI else SafeDummyRouter

__all__ = [
    "HAS_FASTAPI",
    "HAS_PYDANTIC",
    "get_safe_router",
    "APIRouter",
    "SafeDummyRouter",
    "HTTPException",
    "BaseModel",
    "Field",
    "Response",
    "HTMLResponse",
    "FileResponse",
    "JSONResponse",
    "Request",
    "WebSocket",
    "WebSocketDisconnect",
    "FastAPI",
    "CORSMiddleware",
]
