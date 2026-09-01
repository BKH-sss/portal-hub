"""
skadi_memory_engine.py
------------------------------------------------------------
헤르메스 AI(Hermes Agent) 아키텍처 기반의
스카디(Skadi) 전용 자가 발전(Self-Improvement) 및 장기 기억(Long-term Memory) 엔진.

핵심 기능:
1. 장기 기억 저장소 (User Profile & Episodic Fact Vault)
   - 유저의 취향, 성향, 이름, 목표, 습관, 약속 등 핵심 정보를 지속적으로 추출/저장
   - 대화 시 질문과 연관된 과거 기억 및 유저 팩트를 벡터 검색하여 프롬프트에 자동 주입
2. 자가 발전 루프 (Self-Improving Reflection & Skill Accumulation)
   - 매 대화 직후 백그라운드에서 복기(Reflection) 진행
   - 답변이 부족했거나 몰랐던 정보(Knowledge Gap)를 스스로 감지
   - 자율 웹 검색(DDGS)을 통해 지식을 보완하고 ChromaDB 지식 베이스 및 스킬북에 영구 축적
   - 자가 성장 일지(skadi_growth_journal.md)에 발전 과정 기록
------------------------------------------------------------
"""

import os
import json
import time
import datetime
import threading
from typing import List, Dict, Any, Optional
from duckduckgo_search import DDGS
from ollama_utils import ollama_generate, safe_json_parse

# 기본 저장 경로 설정 (B:\AI_Brain 우선, 없을 시 로컬 폴더 폴백)
PRIMARY_DIR = r"B:\AI_Brain"
FALLBACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory")
BASE_DIR = PRIMARY_DIR if os.path.exists(r"B:") else FALLBACK_DIR
os.makedirs(BASE_DIR, exist_ok=True)

FACTS_FILE = os.path.join(BASE_DIR, "skadi_profile_facts.json")
SKILLS_FILE = os.path.join(BASE_DIR, "skadi_skills.json")
JOURNAL_FILE = os.path.join(BASE_DIR, "skadi_growth_journal.md")
GAP_QUEUE_FILE = os.path.join(BASE_DIR, "skadi_knowledge_gaps.json")

_lock = threading.RLock()


# ==========================================
# 1. 장기 기억 (Long-Term Memory / Facts) 관리
# ==========================================

def load_user_facts() -> Dict[str, Any]:
    """유저에 대해 축적된 핵심 장기 기억(프로필 팩트) 로드"""
    with _lock:
        if not os.path.exists(FACTS_FILE):
            default_data = {
                "user_name": "마스터 (매니저님)",
                "interests": [],
                "personality_traits": [],
                "habits_and_preferences": [],
                "important_memories": [],
                "last_updated": datetime.datetime.now().isoformat()
            }
            save_user_facts(default_data)
            return default_data
        try:
            with open(FACTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SkadiMemory] 팩트 로드 실패: {e}")
            return {"user_name": "마스터", "important_memories": []}


def save_user_facts(data: Dict[str, Any]):
    """유저 장기 기억 영구 저장"""
    with _lock:
        os.makedirs(os.path.dirname(FACTS_FILE), exist_ok=True)
        data["last_updated"] = datetime.datetime.now().isoformat()
        with open(FACTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def get_fact_sheet_prompt() -> str:
    """프롬프트 주입용 유저 요약 시트 생성"""
    facts = load_user_facts()
    memories = facts.get("important_memories", [])
    interests = facts.get("interests", [])
    prefs = facts.get("habits_and_preferences", [])
    
    parts = []
    if facts.get("user_name") and facts.get("user_name") != "마스터 (매니저님)":
        parts.append(f"- 유저 호칭/이름: {facts['user_name']}")
    if interests:
        parts.append(f"- 관심사/플레이 게임: {', '.join(interests[-5:])}")
    if prefs:
        parts.append(f"- 유저 취향/성향: {', '.join(prefs[-5:])}")
    if memories:
        recent_mems = "\n  * ".join(memories[-6:])
        parts.append(f"- 기억하고 있는 중요 사실/사건:\n  * {recent_mems}")
        
    if not parts:
        return ""
    return "[스카디가 기억하는 마스터에 대한 장기 기억]\n" + "\n".join(parts)


def add_explicit_memory(memory_text: str, category: str = "general") -> bool:
    """사용자가 명시적으로 기억하라고 한 내용 즉각 저장"""
    facts = load_user_facts()
    if "important_memories" not in facts:
        facts["important_memories"] = []
    
    entry = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}] {memory_text.strip()}"
    if entry not in facts["important_memories"]:
        facts["important_memories"].append(entry)
        save_user_facts(facts)
        print(f"[SkadiMemory] 명시적 기억 저장 완료: {entry}")
        return True
    return False


