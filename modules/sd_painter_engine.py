"""
modules/sd_painter_engine.py
------------------------------------------------------------
스카디(Skadi) 챗봇 전용 S급 AI 화가(Painter) 렌더링 엔진 모듈.
- Stable Diffusion WebUI Forge / A1111 REST API 연동 (http://127.0.0.1:7860)
- S급 퀄리티 자동 프롬프트 인핸서 (화풍 프리셋 & 네거티브 템플릿)
- ADetailer (얼굴/손 2차 정밀 복원) 및 4x-UltraSharp 초고해상도 업스케일 지원
- 비동기(Async) / 동기(Sync) 렌더링 및 디스코드 업로드 지원
------------------------------------------------------------
"""

import os
import io
import re
import time
import base64
import json
import logging
import asyncio
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import httpx

logger = logging.getLogger("SkadiPainterEngine")

# 기본 경로 및 저장 디렉토리
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
OUTPUT_DIR = Path(r"A:\AI_Studio\outputs") if os.path.exists(r"A:\AI_Studio") else PROJECT_ROOT / "data" / "generated_images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# WebUI API 기본 주소 (.env 또는 기본 127.0.0.1:7860)
SD_API_URL = os.environ.get("SD_WEBUI_URL", "http://127.0.0.1:7860").rstrip("/")

# ------------------------------------------------------------
# 1. S급 마스터 프롬프트 및 화풍 프리셋
# ------------------------------------------------------------
S_TIER_NEGATIVE_PROMPT = (
    "lowres, (bad anatomy:1.2), (bad hands:1.2), (extra fingers:1.2), (missing fingers:1.2), "
    "(fewer digits:1.2), (deformed eyes:1.2), (mutated face:1.2), (cropped:1.2), text, error, "
    "worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, "
    "blurry, poorly drawn, bad proportions, cloned face, skin spots, acnes, skin blemishes, "
    "bad background, ugly, disgusting, nsfw"
)

STYLE_PRESETS = {
    "watercolor": {
        "name": "수채화 / 몽환적 일러스트 (라이덴 쇼군 스타일)",
        "positive_prefix": "masterpiece, best quality, very aesthetic, absurdres, watercolor style, fluid acrylic, vibrant ink wash, soft color blooming, delicate brushstrokes, floating petals, glowing ethereal particle lighting, highly detailed intricate illustration, ",
        "positive_suffix": ", 8k wallpaper, studio lighting, dynamic composition, dramatic rim light",
        "steps": 28,
        "cfg_scale": 6.5,
        "sampler": "Euler a",
    },
    "anime_s_tier": {
        "name": "S급 애니메이션 / 게임 키비주얼 (애니마진/포니)",
        "positive_prefix": "masterpiece, best quality, very aesthetic, absurdres, official art, extremely detailed, vibrant colors, sharp focus, refined lineart, volumetric lighting, ",
        "positive_suffix": ", cinematic lighting, 8k resolution, pixiv daily top 1",
        "steps": 30,
        "cfg_scale": 7.0,
        "sampler": "DPM++ 2M Karras",
    },
    "semi_realistic": {
        "name": "반실사 / AAA급 3D 시네마틱 (언리얼 5 질감)",
        "positive_prefix": "masterpiece, best quality, ultra-detailed 3d cg, octane render, unreal engine 5, ray tracing, subsurface scattering, realistic skin texture, photorealistic eyes, ",
        "positive_suffix": ", 8k resolution, cinematic lighting, dramatic shadow",
        "steps": 32,
        "cfg_scale": 6.0,
        "sampler": "DPM++ SDE Karras",
    },
    "cyberpunk": {
        "name": "사이버펑크 / 네온 SF 스타일",
        "positive_prefix": "masterpiece, best quality, cyberpunk aesthetic, neon glow, holographic interface, reflective wet surface, futuristic city lights, cinematic atmosphere, ",
        "positive_suffix": ", 8k, sharp focus, depth of field",
        "steps": 28,
        "cfg_scale": 7.0,
        "sampler": "Euler a",
    }
}


