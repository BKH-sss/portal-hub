"""
ollama_utils.py
------------------------------------------------------------
Ollama 로컬 LLM 호출을 위한 공용 유틸리티.
local_fact_checker / local_video_analyzer / autonomous_learner / grounded_writer
가 전부 이 모듈을 공유합니다. brain_server.py와 같은 폴더에 두세요.
------------------------------------------------------------
"""
import json
import base64
import requests
import os

try:
    from config import API_KEYS, OLLAMA_HOST
    GEMINI_API_KEY = API_KEYS.get("GEMINI") or os.environ.get("GEMINI_API_KEY", "")
except Exception:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def gemini_generate(prompt: str, system_instruction: str = "") -> str:
    """구글 Gemini API를 안전하게 호출합니다."""
    if not GEMINI_API_KEY:
        return ""
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        for m in ["gemini-flash-latest", "gemini-3.5-flash", "gemini-2.5-flash"]:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction if system_instruction else None,
                    temperature=0.4
                )
                res = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=config
                )
                if res and res.text:
                    return res.text.strip()
            except Exception as e:
                continue
    except Exception:
        pass
    return ""


def ollama_generate(prompt: str, model: str = "llama3.1", temperature: float = 0.1,
                     num_predict: int = 1024, timeout: int = 120) -> str:
    """Gemini API 우선 시도 후 실패 시 Ollama로 폴백합니다."""
    gemini_res = gemini_generate(prompt)
    if gemini_res:
        return gemini_res

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    try:
        res = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=timeout)
        res.raise_for_status()
        return res.json().get("response", "").strip()
    except Exception as e:
        print(f"[ollama_utils] generate 실패 (model={model}): {e}")
        return ""


def ollama_chat_with_images(prompt: str, image_paths: list[str] | None = None,
                             model: str = "qwen3-vl:8b", temperature: float = 0.2,
                             num_predict: int = 512, timeout: int = 180) -> str:
    """이미지(비디오 프레임 등) + 텍스트 프롬프트를 VLM에 던지고 설명을 받는다."""
    images_b64 = []
    if image_paths:
        for p in image_paths:
            try:
                with open(p, "rb") as f:
                    images_b64.append(base64.b64encode(f.read()).decode("utf-8"))
            except Exception as e:
                print(f"[ollama_utils] 이미지 로드 실패 ({p}): {e}")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": images_b64}],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    try:
        res = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=timeout)
        res.raise_for_status()
        return res.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"[ollama_utils] vision chat 실패 (model={model}): {e}")
        return ""


def safe_json_parse(text: str, default=None):
    """LLM이 뱉은 텍스트에서 JSON 부분만 최대한 안전하게 뽑아 파싱. 실패하면 default 반환."""
    if default is None:
        default = {}
    if not text:
        return default

    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]

    obj_start, obj_end = t.find("{"), t.rfind("}")
    arr_start, arr_end = t.find("["), t.rfind("]")

    # 객체({})와 배열([]) 중 더 바깥쪽에 있는(더 먼저 시작하는) 형태를 우선 시도
    candidates = []
    if obj_start != -1 and obj_end != -1:
        candidates.append(t[obj_start:obj_end + 1])
    if arr_start != -1 and arr_end != -1:
        candidates.append(t[arr_start:arr_end + 1])

    for c in candidates:
        try:
            return json.loads(c)
        except Exception:
            continue
    return default
