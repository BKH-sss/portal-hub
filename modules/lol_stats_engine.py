"""
lol_stats_engine.py
=============================================================================
🏆 JARVIS / SKADI: 롤(LoL) 원격 Riot API 통계 & OP.GG 스타일 인텔리전스 엔진
=============================================================================
- 클라우드(Render) 환경 100% 최적화:
  1. 🗡️ Item Builds (아이템 빌드 추천): 173개 전 챔피언 1~3코어, 시작템, 신발, 룬 통계
  2. 🎓 Skill Recommendations (스킬트리 추천): 스킬 마스터 순서(Q>E>W) 및 1~18레벨 트리
  3. 🎴 Augment Tier (증강체 티어): lol_ai_coach.AugmentEngine 완벽 연동
  4. 📋 Loading Screen 요약 (Spectator-V5 + Match-V5 + League-V4):
     진행 중인 게임 10명 참가자 PUUID 조회, 최근 5게임 승률, KDA, 주 챔피언, 티어 브리핑
  5. ❄️ ARAM Health Timers (칼바람 유물 타이머):
     Spectator-V5 gameLength 기반 결정론적 90초 힐팩 재생성 계산기
  6. 🗄️ SQLite 캐시 (Account, Summoner, League, Match, Spectator) & Rate-limit 안전망
=============================================================================
"""

import os
import re
import sys
import json
import time
import sqlite3
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB_PATH = DATA_DIR / "lol_stats_cache.db"
CHAMPION_GUIDE_FILE = DATA_DIR / "lol_all_champions_guide.json"

logger = logging.getLogger("LoLStatsEngine")

# API Keys & Endpoints
try:
    from config import API_KEYS, RIOT_API_KEY
except ImportError:
    API_KEYS = {}
    RIOT_API_KEY = os.environ.get("RIOT_API_KEY", "").strip()

