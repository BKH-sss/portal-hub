"""
obsidian_writer.py
------------------------------------------------------------
web_crawler.py가 긁어온(또는 local_video_analyzer가 분석한) 결과를
옵시디언 볼트(Vault)에 마크다운 노트로 저장하는 모듈.

두 모듈이 "효율적으로" 맞물리는 지점은 이렇습니다:
  - web_crawler.search_and_crawl()은 여러 URL을 한 번에 긁어서 리스트로 반환
  - 이 모듈은 그 리스트를 받아 "볼트 인덱스 1회 로딩 -> 여러 노트 저장"으로 처리
    (노트 하나 저장할 때마다 볼트 전체를 다시 스캔하면 노트 수가 늘수록 느려지므로,
     ObsidianVault 객체가 제목 인덱스를 메모리에 캐싱해두고 재사용합니다)
  - 이미 크롤링/저장한 URL은 history 파일로 걸러서 중복 크롤링·중복 노트 생성을 방지
    (brain_server.py의 scraped_history.txt와 동일한 패턴)

핵심 기능:
  1. YAML 프론트매터 자동 생성 (source, date, tags, score)
  2. 자동 위키링크: 볼트에 이미 있는 노트 제목이 새 노트 본문에 등장하면 [[노트제목]]으로 치환
  3. 카테고리별 폴더 자동 분류
  4. 중복 방지 (URL 해시 기반)

사용법 - 가장 간단한 통합 사용 (권장):
    from obsidian_writer import crawl_search_and_save

    result = crawl_search_and_save(
        query="리그오브레전드 15.1 패치노트",
        vault_path=r"B:\AI_Brain\Obsidian_Knowledge",
        category="lol",
        max_results=5,
    )
    # result = {"saved": 3, "skipped_duplicate": 1, "skipped_low_score": 1, "notes": [...]}

사용법 - 세밀하게 직접 제어:
    from web_crawler import search_and_crawl
    from obsidian_writer import ObsidianVault

    vault = ObsidianVault(r"C:\\...\\ObsidianVault")
    pages = search_and_crawl("검색어")
    for page in pages:
        vault.save_note(title=page["title"], content=page["content"],
                         source_url=page["url"], category="general")
"""
import os
import re
import json
import hashlib
import datetime

from ollama_utils import ollama_generate, safe_json_parse

try:
    from local_fact_checker import local_check_and_chunk_knowledge
except ImportError:
    local_check_and_chunk_knowledge = None


SUMMARY_MODEL = "gemma4:12b"


# ------------------------------------------------------------------
# 볼트 관리 - 인덱스를 캐싱해서 노트를 여러 개 저장할 때 반복 스캔을 피함
# ------------------------------------------------------------------

class ObsidianVault:
    def __init__(self, vault_path: str, history_filename: str = ".crawled_history.json"):
        self.vault_path = vault_path
        os.makedirs(vault_path, exist_ok=True)
        self.history_path = os.path.join(vault_path, history_filename)
        self._history = self._load_history()
        self._title_index = self._build_title_index()  # {정규화된 제목: 실제 노트 제목}

    # --- 중복 방지 (URL 해시 기반) ---
    def _load_history(self) -> dict:
        if not os.path.exists(self.history_path):
            return {}
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_history(self):
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self._history, f, ensure_ascii=False, indent=2)

    def _url_hash(self, url: str) -> str:
        return hashlib.md5(url.encode("utf-8")).hexdigest()[:12]

    def already_crawled(self, url: str) -> bool:
        return self._url_hash(url) in self._history

    # --- 위키링크 인덱스 (볼트 전체를 1회만 스캔, 이후 재사용) ---
    def _build_title_index(self) -> dict:
        index = {}
        for root, _, files in os.walk(self.vault_path):
            for f in files:
                if f.endswith(".md"):
                    title = os.path.splitext(f)[0]
                    if len(title) >= 2:  # 너무 짧은 제목은 오탐 링크가 많아지므로 제외
                        index[title.lower()] = title
        return index

    def _auto_wikilink(self, content: str) -> str:
        """본문에 등장하는 기존 노트 제목을 [[노트]] 형태로 치환."""
        if not self._title_index:
            return content
        # 제목이 긴 것부터 치환해야 짧은 제목이 긴 제목 안쪽을 먼저 깨물지 않음
        for title_lower, title_actual in sorted(self._title_index.items(), key=lambda x: -len(x[0])):
            if title_lower in content.lower() and f"[[{title_actual}]]" not in content:
                pattern = re.compile(re.escape(title_actual), re.IGNORECASE)
                content = pattern.sub(f"[[{title_actual}]]", content, count=1)  # 첫 등장만 링크
        return content

    # --- 노트 저장 ---
    def _safe_filename(self, title: str) -> str:
        safe = re.sub(r'[\\/:*?"<>|]', "_", title).strip()
        return safe[:120] if safe else "untitled"

    def save_note(self, title: str, content: str, source_url: str = "",
                  category: str = "general", tags: list[str] | None = None,
                  score: int | None = None, extra_frontmatter: dict | None = None) -> str:
        """노트를 볼트에 저장하고 파일 경로를 반환. history와 title_index도 갱신."""
        folder = os.path.join(self.vault_path, category)
        os.makedirs(folder, exist_ok=True)

        now = datetime.datetime.now()
        filename = f"{self._safe_filename(title)}.md"
        filepath = os.path.join(folder, filename)

        linked_content = self._auto_wikilink(content)

        tag_list = list(tags or [])
        if category not in tag_list:
            tag_list.append(category)

        fm = {
            "title": title,
            "source": source_url or "local",
            "created": now.strftime("%Y-%m-%d %H:%M"),
            "tags": tag_list,
        }
        if score is not None:
            fm["score"] = score
        if extra_frontmatter:
            fm.update(extra_frontmatter)

        frontmatter_lines = ["---"]
        for k, v in fm.items():
            if isinstance(v, list):
                frontmatter_lines.append(f"{k}: [{', '.join(v)}]")
            else:
                frontmatter_lines.append(f'{k}: "{v}"')
        frontmatter_lines.append("---\n")

        body = f"# {title}\n\n{linked_content}\n"
        if source_url:
            body += f"\n---\n출처: {source_url}\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(frontmatter_lines) + body)

        # 인덱스/히스토리 갱신 (다음 노트 저장 시 이 노트도 위키링크 후보가 됨)
        self._title_index[title.lower()] = title
        if source_url:
            self._history[self._url_hash(source_url)] = {
                "title": title, "saved_at": now.isoformat(), "path": filepath,
            }
            self._save_history()

        print(f"[Obsidian] 노트 저장 완료: {filepath}")
        return filepath


