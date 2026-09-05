"""
modules/prompt_crafter.py
------------------------------------------------------------
스카디 AI 화가 전용 지능형 프롬프트 마법 생성기 (Prompt Crafter & Expander)
- 한국어 자연어/단어 ➔ SDXL & Animagine XL 3.1 특화 S급 Danbooru 영문 태그로 자동 확장
- LLM (Gemini / Ollama) 초지능 확장 + 0ms 시맨틱 지식베이스 무중단 듀얼 엔진
------------------------------------------------------------
"""
import os
import re
import json
import random
import asyncio
from typing import Dict, Any, List, Optional
import httpx

# 한국어 ➔ Danbooru 마스터 태그 지식 베이스
SEMANTIC_TAG_DICT = {
    # 캐릭터
    "스카디": {
        "tags": ["skadi (arknights)", "silver hair", "long hair", "red eyes", "ahoge", "stoic expression", "beautiful face"],
        "desc": "명일방주 스카디"
    },
    "글래디아": {
        "tags": ["gladiia (arknights)", "white hair", "red eyes", "high ponytail", "tall female", "abyssal hunter"],
        "desc": "명일방주 글래디아"
    },
    "스펙터": {
        "tags": ["specter (arknights)", "silver hair", "red eyes", "nun", "habit", "insane smile"],
        "desc": "명일방주 스펙터"
    },
    "라이덴": {
        "tags": ["raiden shogun (genshin impact)", "purple hair", "long braided hair", "purple eyes", "hair ornament", "kimono"],
        "desc": "원신 라이덴 쇼군"
    },
    "라이덴 쇼군": {
        "tags": ["raiden shogun (genshin impact)", "purple hair", "long braided hair", "purple eyes", "hair ornament", "kimono"],
        "desc": "원신 라이덴 쇼군"
    },
    "나히다": {
        "tags": ["nahida (genshin impact)", "white hair", "side ponytail", "green eyes", "elf ears", "dress"],
        "desc": "원신 나히다"
    },
    "푸리나": {
        "tags": ["furina (genshin impact)", "white hair", "streaked hair", "blue eyes", "top hat", "aristocrat"],
        "desc": "원신 푸리나"
    },
    # 의상
    "수영복": ["swimsuit", "bikini", "wet skin", "water drops"],
    "비키니": ["bikini", "two-piece swimsuit", "navel", "collarbone"],
    "기모노": ["kimono", "wide sleeves", "obi", "floral print"],
    "한복": ["hanbok", "jeogori", "chima", "traditional korean clothing", "ribbon"],
    "메이드": ["maid uniform", "maid apron", "maid headdress", "white frills"],
    "교복": ["school uniform", "serafuku", "pleated skirt", "necktie"],
    "정장": ["suit", "black jacket", "white shirt", "necktie", "formal wear"],
    "드레스": ["elegant dress", "ballgown", "flowing fabric", "lacing", "frills"],
    "갑옷": ["armor", "breastplate", "gauntlets", "knight armor", "silver armor"],
    "무녀": ["miko", "shrine maiden", "white kosode", "red hakama"],
    "바니걸": ["bunny suit", "bunny ears", "fake animal ears", "leotard", "bow tie"],
    "후드": ["hoodie", "hood down", "oversized hoodie", "casual clothes"],
    "산타": ["santa costume", "santa hat", "red dress", "white fur trim"],
    # 헤어 / 외모
    "은발": ["silver hair", "long flowing silver hair"],
    "백발": ["white hair", "glowing white hair"],
    "흑발": ["black hair", "silky black hair"],
    "금발": ["blonde hair", "golden hair"],
    "적발": ["red hair", "crimson hair"],
    "청발": ["blue hair", "azure hair"],
    "갈색머리": ["brown hair", "chestnut hair"],
    "분홍머리": ["pink hair", "cherry blossom hair"],
    "보라머리": ["purple hair", "violet hair"],
    "적안": ["red eyes", "crimson glowing eyes"],
    "청안": ["blue eyes", "crystal blue eyes", "sparkling eyes"],
    "녹안": ["green eyes", "emerald eyes"],
    "금안": ["yellow eyes", "golden amber eyes"],
    "벽안": ["cyan eyes", "sapphire eyes"],
    "자안": ["purple eyes", "amethyst eyes"],
    "고양이귀": ["cat ears", "animal ear fluff"],
    "여우귀": ["fox ears", "fox tail", "fluffy tail"],
    "토끼귀": ["rabbit ears", "fluffy ears"],
    # 배경 / 환경
    "벚꽃": ["cherry blossoms", "falling petals", "blooming sakura trees", "pink flowers"],
    "밤하늘": ["night sky", "starry sky", "milky way", "constellations", "deep night"],
    "보름달": ["full moon", "glowing giant moon", "moonlight"],
    "달": ["crescent moon", "moonlight illumination"],
    "바다": ["ocean", "waves", "clear blue water", "sparkling sea"],
    "해변": ["beach", "sandy beach", "seashore", "coastal"],
    "석양": ["sunset", "golden hour", "orange glow", "twilight sky", "dramatic lighting"],
    "노을": ["sunset", "twilight", "dusk", "gradient sky", "warm lighting"],
    "설원": ["snowy field", "snowscape", "falling snowflakes", "winter landscape"],
    "눈": ["falling snow", "snow covered ground", "frost"],
    "비": ["rain", "wet asphalt", "puddles with reflection", "water splashes", "rainy day"],
    "신사": ["japanese shrine", "torii gate", "stone lanterns", "sacred grove"],
    "도서관": ["grand library", "bookshelves", "floating magical books", "ancient library"],
    "숲": ["enchanted forest", "sunlight filtering through trees", "moss", "lush foliage"],
    "사이버펑크": ["cyberpunk city", "neon lights", "holographic signs", "futuristic skyscraper", "flying vehicles", "cyber glow"],
    "우주": ["deep space", "nebula", "colorful galaxy", "space station", "floating stardust"],
    "성": ["fantasy castle", "gothic palace", "stained glass windows", "chandeliers"],
    "카페": ["cozy cafe", "wooden interior", "warm light", "coffee cup on table"],
    "정원": ["flower garden", "rose garden", "fountain", "blooming flora"],
    # 분위기 / 구도
    "미소": ["gentle smile", "looking at viewer", "blush"],
    "우아함": ["elegant pose", "graceful", "poetic atmosphere"],
    "신비로운": ["mysterious aura", "magical glow", "ethereal atmosphere", "floating light particles"],
    "역동적인": ["dynamic angle", "dynamic pose", "wind blowing", "action shot"],
    "감성적인": ["moody lighting", "cinematic shot", "emotional atmosphere", "soft focus"]
}