KO_TO_EN_TAGS = {
    "명일방주": "arknights",
    "스카디": "skadi (arknights)",
    "원신": "genshin impact",
    "라이덴 쇼군": "raiden shogun (genshin impact)",
    "라이덴": "raiden shogun (genshin impact)",
    "나히다": "nahida (genshin impact)",
    "푸리나": "furina (genshin impact)",
    "은발": "silver hair",
    "백발": "white hair",
    "금발": "blonde hair",
    "흑발": "black hair",
    "적발": "red hair",
    "벽발": "blue hair",
    "갈색머리": "brown hair",
    "분홍머리": "pink hair",
    "보라머리": "purple hair",
    "적안": "red eyes",
    "붉은 눈": "red eyes",
    "붉은눈": "red eyes",
    "청안": "blue eyes",
    "푸른 눈": "blue eyes",
    "푸른눈": "blue eyes",
    "녹안": "green eyes",
    "초록 눈": "green eyes",
    "금안": "yellow eyes",
    "고양이귀": "cat ears",
    "여우귀": "fox ears",
    "토끼귀": "rabbit ears",
    "무녀": "miko, shrine maiden",
    "기모노": "kimono",
    "한복": "hanbok",
    "메이드": "maid",
    "교복": "school uniform",
    "정장": "suit",
    "드레스": "dress",
    "갑옷": "armor",
    "수영복": "swimsuit, bikini",
    "바니걸": "bunny suit",
    "소녀": "1girl, solo",
    "소년": "1boy, solo",
    "여성": "1girl, solo",
    "남성": "1boy, solo",
    "마법사": "mage, wizard",
    "기사": "knight",
    "벚꽃": "cherry blossoms, falling petals",
    "밤하늘": "night sky, starry sky",
    "달": "moon",
    "보름달": "full moon",
    "바다": "ocean, beach",
    "해변": "beach, sandy beach",
    "석양": "sunset, golden hour",
    "노을": "sunset, twilight",
    "설원": "snow, snowy landscape",
    "눈": "snow",
    "비": "rain, wet",
    "신사": "shrine",
    "도서관": "library",
    "사이버펑크": "cyberpunk, neon glow",
    "네온": "neon lights",
    "수채화": "watercolor (medium)",
    "수채화풍": "watercolor (medium)",
}


