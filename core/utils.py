"""
core/utils.py
==============================================================================
JARVIS 시스템 공용 유틸리티 및 헬퍼 함수 모듈
==============================================================================
이 모듈은 여러 라우터와 엔진에서 자주 사용되는 공통 작업들을 모아놓은 유틸리티입니다:
  1) Google GenAI 클라이언트 싱글톤 인스턴스 제공
  2) 대용량 마크다운 지식 파일 mtime 기반 고속 인메모리 캐싱 (디스크 I/O 절약)
  3) 상위 디렉터리 탈출(../) 공격을 차단하는 정적 파일 보안 경로 검증기
==============================================================================
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from config import API_KEYS, MEMORY_DIR

# ==============================================================================
# 1. Google GenAI 싱글톤 클라이언트 팩토리
# ==============================================================================
_GENAI_CLIENT = None

def get_genai_client():
    """
    Google GenAI SDK (google.genai) 클라이언트를 싱글톤(Singleton)으로 생성하여 반환합니다.
    - .env에서 로드된 GEMINI_API_KEY를 자동으로 바인딩합니다.
    - 매번 새 클라이언트를 만들지 않고 기존 연결 객체를 재사용하여 통신 오버헤드를 줄입니다.
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

# ==============================================================================
# 2. 지식 파일 고속 인메모리 캐시 (mtime 기반)
# ==============================================================================
_KNOWLEDGE_CACHE: Dict[str, Dict[str, Any]] = {}

def get_cached_file_content(file_path: str) -> str:
    """
    LoL_Combined_Knowledge.md, MapleStory_Combined_Knowledge.md 등 대용량 게임 지식 파일을
    메모리에 캐싱하여 대화할 때마다 디스크를 반복해서 읽는 병목 현상을 방지합니다.
    - 파일의 최종 수정 시간(mtime)이 변경되었을 때만 디스크에서 새로 읽어옵니다.
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

# ==============================================================================
# 3. 정적 파일 경로 보안 검증기 (Directory Traversal 방지)
# ==============================================================================
ALLOWED_STATIC_EXTS = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".json", ".txt"}

def safe_static_path(base_dir: str, filename: str) -> Optional[str]:
    """
    웹 브라우저의 파일 요청 시 악의적인 상위 폴더 접근(../) 및 시스템 파일 탈취 공격을 방어합니다.
    - 슬래시(/, \\)나 .. 가 포함된 파일명을 원천 차단합니다.
    - 허용된 안전한 확장자(.html, .css, .js, .png 등)만 통과시킵니다.
    - 실제 경로(realpath)가 지정된 base_dir 내부에 존재하는지 이중 검증합니다.
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
