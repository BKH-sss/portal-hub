"""
smart_search.py
------------------------------------------------------------
GPT-4o / Perplexity / Gemini 급 실시간 웹 검색 및 팩트 그라운딩 엔진.
- DuckDuckGo Search (DDGS) 고속 비동기 검색
- Wikipedia 한국어/영어 백과사전 API 연동
- 실시간 웹페이지 스크래퍼 및 핵심 스니펫 추출
- 인용(Citations) 및 출처 URL 자동 포맷팅
- 로컬 모델(Ollama) 및 클라우드 모델(Gemini/Claude/GPT) 모두에 완벽한 팩트 주입
------------------------------------------------------------
"""

import os
import re
import json
import asyncio
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

# 검색 캐시 (중복 검색 방지 및 5분 TTL)
_SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 300  # 5분


def _clean_search_query(raw_query: str) -> str:
    """자연어 질문에서 핵심 검색 키워드 추출"""
    q = raw_query.strip()
    # 조사 및 질문 어미 제거
    q = re.sub(r'^(스카디야|스카디|봇|인공지능|ai)[,\s]*', '', q, flags=re.IGNORECASE)
    q = re.sub(r'(에\s*대해서?|에\s*관해서?)\s*(알려줘|설명해줘|말해줘|가르쳐줘|요약해줘)?', ' ', q)
    q = re.sub(r'(알려줘|설명해줘|말해줘|가르쳐줘|요약해줘|어때|어때요|뭐야|뭔지|무엇인가요|누구야|누군지|어떻게|최신\s*정보|근황|시세|가격)\??', ' ', q)
    q = re.sub(r'\s+', ' ', q).strip()
    return q if len(q) >= 2 else raw_query.strip()


async def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """DuckDuckGo를 통한 고속 웹 검색"""
    if not DDGS:
        return []
    
    clean_q = _clean_search_query(query)
    
    def _run_ddgs():
        results = []
        try:
            with DDGS() as ddgs:
                # 1. 정제된 키워드로 한국어 검색
                raw_results = list(ddgs.text(clean_q, region="kr-kr", max_results=max_results))
                if not raw_results and clean_q != query:
                    raw_results = list(ddgs.text(query, region="kr-kr", max_results=max_results))
                if not raw_results:
                    raw_results = list(ddgs.text(clean_q, region="wt-wt", max_results=max_results))
                for r in raw_results:
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", "") or r.get("snippet", ""),
                        "url": r.get("href", "") or r.get("link", ""),
                        "source": "Web"
                    })
        except Exception as e:
            print(f"[SmartSearch] DDGS 검색 오류: {e}")
        return results

    return await asyncio.to_thread(_run_ddgs)


async def search_wikipedia(query: str, lang: str = "ko") -> Optional[Dict[str, str]]:
    """위키백과 API를 통한 개념/인물/역사 공식 정의 검색"""
    try:
        clean_q = re.sub(r'[?!\'"]', '', query).strip()
        encoded = urllib.parse.quote(clean_q)
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        
        async with httpx.AsyncClient(timeout=4.0) as client:
            res = await client.get(url, headers={"User-Agent": "JarvisAssistant/2.0"})
            if res.status_code == 200:
                data = res.json()
                title = data.get("title", "")
                extract = data.get("extract", "")
                page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                if extract:
                    return {
                        "title": f"위키백과: {title}",
                        "snippet": extract,
                        "url": page_url,
                        "source": "Wikipedia"
                    }
    except Exception as e:
        pass
    return None


async def scrape_web_page(url: str, max_chars: int = 2500) -> str:
    """웹페이지 URL의 본문 텍스트를 고속 추출"""
    if not url or not url.startswith("http"):
        return ""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
                    tag.decompose()
                text = ' '.join(soup.stripped_strings)
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:max_chars]
    except Exception as e:
        print(f"[SmartSearch] Scrape 에러 ({url}): {e}")
    return ""