class SkadiPainterEngine:
    """스카디 AI 화가 렌더링 코어 엔진"""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = (api_url or SD_API_URL).rstrip("/")

    @staticmethod
    def translate_korean_prompt(prompt: str) -> str:
        """한국어 키워드를 Danbooru / SDXL 마스터 영문 태그로 스마트 치환 및 보강"""
        translated = prompt
        for ko, en in KO_TO_EN_TAGS.items():
            translated = re.sub(re.escape(ko), en, translated, flags=re.IGNORECASE)
        return translated

    async def check_health(self) -> Dict[str, Any]:
        """WebUI Forge / SD API 서버 가동 여부 및 활성 모델 확인"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{self.api_url}/sdapi/v1/sd-models")
                if r.status_code == 200:
                    models = r.json()
                    model_names = [m.get("model_name") or m.get("title", "") for m in models]
                    return {
                        "online": True,
                        "url": self.api_url,
                        "model_count": len(models),
                        "models": model_names
                    }
        except Exception as e:
            pass
        return {"online": False, "url": self.api_url, "error": "WebUI API 서버에 연결할 수 없습니다. (A:\\AI_Studio\\AI_스튜디오_실행.bat 실행 필요)"}

    def build_s_tier_payload(
        self,
        raw_prompt: str,
        style: str = "watercolor",
        negative_prompt: Optional[str] = None,
        width: int = 896,
        height: int = 1152,
        steps: Optional[int] = None,
        cfg_scale: Optional[float] = None,
        sampler_name: Optional[str] = None,
        seed: int = -1,
        enable_adetailer: bool = True,
        enable_hires: bool = False,
        init_image: Optional[str] = None,
        denoising_strength: Optional[float] = 0.65
    ) -> Dict[str, Any]:
        """S급 화질 옵션과 ADetailer / Hires.fix / img2img가 결합된 REST API 요청 페이로드 조립"""
        preset = STYLE_PRESETS.get(style, STYLE_PRESETS["watercolor"])

        # 1. 한국어 스마트 번역 및 프롬프트 조립
        translated_prompt = self.translate_korean_prompt(raw_prompt.strip())
        final_prompt = f"{preset['positive_prefix']}{translated_prompt}{preset['positive_suffix']}"
        final_neg = f"{S_TIER_NEGATIVE_PROMPT}, {negative_prompt.strip()}" if negative_prompt else S_TIER_NEGATIVE_PROMPT

        actual_steps = steps or preset["steps"]
        actual_cfg = cfg_scale or preset["cfg_scale"]
        actual_sampler = sampler_name or preset["sampler"]

        payload: Dict[str, Any] = {
            "prompt": final_prompt,
            "negative_prompt": final_neg,
            "steps": actual_steps,
            "cfg_scale": actual_cfg,
            "sampler_name": actual_sampler,
            "width": width,
            "height": height,
            "seed": seed,
            "batch_size": 1,
            "n_iter": 1,
            "restore_faces": False,  # ADetailer가 대신 더 정밀하게 복원
            "tiling": False,
        }

        # 1. img2img (참조 사진이 등록된 경우)
        if init_image:
            clean_b64 = init_image
            if "," in clean_b64:
                clean_b64 = clean_b64.split(",", 1)[1]
            payload["init_images"] = [clean_b64]
            payload["denoising_strength"] = float(denoising_strength if denoising_strength is not None else 0.65)
        else:
            # txt2img 일 때 고해상도 복원 (Hires.fix / 4x-UltraSharp)
            if enable_hires:
                payload["enable_hr"] = True
                payload["hr_scale"] = 1.5
                payload["hr_upscaler"] = "4x-UltraSharp"
                payload["hr_second_pass_steps"] = 15
                payload["denoising_strength"] = 0.35

        # 2. ADetailer (얼굴 및 손 2차 정밀 복원기)
        if enable_adetailer:
            payload["alwayson_scripts"] = {
                "ADetailer": {
                    "args": [
                        True,  # 활성화
                        False,
                        {
                            "ad_model": "face_yolov8n.pt",
                            "ad_prompt": "masterpiece, ultra-detailed face, expressive eyes, perfect anatomy",
                            "ad_negative_prompt": "ugly, deformed face, bad eyes",
                            "ad_confidence": 0.3,
                            "ad_mask_blur": 4,
                            "ad_denoising_strength": 0.35,
                        },
                        {
                            "ad_model": "hand_yolov8n.pt",
                            "ad_prompt": "masterpiece, ultra-detailed hands, five fingers",
                            "ad_negative_prompt": "bad hands, extra fingers, missing fingers",
                            "ad_confidence": 0.3,
                            "ad_mask_blur": 4,
                            "ad_denoising_strength": 0.35,
                        }
                    ]
                }
            }

        return payload

    async def generate_image_async(
        self,
        prompt: str,
        style: str = "watercolor",
        negative_prompt: Optional[str] = None,
        width: int = 896,
        height: int = 1152,
        steps: Optional[int] = None,
        cfg_scale: Optional[float] = None,
        seed: int = -1,
        enable_adetailer: bool = True,
        enable_hires: bool = False,
        init_image: Optional[str] = None,
        denoising_strength: Optional[float] = 0.65
    ) -> Dict[str, Any]:
        """비동기 S급 이미지 렌더링 실행 (txt2img / img2img 자동 전환) 및 이미지 파일 저장"""
        start_t = time.time()

        # 1. 서버 온라인 체크
        health = await self.check_health()
        if not health["online"]:
            return {
                "success": False,
                "error": "🎨 AI 스튜디오(WebUI Forge)가 실행되어 있지 않습니다. 로컬에서 'A:\\AI_Studio\\AI_스튜디오_실행.bat'을 먼저 실행해주세요.",
                "elapsed": round(time.time() - start_t, 2)
            }

        # 2. 페이로드 생성
        payload = self.build_s_tier_payload(
            raw_prompt=prompt,
            style=style,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            enable_adetailer=enable_adetailer,
            enable_hires=enable_hires,
            init_image=init_image,
            denoising_strength=denoising_strength
        )

        # 3. WebUI API 호출 (img2img vs txt2img 엔드포인트 자동 분기)
        endpoint = "/sdapi/v1/img2img" if init_image else "/sdapi/v1/txt2img"
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                r = await client.post(f"{self.api_url}{endpoint}", json=payload)
                if r.status_code != 200:
                    return {
                        "success": False,
                        "error": f"WebUI 렌더링 오류 (HTTP {r.status_code}): {r.text[:200]}",
                        "elapsed": round(time.time() - start_t, 2)
                    }

                result_json = r.json()
                images = result_json.get("images", [])
                if not images:
                    return {
                        "success": False,
                        "error": "생성된 이미지 데이터를 수신하지 못했습니다.",
                        "elapsed": round(time.time() - start_t, 2)
                    }

                # 4. 첫 번째 이미지 디코딩 및 파일 저장
                b64_data = images[0]
                if "," in b64_data:
                    b64_data = b64_data.split(",", 1)[1]
                img_bytes = base64.b64decode(b64_data)

                # 파일명 생성
                now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_tag = re.sub(r'[^a-zA-Z0-9]', '_', prompt[:20]).strip('_')
                file_name = f"skadi_{now_str}_{safe_tag}.png"
                file_path = OUTPUT_DIR / file_name

                with open(file_path, "wb") as f:
                    f.write(img_bytes)

                info_str = result_json.get("info", "{}")
                info_data = {}
                try:
                    info_data = json.loads(info_str)
                except Exception:
                    pass

                elapsed = round(time.time() - start_t, 2)
                logger.info(f"✨ [스카디 화가] S급 일러스트 렌더링 완료 ({elapsed}초) -> {file_path}")

                return {
                    "success": True,
                    "file_path": str(file_path),
                    "file_name": file_name,
                    "image_bytes": img_bytes,
                    "prompt": prompt,
                    "style": style,
                    "seed": info_data.get("seed", seed),
                    "elapsed": elapsed,
                    "width": width,
                    "height": height
                }

        except Exception as e:
            logger.error(f"렌더링 통신 예외: {e}")
            return {
                "success": False,
                "error": f"이미지 렌더링 중 오류 발생: {e}",
                "elapsed": round(time.time() - start_t, 2)
            }


# 싱글톤 인스턴스
painter_engine = SkadiPainterEngine()