def remove_explicit_memory(keyword: str) -> bool:
    """키워드가 포함된 장기 기억 항목 삭제"""
    facts = load_user_facts()
    memories = facts.get("important_memories", [])
    initial_len = len(memories)
    kw = keyword.lower().strip()
    
    facts["important_memories"] = [m for m in memories if kw not in m.lower()]
    facts["interests"] = [i for i in facts.get("interests", []) if kw not in i.lower()]
    facts["habits_and_preferences"] = [p for p in facts.get("habits_and_preferences", []) if kw not in p.lower()]
    
    if len(facts["important_memories"]) != initial_len or True:
        save_user_facts(facts)
        print(f"[SkadiMemory] 기억 항목 삭제 완료 (키워드: '{keyword}')")
        return True
    return False


# ==========================================
# 2. 자가 발전(Self-Evolution) & 스킬/지식 축적
# ==========================================

def load_skills() -> List[Dict[str, Any]]:
    """스카디가 스스로 터득한 스킬 및 지식 로드"""
    with _lock:
        if not os.path.exists(SKILLS_FILE):
            return []
        try:
            with open(SKILLS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []


def save_skill(skill_title: str, description: str, category: str = "general"):
    """새로운 스킬 또는 해결 노하우 저장"""
    with _lock:
        skills = []
        if os.path.exists(SKILLS_FILE):
            try:
                with open(SKILLS_FILE, "r", encoding="utf-8") as f:
                    skills = json.load(f)
            except Exception:
                skills = []
        
        # 중복 방지
        for s in skills:
            if s.get("title") == skill_title:
                s["description"] = description
                s["updated_at"] = datetime.datetime.now().isoformat()
                break
        else:
            skills.append({
                "title": skill_title,
                "description": description,
                "category": category,
                "created_at": datetime.datetime.now().isoformat()
            })
            
        with open(SKILLS_FILE, "w", encoding="utf-8") as f:
            json.dump(skills, f, ensure_ascii=False, indent=2)


def append_growth_journal(entry: str, title: str = "자가 학습 및 성찰"):
    """스카디의 자기 성장 일지에 항목 추가"""
    with _lock:
        os.makedirs(os.path.dirname(JOURNAL_FILE), exist_ok=True)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n### 📖 [{now_str}] {title}\n{entry.strip()}\n")


def get_growth_journal(max_chars: int = 2500) -> str:
    """최근 자기 성장 일지 내용 읽기"""
    if not os.path.exists(JOURNAL_FILE):
        return "아직 기록된 성장 일지가 없어."
    try:
        with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
            text = f.read()
        return text[-max_chars:] if len(text) > max_chars else text
    except Exception as e:
        return f"일지 로드 오류: {e}"


# ==========================================
# 3. 백그라운드 대화 복기 & 자율 학습 사이클
# ==========================================

def background_reflection_and_learn(user_msg: str, bot_reply: str, agent_name: str = "skadi", target_collection=None):
    """
    대화 직후 백그라운드에서 실행되는 자율 복기(Reflection) 및 자가 발전 루프
    1. 유저 정보 추출 (장기 기억 갱신)
    2. 지식 공백(Knowledge Gap) 감지 및 웹 자율 학습
    3. ChromaDB 지식 베이스 업데이트 및 성장 일지 기록
    """
    clean_user = user_msg.strip()
    if len(clean_user) < 5 or clean_user.startswith(("/", "!", "[")):
        return

    try:
        # LLM 복기 프롬프트 (Hermes Agent Reflection 스타일)
        reflection_prompt = f"""너는 AI 에이전트의 대화 복기 및 자아성찰 분석기야.
다음 유저와 AI(스카디)의 대화를 분석해줘.

[유저 발화]: {clean_user}
[스카디 답변]: {bot_reply}

반드시 아래 JSON 포맷으로만 응답해:
{{
  "user_facts": ["유저에 대해 새로 알게 된 사실이나 취향, 약속, 상태 (없으면 빈 리스트)"],
  "knowledge_gap": "스카디가 확실하게 답하지 못했거나 지식이 부족했던 주제/키워드 (충분했으면 null)",
  "search_query": "지식 보완을 위해 스스로 인터넷에서 검색할 최적의 쿼리 1개 (지식 공백 없으면 null)",
  "reflection_summary": "이번 대화에서 스카디가 배운 점이나 기억할 핵심 요약 1줄"
}}
"""
        from ollama_utils import gemini_generate
        raw_res = gemini_generate(reflection_prompt)
        if not raw_res:
            return
        data = safe_json_parse(raw_res, default={})

        if not isinstance(data, dict):
            return

        # 1. 장기 기억 업데이트
        new_facts = data.get("user_facts", [])
        if isinstance(new_facts, list) and new_facts:
            facts = load_user_facts()
            updated = False
            for fact in new_facts:
                if isinstance(fact, str) and fact.strip():
                    fact_entry = f"[{datetime.datetime.now().strftime('%m/%d %H:%M')}] {fact.strip()}"
                    if fact_entry not in facts.get("important_memories", []):
                        facts.setdefault("important_memories", []).append(fact_entry)
                        updated = True
            if updated:
                save_user_facts(facts)
                print(f"[SkadiMemory] 🧠 유저 장기 기억 자동 갱신: {new_facts}")

        # 2. 지식 공백 및 자율 학습 (Self-Learning)
        search_query = data.get("search_query")
        gap = data.get("knowledge_gap")
        summary = data.get("reflection_summary", "")

        if search_query and isinstance(search_query, str) and search_query.strip():
            print(f"[SkadiEvolution] 🔍 자율 학습 검색 시작: '{search_query}' (원인: {gap})")
            search_results_text = ""
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(search_query, region="kr-kr", max_results=2))
                if results:
                    search_results_text = "\n".join([f"- {r.get('title')}: {r.get('body')}" for r in results])
            except Exception as se:
                print(f"[SkadiEvolution] 검색 오류: {se}")

            if search_results_text:
                # 습득한 지식 정제
                study_prompt = f"""스카디가 스스로 부족했던 지식을 공부하는 중이야.
[검색 주제]: {search_query}
[검색 데이터]:
{search_results_text}

위 내용을 바탕으로 스카디가 앞으로 마스터에게 바로 알려줄 수 있도록 핵심 지식을 2~3문장의 명확한 노하우/지식으로 요약해."""
                learned_summary = ollama_generate(study_prompt, model="llama3.1", temperature=0.3, num_predict=300)
                
                # ChromaDB에 자가 습득 지식으로 저장
                if target_collection and learned_summary:
                    doc_id = f"self_learned_{int(time.time())}"
                    target_collection.upsert(
                        documents=[f"[스카디 자가 학습 지식: {search_query}]\n{learned_summary}"],
                        metadatas=[{"source": "skadi_self_evolution", "query": search_query, "timestamp": datetime.datetime.now().isoformat()}],
                        ids=[doc_id]
                    )
                    save_skill(f"자가학습: {search_query}", learned_summary, category="autonomous_learning")
                    print(f"[SkadiEvolution] ✅ 자가 발전 지식 DB 및 스킬북 등록 완료 ({doc_id})")

                # 성장 일지 작성
                journal_entry = f"- 탐구한 지식: {search_query}\n- 자아성찰: {summary}\n- 습득한 핵심: {learned_summary.strip()}"
                append_growth_journal(journal_entry, title=f"자율 학습: {search_query}")
        elif summary:
            # 단순 대화 성찰 기록
            append_growth_journal(f"- 대화 요약: {summary}", title="대화 복기 및 교감")

    except Exception as e:
        print(f"[SkadiMemory] 자가 발전 복기 중 에러: {e}")
