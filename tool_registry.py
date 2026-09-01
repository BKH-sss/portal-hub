"""
tool_registry.py
------------------------------------------------------------
AI 비서가 사용할 수 있는 모든 도구(Tool / Function Calling)를 등록하고
실행하는 확장 가능한 툴 레지스트리 모듈.

- @tool_registry.register 데코레이터 기반으로 새로운 도구를 1줄로 추가
- 실시간 웹 검색, 파이썬 샌드박스, 주식 금융 분석, 장기 기억 제어 통합
------------------------------------------------------------
"""

import time
import inspect
import asyncio
from dataclasses import dataclass
from typing import Callable, Dict, Any, List, Optional

from smart_search import smart_web_grounding, search_duckduckgo, scrape_web_page
from python_sandbox import run_safe_python


@dataclass
class ToolDefinition:
    name: str
    description: str
    func: Callable
    parameters: Optional[Dict[str, Any]] = None
    is_async: bool = False


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register(self, name: str, description: str, parameters: Optional[Dict[str, Any]] = None):
        """함수를 도구로 등록하는 데코레이터"""
        def decorator(func: Callable):
            is_async = inspect.iscoroutinefunction(func)
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                func=func,
                parameters=parameters,
                is_async=is_async
            )
            return func
        return decorator

    async def execute(self, name: str, **kwargs) -> Dict[str, Any]:
        """등록된 도구 안전 비동기 실행"""
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"존재하지 않는 도구: '{name}'"}

        start_ts = time.time()
        try:
            if tool.is_async:
                result = await tool.func(**kwargs)
            else:
                result = await asyncio.to_thread(tool.func, **kwargs)
            
            elapsed_ms = round((time.time() - start_ts) * 1000, 2)
            return {
                "success": True,
                "tool": name,
                "result": result,
                "elapsed_ms": elapsed_ms
            }
        except Exception as e:
            return {
                "success": False,
                "tool": name,
                "error": str(e),
                "elapsed_ms": round((time.time() - start_ts) * 1000, 2)
            }

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters
            }
            for t in self._tools.values()
        ]

    def _register_default_tools(self):
        # 1. 실시간 웹 검색 도구
        @self.register(name="web_search", description="실시간 인터넷 검색 및 팩트 데이터 추출")
        async def _tool_web_search(query: str, max_sources: int = 4):
            return await smart_web_grounding(query, max_sources=max_sources)

        # 2. 파이썬 샌드박스 연산 도구
        @self.register(name="python_exec", description="안전한 파이썬 코드 실행 및 수학/데이터 계산")
        def _tool_python_exec(code: str):
            return run_safe_python(code)

        # 3. 주식 분석 도구
        @self.register(name="stock_analysis", description="한국/미국 주식 및 ETF 실시간 기술/재무 지표 분석")
        def _tool_stock_analysis(query: str):
            import stock_engine
            return stock_engine.generate_skadi_stock_report(query)

        # 4. 웹페이지 스크래퍼 도구
        @self.register(name="url_scrape", description="지정된 웹 URL 본문 텍스트 고속 추출")
        async def _tool_url_scrape(url: str, max_chars: int = 2500):
            return await scrape_web_page(url, max_chars=max_chars)


tool_registry = ToolRegistry()