RANDOM_INSPIRATIONS = [
    {
        "title": "🌸 밤하늘의 벚꽃 무녀 스카디",
        "prompt": "1girl, solo, skadi (arknights), red eyes, long silver hair, ornate miko outfit, white and red shrine maiden clothes, standing under ancient blooming cherry blossom tree, falling pink petals, night sky, giant glowing full moon, stone lantern, gentle moonlight, soft wind blowing, looking at viewer, cinematic lighting, masterpiece, absurdres"
    },
    {
        "title": "🌅 황금빛 석양 해변의 소녀",
        "prompt": "1girl, solo, silver hair, glowing blue eyes, stylish black bikini, wet skin, standing on sandy beach, ocean tide splashing at feet, golden hour sunset, vibrant orange and purple sky, sun ray reflection on water, gentle breeze, holding straw hat, radiant smile, masterpiece, ultra-detailed"
    },
    {
        "title": "🌃 비 내리는 사이버펑크 네온 시티",
        "prompt": "1girl, solo, cyberpunk style, glowing neon cat ears, black techwear jacket, glowing blue lines, short black hair, purple eyes, holding umbrella, standing on wet asphalt street, puddles with vibrant neon sign reflections, heavy rain, futuristic skyscrapers in background, cinematic atmosphere, masterpiece"
    },
    {
        "title": "✨ 고대 대도서관의 천재 마법사",
        "prompt": "1girl, solo, long golden blonde hair, emerald green eyes, ornate wizard robe, witch hat, casting light spell, magical circle glowing in hand, floating ancient spellbooks, grand fantasy library, gigantic towering bookshelves, warm mystical dust motes, rays of light filtering from stained glass, masterpiece"
    },
    {
        "title": "❄️ 눈 내리는 겨울 설원의 은발 기사",
        "prompt": "1girl, solo, silver hair in ponytail, sharp crimson eyes, silver knight armor with gold trim, white fur cape, holding holy sword, standing on snowy mountain peak, falling snowflakes, winter blizzard, dramatic rim lighting, majestic fantasy landscape, cinematic composition, masterpiece"
    },
    {
        "title": "🎨 몽환적인 수채화풍의 라이덴 쇼군",
        "prompt": "1girl, solo, raiden shogun (genshin impact), purple hair, braided ponytail, glowing purple eyes, elegant purple kimono, floral patterns, holding electrical katana, traditional japanese shrine in background, watercolor ink wash medium, soft pastel splash, artistic brush strokes, ethereal lighting, masterpiece"
    }
]


