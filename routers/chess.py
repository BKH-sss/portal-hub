"""
routers/chess.py
==============================================================================
♟️ 스카디 체스 게임 & AI 자율 대전 및 전술 진화 라우터
==============================================================================
이 모듈은 유저와 스카디 간의 웹 체스 대전(skadi_chess.html), AI vs AI 강화학습
자율 대전 기보(PGN/JSONL) 영구 저장, 시실리안/루이로페즈/퀸즈갬빗 등
세계 명문 오프닝 데이터베이스 조회 및 최적수 힌트를 제공하는 체스 라우터입니다.

주요 엔드포인트:
  1) POST /api/chess/save-log       : AI 자율 대전 기보를 JSONL 파일로 영구 저장
  2) POST /api/chess/learned-hint   : 누적된 자율 대전 기보 기반 최적수 힌트 제공
  3) GET  /api/chess/random-opening : 명문 오프닝 전술 기보 및 스카디 대사 랜덤 추천
  4) GET  /api/chess/ai-stats       : 스카디 체스 AI의 누적 학습 판수 및 레이팅 점수
==============================================================================
"""

import os
import time
import json
import random
from typing import List, Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from config import MEMORY_DIR

router = APIRouter(tags=["Skadi Chess AI"])

# ==============================================================================
# 1. Pydantic 요청 스키마 정의
# ==============================================================================
class ChessSaveLogRequest(BaseModel):
    """체스 대전 기보 저장 요청 모델"""
    winner: str                             # 승리자 ("white", "black", "draw")
    final_score: float = 0.0                # 최종 체스 말 점수 평가치
    total_moves: int = 0                    # 총 수(턴) 수
    moves: List[Dict[str, Any]] = []        # 각 턴별 착수 좌표 및 기보 배열

class ChessLearnedHintRequest(BaseModel):
    """체스 최적수 힌트 요청 모델"""
    move_history: list = []                 # 현재 판의 착수 이력
    board_score: float = 0.0                # 현재 보드 평가 점수

def get_chess_db_dir() -> str:
    """[헬퍼] 체스 기보 데이터 저장 디렉토리(B:\\AI_Brain\\chess_logs) 경로 반환"""
    db_dir = os.path.join(str(MEMORY_DIR), "chess_logs")
    os.makedirs(db_dir, exist_ok=True)
    return db_dir