def _clean_image_query(raw_query: str) -> str:
    """자연어 이미지 요청 문장에서 핵심 검색 대상 키워드만 정밀 추출"""
    q = raw_query.strip()
    q = re.sub(r'^(스카디야|스카디|브라이어|비서|봇|ai|인공지능)[,\s]*', '', q, flags=re.IGNORECASE)
    q = re.sub(r'(사진|이미지|짤|포토|일러스트|그림|모습|생김새|얼굴|외형|전경|풍경)\s*(들)?\s*(좀|좀더)?\s*(찾아줘|보여줘|구해줘|띄워줘|알려줘|가져와|줘|해줘|어때|있어)?', '', q)
    q = re.sub(r'(에\s*대해서?|에\s*관해서?)\s*(알려줘|설명해줘|말해줘)?', '', q)
    q = re.sub(r'(찾아줘|보여줘|구해줘|띄워줘|알려줘|가르쳐줘|가져와|줘|해줘|어때|있어|있니|어떻게 생겼어)', '', q)
    q = re.sub(r'\s+', ' ', q).strip()
    return q if len(q) >= 2 else raw_query.strip()


async def search_live_images(query: str, max_images: int = 5, extra_sub_terms: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """
    위키백과 및 실시간 웹 미디어 API 기반 고품질 이미지 스크랩 엔진
    - 한국어/영어 위키백과 미디어 API 병렬 조회
    - 고해상도 썸네일(800px+) URL 자동 추출
    - 하위 엔티티 키워드 다중 검색 지원
    """
    clean_q = _clean_image_query(query)
    images = []
    seen_urls = set()

    async def _fetch_wiki_images(term: str, lang: str):
        if not term or len(term.strip()) < 2:
            return
        try:
            encoded = urllib.parse.quote(term.strip())
            url = f"https://{lang}.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={encoded}&gsrlimit=3&prop=pageimages&pithumbsize=900&format=json"
            headers = {
                "User-Agent": "JarvisAI/2.0 (admin@jarvis.local)",
                "Accept": "application/json"
            }
            async with httpx.AsyncClient(timeout=4.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    pages = res.json().get("query", {}).get("pages", {})
                    for pid, pinfo in pages.items():
                        thumb = pinfo.get("thumbnail", {}).get("source")
                        title = pinfo.get("title", "")
                        if thumb and thumb not in seen_urls:
                            if not any(f in thumb.lower() for f in ["flag_of", "map", "icon", "symbol", "stub"]):
                                seen_urls.add(thumb)
                                images.append({"title": title, "url": thumb})
        except Exception:
            pass

    # 1. 메인 검색어(한국어) 최우선 조회
    await _fetch_wiki_images(clean_q, "ko")

    # 2. 결과가 부족할 경우 영어 위키백과 및 변형어 조회
    if len(images) < 2:
        await _fetch_wiki_images(clean_q, "en")
    if len(images) < 2 and clean_q != query:
        await _fetch_wiki_images(query, "ko")

    # 3. 하위 서브 엔티티 조회 (다중 항목 비교 시)
    if extra_sub_terms and len(images) < max_images:
        for st in extra_sub_terms[:4]:
            st_clean = _clean_image_query(st)
            if st_clean and st_clean != clean_q:
                await _fetch_wiki_images(st_clean, "ko")
                if len(images) >= max_images:
                    break

    return images[:max_images]


async def smart_web_grounding(query: str, max_sources: int = 4) -> Dict[str, Any]:
    """
    통합 실시간 팩트 및 시각 이미지 그라운딩 실행:
    - DuckDuckGo + Wikipedia 병렬 질의
    - 고화질 실시간 사진(Image) 스크랩 및 마크다운 주입
    """
    import time
    now_ts = time.time()
    cache_key = query.strip().lower()

    if cache_key in _SEARCH_CACHE:
        cached = _SEARCH_CACHE[cache_key]
        if now_ts - cached["timestamp"] < CACHE_TTL:
            return cached["data"]

    # 사진/이미지 요구 여부 판별
    is_image_request = any(k in query for k in [
        "사진", "이미지", "모습", "그림", "생김새", "보여줘", "외형", "얼굴", "룩",
        "건축물", "풍경", "전경", "구경", "어떻게 생겼", "사진도", "사진은", "포토"
    ])

    # 1. 텍스트 검색 우선 실행
    tasks = [
        search_duckduckgo(query, max_results=max_sources),
        search_wikipedia(query, lang="ko")
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    web_results = results[0] if isinstance(results[0], list) else []
    wiki_result = results[1] if isinstance(results[1], dict) else None

    combined_sources = []
    if wiki_result:
        combined_sources.append(wiki_result)
    combined_sources.extend(web_results)

    # 중복 URL 제거 및 상위 항목 선별
    seen_urls = set()
    unique_sources = []
    sub_terms = []
    for s in combined_sources:
        u = s.get("url", "")
        t = s.get("title", "").replace("위키백과: ", "").strip()
        if t and t not in sub_terms:
            sub_terms.append(t)
        if u and u not in seen_urls:
            seen_urls.add(u)
            unique_sources.append(s)
        elif not u:
            unique_sources.append(s)

    final_sources = unique_sources[:max_sources]

    # 2. 이미지 검색 실행 (메인 질의어 + 검색된 세부 항목들)
    found_images = []
    if is_image_request:
        found_images = await search_live_images(query, max_images=4, extra_sub_terms=sub_terms)

    if not final_sources and not found_images:
        return {
            "success": False,
            "query": query,
            "grounding_text": "",
            "sources": [],
            "images": []
        }

    # 프롬프트 주입용 그라운딩 텍스트 생성
    grounding_lines = ["[실시간 웹 검색 팩트 & 시각 자료 (Grounding Context)]"]
    grounding_lines.append("다음은 인터넷 실시간 검색을 통해 획득한 최신 팩트 및 실제 사진 자료이다. 이 사실을 바탕으로 질문에 정확하고 자연스럽게 대답해라:\n")

    citations = []
    for idx, item in enumerate(final_sources, 1):
        title = item.get("title", "정보")
        snippet = item.get("snippet", "").strip()
        url = item.get("url", "")
        if snippet:
            grounding_lines.append(f"[{idx}] {title}")
            grounding_lines.append(f"내용: {snippet}")
            if url:
                grounding_lines.append(f"출처 링크: {url}")
            grounding_lines.append("")
            citations.append({
                "index": idx,
                "title": title,
                "url": url,
                "snippet": snippet[:150]
            })

    # 실시간 사진 자료 주입 및 엄격한 URL/구글 검색 연동 지침
    if found_images:
        grounding_lines.append("\n[실시간 검색된 실제 사진 및 구글 검색 바로가기 목록]")
        for img in found_images:
            item_title = img.get('title', '이미지')
            img_url = img.get('url', '')
            g_url = f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(item_title)}"
            img["google_url"] = g_url
            grounding_lines.append(f"- 항목: {item_title}")
            grounding_lines.append(f"  * 이미지 URL: {img_url}")
            grounding_lines.append(f"  * 구글 이미지 검색 URL: {g_url}")
            grounding_lines.append(f"  * 클릭 가능한 마크다운 링크: [![{item_title}]({img_url})]({g_url})")

        grounding_lines.append("\n[⚠️ 사진 출력 및 URL 정확성 절대 규칙 (매우 중요)]")
        grounding_lines.append("1. 사용자가 사진/이미지를 요구했을 때는 반드시 위 [실시간 검색된 실제 사진 및 구글 검색 바로가기 목록]에 있는 검증된 마크다운 링크 `[![항목이름](실제이미지URL)](구글검색URL)`를 답변 본문에 그대로 포함시켜라!")
        grounding_lines.append("2. [절대 금지] 절대로 `images.unsplash.com`, `example.com`, `placehold.co` 등 임의의 가짜/스톡 사진 URL을 상상해서 넣지 마라! (산 질문에 엉뚱한 바다/해변 사진이 나오는 치명적인 불일치가 발생한다.)")
        grounding_lines.append("3. 반드시 질문한 주제(예: 마터호른, 스위스 산, 동물, 인물 등)와 100% 일치하는 실제 사진만 출력하고, 목록에 없는 항목은 텍스트 설명만 제공해라.")
        grounding_lines.append("4. 절대로 '텍스트 기반 AI라 사진을 못 보여준다'고 거절하지 마라.")

    grounding_text = "\n".join(grounding_lines).strip()

    data = {
        "success": True,
        "query": query,
        "grounding_text": grounding_text,
        "sources": citations,
        "images": found_images
    }

    _SEARCH_CACHE[cache_key] = {
        "timestamp": now_ts,
        "data": data
    }
    return data