class SkadiPromptCrafter:
    """지능형 프롬프트 생성/확장 마스터 엔진"""

    @classmethod
    def expand_with_rules(cls, user_text: str, style: str = "watercolor") -> Dict[str, Any]:
        """0ms 지능형 시맨틱 태그 분석 및 SDXL 특화 프롬프트 조합"""
        cleaned = user_text.strip()
        tags: List[str] = ["1girl", "solo"]
        detected_themes = []

        # 1. 키워드 사전 매핑
        lower_input = cleaned.lower()
        has_character = False

        for keyword, data in SEMANTIC_TAG_DICT.items():
            if keyword in cleaned or keyword.lower() in lower_input:
                if isinstance(data, dict):  # 캐릭터
                    tags.extend(data["tags"])
                    detected_themes.append(data.get("desc", keyword))
                    has_character = True
                elif isinstance(data, list):
                    tags.extend(data)
                    detected_themes.append(keyword)

        # 기본 외모 보강 (캐릭터/외모 태그가 없을 때)
        if not has_character:
            if "silver hair" not in tags and "white hair" not in tags and "black hair" not in tags and "blonde hair" not in tags:
                tags.extend(["silver hair", "long hair", "expressive eyes"])

        # 2. 화풍별 필수 마스터 태그 주입
        if style == "watercolor":
            tags.extend(["watercolor (medium)", "ink wash", "soft lighting", "artistic background", "masterpiece", "absurdres"])
        elif style == "anime_s_tier":
            tags.extend(["official anime art", "key visual", "vibrant colors", "clean sharp lines", "cinematic lighting", "masterpiece", "best quality"])
        elif style == "semi_realistic":
            tags.extend(["semi-realistic", "3d render style", "unreal engine 5", "subsurface scattering", "ray tracing", "volumetric light", "photorealistic lighting", "masterpiece"])
        elif style == "cyberpunk":
            tags.extend(["cyberpunk", "neon glow", "futuristic", "high contrast", "night atmosphere", "cinematic shot", "masterpiece"])

        # 중복 제거 (순서 보존)
        seen = set()
        unique_tags = []
        for t in tags:
            t_clean = t.strip()
            if t_clean and t_clean.lower() not in seen:
                seen.add(t_clean.lower())
                unique_tags.append(t_clean)

        final_prompt = ", ".join(unique_tags)
        korean_desc = f"AI 지능 확장: [{', '.join(detected_themes) if detected_themes else cleaned}] 요소를 바탕으로 {len(unique_tags)}개의 S급 태그를 최적 조합했습니다."

        return {
            "success": True,
            "original_prompt": cleaned,
            "enhanced_prompt": final_prompt,
            "korean_description": korean_desc,
            "tags_count": len(unique_tags),
            "style": style
        }

    @classmethod
    async def enhance_prompt_async(cls, user_text: str, style: str = "watercolor", mode: str = "expand") -> Dict[str, Any]:
        """
        AI 프롬프트 마법 확장:
        1. 모드가 random_idea 일 때: 엄선된 S급 일러스트 아이디어 즉시 반환
        2. Gemini / Ollama LLM을 통한 창의적 태그 확장 시도
        3. LLM 미응답 시 0ms 룰베이스 엔진으로 무중단 100% 즉시 폴백
        """
        if mode == "random_idea" or not user_text.strip():
            sample = random.choice(RANDOM_INSPIRATIONS)
            return {
                "success": True,
                "original_prompt": sample["title"],
                "enhanced_prompt": sample["prompt"],
                "korean_description": f"🎲 AI 추천 테마: {sample['title']}",
                "tags_count": len(sample["prompt"].split(",")),
                "style": style
            }

        # 1. 룰베이스 사전 조합
        rule_result = cls.expand_with_rules(user_text, style)

        # 2. 로컬 또는 클라우드 LLM을 통한 초지능 태그 보강 시도 (선택적)
        try:
            from config import API_KEYS
            gemini_key = API_KEYS.get("GEMINI", "")
            if gemini_key:
                system_instruction = (
                    "You are an expert Anime/SDXL Prompt Engineer specialized in Danbooru tags and Animagine XL 3.1. "
                    "Convert the user's Korean idea into a comma-separated list of Danbooru tags and cinematic keywords. "
                    "Do NOT write conversational sentences, markdown backticks, or explanations. "
                    "Output ONLY the comma-separated tags in English. "
                    "Always include character details, costume, background, lighting, and quality tags (e.g. masterpiece, absurdres, cinematic lighting)."
                )
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                body = {
                    "contents": [{"parts": [{"text": f"User Idea: {user_text}\nStyle: {style}\nCreate Danbooru tag prompt:"}]}],
                    "systemInstruction": {"parts": [{"text": system_instruction}]},
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 300}
                }
                
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post(url, json=body)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            raw_llm_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                            clean_tags = re.sub(r'```[a-zA-Z]*', '', raw_llm_text).replace('```', '').strip()
                            if len(clean_tags.split(",")) >= 6:
                                return {
                                    "success": True,
                                    "original_prompt": user_text,
                                    "enhanced_prompt": clean_tags,
                                    "korean_description": f"✨ Gemini AI가 '{user_text}'의 분위기, 의상, 조명을 분석하여 S급 프롬프트로 완성했습니다.",
                                    "tags_count": len(clean_tags.split(",")),
                                    "style": style
                                }
        except Exception:
            pass

        # LLM 실패나 오프라인 시 룰베이스 결과 반환
        return rule_result