# ------------------------------------------------------------------
# 요약 (팩트체커 없이 가볍게 쓰고 싶을 때용 - 선택 사항)
# ------------------------------------------------------------------

def _summarize_for_note(title: str, content: str) -> str:
    """옵시디언 노트에 넣기 좋은 형태(핵심 요약 + 구조화)로 정리."""
    prompt = f"""다음은 '{title}'라는 페이지에서 크롤링한 원문이다.
이 내용을 옵시디언 노트에 저장할 형태로 정리해라.
- 핵심 정보를 놓치지 말고, 불필요한 광고/네비게이션 문구는 제거해라.
- 소제목(##)을 활용해 구조화해라.
- 원문에 없는 내용은 절대 추가하지 마라.

[원문]
{content[:6000]}
"""
    result = ollama_generate(prompt, model=SUMMARY_MODEL, temperature=0.1, num_predict=1200)
    return result if result else content  # 요약 실패 시 원문 그대로 저장 (정보 손실 방지)


# ------------------------------------------------------------------
# 통합 파이프라인 - web_crawler + (선택)local_fact_checker + 이 모듈을 한 번에
# ------------------------------------------------------------------

def crawl_search_and_save(query: str, vault_path: str = r"B:\AI_Brain\Obsidian_Knowledge", category: str = "general",
                           max_results: int = 5, use_fact_check: bool = True,
                           min_score: int = 70) -> dict:
    """
    검색 -> 크롤링 -> (선택)팩트체크 -> 요약 -> 옵시디언 저장까지 한 번에 처리하는 진입점.

    효율화 포인트:
      - ObsidianVault를 한 번만 생성해서 볼트 인덱스를 재사용 (페이지마다 새로 만들지 않음)
      - 이미 크롤링한 URL은 크롤링 자체를 건너뜀 (search_and_crawl 호출 전에 필터링)
      - use_fact_check=False로 두면 로컬 LLM 요약만 거치고 바로 저장 (더 빠름, 팩트체크 생략)
    """
    from web_crawler import search_and_crawl

    vault = ObsidianVault(vault_path)

    pages = search_and_crawl(query, max_results=max_results)
    saved, skipped_dup, skipped_low_score, notes = 0, 0, 0, []

    for page in pages:
        if vault.already_crawled(page["url"]):
            skipped_dup += 1
            continue

        score = None
        content_to_save = page["content"]

        if use_fact_check and local_check_and_chunk_knowledge is not None:
            chunks = local_check_and_chunk_knowledge(page["content"], page["title"], category=category)
            if not chunks:
                skipped_low_score += 1
                continue
            score = chunks[0]["metadata"].get("score")
            # 챕터로 쪼개져 있으면 하나의 노트로 재조립 (옵시디언은 노트 단위가 자연스러움)
            content_to_save = "\n\n".join(
                f"## {c['metadata'].get('chapter', '섹션')}\n{c['content']}" for c in chunks
            )
        else:
            content_to_save = _summarize_for_note(page["title"], page["content"])

        path = vault.save_note(
            title=page["title"], content=content_to_save, source_url=page["url"],
            category=category, score=score,
        )
        notes.append(path)
        saved += 1

    return {
        "query": query, "saved": saved,
        "skipped_duplicate": skipped_dup, "skipped_low_score": skipped_low_score,
        "notes": notes,
    }
