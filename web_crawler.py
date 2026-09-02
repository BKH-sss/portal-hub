"""
web_crawler.py
------------------------------------------------------------
YouTube뿐 아니라 "일반 웹페이지"를 크롤링해서 본문 텍스트를 뽑아내는 범용 모듈.
DDGS로 검색 -> 상위 결과 URL들 -> requests+BeautifulSoup으로 본문 추출.

기존 파이프라인(local_fact_checker의 팩트체크/청킹, grounded_writer, ChromaDB 저장)에
그대로 태울 수 있게 "제목 + 본문 텍스트"만 깔끔하게 뽑아주는 역할만 합니다.

사용법:
    from web_crawler import search_and_crawl, crawl_url

    # 키워드로 검색해서 상위 N개 페이지를 크롤링
    pages = search_and_crawl("리그오브레전드 15.1 패치노트", max_results=5)
    # pages = [{"url": ..., "title": ..., "content": ...}, ...]

    # URL 하나만 직접 크롤링
    page = crawl_url("https://example.com/article")
"""
import re
import requests
from bs4 import BeautifulSoup

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# 본문 추출 시 노이즈로 걸러낼 태그
NOISE_TAGS = ["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript"]


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def crawl_url(url: str, timeout: int = 15, max_chars: int = 8000) -> dict | None:
    """URL 하나를 가져와서 제목과 본문 텍스트를 추출. 실패하면 None."""
    try:
        res = requests.get(url, headers=HEADERS, timeout=timeout)
        res.raise_for_status()
    except Exception as e:
        print(f"[web_crawler] 페이지 요청 실패 ({url}): {e}")
        return None

    try:
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"[web_crawler] 파싱 실패 ({url}): {e}")
        return None

    for tag in soup(NOISE_TAGS):
        tag.decompose()

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    # <article> 태그가 있으면 우선 사용, 없으면 <main>, 그것도 없으면 <body> 전체
    main = soup.find("article") or soup.find("main") or soup.find("body")
    if not main:
        return None

    text = _clean_text(main.get_text(separator="\n"))
    if len(text) < 100:  # 본문이 사실상 없는 페이지(로그인 필요, 빈 페이지 등)는 스킵
        print(f"[web_crawler] 본문이 너무 짧아 스킵: {url}")
        return None

    return {
        "url": url,
        "title": title,
        "content": text[:max_chars],
    }


def search_and_crawl(query: str, max_results: int = 5, region: str = "kr-kr") -> list[dict]:
    """DDGS로 검색해서 상위 결과들을 순서대로 크롤링. 실패한 페이지는 건너뜀."""
    if DDGS is None:
        print("[web_crawler] duckduckgo_search 미설치")
        return []

    urls = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, region=region, max_results=max_results):
                href = r.get("href", "")
                if href:
                    urls.append(href)
    except Exception as e:
        print(f"[web_crawler] 검색 실패 ('{query}'): {e}")
        return []

    pages = []
    for url in urls:
        page = crawl_url(url)
        if page:
            pages.append(page)
    return pages
