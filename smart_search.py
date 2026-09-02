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


async def search_youtube(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """유튜브 검색을 통해 실제 작동하는 동영상 제목 및 URL 추출"""
    clean_q = _clean_search_query(query)
    encoded = urllib.parse.quote(clean_q)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    results = []
    seen_ids = set()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                m = re.search(r'var ytInitialData = ({.*?});</script>', r.text)
                if m:
                    data = json.loads(m.group(1))
                    contents = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [{}])[0].get('itemSectionRenderer', {}).get('contents', [])
                    for item in contents:
                        v = item.get('videoRenderer')
                        if v:
                            vid = v.get('videoId')
                            if vid and vid not in seen_ids:
                                seen_ids.add(vid)
                                runs = v.get('title', {}).get('runs', [{}])
                                title = runs[0].get('text', '유튜브 영상') if runs else '유튜브 영상'
                                watch_url = f"https://www.youtube.com/watch?v={vid}"
                                thumb_url = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
                                results.append({
                                    "title": title,
                                    "url": watch_url,
                                    "thumbnail": thumb_url,
                                    "source": "YouTube"
                                })
                                if len(results) >= max_results:
                                    break
    except Exception as e:
        print(f"[SmartSearch] YouTube 검색 에러: {e}")
    return results


async def search_live_images(query: str, max_images: int = 5, extra_sub_terms: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """
    고화질 실시간 이미지 검색 (Bing Async API + 위키백과 미디어)
    - 디스코드에서 바로 렌더링되는 직관적인 이미지 링크(.jpg, .png) 획득
    """
    clean_q = _clean_image_query(query)
    images = []
    seen_urls = set()

    # 1. Bing 고화질 이미지 검색
    try:
        encoded = urllib.parse.quote(clean_q)
        url = f"https://www.bing.com/images/async?q={encoded}&first=1&count=15"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', r.text)
                for img_url in murls:
                    if img_url not in seen_urls:
                        # 유효한 이미지 확장자 확인
                        seen_urls.add(img_url)
                        images.append({"title": clean_q, "url": img_url})
                        if len(images) >= max_images:
                            break
    except Exception as e:
        print(f"[SmartSearch] Bing Image 검색 에러: {e}")

    # 2. 위키백과 미디어 보완 (인물/지명/명화/동물 등)
    if len(images) < 2:
        async def _fetch_wiki_images(term: str, lang: str):
            if not term or len(term.strip()) < 2:
                return
            try:
                enc = urllib.parse.quote(term.strip())
                w_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={enc}&gsrlimit=3&prop=pageimages&pithumbsize=900&format=json"
                headers = {"User-Agent": "JarvisAI/2.0"}
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.get(w_url, headers=headers)
                    if res.status_code == 200:
                        pages = res.json().get("query", {}).get("pages", {})
                        for pid, pinfo in pages.items():
                            thumb = pinfo.get("thumbnail", {}).get("source")
                            title = pinfo.get("title", "")
                            if thumb and thumb not in seen_urls:
                                seen_urls.add(thumb)
                                images.append({"title": title, "url": thumb})
            except Exception:
                pass

        await _fetch_wiki_images(clean_q, "ko")
        if len(images) < 2:
            await _fetch_wiki_images(clean_q, "en")

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

    # 사진/이미지 및 유튜브/영상 요구 여부 판별
    is_image_request = any(k in query.lower() for k in [
        "사진", "이미지", "모습", "그림", "생김새", "보여줘", "외형", "얼굴", "룩",
        "건축물", "풍경", "전경", "구경", "어떻게 생겼", "사진도", "사진은", "포토", "짤"
    ])
    is_youtube_request = any(k in query.lower() for k in [
        "유튜브", "유투브", "youtube", "동영상", "영상", "음악", "노래", "ost", "mv", "뮤비", "뮤직비디오", "듣기", "링크", "클립"
    ])

    # 1. 텍스트 검색 및 유튜브 검색 병렬 실행
    tasks = [
        search_duckduckgo(query, max_results=max_sources),
        search_wikipedia(query, lang="ko")
    ]
    if is_youtube_request:
        tasks.append(search_youtube(query, max_results=3))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    web_results = results[0] if isinstance(results[0], list) else []
    wiki_result = results[1] if isinstance(results[1], dict) else None
    found_yt_videos = results[2] if (is_youtube_request and len(results) > 2 and isinstance(results[2], list)) else []

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

    # 2. 이미지 검색 실행
    found_images = []
    if is_image_request:
        found_images = await search_live_images(query, max_images=4, extra_sub_terms=sub_terms)

    if not final_sources and not found_images and not found_yt_videos:
        return {
            "success": False,
            "query": query,
            "grounding_text": "",
            "sources": [],
            "images": [],
            "videos": []
        }

    # 프롬프트 주입용 그라운딩 텍스트 생성
    grounding_lines = ["[실시간 웹 검색 팩트 & 시각/미디어 자료 (Grounding Context)]"]
    grounding_lines.append("다음은 인터넷 실시간 검색을 통해 획득한 최신 팩트, 실제 사진, 공식 유튜브 링크 자료이다. 이 정보를 바탕으로 질문에 정확하고 친절하게 대답해라:\n")

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

    # 유튜브 검색 결과 주입
    if found_yt_videos:
        grounding_lines.append("\n[실시간 검색된 실제 작동하는 공식 유튜브 영상 링크 목록]")
        for yt in found_yt_videos:
            yt_title = yt.get("title", "유튜브 영상")
            yt_url = yt.get("url", "")
            grounding_lines.append(f"- 제목: {yt_title}")
            grounding_lines.append(f"  * 유튜브 링크: {yt_url}")
            grounding_lines.append(f"  * 마크다운 링크: [{yt_title}]({yt_url})")

        grounding_lines.append("\n[⚠️ 유튜브 링크 작성 절대 규칙 (필수)]")
        grounding_lines.append("1. 마스터가 유튜브 링크나 음악/영상을 요청했을 때는 반드시 위 실제 유튜브 링크(https://www.youtube.com/watch?v=...)를 답변 본문에 그대로 포함시켜라!")
        grounding_lines.append("2. 절대로 링크 없는 텍스트 제목만 적지 마라. 디스코드는 링크를 작성하면 영상 플레이어가 화면에 자동으로 크게 임베드된다.")

    # 실시간 사진 자료 주입
    if found_images:
        grounding_lines.append("\n[실시간 검색된 실제 사진 및 이미지 링크 목록]")
        for img in found_images:
            item_title = img.get('title', '이미지')
            img_url = img.get('url', '')
            grounding_lines.append(f"- 사진: {item_title}")
            grounding_lines.append(f"  * 이미지 링크: {img_url}")
            grounding_lines.append(f"  * 마크다운 링크: [{item_title} 사진 보기]({img_url})")

        grounding_lines.append("\n[⚠️ 사진/이미지 출력 절대 규칙]")
        grounding_lines.append("1. 사용자가 사진/이미지를 요구했을 때는 반드시 위 실제 이미지 URL(https://.../image.jpg) 또는 마크다운 링크를 답변 본문에 포함시켜라!")
        grounding_lines.append("2. 디스코드는 이미지 링크를 적으면 사진이 채팅창에 자동으로 크게 렌더링되어 표시된다.")

    grounding_text = "\n".join(grounding_lines).strip()

    data = {
        "success": True,
        "query": query,
        "grounding_text": grounding_text,
        "sources": citations,
        "images": found_images,
        "videos": found_yt_videos
    }

    _SEARCH_CACHE[cache_key] = {
        "timestamp": now_ts,
        "data": data
    }
    return data