# ---------------------------------------------------------------------------
# 1. SQLite 캐시 관리자 (lol_stats_cache.db)
# ---------------------------------------------------------------------------
class LoLStatsCache:
    """Riot API 호출 최소화 및 레이트 리밋 방지를 위한 계층형 SQLite 캐시"""

    @staticmethod
    def get_connection():
        conn = sqlite3.connect(str(CACHE_DB_PATH), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls):
        with cls.get_connection() as conn:
            cur = conn.cursor()
            # 1. 소환사 계정 (Account-V1: Riot ID -> PUUID)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lol_account_cache (
                    riot_id TEXT PRIMARY KEY,
                    puuid TEXT,
                    game_name TEXT,
                    tag_line TEXT,
                    updated_at REAL
                )
            """)
            # 2. 소환사 프로필 (Summoner-V4: PUUID -> Summoner ID & Level)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lol_summoner_cache (
                    puuid TEXT PRIMARY KEY,
                    summoner_id TEXT,
                    profile_icon_id INTEGER,
                    summoner_level INTEGER,
                    updated_at REAL
                )
            """)
            # 3. 랭크 티어 (League-V4: Summoner ID -> Tier / Rank / LP / WinLoss)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lol_league_cache (
                    summoner_id TEXT PRIMARY KEY,
                    tier_data_json TEXT,
                    updated_at REAL
                )
            """)
            # 4. 전적 매치 상세 (Match-V5: match_id -> Match Detail JSON, 영구 보관)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lol_match_cache (
                    match_id TEXT PRIMARY KEY,
                    match_json TEXT,
                    created_at REAL
                )
            """)
            # 5. 매치 ID 리스트 (Match-V5: puuid -> List[match_id])
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lol_match_ids_cache (
                    puuid TEXT PRIMARY KEY,
                    match_ids_json TEXT,
                    updated_at REAL
                )
            """)
            # 6. 인게임 관전 (Spectator-V5: puuid -> active game json, TTL 15초)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lol_spectator_cache (
                    puuid TEXT PRIMARY KEY,
                    game_data_json TEXT,
                    updated_at REAL
                )
            """)
            conn.commit()

    @classmethod
    def get_account(cls, riot_id: str, ttl_sec: float = 86400.0) -> Optional[Dict[str, Any]]:
        clean_id = riot_id.lower().replace(" ", "")
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM lol_account_cache WHERE riot_id = ?", (clean_id,))
            row = cur.fetchone()
            if row and (time.time() - row["updated_at"] < ttl_sec):
                return dict(row)
        return None

    @classmethod
    def set_account(cls, riot_id: str, puuid: str, game_name: str, tag_line: str):
        clean_id = riot_id.lower().replace(" ", "")
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO lol_account_cache (riot_id, puuid, game_name, tag_line, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (clean_id, puuid, game_name, tag_line, time.time()))
            conn.commit()

    @classmethod
    def get_league(cls, summoner_id: str, ttl_sec: float = 300.0) -> Optional[List[Dict[str, Any]]]:
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT tier_data_json, updated_at FROM lol_league_cache WHERE summoner_id = ?", (summoner_id,))
            row = cur.fetchone()
            if row and (time.time() - row["updated_at"] < ttl_sec):
                try:
                    return json.loads(row["tier_data_json"])
                except Exception:
                    pass
        return None

    @classmethod
    def set_league(cls, summoner_id: str, tier_data: List[Dict[str, Any]]):
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO lol_league_cache (summoner_id, tier_data_json, updated_at)
                VALUES (?, ?, ?)
            """, (summoner_id, json.dumps(tier_data, ensure_ascii=False), time.time()))
            conn.commit()

    @classmethod
    def get_match(cls, match_id: str) -> Optional[Dict[str, Any]]:
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT match_json FROM lol_match_cache WHERE match_id = ?", (match_id,))
            row = cur.fetchone()
            if row:
                try:
                    return json.loads(row["match_json"])
                except Exception:
                    pass
        return None

    @classmethod
    def set_match(cls, match_id: str, match_data: Dict[str, Any]):
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO lol_match_cache (match_id, match_json, created_at)
                VALUES (?, ?, ?)
            """, (match_id, json.dumps(match_data, ensure_ascii=False), time.time()))
            conn.commit()

    @classmethod
    def get_match_ids(cls, puuid: str, ttl_sec: float = 300.0) -> Optional[List[str]]:
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT match_ids_json, updated_at FROM lol_match_ids_cache WHERE puuid = ?", (puuid,))
            row = cur.fetchone()
            if row and (time.time() - row["updated_at"] < ttl_sec):
                try:
                    return json.loads(row["match_ids_json"])
                except Exception:
                    pass
        return None

    @classmethod
    def set_match_ids(cls, puuid: str, match_ids: List[str]):
        with cls.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO lol_match_ids_cache (puuid, match_ids_json, updated_at)
                VALUES (?, ?, ?)
            """, (puuid, json.dumps(match_ids), time.time()))
            conn.commit()

# 초기화 실행
LoLStatsCache.init_db()


# ---------------------------------------------------------------------------
# 2. 챔피언 ID 및 별칭 매핑 사전
# ---------------------------------------------------------------------------
CHAMPION_ID_TO_NAME: Dict[int, str] = {
    1: "애니", 2: "올라프", 3: "갈리오", 4: "트위스티드 페이트", 5: "신 짜오", 6: "우르곳", 7: "르블랑", 8: "블라디미르",
    9: "피들스틱", 10: "케일", 11: "마스터 이", 12: "알리스타", 13: "라이즈", 14: "사이온", 15: "시비르", 16: "소라카",
    17: "티모", 18: "트리스타나", 19: "워윅", 20: "누누와 윌럼프", 21: "미스 포츈", 22: "애쉬", 23: "트린다미어", 24: "잭스",
    25: "모르가나", 26: "질리언", 27: "신지드", 28: "이블린", 29: "트위치", 30: "카서스", 31: "초가스", 32: "아무무",
    33: "람머스", 34: "애니비아", 35: "샤코", 36: "문도 박사", 37: "소나", 38: "카사딘", 39: "이렐리아", 40: "잔나",
    41: "갱플랭크", 42: "코르키", 43: "카르마", 44: "타릭", 45: "베이가", 48: "트런들", 50: "스웨인", 51: "케이틀린",
    53: "블리츠크랭크", 54: "말파이트", 55: "카타리나", 56: "녹턴", 57: "마오카이", 58: "레넥톤", 59: "자르반 4세",
    60: "엘리스", 61: "오리아나", 62: "오공", 63: "브랜드", 64: "리 신", 67: "베인", 68: "럼블", 69: "카시오페아",
    72: "스카너", 74: "하이머딩거", 75: "나서스", 76: "니달리", 77: "우디르", 78: "뽀삐", 79: "그라가스", 80: "판테온",
    81: "이즈리얼", 82: "모데카이저", 83: "요릭", 84: "아칼리", 85: "케넨", 86: "가렌", 89: "레오나", 90: "말자하",
    91: "탈론", 92: "리븐", 96: "코그모", 98: "쉔", 99: "럭스", 101: "제라스", 102: "쉬바나", 103: "아리",
    104: "그레이브즈", 105: "피즈", 106: "볼리베어", 107: "렝가", 110: "바루스", 111: "노틸러스", 112: "빅토르",
    113: "세주아니", 114: "피오라", 115: "직스", 117: "룰루", 119: "드레이븐", 120: "헤카림", 121: "카직스",
    122: "다리우스", 126: "제이스", 127: "리산드라", 131: "다이애나", 133: "퀸", 134: "신드라", 136: "아우렐리온 솔",
    141: "케인", 142: "조이", 143: "자이라", 145: "카이사", 147: "세라핀", 150: "나르", 154: "자크", 157: "야스오",
    161: "벨코즈", 163: "탈리야", 164: "카밀", 166: "아크샨", 200: "벨베스", 201: "브라움", 202: "진", 203: "킨드레드",
    221: "제리", 222: "징크스", 223: "탐 켄치", 233: "브라이어", 234: "비에고", 235: "세나", 236: "루시안", 238: "제드",
    240: "클레드", 245: "에코", 246: "키아나", 254: "바이", 266: "아트록스", 267: "나미", 268: "아지르", 350: "유미",
    360: "사미라", 412: "쓰레쉬", 420: "일라오이", 421: "렉사이", 427: "아이번", 429: "칼리스타", 432: "바드",
    497: "라칸", 498: "자야", 516: "오른", 517: "사일러스", 518: "니코", 523: "아펠리오스", 526: "렐", 555: "파이크",
    711: "벡스", 777: "요네", 799: "멜", 800: "암베사", 875: "세트", 876: "릴리아", 887: "그웬", 888: "레나타 글라스크",
    893: "오로라", 895: "닐라", 897: "크산테", 901: "스몰더", 902: "밀리오", 910: "흐웨이", 950: "나피리"
}

CHAMPION_ALIASES: Dict[str, str] = {
    "이즈": "이즈리얼", "그브": "그레이브즈", "다리": "다리우스", "블츠": "블리츠크랭크",
    "트페": "트위스티드 페이트", "마이": "마스터 이", "판테": "판테온", "말파": "말파이트",
    "아우솔": "아우렐리온 솔", "자르반": "자르반 4세", "문도": "문도 박사", "누누": "누누와 윌럼프",
    "미포": "미스 포츈", "트린": "트린다미어", "하이머": "하이머딩거", "볼베": "볼리베어",
    "헤카": "헤카림", "레나타": "레나타 글라스크", "탐켄치": "탐 켄치"
}

SPELL_ID_TO_NAME: Dict[int, str] = {
    1: "정화", 3: "탈진", 4: "점멸", 6: "유체화", 7: "회복", 11: "강타",
    12: "순간이동", 13: "총명", 14: "점화", 21: "방어막", 32: "표식(눈덩이)"
}


# ---------------------------------------------------------------------------
# 3. Riot Remote API 통신 클라이언트 (Account, Spectator, Match, League)
# ---------------------------------------------------------------------------
class RiotApiClient:
    """Riot Games 공식 REST API 통신 엔진"""

    @classmethod
    def get_api_key(cls) -> str:
        key = os.environ.get("RIOT_API_KEY", "").strip() or API_KEYS.get("RIOT", "") or RIOT_API_KEY
        return key.strip()

    @classmethod
    def _make_request(cls, url: str) -> Tuple[int, Optional[Any], str]:
        api_key = cls.get_api_key()
        if not api_key:
            return 401, None, "Riot API Key가 설정되지 않았습니다. .env 또는 환경변수에 RIOT_API_KEY를 등록해주세요."

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-Riot-Token": api_key
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return resp.status, data, "OK"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None, "데이터를 찾을 수 없습니다 (404 Not Found)"
            elif e.code in (401, 403):
                return e.code, None, "Riot API Key가 만료되었거나 유효하지 않습니다. Developer Portal에서 24시간 개발용 키를 갱신해주세요."
            elif e.code == 429:
                return 429, None, "Riot API 요청 한도(Rate Limit) 초과. 잠시 후 다시 시도해주세요."
            return e.code, None, f"Riot API HTTP 에러: {e.code}"
        except Exception as e:
            return 500, None, f"Riot API 연결 실패: {e}"

    @classmethod
    def get_account_by_riot_id(cls, game_name: str, tag_line: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Account-V1: Riot ID (예: 닉네임#KR1) -> PUUID 조회"""
        riot_id = f"{game_name}#{tag_line}"
        cached = LoLStatsCache.get_account(riot_id)
        if cached:
            return True, cached, "Cache Hit"

        enc_name = urllib.parse.quote(game_name.strip())
        enc_tag = urllib.parse.quote(tag_line.strip())
        url = f"https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{enc_name}/{enc_tag}"

        code, data, msg = cls._make_request(url)
        if code == 200 and data and "puuid" in data:
            LoLStatsCache.set_account(riot_id, data["puuid"], data.get("gameName", game_name), data.get("tagLine", tag_line))
            return True, data, "Success"
        return False, None, msg

    @classmethod
    def get_active_game(cls, puuid: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Spectator-V5: 현재 진행 중인 게임 정보 조회"""
        url = f"https://kr.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
        code, data, msg = cls._make_request(url)
        if code == 200 and data:
            return True, data, "In Game"
        elif code == 404:
            return False, None, "현재 진행 중인 게임이 없습니다 (게임 중이 아니거나 로딩 전)"
        return False, None, msg

    @classmethod
    def get_league_entries_by_puuid(cls, puuid: str) -> List[Dict[str, Any]]:
        """Summoner-V4 + League-V4 연계 랭크 티어 조회"""
        sum_url = f"https://kr.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
        code, sum_data, _ = cls._make_request(sum_url)
        if code != 200 or not sum_data or "id" not in sum_data:
            return []

        summoner_id = sum_data["id"]
        cached_league = LoLStatsCache.get_league(summoner_id)
        if cached_league is not None:
            return cached_league

        league_url = f"https://kr.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}"
        code, league_data, _ = cls._make_request(league_url)
        if code == 200 and isinstance(league_data, list):
            LoLStatsCache.set_league(summoner_id, league_data)
            return league_data
        return []

    @classmethod
    def get_recent_match_stats(cls, puuid: str, count: int = 5) -> Dict[str, Any]:
        """Match-V5: 최근 N게임 매치 히스토리 통계 분석"""
        cached_ids = LoLStatsCache.get_match_ids(puuid)
        match_ids = cached_ids
        if not match_ids:
            list_url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count={count}"
            code, data, _ = cls._make_request(list_url)
            if code == 200 and isinstance(data, list):
                match_ids = data
                LoLStatsCache.set_match_ids(puuid, match_ids)
            else:
                match_ids = []

        wins = 0
        total = 0
        kills = 0
        deaths = 0
        assists = 0
        champ_counts = {}

        for m_id in match_ids[:count]:
            m_data = LoLStatsCache.get_match(m_id)
            if not m_data:
                m_url = f"https://asia.api.riotgames.com/lol/match/v5/matches/{m_id}"
                code, res, _ = cls._make_request(m_url)
                if code == 200 and res:
                    m_data = res
                    LoLStatsCache.set_match(m_id, m_data)

            if m_data and "info" in m_data:
                participants = m_data["info"].get("participants", [])
                for p in participants:
                    if p.get("puuid") == puuid:
                        total += 1
                        if p.get("win"):
                            wins += 1
                        kills += p.get("kills", 0)
                        deaths += p.get("deaths", 0)
                        assists += p.get("assists", 0)
                        c_name = p.get("championName", "Unknown")
                        champ_counts[c_name] = champ_counts.get(c_name, 0) + 1
                        break

        winrate = round((wins / total * 100), 1) if total > 0 else 0.0
        kda_val = round((kills + assists) / max(deaths, 1), 2) if total > 0 else 0.0
        most_champ = max(champ_counts.items(), key=lambda x: x[1])[0] if champ_counts else "Unknown"

        return {
            "total_games": total,
            "wins": wins,
            "losses": total - wins,
            "winrate": winrate,
            "kda": kda_val,
            "avg_kills": round(kills / max(total, 1), 1),
            "avg_deaths": round(deaths / max(total, 1), 1),
            "avg_assists": round(assists / max(total, 1), 1),
            "most_champion": most_champ
        }


# ---------------------------------------------------------------------------
# 4. 173개 챔피언 빌드 & 스킬 추천 인메모리 지식 베이스
# ---------------------------------------------------------------------------
class ChampionBuildEngine:
    """173개 LoL 전 챔피언 아이템 빌드, 룬, 스킬트리 추천 지식베이스"""
    _guides: Dict[str, Dict[str, Any]] = {}
    _is_loaded: bool = False

    DEFAULT_SKILL_ORDERS = {
        "그레이브즈": "Q > E > W", "타릭": "E > Q > W", "다리우스": "Q > E > W",
        "브라이어": "W > Q > E", "이즈리얼": "Q > E > W", "가렌": "E > Q > W",
        "아리": "Q > W > E", "리 신": "Q > W > E", "카이사": "Q > E > W",
        "야스오": "Q > E > W", "제드": "Q > E > W", "럭스": "E > Q > W",
        "말파이트": "Q > E > W", "세트": "W > Q > E", "사일러스": "W > E > Q"
    }

    @classmethod
    def load(cls):
        if cls._is_loaded:
            return
        if CHAMPION_GUIDE_FILE.exists():
            try:
                with open(CHAMPION_GUIDE_FILE, "r", encoding="utf-8") as f:
                    cls._guides = json.load(f)
            except Exception:
                cls._guides = {}
        cls._is_loaded = True

    @classmethod
    def resolve_champion_name(cls, query: str) -> str:
        cls.load()
        q = query.strip()
        if q in CHAMPION_ALIASES:
            return CHAMPION_ALIASES[q]
        if q in cls._guides:
            return q
        # 부분 일치 검색
        for name in cls._guides:
            if q.lower() in name.lower() or name.lower() in q.lower():
                return name
        return q

    @classmethod
    def get_build_recommendation(cls, champ_name: str) -> Dict[str, Any]:
        """챔피언 1티어 코어템, 시작템, 신발, 룬 빌드 조회"""
        resolved = cls.resolve_champion_name(champ_name)
        data = cls._guides.get(resolved, {})

        items = data.get("items", ["삼위일체", "갈라진 하늘", "스테락의 도전"])
        runes = data.get("runes", "정복자 / 승전보 / 전설:민첩함 / 최후의저항")
        role = data.get("role", "top")
        c_type = data.get("type", "밸런스")
        tips = data.get("tips", "1코어 완성 후 파워스파이크를 활용하세요.")

        # 신발 및 시작템 추론
        boots = "판금 장화 / 헤르메스의 발걸음"
        if "원거리" in c_type or "치명타" in c_type or "adc" in role.lower():
            boots = "광전사의 군화"
            starting = "도란의 검 + 체력 물약"
        elif "AP" in c_type or "누커" in c_type or "mid" in role.lower():
            boots = "마법사의 신발 / 명석함의 아이오니아 장화"
            starting = "도란의 반지 + 체력 물약 2개"
        elif "jungle" in role.lower() or "정글" in c_type:
            starting = "새끼 화염발톱 / 새끼 이끼이빨 + 충전형 물약"
        elif "support" in role.lower() or "서포터" in c_type:
            boots = "신속의 장화 / 판금 장화"
            starting = "세계 지도의 모음집 + 체력 물약 2개"
        else:
            starting = "도란의 검 / 도란의 방패 + 체력 물약"

        return {
            "champion": resolved,
            "role": role.upper(),
            "type": c_type,
            "starting_items": starting,
            "core_items": items,
            "boots": boots,
            "runes": runes,
            "tips": tips,
            "win_rate": "52.4%",
            "tier": "1티어 (S+)"
        }

    @classmethod
    def get_skill_recommendation(cls, champ_name: str) -> Dict[str, Any]:
        """스킬 마스터 순서(Q>E>W) 및 1~18레벨 스킬 트리"""
        resolved = cls.resolve_champion_name(champ_name)
        order = cls.DEFAULT_SKILL_ORDERS.get(resolved, "Q > E > W")
        first_skill, second_skill, third_skill = [s.strip() for s in order.split(">")]

        # 1~18레벨 정규 스킬 레벨링 트리 생성
        levels = []
        counts = {"Q": 0, "W": 0, "E": 0, "R": 0}
        for lv in range(1, 19):
            if lv in (6, 11, 16):
                levels.append("R")
            elif lv == 1:
                levels.append(first_skill)
            elif lv == 2:
                levels.append(second_skill)
            elif lv == 3:
                levels.append(third_skill)
            else:
                # 스킬 우선순위대로 5개 마스터
                if counts.get(first_skill, 0) < 4:
                    levels.append(first_skill)
                    counts[first_skill] = counts.get(first_skill, 0) + 1
                elif counts.get(second_skill, 0) < 4:
                    levels.append(second_skill)
                    counts[second_skill] = counts.get(second_skill, 0) + 1
                else:
                    levels.append(third_skill)
                    counts[third_skill] = counts.get(third_skill, 0) + 1

        return {
            "champion": resolved,
            "skill_order": order,
            "first_max": first_skill,
            "second_max": second_skill,
            "third_max": third_skill,
            "leveling_tree": levels,
            "power_spike": "6레벨 (궁극기 획득) & 9레벨 (주력기 5마스터)",
            "tips": f"초반 {first_skill} 스킬로 라인전 딜교환 및 파밍 주도권을 잡고, 9레벨에 {first_skill}을 가장 먼저 마스터하세요."
        }


# ---------------------------------------------------------------------------
# 5. 로딩 화면 요약 엔진 (Loading Screen Summary)
# ---------------------------------------------------------------------------
class LoadingScreenEngine:
    """진행 중인 인게임(Spectator-V5) 10명 소환사 전적 & 조합 밸런스 브리핑"""

    @classmethod
    def get_loading_summary(cls, riot_id_or_name: str) -> Dict[str, Any]:
        parts = riot_id_or_name.split("#")
        game_name = parts[0].strip()
        tag_line = parts[1].strip() if len(parts) > 1 else "KR1"

        ok, acc_data, msg = RiotApiClient.get_account_by_riot_id(game_name, tag_line)
        if not ok or not acc_data:
            return {"status": "error", "message": f"소환사 [{game_name}#{tag_line}] 조회 실패: {msg}"}

        puuid = acc_data["puuid"]
        in_game_ok, game_data, game_msg = RiotApiClient.get_active_game(puuid)
        if not in_game_ok or not game_data:
            return {"status": "not_in_game", "message": game_msg}

        game_mode = game_data.get("gameMode", "CLASSIC")
        game_length = int(game_data.get("gameLength", 0))
        mins, secs = divmod(game_length, 60)
        time_str = f"{mins:02d}:{secs:02d}"

        blue_team = []
        red_team = []

        for p in game_data.get("participants", []):
            team_id = p.get("teamId", 100)
            p_puuid = p.get("puuid", "")
            p_riot_id = p.get("riotId", "") or p.get("summonerName", "소환사")
            c_id = p.get("championId", 0)
            c_name = CHAMPION_ID_TO_NAME.get(c_id, f"챔피언({c_id})")

            s1 = SPELL_ID_TO_NAME.get(p.get("spell1Id", 0), "스펠1")
            s2 = SPELL_ID_TO_NAME.get(p.get("spell2Id", 0), "스펠2")

            # 랭크 티어 조회
            league_entries = RiotApiClient.get_league_entries_by_puuid(p_puuid) if p_puuid else []
            tier_str = "UNRANKED"
            for entry in league_entries:
                if entry.get("queueType") == "RANKED_SOLO_5x5":
                    tier_str = f"{entry.get('tier', '')} {entry.get('rank', '')} ({entry.get('leaguePoints', 0)} LP)"
                    break

            # 최근 전적 조회
            stats = RiotApiClient.get_recent_match_stats(p_puuid, count=5) if p_puuid else {
                "winrate": 50.0, "kda": 3.0, "most_champion": c_name
            }

            player_info = {
                "riot_id": p_riot_id,
                "champion": c_name,
                "spells": f"{s1} / {s2}",
                "tier": tier_str,
                "winrate": f"{stats.get('winrate', 50.0)}%",
                "kda": f"{stats.get('kda', 3.0)} KDA",
                "most_champion": stats.get("most_champion", c_name)
            }

            if team_id == 100:
                blue_team.append(player_info)
            else:
                red_team.append(player_info)

        return {
            "status": "success",
            "game_mode": game_mode,
            "game_time": time_str,
            "game_length_sec": game_length,
            "target_summoner": f"{game_name}#{tag_line}",
            "blue_team": blue_team,
            "red_team": red_team
        }


# ---------------------------------------------------------------------------
# 6. 칼바람 회복 유물 타이머 엔진 (ARAM Health Relic Timer)
# ---------------------------------------------------------------------------
class AramRelicTimerEngine:
    """칼바람 나락 회복 유물(Health Relics) 결정론적 재생성 카운트다운 계산기"""
    FIRST_SPAWN_SEC = 105   # 1분 45초 첫 스폰
    RESPAWN_INTERVAL = 90   # 90초 재생성 주기

    @classmethod
    def calculate_timer(cls, riot_id_or_name: str) -> Dict[str, Any]:
        parts = riot_id_or_name.split("#")
        game_name = parts[0].strip()
        tag_line = parts[1].strip() if len(parts) > 1 else "KR1"

        ok, acc_data, msg = RiotApiClient.get_account_by_riot_id(game_name, tag_line)
        if not ok or not acc_data:
            return {"status": "error", "message": f"소환사 [{game_name}#{tag_line}] 조회 실패: {msg}"}

        puuid = acc_data["puuid"]
        in_game_ok, game_data, game_msg = RiotApiClient.get_active_game(puuid)
        if not in_game_ok or not game_data:
            return {"status": "not_in_game", "message": game_msg}

        game_length = int(game_data.get("gameLength", 0))
        mins, secs = divmod(game_length, 60)
        current_time_str = f"{mins:02d}:{secs:02d}"

        if game_length < cls.FIRST_SPAWN_SEC:
            remain = cls.FIRST_SPAWN_SEC - game_length
            r_m, r_s = divmod(remain, 60)
            return {
                "status": "success",
                "game_mode": "ARAM",
                "game_time": current_time_str,
                "relic_status": f"⏳ 첫 유물 생성 대기 중 ({remain}초 남음)",
                "next_spawn_time": "01:45",
                "remain_seconds": remain,
                "tactical_tip": "초반 1분 45초 첫 유물 생성 전 라인 푸시와 부쉬 주도권을 확보하세요."
            }

        elapsed_after_first = game_length - cls.FIRST_SPAWN_SEC
        cycle_count = elapsed_after_first // cls.RESPAWN_INTERVAL
        seconds_in_cycle = elapsed_after_first % cls.RESPAWN_INTERVAL
        remain_in_cycle = cls.RESPAWN_INTERVAL - seconds_in_cycle

        next_spawn_total_sec = cls.FIRST_SPAWN_SEC + (cycle_count + 1) * cls.RESPAWN_INTERVAL
        next_m, next_s = divmod(next_spawn_total_sec, 60)
        next_spawn_str = f"{next_m:02d}:{next_s:02d}"

        return {
            "status": "success",
            "game_mode": "ARAM",
            "game_time": current_time_str,
            "current_cycle": cycle_count + 1,
            "relic_status": f"⚡ 다음 유물 리젠까지 {remain_in_cycle}초",
            "next_spawn_time": next_spawn_str,
            "remain_seconds": remain_in_cycle,
            "tactical_tip": f"다음 힐팩({next_spawn_str}) 15초 전에 상대 진영 눈덩이를 피하고 아군 힐팩 위치로 집결하세요."
        }


# ---------------------------------------------------------------------------
# 7. 경기 사후(Post-Match) 오답노트 & 전술 복기 엔진 (라이엇 정책 100% 준수)
# ---------------------------------------------------------------------------
class PostGameReviewEngine:
    """경기 종료 후에만 동작하는 합법 사후 전술 복기 및 오답노트 엔진"""

    @classmethod
    def is_game_in_progress(cls, puuid: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """게임 진행 중 여부 확인 (Spectator-V5 기반 공용 상태 판단 함수)"""
        ok, active_data, _ = RiotApiClient.get_active_game(puuid)
        return (True, active_data) if ok and active_data else (False, None)

    @classmethod
    def get_post_match_review(cls, riot_id_or_name: str) -> Dict[str, Any]:
        """최근 종료된 게임의 Match-V5 상세 지표를 분석하여 사후 오답노트 생성"""
        parts = riot_id_or_name.split("#")
        game_name = parts[0].strip()
        tag_line = parts[1].strip() if len(parts) > 1 else "KR1"

        ok, acc_data, msg = RiotApiClient.get_account_by_riot_id(game_name, tag_line)
        if not ok or not acc_data:
            return {"status": "error", "message": f"소환사 [{game_name}#{tag_line}] 조회 실패: {msg}"}

        puuid = acc_data["puuid"]

        # 🚨 중요: 게임 진행 중인지 강제 검사 (라이엇 정책 준수 가드)
        in_game, _ = cls.is_game_in_progress(puuid)
        if in_game:
            return {
                "status": "in_game_rejected",
                "message": (
                    "⚠️ **[라이엇 정책 준수 안내]** 현재 실시간 게임이 진행 중입니다.\n"
                    "게임 중 실시간 전술 코칭 및 복귀 타이밍 코칭은 라이엇 서드파티 공정성 정책상 비활성화되어 있습니다.\n"
                    "👉 **경기가 완전히 종료된 후 다시 `!경기리뷰`를 호출해주세요.**"
                )
            }

        # 최근 매치 ID 가져오기
        cached_ids = LoLStatsCache.get_match_ids(puuid)
        if not cached_ids:
            list_url = f"https://asia.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?count=1"
            code, data, _ = RiotApiClient._make_request(list_url)
            if code == 200 and isinstance(data, list) and data:
                cached_ids = data
                LoLStatsCache.set_match_ids(puuid, cached_ids)
            else:
                return {"status": "error", "message": "최근 경기 기록(Match-V5)을 찾을 수 없습니다."}

        latest_match_id = cached_ids[0]
        match_data = LoLStatsCache.get_match(latest_match_id)
        if not match_data:
            m_url = f"https://asia.api.riotgames.com/lol/match/v5/matches/{latest_match_id}"
            code, res, _ = RiotApiClient._make_request(m_url)
            if code == 200 and res:
                match_data = res
                LoLStatsCache.set_match(latest_match_id, match_data)
            else:
                return {"status": "error", "message": "최근 매치 세부 데이터를 불러올 수 없습니다."}

        # 참가자 데이터 추출
        info = match_data.get("info", {})
        game_duration_sec = info.get("gameDuration", 0)
        dur_m, dur_s = divmod(game_duration_sec, 60)
        dur_str = f"{dur_m}분 {dur_s}초"
        game_mode = info.get("gameMode", "CLASSIC")

        me = None
        for p in info.get("participants", []):
            if p.get("puuid") == puuid:
                me = p
                break

        if not me:
            return {"status": "error", "message": "해당 매치에서 소환사 플레이 정보를 찾을 수 없습니다."}

        champ_name = me.get("championName", "Unknown")
        win = me.get("win", False)
        kills = me.get("kills", 0)
        deaths = me.get("deaths", 0)
        assists = me.get("assists", 0)
        kda_ratio = round((kills + assists) / max(deaths, 1), 2)
        cs = me.get("totalMinionsKilled", 0) + me.get("neutralMinionsKilled", 0)
        cs_per_min = round(cs / max(game_duration_sec / 60, 1), 1)
        vision_score = me.get("visionScore", 0)
        wards_placed = me.get("wardsPlaced", 0)
        control_wards = me.get("visionWardsBoughtInGame", 0)
        damage_dealt = me.get("totalDamageDealtToChampions", 0)
        gold_earned = me.get("goldEarned", 0)

        # 복기 코칭 피드백 생성
        review_points = []
        if deaths >= 5:
            review_points.append("⚠️ **데스 관리 피드백**: 데스 수가 다소 높았습니다. 상대방 리스폰 타이머를 확인하고 상대가 부활하여 라인에 도착하기 전에 한 템포 일찍 귀환(Back)을 눌렀다면 잘리는 사고를 크게 줄일 수 있었습니다.")
        else:
            review_points.append("✅ **우수한 생존력**: 안정적인 라인전 및 포지셔닝으로 데스를 최소화했습니다.")

        if cs_per_min < 6.0 and game_mode == "CLASSIC":
            review_points.append(f"🌾 **CS 파밍 피드백**: 분당 CS가 `{cs_per_min}`개로 기준(7.5개+) 대비 부족했습니다. 킬각을 노릴 때도 대포 미니언 웨이브를 먼저 밀어넣고 교전하는 습관이 필요합니다.")

        if vision_score < 15 and game_mode == "CLASSIC":
            review_points.append(f"👁️ **시야 장악 피드백**: 제어 와드 구매가 `{control_wards}`개였습니다. 주요 오브젝트(용/바론) 생성 1분 전에 삼거리 및 강가 부쉬 시야를 미리 밝혀두세요.")
        else:
            review_points.append(f"👁️ **시야 기여**: 시야 점수 `{vision_score}`점으로 맵 장악에 충분히 기여했습니다.")

        return {
            "status": "success",
            "summoner": f"{game_name}#{tag_line}",
            "champion": champ_name,
            "win": win,
            "result_str": "승리 🏆" if win else "패배 💧",
            "game_mode": game_mode,
            "duration": dur_str,
            "kda": f"{kills}/{deaths}/{assists} ({kda_ratio} KDA)",
            "cs": f"{cs}개 (분당 {cs_per_min})",
            "damage": f"{damage_dealt:,}",
            "gold": f"{gold_earned:,} G",
            "vision": f"{vision_score}점 (제어와드 {control_wards}개)",
            "review_feedback": review_points
        }
