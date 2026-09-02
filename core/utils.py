"""
core/utils.py
------------------------------------------------------------
JARVIS 시스템 공용 유틸리티 및 헬퍼 함수 모듈.
- Google GenAI 싱글톤 클라이언트 팩토리
- 지식 파일 mtime 기반 고속 인메모리 캐싱
- 정적 파일 경로 보안 검증 (_safe_static_path)
------------------------------------------------------------
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from config import API_KEYS, MEMORY_DIR

# 1. Google GenAI 싱글톤 클라이언트
_GENAI_CLIENT = None

def get_genai_client():
    """
    Google GenAI Client 인스턴스를 싱글톤으로 안전하게 반환합니다.
    API 키가 없거나 초기화 실패 시 None을 반환합니다.
    """
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        try:
            from google import genai
            gemini_key = API_KEYS.get("GEMINI") or os.environ.get("GEMINI_API_KEY", "")
            if not gemini_key:
                return None
            _GENAI_CLIENT = genai.Client(api_key=gemini_key)
        except Exception as e:
            print(f"[GenAI Client Init Error] {e}")
            return None
    return _GENAI_CLIENT

# 2. 지식 파일 고속 인메모리 캐시 (파일 수정 시간 mtime 기반 갱신)
_KNOWLEDGE_CACHE: Dict[str, Dict[str, Any]] = {}

def get_cached_file_content(file_path: str) -> str:
    """
    지식 마크다운 또는 텍스트 파일을 메모리에 캐싱하여 디스크 I/O를 최소화합니다.
    파일의 수정 시간(mtime)이 변경되었을 때만 다시 읽어옵니다.
    """
    if not file_path or not os.path.exists(file_path):
        return ""
    try:
        mtime = os.path.getmtime(file_path)
        if file_path in _KNOWLEDGE_CACHE and _KNOWLEDGE_CACHE[file_path]["mtime"] == mtime:
            return _KNOWLEDGE_CACHE[file_path]["content"]
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        _KNOWLEDGE_CACHE[file_path] = {"mtime": mtime, "content": content}
        return content
    except Exception:
        return ""

# 3. 정적 파일 보안 검증 (디렉터리 경로 탈출 ../ 방지)
ALLOWED_STATIC_EXTS = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".json", ".txt"}

def safe_static_path(base_dir: str, filename: str) -> Optional[str]:
    """
    경로 탈출(Directory Traversal: ../) 및 절대경로 주입을 완벽히 차단하는 안전한 정적 파일 경로 검증기.
    """
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_STATIC_EXTS:
        return None
    base_dir_real = os.path.realpath(base_dir)
    candidate = os.path.realpath(os.path.join(base_dir, filename))
    if os.path.commonpath([base_dir_real, candidate]) != base_dir_real:
        return None
    if os.path.isfile(candidate):
        return candidate
    return None
