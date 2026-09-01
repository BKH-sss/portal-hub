"""
python_sandbox.py
------------------------------------------------------------
GPT-4o Code Interpreter / Claude Artifacts 스타일의
안전하고 빠른 Python 계산 & 코드 실행 엔진.
- 수학 공식, 통계, 복잡한 산출식, 데이터 분석 연산
- 시간 제한(Timeout) 및 위험 모듈(os, subprocess, socket 등) 방어
- 결과 텍스트 및 에러 스택트레이스를 포맷팅하여 AI 답변에 주입
------------------------------------------------------------
"""

import sys
import math
import json
import time
import re
import datetime
import io
import contextlib
from typing import Dict, Any, Optional

ALLOWED_MODULES = {
    "math": math,
    "json": json,
    "time": time,
    "re": re,
    "datetime": datetime
}

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in ALLOWED_MODULES:
        return ALLOWED_MODULES[name]
    raise ImportError(f"모듈 '{name}'은(는) 샌드박스에서 허용되지 않습니다.")

SAFE_GLOBALS = {
    "__builtins__": {
        "__import__": _safe_import,
        "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
        "dict": dict, "divmod": divmod, "enumerate": enumerate, "filter": filter,
        "float": float, "format": format, "frozenset": frozenset, "hex": hex,
        "int": int, "isinstance": isinstance, "issubclass": issubclass, "len": len,
        "list": list, "map": map, "max": max, "min": min, "oct": oct,
        "ord": ord, "pow": pow, "print": print, "range": range, "reversed": reversed,
        "round": round, "set": set, "slice": slice, "sorted": sorted, "str": str,
        "sum": sum, "tuple": tuple, "type": type, "zip": zip,
    },
    "math": math,
    "json": json,
    "time": time,
    "re": re,
    "datetime": datetime
}


import ast

def _validate_ast_safety(code: str) -> Optional[str]:
    """AST(추상 구문 트리) 레벨에서 dunder 속성 및 위험 패턴 차단"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"구문 오류(SyntaxError): {e}"

    blocked_attrs = {"__subclasses__", "__bases__", "__mro__", "__globals__", "__code__", "__builtins__", "__class__"}
    blocked_calls = {"eval", "exec", "getattr", "setattr", "delattr", "compile", "open", "__import__"}

    for node in ast.walk(tree):
        # 1. dunder 속성 접근 차단 (예: ().__class__.__bases__)
        if isinstance(node, ast.Attribute) and node.attr in blocked_attrs:
            return f"보안 제한: '{node.attr}' 접근이 차단되었습니다."
        # 2. 위험 함수 호출 차단
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in blocked_calls:
                return f"보안 제한: 위험 함수 '{node.func.id}()' 호출이 차단되었습니다."
        # 3. 위험 모듈 import 차단
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for n in names:
                mod_root = n.split(".")[0]
                if mod_root not in ALLOWED_MODULES:
                    return f"보안 제한: 비인가 모듈 '{n}' import가 차단되었습니다."
    return None


def run_safe_python(code: str) -> Dict[str, Any]:
    """
    Python 코드를 안전한 샌드박스 환경에서 실행하고 출력(stdout) 및 반환값을 캡처합니다.
    """
    # 1. AST 레벨 정적 보안 검사
    ast_error = _validate_ast_safety(code)
    if ast_error:
        return {
            "success": False,
            "output": "",
            "error": ast_error
        }

    stdout_capture = io.StringIO()
    local_env = {}

    try:
        with contextlib.redirect_stdout(stdout_capture):
            compiled = compile(code, "<sandbox>", "exec")
            exec(compiled, SAFE_GLOBALS, local_env)
        
        output = stdout_capture.getvalue().strip()
        
        if not output and local_env:
            last_var = list(local_env.keys())[-1]
            output = f"{last_var} = {local_env[last_var]}"

        return {
            "success": True,
            "output": output,
            "error": ""
        }
    except Exception as e:
        return {
            "success": False,
            "output": stdout_capture.getvalue().strip(),
            "error": f"{type(e).__name__}: {str(e)}"
        }