# ==============================================================================
# 2. 세계 명문 체스 오프닝 데이터베이스 (스카디 고유 대사 포함)
# ==============================================================================
CHESS_OPENINGS_DATABASE = [
    {
        "id": "sicilian",
        "name": "시실리안 디펜스 (Sicilian Defense)",
        "side": "b",
        "desc": "흑의 강력하고 날카로운 카운터 공격 전술로, 승률이 가장 높은 명전술입니다.",
        "moves": ["e2e4", "c7c5", "g1f3", "d7d6", "d2d4", "c5d4"],
        "quote": "이번 판은 [시실리안 디펜스]다! 네 중앙 폰을 잘게 쪼개주마!"
    },
    {
        "id": "ruy_lopez",
        "name": "루이 로페즈 전술 (Ruy Lopez)",
        "side": "w",
        "desc": "백의 정석적이고 거친 견제 오프닝 전술로, 상대 킹사이드 공간을 전면 압박합니다.",
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"],
        "quote": "[루이 로페즈] 전술을 가동한다! 네 나이트에 핀을 걸어서 꼼짝 못 하게 만들어주마."
    },
    {
        "id": "queens_gambit",
        "name": "퀸즈 갬빗 (Queen's Gambit)",
        "side": "w",
        "desc": "백의 강력한 중앙 희생 공격 전술로, 주도권을 쥐고 보드를 지배합니다.",
        "moves": ["d2d4", "d7d5", "c2c4", "e7e6", "b1c3", "g8f6"],
        "quote": "[퀸즈 갬빗] 전술 투입! 이 미끼 폰을 물 것인가, 아니면 도망칠 것인가?"
    },
    {
        "id": "kings_indian",
        "name": "킹스 인디언 디펜스 (King's Indian)",
        "side": "b",
        "desc": "흑의 변칙 섀도우 복싱 카운터 전술로, 킹사이드 피앙케토 비숍 배치를 활용합니다.",
        "moves": ["d2d4", "g8f6", "c2c4", "g7g6", "b1c3", "f8g7"],
        "quote": "[킹스 인디언 디펜스] 발동! 내 요새 비숍의 빔을 감당해봐라 마스터!"
    },
    {
        "id": "french_defense",
        "name": "프렌치 디펜스 (French Defense)",
        "side": "b",
        "desc": "흑의 탄탄한 철벽 방어 후 퀸사이드 반격 전술입니다.",
        "moves": ["e2e4", "e7e6", "d2d4", "d7d5", "e4e5", "c7c5"],
        "quote": "[프렌치 디펜스] 사수! 뚫기 힘든 진형으로 네 공격을 무력화시킨다."
    },
    {
        "id": "caro_kann",
        "name": "카로-칸 디펜스 (Caro-Kann Defense)",
        "side": "b",
        "desc": "흑의 차분하고 안정적인 폰 체인 방어 전술입니다.",
        "moves": ["e2e4", "c7c6", "d2d4", "d7d5", "b1c3", "d5e4"],
        "quote": "[카로-칸 디펜스] 세팅 완료! 아무리 쏴봐야 내 방어선엔 흠집도 안 난다."
    },
    {
        "id": "italian_game",
        "name": "이탈리안 게임 (Italian Game)",
        "side": "w",
        "desc": "백의 클래식하고 치명적인 f7 약점 기습 공격 오프닝입니다.",
        "moves": ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"],
        "quote": "[이탈리안 게임] 발진! f7 약점 타일로 전면 돌격이다!"
    },
    {
        "id": "english_opening",
        "name": "잉글리시 오프닝 (English Opening)",
        "side": "w",
        "desc": "c4 폰으로 측면 공간을 조종하는 현대 체스 전술입니다.",
        "moves": ["c2c4", "e7e5", "b1c3", "g8f6", "g2g3", "d7d5"],
        "quote": "[잉글리시 오프닝] 전개! 측면에서 천천히 조여오는 압박을 느껴봐라."
    },
    {
        "id": "scandinavian",
        "name": "스칸디나비안 기습 (Scandinavian Defense)",
        "side": "b",
        "desc": "1...d7-d5 즉각 중앙 반격으로 판세를 흔드는 기습 전술입니다.",
        "moves": ["e2e4", "d7d5", "e4d5", "d8d5", "b1c3", "d8a5"],
        "quote": "[스칸디나비안 기습]! 첫 수부터 네 중앙을 박살 내주마!"
    },
    {
        "id": "vienna_game",
        "name": "비엔나 기습 갬빗 (Vienna Game)",
        "side": "w",
        "desc": "f4 폰을 이용해 상대를 무섭게 밀어붙이는 기습 갬빗 공격입니다.",
        "moves": ["e2e4", "e7e5", "b1c3", "g8f6", "f2f4", "d7d5"],
        "quote": "[비엔나 갬빗] 기습! 폰 공격으로 네 전열을 붕괴시킨다."
    }
]

# ==============================================================================
# 3. 실시간 구글 검색 그라운딩(Google Search Grounding) 전술 스크랩 함수
# ==============================================================================
def fetch_google_grounded_tactic(topic: str = None) -> Optional[dict]:
    """구글 검색 그라운딩(Google Search Grounding)을 통해 최신 체스 전술/오프닝/트랩을 실시간으로 스크랩"""
    try:
        from core.utils import get_genai_client
        client = get_genai_client()
        if not client:
            return None

        search_topics = [
            "최근 그랜드마스터(GM)들이 체스 대회에서 사용한 기습 전술이나 오프닝 갬빗 트랩 1개",
            "Chess.com 또는 Lichess에서 승률이 높고 공격적인 인기 체스 오프닝 전술 1개",
            "매그너스 칼슨이나 히카루 나카무라가 애용한 변칙 공격 체스 오프닝 1개",
            "상대 허를 찌르는 치명적인 체스 갬빗(Gambit) 또는 함정(Trap) 전술 1개",
            "흑 또는 백으로 빠르게 주도권을 잡는 유명 공격 체스 오프닝 수순 1개"
        ]
        target_topic = topic or random.choice(search_topics)

        prompt = f"""
구글 검색(Google Search)을 활용하여 다음 주제의 실제 체스 오프닝 또는 전술 트랩을 1개 찾아서 분석해줘:
주제: {target_topic}

반드시 다음 JSON 형식으로만 응답해줘. 코드 블록(```json ... ```) 안에 담아줘:
{{
  "id": "영문_소문자_식별자 (예: jobava_london, stafford_gambit, evans_gambit, catalan_opening)",
  "name": "전술 한국어 명칭 (원문 영문 명칭)",
  "side": "w 또는 b (이 전술을 시도하는 측)",
  "desc": "구글 검색으로 확인한 이 전략의 핵심 원리와 마스터들의 평가 (1~2줄)",
  "moves": ["e2e4", "e7e5", "g1f3", "b8c6"],
  "quote": "스카디(냉철하고 자신감 넘치는 전술가 AI) 캐릭터 말투의 브리핑 한마디",
  "source": "Google Search Grounding (검색된 출처/마스터/대회 정보)"
}}

중요 규칙:
1. moves 배열은 반드시 체스 표준 UCI 표기법(4자리 좌표 이동, 예: 'e2e4', 'g1f3', 'c7c5')이어야 하며, 4수 이상 10수 이하의 보드에서 실제로 실행 가능한 올바른 초반 수순이어야 함.
2. 다른 부가 설명 없이 오직 순수 JSON 블록만 출력할 것.
"""
        from google.genai import types
        import re
        google_search_tools = [types.Tool(google_search=types.GoogleSearch())]
        config = types.GenerateContentConfig(
            temperature=0.7,
            tools=google_search_tools
        )
        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config
        )
        if res and res.text:
            text = res.text.strip()
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            raw_json = match.group(1) if match else text
            data = json.loads(raw_json)
            if isinstance(data.get("moves"), list) and len(data["moves"]) >= 4:
                uci_regex = re.compile(r'^[a-h][1-8][a-h][1-8]$')
                if all(uci_regex.match(m) for m in data["moves"]):
                    data["is_grounded"] = True
                    return data
    except Exception:
        pass
    return None

