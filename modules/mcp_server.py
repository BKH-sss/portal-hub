"""
mcp_server.py
=============================================================================
🔌 JARVIS 표준 MCP (Model Context Protocol) 서버 모듈
=============================================================================
- 기능:
    1. Anthropic MCP 표준 규격(JSON-RPC 2.0) 완벽 호환
    2. Claude Desktop, VS Code, Cursor, Antigravity 등 외부 IDE와 도구 공유
    3. JARVIS의 핵심 기능(하드웨어 진단, 볼륨/OS 제어, 일정, 검색 등)을 MCP Tool로 노출
    4. Stdio 모드 (터미널 기반) 및 HTTP SSE 모드 동시 지원
=============================================================================
"""

import sys
import json
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
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

# 상위 모듈 참조 설정
sys.path.append(str(Path(__file__).parent.parent))
from modules.native_tool_engine import JARVIS_TOOLS_SCHEMA, NativeToolEngine

# =============================================================================
# 🚀 1. FastAPI APIRouter 생성 (HTTP/SSE 연동용)
# =============================================================================
router = APIRouter(prefix="/mcp", tags=["Model Context Protocol Server"])


# =============================================================================
# 📦 2. MCP JSON-RPC 메시지 처리기
# =============================================================================
class MCPServer:
    """Model Context Protocol (JSON-RPC 2.0) 표준 서버 구현체"""

    SERVER_NAME = "jarvis-mcp-server"
    SERVER_VERSION = "1.0.0"

    @classmethod
    def get_tools_list(cls) -> List[Dict[str, Any]]:
        """MCP 형식에 맞춘 도구 정의 목록 반환"""
        mcp_tools = []
        for item in JARVIS_TOOLS_SCHEMA:
            fn = item.get("function", {})
            mcp_tools.append({
                "name": fn.get("name"),
                "description": fn.get("description"),
                "inputSchema": fn.get("parameters", {})
            })
        return mcp_tools

    @classmethod
    async def process_json_rpc(cls, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """JSON-RPC 2.0 프로토콜 메시지 해석 및 처리"""
        msg_id = message.get("id")
        method = message.get("method")
        params = message.get("params", {})

        # 1. 초기화 핸드셰이크 (initialize)
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": cls.SERVER_NAME,
                        "version": cls.SERVER_VERSION
                    }
                }
            }

        # 2. 초기화 완료 알림 (notifications/initialized)
        elif method == "notifications/initialized":
            return None  # 알림(Notification)은 응답 불필요

        # 3. 도구 목록 요청 (tools/list)
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": cls.get_tools_list()
                }
            }

        # 4. 도구 호출 실행 (tools/call)
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            # NativeToolEngine을 통해 도구 실행
            result = await NativeToolEngine.execute_tool(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ],
                    "isError": "error" in result
                }
            }

        # 5. 미지원 메소드 에러 처리
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: '{method}'"
                }
            }


# =============================================================================
# 🌐 3. FastAPI HTTP 엔드포인트
# =============================================================================

@router.post("/rpc", summary="MCP JSON-RPC HTTP 엔드포인트")
async def handle_mcp_http(request: Request):
    """외부 HTTP 클라이언트로부터 MCP JSON-RPC 요청을 수신하여 처리합니다."""
    try:
        body = await request.json()
        response = await MCPServer.process_json_rpc(body)
        if response:
            return JSONResponse(content=response)
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse(status_code=400, content={
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
        })


# =============================================================================
# 💻 4. Stdio 실행 진입점 (Claude Desktop / Cursor 직접 연동용)
# =============================================================================
async def run_stdio_server():
    """표준 입출력(stdin/stdout)을 사용하는 MCP Stdio 서버 루프"""
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break
        raw_text = line.decode('utf-8').strip()
        if not raw_text:
            continue
        try:
            req_json = json.loads(raw_text)
            res_json = await MCPServer.process_json_rpc(req_json)
            if res_json:
                sys.stdout.write(json.dumps(res_json, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": str(e)}
            }
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    # 터미널에서 'python mcp_server.py'로 직접 실행 시 Stdio 모드로 동작
    asyncio.run(run_stdio_server())
