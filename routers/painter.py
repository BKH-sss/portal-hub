"""
routers/painter.py
------------------------------------------------------------
스카디 AI 화가 (AI Painter) REST API 라우터
- Stable Diffusion WebUI Forge 연동 및 렌더링 요청
- 갤러리 조회 및 생성 이미지 서빙
------------------------------------------------------------
"""

import os
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from modules.sd_painter_engine import SkadiPainterEngine, OUTPUT_DIR, STYLE_PRESETS
from modules.prompt_crafter import SkadiPromptCrafter

router = APIRouter(prefix="/api/painter", tags=["painter"])
engine = SkadiPainterEngine()


class EnhancePromptRequest(BaseModel):
    prompt: Optional[str] = ""
    style: str = "watercolor"
    mode: str = "expand"  # "expand" or "random_idea"


@router.post("/enhance-prompt")
async def enhance_prompt_api(req: EnhancePromptRequest):
    """AI 프롬프트 자동 마법 생성 / 확장 API"""
    res = await SkadiPromptCrafter.enhance_prompt_async(
        user_text=req.prompt or "",
        style=req.style,
        mode=req.mode
    )
    return res


class GenerateRequest(BaseModel):
    prompt: str
    style: str = "watercolor"
    negative_prompt: Optional[str] = None
    width: int = 896
    height: int = 1152
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    seed: int = -1
    enable_adetailer: bool = True
    enable_hires: bool = False
    init_image: Optional[str] = None
    denoising_strength: Optional[float] = 0.65


@router.get("/status")
async def get_painter_status():
    """WebUI Forge 연결 상태 및 모델 정보 확인"""
    health = await engine.check_health()
    return {
        "status": "online" if health.get("online") else "offline",
        "health": health,
        "presets": {k: v["name"] for k, v in STYLE_PRESETS.items()},
        "output_dir": str(OUTPUT_DIR)
    }


@router.post("/generate")
async def generate_artwork(req: GenerateRequest):
    """S급 AI 이미지 렌더링 요청 (txt2img & img2img 지원)"""
    res = await engine.generate_image_async(
        prompt=req.prompt,
        style=req.style,
        negative_prompt=req.negative_prompt,
        width=req.width,
        height=req.height,
        steps=req.steps,
        cfg_scale=req.cfg_scale,
        seed=req.seed,
        enable_adetailer=req.enable_adetailer,
        enable_hires=req.enable_hires,
        init_image=req.init_image,
        denoising_strength=req.denoising_strength
    )
    if res.get("success"):
        file_name = res.get("file_name")
        res["image_url"] = f"/api/painter/image/{file_name}"
        # JSON 직렬화를 위해 binary image_bytes 필드 제거
        res.pop("image_bytes", None)
    return res


@router.get("/gallery")
async def get_gallery(limit: int = 40):
    """최근 생성된 이미지 목록 조회"""
    if not OUTPUT_DIR.exists():
        return {"images": []}

    files = sorted(
        OUTPUT_DIR.glob("*.png"),
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )

    gallery = []
    for f in files[:limit]:
        stat = f.stat()
        gallery.append({
            "file_name": f.name,
            "url": f"/api/painter/image/{f.name}",
            "size_kb": round(stat.st_size / 1024, 1),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
        })

    return {"count": len(gallery), "images": gallery}


@router.get("/image/{file_name}")
async def get_image_file(file_name: str):
    """생성된 이미지 파일 반환"""
    # 보안: 파일명에 디렉토리 트래버셜 방지
    safe_name = os.path.basename(file_name)
    file_path = OUTPUT_DIR / safe_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")

    return FileResponse(
        path=str(file_path),
        media_type="image/png",
        filename=safe_name
    )
