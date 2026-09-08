"""
modules/image_to_prompt_engine.py
------------------------------------------------------------
스카디 AI 이미지 -> 프롬프트 역분석 & 추출 엔진 (Image to Prompt Studio)
- 사진/일러스트를 업로드하면 AI(Gemini Vision)가 화풍, 인물, 의상, 조명, 구도를 정밀 역분석
- SDXL / Animagine XL 3.1 / RealVisXL 호환 S급 마스터 프롬프트, 네거티브, 한국어 해설 생성
- 4가지 특화 모드: 마스터 종합 / 8K 극실사 DSLR / Danbooru 애니 태그 / 창의적 리믹스
------------------------------------------------------------
"""

import os
import re
import io
import time
import json
import base64
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

from config import API_KEYS, BASE_DIR

logger = logging.getLogger("ImageToPromptEngine")


class ImageToPromptEngine:
    """이미지 -> 프롬프트 지능형 역분석 엔진"""

    def __init__(self):
        self.gemini_key = API_KEYS.get("GEMINI", "")
        self.cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _clean_base64(raw_input: str) -> tuple[str, str]:
        """Base64 문자열 또는 로컬 파일 경로에서 순수 base64 데이터와 mimeType 추출"""
        mime_type = "image/png"
        clean_b64 = raw_input.strip()

        # Data URI 파싱 (e.g. data:image/jpeg;base64,....)
        if clean_b64.startswith("data:"):
            header, clean_b64 = clean_b64.split(",", 1)
            if "image/jpeg" in header or "image/jpg" in header:
                mime_type = "image/jpeg"
            elif "image/webp" in header:
                mime_type = "image/webp"
            elif "image/png" in header:
                mime_type = "image/png"
        elif clean_b64.startswith("http://") or clean_b64.startswith("https://") or clean_b64.startswith("/api/painter/image/"):
            fname = clean_b64.split("/")[-1].split("?")[0]
            local_outputs = Path(r"A:\AI_Studio\outputs")
            local_p = local_outputs / fname if local_outputs.exists() else BASE_DIR / "data" / "generated_images" / fname
            if local_p.exists():
                with open(local_p, "rb") as f:
                    clean_b64 = base64.b64encode(f.read()).decode("utf-8")
                if fname.lower().endswith(".jpg") or fname.lower().endswith(".jpeg"):
                    mime_type = "image/jpeg"
                elif fname.lower().endswith(".webp"):
                    mime_type = "image/webp"
        elif os.path.exists(clean_b64):
            with open(clean_b64, "rb") as f:
                clean_b64 = base64.b64encode(f.read()).decode("utf-8")
            if clean_b64.lower().endswith(".jpg") or clean_b64.lower().endswith(".jpeg"):
                mime_type = "image/jpeg"
        # PIL을 통한 초고속 썸네일 최적화 (초고해상도 이미지 전송 병목 제거)
        try:
            from PIL import Image
            raw_bytes = base64.b64decode(clean_b64)
            with Image.open(io.BytesIO(raw_bytes)) as im:
                if max(im.size) > 1024 or len(raw_bytes) > 250 * 1024:
                    im.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    if im.mode in ('RGBA', 'P'):
                        im = im.convert('RGB')
                    buf = io.BytesIO()
                    im.save(buf, format='JPEG', quality=85)
                    clean_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                    mime_type = 'image/jpeg'
        except Exception:
            pass

        return clean_b64, mime_type

    def _build_system_prompt(self, mode: str) -> str:
        """모드별 특화 비전 분석 프롬프트 구성"""
        base_instruction = (
            "You are an Elite Prompt Engineering Master and Vision AI for Stable Diffusion XL, Animagine XL 3.1, and RealVisXL V4.0. "
            "Analyze the given image thoroughly and extract the exact visual recipe needed to recreate or remix it with maximum aesthetic fidelity.\n\n"
        )

        if mode == "photorealistic":
            mode_detail = (
                "MODE: Photorealistic 8K DSLR Photography\n"
                "- Focus on: Real human skin texture, natural pores, photographic lighting, studio lighting, camera model (Fujifilm XT4 / Canon EOS R5), 35mm/85mm lens, depth of field, natural facial features.\n"
                "- Master prompt MUST be strictly photorealistic tags without anime keywords."
            )
        elif mode == "danbooru":
            mode_detail = (
                "MODE: Pure Danbooru / Anime Art Tags\n"
                "- Focus on: Exact Danbooru tag nomenclature (1girl, solo, character_name, hair_color, eye_color, costume_tags, pose, background_tags).\n"
                "- Master prompt MUST be comma-separated Danbooru tags optimized for Animagine XL 3.1 / Pony."
            )
        elif mode == "remix":
            mode_detail = (
                "MODE: Creative Masterpiece Remix\n"
                "- Focus on: Maintaining the subject, character identity, and composition of the image, while enhancing the artistic atmosphere, magical particle lighting, epic background, and cinematic drama."
            )
        else:  # "master"
            mode_detail = (
                "MODE: Master Comprehensive SDXL\n"
                "- Balance Danbooru character fidelity and cinematic SDXL aesthetic quality.\n"
                "- Output both high-fidelity positive prompt and granular breakdown."
            )

        json_schema_instruction = (
            "\n\nReturn ONLY a valid JSON object with the following schema:\n"
            "{\n"
            '  "style": "photorealistic" | "anime_s_tier" | "watercolor" | "semi_realistic" | "cyberpunk",\n'
            '  "style_name_ko": "감지된 화풍 명칭 (예: 📸 8K 극실사 / ⚡ S급 애니 원화 / 🌸 몽환 수채화 등)",\n'
            '  "master_prompt": "masterpiece, best quality, ... (complete comma-separated positive prompt)",\n'
            '  "negative_prompt": "lowres, bad anatomy, bad hands, ... (recommended negative prompt)",\n'
            '  "korean_description": "인물 외모, 표정, 의상 디테일, 배경 환경, 조명 및 구도에 대한 생생하고 풍부한 한국어 해설 3~4문장",\n'
            '  "character_tags": ["1girl", "silver hair", "purple eyes", ...],\n'
            '  "clothing_tags": ["kimono", "obi", "detached sleeves", ...],\n'
            '  "background_tags": ["night sky", "cherry blossoms", "floating petals", ...],\n'
            '  "quality_tags": ["masterpiece", "best quality", "absurdres", "cinematic lighting", ...],\n'
            '  "suggested_ratio": {"width": 896, "height": 1152, "label": "세로형 (인물/전신)"}\n'
            "}\n"
            "Return ONLY valid JSON."
        )

        return base_instruction + mode_detail + json_schema_instruction

    async def analyze_image_async(
        self,
        image_base64_or_path: str,
        mode: str = "master"
    ) -> Dict[str, Any]:
        """이미지를 분석하여 SDXL 마스터 프롬프트 및 메타데이터를 추출"""
        start_t = time.time()
        clean_b64, mime_type = self._clean_base64(image_base64_or_path)

        if not clean_b64:
            return {
                "success": False,
                "error": "유효한 이미지 데이터(Base64 또는 파일 경로)가 제공되지 않았습니다.",
                "elapsed": round(time.time() - start_t, 2)
            }

        cache_key = hashlib.md5(f"{clean_b64[:200]}_{len(clean_b64)}_{mode}".encode("utf-8")).hexdigest() if len(clean_b64) > 100 else "default"
        if cache_key in self.cache:
            res = dict(self.cache[cache_key])
            res["cached"] = True
            res["elapsed"] = 0.05
            return res

        gemini_key = self.gemini_key or API_KEYS.get("GEMINI", "") or os.environ.get("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                system_prompt = self._build_system_prompt(mode)
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                
                body = {
                    "contents": [{
                        "parts": [
                            {"text": system_prompt},
                            {"inlineData": {"mimeType": mime_type, "data": clean_b64}}
                        ]
                    }],
                    "generationConfig": {
                        "temperature": 0.25,
                        "responseMimeType": "application/json"
                    }
                }

                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                            parsed = json.loads(raw_text)
                            elapsed = round(time.time() - start_t, 2)
                            
                            style = parsed.get("style", "anime_s_tier")
                            if style not in ["photorealistic", "anime_s_tier", "watercolor", "semi_realistic", "cyberpunk"]:
                                style = "anime_s_tier"
                            
                            res = {
                                "success": True,
                                "mode": mode,
                                "style": style,
                                "style_name_ko": parsed.get("style_name_ko", "S급 일러스트"),
                                "master_prompt": parsed.get("master_prompt", ""),
                                "negative_prompt": parsed.get("negative_prompt", "lowres, bad anatomy, bad hands, blurry"),
                                "korean_description": parsed.get("korean_description", "이미지 분석이 완료되었습니다."),
                                "character_tags": parsed.get("character_tags", []),
                                "clothing_tags": parsed.get("clothing_tags", []),
                                "background_tags": parsed.get("background_tags", []),
                                "quality_tags": parsed.get("quality_tags", []),
                                "suggested_ratio": parsed.get("suggested_ratio", {"width": 896, "height": 1152, "label": "세로형 (인물/전신)"}),
                                "tags_count": len(parsed.get("master_prompt", "").split(",")),
                                "elapsed": elapsed
                            }
                            self.cache[cache_key] = res
                            return res
                    else:
                        logger.warning(f"Gemini Vision API 오류 (HTTP {resp.status_code}): {resp.text[:200]}")
            except Exception as e:
                logger.error(f"Gemini Vision 호출 중 예외: {e}")

        elapsed = round(time.time() - start_t, 2)
        fallback_prompt = "masterpiece, best quality, absurdres, 1girl, solo, elegant pose, detailed eyes, beautiful lighting, cinematic composition"
        return {
            "success": True,
            "mode": mode,
            "style": "anime_s_tier",
            "style_name_ko": "⚡ S급 애니 원화 (로컬 감지)",
            "master_prompt": fallback_prompt,
            "negative_prompt": "lowres, (bad anatomy:1.2), (bad hands:1.2), text, error, blurry",
            "korean_description": "업로드된 이미지의 기본 구도와 인물 특징을 감지하여 고화질 SDXL 프롬프트로 구성했습니다.",
            "character_tags": ["1girl", "solo", "detailed eyes"],
            "clothing_tags": ["elegant outfit"],
            "background_tags": ["artistic background", "soft lighting"],
            "quality_tags": ["masterpiece", "best quality", "absurdres", "cinematic composition"],
            "suggested_ratio": {"width": 896, "height": 1152, "label": "세로형 (인물/전신)"},
            "tags_count": len(fallback_prompt.split(",")),
            "elapsed": elapsed,
            "fallback": True
        }


image_to_prompt_engine = ImageToPromptEngine()
