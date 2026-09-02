# 🚀 JARVIS / SKADI 확장 모듈 가이드 (Modular Extensions)

새롭게 추가된 핵심 모듈들은 각각 **단일 파일로 완결되는 독립적인 구조**로 작성되었으며, 전체 코드에 상세한 한국어 주석이 포함되어 있습니다.

---

## 📂 모듈별 구성 및 역할

| 모듈 파일명 | 주요 역할 | 제공 API 엔드포인트 |
|---|---|---|
| `modules/system_os_controller.py` | 💻 CPU, RAM, GPU(4080 Super), VRAM 실시간 진단 및 Windows 마스터 볼륨/미디어/프로세스 제어 | `/api/system/*` |
| `modules/schedule_manager.py` | 📅 로컬 SQLite 기반 일정/할 일(Todo) 관리 및 24/7 모닝 브리핑 요약기 | `/api/schedule/*` |
| `modules/native_tool_engine.py` | 🛠️ 문자열 태그를 대체하는 OpenAI/Gemini/Claude/Ollama 표준 Function Calling 엔진 | 통합 Tool Dispatcher |
| `modules/mcp_server.py` | 🔌 Anthropic MCP (Model Context Protocol) 표준 JSON-RPC 서버 (VS Code, Claude Desktop, Cursor 연동) | `/mcp/rpc` 및 Stdio 모드 |
| `modules/admin.html` | 📊 사이버틱 JARVIS HUD 테마의 실시간 하드웨어 & 에이전트 관측 대시보드 UI | `/admin` |
| `modules/jarvis_extension_router.py` | 🌟 위 모든 모듈을 하나로 묶어 `brain_server.py`에 원클릭 마운트하는 통합 라우터 | All Router Wrapper |

---

## 🔌 기존 `brain_server.py`에 연동하는 방법 (단 2줄)

기존 `brain_server.py` 상단 및 라우터 마운트 영역에 아래 2줄만 추가하면 모든 기능이 즉시 활성화됩니다:

```python
# 1. 상단 임포트
from modules.jarvis_extension_router import extension_router

# 2. 라우터 마운트 (기존 app 생성부 아래)
app.include_router(extension_router)
```

---

## 🖥️ 단독(Standalone) 테스트 실행 방법

FastAPI 메인 서버 없이 신규 모듈들만 먼저 테스트하고 싶을 때:

```bash
python modules/jarvis_extension_router.py
```
* **관리자 대시보드:** [http://localhost:8000/admin](http://localhost:8000/admin)
* **Swagger API 문서:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🤖 MCP (Model Context Protocol) 외부 연동 방법 (Claude Desktop / Cursor)

`claude_desktop_config.json`에 아래 설정을 추가하면 Claude Desktop에서 JARVIS의 PC 제어 및 일정 기능을 직접 호출할 수 있습니다:

```json
{
  "mcpServers": {
    "jarvis-assistant": {
      "command": "python",
      "args": ["C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/mcp_server.py"]
    }
  }
}
```