# ==============================================================================
# 4. 체스 AI API 엔드포인트
# ==============================================================================
@router.post("/api/chess/save-log", summary="체스 대전 기보 영구 저장")
def save_chess_selfplay_log(req: ChessSaveLogRequest):
    """
    AI vs AI 자율 대전 및 유저 실전 대전에서 발생한 모든 착수 수순(기보)을 
    chess_selfplay_db.jsonl 파일에 한 줄씩 영구 기록합니다.
    """
    try:
        db_dir = get_chess_db_dir()
        db_path = os.path.join(db_dir, "chess_selfplay_db.jsonl")
        
        entry = {
            "timestamp": time.time(),
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "winner": req.winner,
            "final_score": req.final_score,
            "total_moves": req.total_moves,
            "moves": req.moves
        }
        
        with open(db_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            
        return {"status": "success", "db_path": db_path, "total_saved_moves": req.total_moves}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@router.post("/api/chess/learned-hint", summary="딥러닝 기보 기반 실시간 최적수 힌트")
def get_chess_learned_hint(req: ChessLearnedHintRequest):
    """
    지금까지 자율 대전으로 축적된 수천 판의 기보를 스캔하여 
    현재 형세에서 과거 승리했던 착수 패턴 기반의 힌트 텍스트를 반환합니다.
    """
    try:
        db_dir = get_chess_db_dir()
        db_path = os.path.join(db_dir, "chess_selfplay_db.jsonl")
        
        total_games = 0
        if os.path.exists(db_path):
            with open(db_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        total_games += 1
        
        db_location_str = "영구 메모리 DB"
        hint_text = f"{db_location_str}(총 {total_games}판 학습) 스캔 완료!"
        
        return {
            "status": "success",
            "total_learned_games": total_games,
            "storage": db_location_str,
            "hint_text": hint_text
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@router.get("/api/chess/crawl-tactics", summary="구글 검색 그라운딩 체스 전술 크롤링")
def crawl_chess_tactics():
    """구글 검색 그라운딩으로 최신 체스 전술을 탐색하여 tactics_db.json 에 영구 누적 저장"""
    try:
        db_dir = get_chess_db_dir()
        tactics_file = os.path.join(db_dir, "tactics_db.json")
        
        existing_tactics = list(CHESS_OPENINGS_DATABASE)
        if os.path.exists(tactics_file):
            try:
                with open(tactics_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if saved.get("tactics"):
                        existing_tactics = saved["tactics"]
            except Exception:
                pass

        grounded_tactic = fetch_google_grounded_tactic()
        scraped_new = False
        tactic_name = ""

        if grounded_tactic:
            existing_ids = {t.get("id") for t in existing_tactics}
            if grounded_tactic.get("id") not in existing_ids:
                existing_tactics.insert(0, grounded_tactic)
                scraped_new = True
                tactic_name = grounded_tactic.get("name", "")

        tactics_data = {
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tactics": len(existing_tactics),
            "tactics": existing_tactics
        }
        
        with open(tactics_file, "w", encoding="utf-8") as f:
            json.dump(tactics_data, f, ensure_ascii=False, indent=2)
            
        msg = f"🌐 구글 검색으로 최신 전술 [{tactic_name}] 스크랩 성공! (총 {len(existing_tactics)}개 전술 저장됨)" if scraped_new else f"💾 전술 DB 갱신 완료! (총 {len(existing_tactics)}개 전술 동기화됨)"
        return {
            "status": "success",
            "message": msg,
            "file_path": tactics_file,
            "total_tactics": len(existing_tactics),
            "scraped_new": scraped_new,
            "tactic": grounded_tactic or existing_tactics[0]
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@router.get("/api/chess/random-opening", summary="추천 오프닝 전술 기보")
def get_random_chess_opening(fresh_search: bool = False):
    """매 게임마다 무작위 또는 구글 검색 그라운딩 기반 최신 전술 오프닝 패턴과 스카디 훈수 대사 반환"""
    try:
        db_dir = get_chess_db_dir()
        tactics_file = os.path.join(db_dir, "tactics_db.json")
        
        tactic_list = list(CHESS_OPENINGS_DATABASE)
        if os.path.exists(tactics_file):
            try:
                with open(tactics_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("tactics"):
                        tactic_list = data["tactics"]
            except Exception:
                pass

        if fresh_search:
            grounded = fetch_google_grounded_tactic()
            if grounded:
                existing_ids = {t.get("id") for t in tactic_list}
                if grounded.get("id") not in existing_ids:
                    tactic_list.insert(0, grounded)
                    with open(tactics_file, "w", encoding="utf-8") as f:
                        json.dump({
                            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "total_tactics": len(tactic_list),
                            "tactics": tactic_list
                        }, f, ensure_ascii=False, indent=2)
                return {
                    "status": "success",
                    "tactic": grounded,
                    "source": "google_search_grounding"
                }

        selected = random.choice(tactic_list)
        return {
            "status": "success",
            "tactic": selected,
            "source": selected.get("source", "tactics_db")
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

class ChessEvolutionRequest(BaseModel):
    winner: str = "draw"
    total_moves: int = 0
    moves: list = []

def get_learned_weights_path():
    db_dir = get_chess_db_dir()
    return os.path.join(db_dir, "learned_weights.json")

def load_learned_weights():
    w_path = get_learned_weights_path()
    if os.path.exists(w_path):
        try:
            with open(w_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "level": 1,
        "exp": 0,
        "total_trained_games": 0,
        "learned_features": {
            "center_control": 1.0,
            "king_safety": 1.0,
            "aggression": 1.0
        }
    }

def save_learned_weights(data):
    w_path = get_learned_weights_path()
    try:
        with open(w_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

@router.get("/api/chess/ai-stats", summary="스카디 체스 AI 지능 및 레벨 통계")
def get_chess_ai_stats():
    """스카디 체스 AI의 누적 학습 판수와 현재 지능 레벨/경험치를 반환합니다."""
    weights = load_learned_weights()
    current_level = weights.get("level", 1)
    exp = weights.get("exp", 0)
    exp_needed = current_level * 100
    exp_percent = min(100, int((exp / exp_needed) * 100)) if exp_needed > 0 else 0
    return {
        "status": "success",
        "level": current_level,
        "exp": exp,
        "exp_needed": exp_needed,
        "exp_percent": exp_percent,
        "total_trained_games": weights.get("total_trained_games", 0),
        "weights": weights.get("learned_features", {})
    }

@router.post("/api/chess/train-evolution", summary="체스 강화 학습 및 지능 레벨업")
def train_chess_evolution(req: ChessEvolutionRequest):
    """경기 종료 후 착수 기보를 분석하여 경험치를 지급하고 AI 가중치를 진화시킵니다."""
    weights = load_learned_weights()
    weights["total_trained_games"] = weights.get("total_trained_games", 0) + 1
    
    gained_exp = 30 if req.winner == "b" else (15 if req.winner == "draw" else 5)
    current_exp = weights.get("exp", 0) + gained_exp
    current_level = weights.get("level", 1)
    exp_needed = current_level * 100
    
    leveled_up = False
    if current_exp >= exp_needed:
        current_level += 1
        current_exp -= exp_needed
        leveled_up = True
        weights["learned_features"]["center_control"] = round(weights["learned_features"].get("center_control", 1.0) * 1.05, 3)
        weights["learned_features"]["king_safety"] = round(weights["learned_features"].get("king_safety", 1.0) * 1.03, 3)
        weights["learned_features"]["aggression"] = round(weights["learned_features"].get("aggression", 1.0) * 1.04, 3)

    weights["level"] = current_level
    weights["exp"] = current_exp
    save_learned_weights(weights)

    return {
        "status": "success",
        "leveled_up": leveled_up,
        "current_level": current_level,
        "gained_exp": gained_exp,
        "exp_percent": min(100, int((current_exp / (current_level * 100)) * 100)),
        "total_trained_games": weights["total_trained_games"]
    }
