"""
config.example.py
------------------------------------------------------------
JARVIS / Multi-Agent Assistant 중앙 설정 템플릿.
실제 배포 시 환경 변수(Environment Variables)로 API 키를 주입하세요.
------------------------------------------------------------
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR

MEMORY_DIR = BASE_DIR / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# 환경 변수 기반 API 키 관리 (GitHub에 노출되지 않음)
API_KEYS = {
    "GEMINI": os.environ.get("GEMINI_API_KEY", ""),
    "OPENAI": os.environ.get("OPENAI_API_KEY", ""),
    "ANTHROPIC": os.environ.get("ANTHROPIC_API_KEY", ""),
    "GROQ": os.environ.get("GROQ_API_KEY", ""),
    "DEEPSEEK": os.environ.get("DEEPSEEK_API_KEY", ""),
    "DISCORD": os.environ.get("DISCORD_BOT_TOKEN", "")
}

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
GPT_SOVITS_URL = os.environ.get("GPT_SOVITS_URL", "http://127.0.0.1:9880")

MODEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "provider": "gemini",
        "models": ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-pro"],
        "display_name": "Google Gemini 2.5/3.5",
        "supports_grounding": True,
        "supports_vision": True,
    },
    "openai": {
        "provider": "openai",
        "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
        "display_name": "OpenAI GPT-4o / o3-mini",
        "supports_grounding": False,
        "supports_vision": True,
    },
    "claude": {
        "provider": "claude",
        "models": ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022"],
        "display_name": "Anthropic Claude 3.7 Sonnet",
        "supports_grounding": False,
        "supports_vision": True,
    },
    "ollama": {
        "provider": "ollama",
        "models": ["qwen2.5:14b", "llama3.1:8b"],
        "display_name": "Local Ollama (Offline Brain)",
        "supports_grounding": False,
        "supports_vision": False,
    }
}

DEFAULT_GENERATION_PARAMS = {
    "temperature": 0.5,
    "top_p": 0.9,
    "max_tokens": 4096,
    "system_instruction": "너는 마스터를 지키는 스카디야. 100% 한국어로 대답해."
}
