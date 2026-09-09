"""
lol_live_game_tracker.py
=============================================================================
⚔️ JARVIS / SKADI: 롤(LoL) 실시간 인게임 라이브 데이터 & 전술 타이머 엔진
=============================================================================
- 역할:
    1. Riot 공식 라이브 클라이언트 API (https://127.0.0.1:2999/liveclientdata/allgamedata) 초저지연 연동
    2. 적군 5인 소환사 주문(점멸/텔포/점화 등) 원클릭/단축키/음성 실시간 쿨타임 추적 및 15초 전 사전 음성 예고
    3. 협곡 5대 오브젝트(용, 바론, 유충, 전령, 장로) 자동 리젠 타이머 & 60초/30초 전 브리핑
    4. 실시간 팀 골드 격차(Gold Lead/Deficit), 분당 CS(CS/min), 맞라이너 격차 연산
    5. 골드 파워 스파이크(1100G, 1300G, 3000G) 황금 귀환 음성 알리미
    6. FastAPI APIRouter 내장 (/api/lol/live/*)
=============================================================================
"""

import os
import time
import json
import logging
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 로깅 설정
logger = logging.getLogger("LoLLiveGameTracker")

router = APIRouter(prefix="/api/lol/live", tags=["LoL Live Game & Spell/Objective Tracker"])

# 스펠 기본 쿨타임 (초)
SPELL_COOLDOWNS: Dict[str, int] = {
    "SummonerFlash": 300,        # 점멸
    "SummonerTeleport": 360,     # 순간이동 (언리쉬드 전 기준)
    "SummonerDot": 180,          # 점화
    "SummonerExhaust": 210,      # 탈진
    "SummonerHeal": 240,         # 회복
    "SummonerHaste": 210,        # 유체화
    "SummonerBoost": 210,        # 정화
    "SummonerBarrier": 180,      # 방어막
    "SummonerSmite": 90,         # 강타
    "SummonerSnowball": 80,      # 표식(눈덩이)
    "SummonerMana": 240,         # 총명
}

# 스펠 한글 이름 매핑
SPELL_NAME_KO: Dict[str, str] = {
    "SummonerFlash": "점멸",
    "SummonerTeleport": "순간이동",
    "SummonerDot": "점화",
    "SummonerExhaust": "탈진",
    "SummonerHeal": "회복",
    "SummonerHaste": "유체화",
    "SummonerBoost": "정화",
    "SummonerBarrier": "방어막",
    "SummonerSmite": "강타",
    "SummonerSnowball": "눈덩이",
    "SummonerMana": "총명",
}

class SpellUseRequest(BaseModel):
    champion_name: str = Field(..., description="적 챔피언 이름 (예: Ahri, 아리 또는 1~5번 인덱스)")
    spell_name: str = Field("SummonerFlash", description="스펠 식별자 또는 이름 (Flash, Teleport, Ignite 등)")
    custom_cooldown_sec: Optional[int] = Field(None, description="수동 쿨타임 지정 (초)")

class SpellResetRequest(BaseModel):
    champion_name: str = Field(..., description="적 챔피언 이름")
    spell_name: Optional[str] = Field(None, description="특정 스펠 또는 None 시 전체 초기화")


class LoLLiveGameTracker:
    """
    Riot Live Client Data API (Port 2999)와 실시간 통신하여
    스펠 쿨타임, 오브젝트 카운트다운, 골드 격차, CS/분을 관리하는 싱글톤 엔진
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LoLLiveGameTracker, cls).__new__(cls)
                cls._instance._init_tracker()
            return cls._instance

    def _init_tracker(self):
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 실시간 인게임 데이터 캐시
        self.in_game = False
        self.game_time: float = 0.0
        self.game_mode: str = "CLASSIC"
        self.map_name: str = "소환사의 협곡"

        # 플레이어 정보
        self.active_player: Dict[str, Any] = {}
        self.my_team: str = "ORDER"   # ORDER (블루) vs CHAOS (레드)
        self.my_champion: str = ""
        self.my_summoner_name: str = ""
        self.all_players: List[Dict[str, Any]] = []
        self.enemy_players: List[Dict[str, Any]] = []
        self.ally_players: List[Dict[str, Any]] = []

        # 스펠 쿨타임 상태: { champ_name: { spell_key: { cooldown_total, used_at_game_time, expires_at_game_time, remaining_sec, is_ready, warned_15s } } }
        self.enemy_spell_trackers: Dict[str, Dict[str, Any]] = {}

        # 오브젝트 타이머: { object_type: { name, next_spawn_game_time, remaining_sec, is_alive, count } }
        self.objectives: Dict[str, Any] = {
            "DRAGON": {"name": "드래곤", "next_spawn_game_time": 300.0, "remaining_sec": 300, "is_alive": False, "count": 0, "dragon_type": "Normal"},
            "BARON": {"name": "내셔 남작", "next_spawn_game_time": 1200.0, "remaining_sec": 1200, "is_alive": False, "count": 0},
            "HERALD": {"name": "협곡의 전령", "next_spawn_game_time": 840.0, "remaining_sec": 840, "is_alive": False, "expired": False},
            "VOIDGRUBS": {"name": "공허 유충", "next_spawn_game_time": 300.0, "remaining_sec": 300, "is_alive": False, "count": 0, "batches": 0},
            "ELDER": {"name": "장로 드래곤", "next_spawn_game_time": 0.0, "remaining_sec": 0, "is_alive": False, "count": 0}
        }

        # 경제 & 지표
        self.team_gold: Dict[str, float] = {"ORDER": 0.0, "CHAOS": 0.0}
        self.gold_diff: float = 0.0  # 아군 기준 (+는 리드, -는 열세)
        self.my_cs_per_min: float = 0.0
        self.lane_opponent_champ: str = ""
        self.lane_cs_diff: int = 0

        # 이벤트 히스토리
        self.processed_event_ids: set = set()
        self.last_gold_notified: int = 0

        # 백그라운드 워커 시작
        self.start()

    def start(self):
        """백그라운드 폴링 스레드 시작"""
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._polling_loop, daemon=True, name="LoLLiveTrackerThread")
        self._thread.start()
        logger.info("⚔️ [LoL Live Tracker] 실시간 인게임 라이브 데이터 엔진 가동 완료")

    def stop(self):
        """엔진 정지"""
        self.is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("🛑 [LoL Live Tracker] 라이브 데이터 엔진 정지")

    def _polling_loop(self):
        """0.8초 주기로 Riot Live Client API 폴링"""
        while not self._stop_event.is_set():
            try:
                self._update_live_data()
            except Exception as e:
                logger.debug(f"[Live Tracker Error] {e}")
            time.sleep(0.8)

    def _update_live_data(self):
        """API 호출 및 내부 상태 업데이트"""
        try:
            res = requests.get(
                "https://127.0.0.1:2999/liveclientdata/allgamedata",
                verify=False,
                timeout=0.7
            )
            if res.status_code != 200:
                self.in_game = False
                return

            data = res.json()
            self.in_game = True

            # 1. 게임 기본 정보
            game_data = data.get("gameData", {})
            self.game_time = float(game_data.get("gameTime", 0.0))
            self.game_mode = str(game_data.get("gameMode", "CLASSIC")).upper()
            map_num = game_data.get("mapNumber", 11)
            self.map_name = "칼바람 나락" if (map_num == 12 or "ARAM" in self.game_mode) else "소환사의 협곡"

            # 2. 내 정보 및 소속 팀
            active_p = data.get("activePlayer", {})
            self.active_player = active_p
            self.my_summoner_name = active_p.get("summonerName", "")
            current_gold = float(active_p.get("currentGold", 0.0))

            # 3. 전체 플레이어 파싱
            all_p = data.get("allPlayers", [])
            self.all_players = all_p
            
            # 내 팀 식별
            for p in all_p:
                if p.get("summonerName") == self.my_summoner_name or (not self.my_summoner_name and p.get("championName") == self.my_champion):
                    self.my_team = p.get("team", "ORDER")
                    self.my_champion = p.get("championName", "")
                    break

            # 아군 / 적군 분리 및 골드 집계
            enemy_list = []
            ally_list = []
            gold_totals = {"ORDER": 0.0, "CHAOS": 0.0}

            for p in all_p:
                p_team = p.get("team", "ORDER")
                # 대략적인 골드 계산: items 가격 합산 + 현재 레벨 비례 기본 골드
                scores = p.get("scores", {})
                kills = scores.get("kills", 0)
                assists = scores.get("assists", 0)
                cs = scores.get("creepScore", 0)
                
                # 대략적인 총 획득 골드 추정치
                est_gold = 500 + (kills * 300) + (assists * 100) + (cs * 20) + (self.game_time * 2.04)
                gold_totals[p_team] += est_gold

                if p_team == self.my_team:
                    ally_list.append(p)
                else:
                    enemy_list.append(p)
                    # 적 스펠 트래커 초기화/유지
                    self._sync_enemy_spells(p)

            self.ally_players = ally_list
            self.enemy_players = enemy_list
            self.team_gold = gold_totals

            # 골드 격차 계산 (아군 - 적군)
            ally_gold = gold_totals.get(self.my_team, 0.0)
            enemy_team_key = "CHAOS" if self.my_team == "ORDER" else "ORDER"
            enemy_gold = gold_totals.get(enemy_team_key, 0.0)
            self.gold_diff = round(ally_gold - enemy_gold, 0)

            # 분당 CS 계산
            if self.game_time > 60:
                my_cs = 0
                for p in ally_list:
                    if p.get("championName") == self.my_champion or p.get("summonerName") == self.my_summoner_name:
                        my_cs = p.get("scores", {}).get("creepScore", 0)
                        break
                self.my_cs_per_min = round(my_cs / (self.game_time / 60.0), 1)

            # 4. 스펠 쿨다운 실시간 갱신 & 15초 전 음성 예고
            self._update_spell_countdowns()

            # 5. 인게임 이벤트(용/바론 처치 등) 및 오브젝트 타이머 갱신
            events_data = data.get("events", {}).get("Events", [])
            self._process_events(events_data)
            self._update_objective_countdowns()

            # 6. 골드 파워 스파이크 & 황금 귀환 알림
            self._check_gold_power_spikes(current_gold)

        except Exception as e:
            self.in_game = False

    def _sync_enemy_spells(self, enemy_player: Dict[str, Any]):
        """적 챔피언의 소환사 주문 목록을 트래커 사전에 동기화"""
        champ_name = enemy_player.get("championName", "Unknown")
        raw_spells = enemy_player.get("summonerSpells", {})

        if champ_name not in self.enemy_spell_trackers:
            self.enemy_spell_trackers[champ_name] = {}

        for slot_key in ["summonerSpellOne", "summonerSpellTwo"]:
            spell_obj = raw_spells.get(slot_key, {})
            raw_name = spell_obj.get("rawDescription", "")
            disp_name = spell_obj.get("displayName", "")
            
            # 스펠 키 추출 (SummonerFlash 등)
            matched_spell = "SummonerFlash"
            for k in SPELL_COOLDOWNS.keys():
                if k.lower() in raw_name.lower() or k.lower() in disp_name.lower():
                    matched_spell = k
                    break

            ko_name = SPELL_NAME_KO.get(matched_spell, matched_spell)
            base_cd = SPELL_COOLDOWNS.get(matched_spell, 300)

            if matched_spell not in self.enemy_spell_trackers[champ_name]:
                self.enemy_spell_trackers[champ_name][matched_spell] = {
                    "spell_key": matched_spell,
                    "name_ko": ko_name,
                    "slot": slot_key,
                    "cooldown_total": base_cd,
                    "used_at_game_time": 0.0,
                    "expires_at_game_time": 0.0,
                    "remaining_sec": 0,
                    "is_ready": True,
                    "warned_15s": False
                }

    def _update_spell_countdowns(self):
        """적 스펠 쿨다운 남은 시간 계산 및 15초 전 사전 음성 예고"""
        for champ_name, spells in self.enemy_spell_trackers.items():
            for spell_key, info in spells.items():
                if not info["is_ready"]:
                    remaining = int(max(0, info["expires_at_game_time"] - self.game_time))
                    info["remaining_sec"] = remaining

                    # 15초 전 사전 예고
                    if remaining <= 15 and remaining > 0 and not info["warned_15s"]:
                        info["warned_15s"] = True
                        self._trigger_voice_alert(
                            "SPELL_READY_SOON",
                            f"적 {champ_name}의 {info['name_ko']}이 15초 뒤 돌아옵니다! 타이밍 주의하세요!",
                            {"champ": champ_name, "spell": info["name_ko"], "remaining": remaining}
                        )

                    # 쿨타임 완료
                    if remaining <= 0:
                        info["is_ready"] = True
                        info["remaining_sec"] = 0
                        info["warned_15s"] = False

    def mark_spell_used(self, champion_query: str, spell_query: str = "Flash", custom_cd: Optional[int] = None) -> Dict[str, Any]:
        """
        적 챔피언의 스펠 사용을 등록하고 쿨타임 카운트다운을 시작합니다.
        (웹 HUD 버튼 클릭, 단축키 Alt+1~5, 음성 인식 등으로 호출)
        """
        target_champ = self._find_champion_name(champion_query)
        if not target_champ:
            return {"status": "error", "message": f"적 챔피언 '{champion_query}'을(를) 찾을 수 없습니다."}

        # 스펠 찾기
        matched_spell_key = "SummonerFlash"
        query_lower = spell_query.lower()
        if "tele" in query_lower or "텔" in query_lower:
            matched_spell_key = "SummonerTeleport"
        elif "ignite" in query_lower or "점화" in query_lower:
            matched_spell_key = "SummonerDot"
        elif "exhaust" in query_lower or "탈진" in query_lower:
            matched_spell_key = "SummonerExhaust"
        elif "heal" in query_lower or "힐" in query_lower or "회복" in query_lower:
            matched_spell_key = "SummonerHeal"
        elif "ghost" in query_lower or "유체" in query_lower:
            matched_spell_key = "SummonerHaste"
        elif "cleanse" in query_lower or "정화" in query_lower:
            matched_spell_key = "SummonerBoost"
        elif "barrier" in query_lower or "방어" in query_lower:
            matched_spell_key = "SummonerBarrier"

        champ_spells = self.enemy_spell_trackers.get(target_champ, {})
        if matched_spell_key not in champ_spells:
            # 강제 등록
            ko_name = SPELL_NAME_KO.get(matched_spell_key, matched_spell_key)
            champ_spells[matched_spell_key] = {
                "spell_key": matched_spell_key,
                "name_ko": ko_name,
                "slot": "manual",
                "cooldown_total": SPELL_COOLDOWNS.get(matched_spell_key, 300),
                "used_at_game_time": 0.0,
                "expires_at_game_time": 0.0,
                "remaining_sec": 0,
                "is_ready": True,
                "warned_15s": False
            }
            self.enemy_spell_trackers[target_champ] = champ_spells

        spell_info = champ_spells[matched_spell_key]
        cd_total = custom_cd if custom_cd is not None else spell_info["cooldown_total"]
        spell_info["cooldown_total"] = cd_total
        spell_info["used_at_game_time"] = self.game_time
        spell_info["expires_at_game_time"] = self.game_time + cd_total
        spell_info["remaining_sec"] = cd_total
        spell_info["is_ready"] = False
        spell_info["warned_15s"] = False

        # 음성 알림 발화
        spell_name_ko = spell_info["name_ko"]
        mins = cd_total // 60
        secs = cd_total % 60
        time_str = f"{mins}분 {secs}초" if secs > 0 else f"{mins}분"
        
        self._trigger_voice_alert(
            "SPELL_USED",
            f"적 {target_champ} {spell_name_ko} 사용 확인! 쿨타임 {time_str} 동안 노{spell_name_ko}입니다!",
            {"champ": target_champ, "spell": spell_name_ko, "cooldown": cd_total}
        )

        return {
            "status": "success",
            "champion": target_champ,
            "spell": matched_spell_key,
            "name_ko": spell_name_ko,
            "cooldown_sec": cd_total,
            "expires_game_time": spell_info["expires_at_game_time"]
        }

    def reset_spell(self, champion_query: str, spell_query: Optional[str] = None) -> Dict[str, Any]:
        """스펠 쿨타임 즉시 초기화 (Ready 상태로 변경)"""
        target_champ = self._find_champion_name(champion_query)
        if not target_champ:
            return {"status": "error", "message": f"적 챔피언 '{champion_query}'을(를) 찾을 수 없습니다."}

        spells = self.enemy_spell_trackers.get(target_champ, {})
        for k, info in spells.items():
            if spell_query is None or spell_query.lower() in k.lower() or spell_query in info.get("name_ko", ""):
                info["is_ready"] = True
                info["remaining_sec"] = 0
                info["warned_15s"] = False

        return {"status": "success", "champion": target_champ, "message": "스펠 쿨타임이 초기화되었습니다."}

    def _find_champion_name(self, query: str) -> Optional[str]:
        """숫자 인덱스(1~5) 또는 챔피언 이름 매칭"""
        query_str = str(query).strip()
        if query_str.isdigit():
            idx = int(query_str) - 1
            if 0 <= idx < len(self.enemy_players):
                return self.enemy_players[idx].get("championName")
        
        # 이름 부분 일치 검색
        for p in self.enemy_players:
            cname = p.get("championName", "")
            if query_str.lower() in cname.lower():
                return cname
        
        # 캐시된 트래커 키에서 검색
        for k in self.enemy_spell_trackers.keys():
            if query_str.lower() in k.lower():
                return k

        # 오프라인/테스트 중이거나 수동 입력한 경우 직접 등록 지원
        if query_str:
            return query_str
        return None

    def _process_events(self, events: List[Dict[str, Any]]):
        """인게임 이벤트 파싱하여 드래곤/바론/전령 처치 시간 반영"""
        for ev in events:
            ev_id = ev.get("EventID")
            if ev_id in self.processed_event_ids:
                continue
            self.processed_event_ids.add(ev_id)

            ev_name = ev.get("EventName")
            ev_time = float(ev.get("EventTime", self.game_time))

            # 🐉 드래곤 처치
            if ev_name == "DragonKill":
                dragon_type = ev.get("DragonType", "Normal")
                killer_name = ev.get("KillerName", "누군가")
                self.objectives["DRAGON"]["count"] += 1
                self.objectives["DRAGON"]["dragon_type"] = dragon_type
                
                # 4용 영혼 완성 여부에 따라 장로 혹은 다음 용 설정
                if self.objectives["DRAGON"]["count"] >= 4 and dragon_type == "Elder":
                    self.objectives["ELDER"]["next_spawn_game_time"] = ev_time + 360.0
                    self.objectives["ELDER"]["is_alive"] = False
                else:
                    self.objectives["DRAGON"]["next_spawn_game_time"] = ev_time + 300.0  # 5분 후
                    self.objectives["DRAGON"]["is_alive"] = False

                self._trigger_voice_alert(
                    "DRAGON_KILL",
                    f"{killer_name}이(가) {dragon_type} 드래곤을 처치했습니다! 다음 용 5분 뒤 리젠됩니다.",
                    {"type": dragon_type, "killer": killer_name}
                )

            # 👾 바론 처치
            elif ev_name == "BaronKill":
                killer_name = ev.get("KillerName", "누군가")
                self.objectives["BARON"]["count"] += 1
                self.objectives["BARON"]["next_spawn_game_time"] = ev_time + 360.0  # 6분 후
                self.objectives["BARON"]["is_alive"] = False

                self._trigger_voice_alert(
                    "BARON_KILL",
                    f"{killer_name}이(가) 내셔 남작을 처치했습니다! 6분 뒤 바론이 다시 생성됩니다.",
                    {"killer": killer_name}
                )

            # 🦀 전령 처치
            elif ev_name == "HeraldKill":
                self.objectives["HERALD"]["is_alive"] = False
                self.objectives["HERALD"]["expired"] = True

            # 🐛 공허 유충 처치
            elif ev_name == "VoidgrubKill":
                self.objectives["VOIDGRUBS"]["count"] += 1
                if self.objectives["VOIDGRUBS"]["count"] == 3 and self.objectives["VOIDGRUBS"]["batches"] == 0:
                    self.objectives["VOIDGRUBS"]["batches"] = 1
                    self.objectives["VOIDGRUBS"]["next_spawn_game_time"] = ev_time + 135.0  # 2분 15초 후

            # 💀 에이스 (적팀 전멸)
            elif ev_name == "Ace":
                acer = ev.get("Acer", "팀")
                if acer == self.my_team:
                    self._trigger_voice_alert(
                        "ARAM_ACE_PUSH",
                        "적 팀 전멸! 에이스입니다! 지금 타워나 억제기 밀어붙이세요!",
                        {"acer": acer}
                    )

    def _update_objective_countdowns(self):
        """오브젝트 남은 초 계산 및 60초/30초 전 브리핑"""
        if self.map_name != "소환사의 협곡":
            return

        for obj_key, obj_info in self.objectives.items():
            spawn_time = obj_info.get("next_spawn_game_time", 0.0)
            if spawn_time <= 0:
                continue

            remaining = int(max(0, spawn_time - self.game_time))
            obj_info["remaining_sec"] = remaining
            obj_info["is_alive"] = (remaining == 0 and self.game_time >= spawn_time)

    def _check_gold_power_spikes(self, current_gold: float):
        """골드 기준치 도달 시 황금 귀환 알림"""
        # 1300G (BF 대검, 사라진 양피지) / 1100G (톱날단검, 기괴한가면) / 3000G (아수라장)
        thresholds = [3000, 1300, 1100]
        for th in thresholds:
            if current_gold >= th and self.last_gold_notified < th:
                self.last_gold_notified = th
                if self.map_name == "소환사의 협곡" and th in [1100, 1300]:
                    self._trigger_voice_alert(
                        "SR_GOLD_RECALL",
                        f"마스터, {int(current_gold)}골드 모였어요! 대포 웨이브 밀고 집 다녀오기 딱 좋아요!",
                        {"gold": int(current_gold)}
                    )
                elif self.map_name == "칼바람 나락" and th == 3000:
                    self._trigger_voice_alert(
                        "ARAM_GOLD_WARN",
                        f"마스터, {int(current_gold)}골드 쌓였어요! 이번 턴에 아이템 구매하고 복귀하세요!",
                        {"gold": int(current_gold)}
                    )
                break

        # 골드를 썼으면 알림 리셋
        if current_gold < 800:
            self.last_gold_notified = 0

    def _trigger_voice_alert(self, script_key: str, fallback_text: str, data: Dict[str, Any]):
        """음성 알림 엔진(lol_voice_alert_engine)으로 이벤트 전달"""
        try:
            from modules.lol_voice_alert_engine import voice_alert_engine
            if voice_alert_engine:
                voice_alert_engine.push_alert(
                    threat_level="HIGH",
                    script_key=script_key,
                    fallback_text=fallback_text,
                    data=data,
                    cooldown_sec=10.0
                )
        except Exception:
            pass

    def get_full_live_status(self) -> Dict[str, Any]:
        """웹 HUD 및 대시보드를 위한 종합 실시간 상태 반환"""
        mins = int(self.game_time // 60)
        secs = int(self.game_time % 60)
        game_time_str = f"{mins:02d}:{secs:02d}"

        return {
            "in_game": self.in_game,
            "game_time": self.game_time,
            "game_time_str": game_time_str,
            "game_mode": self.game_mode,
            "map_name": self.map_name,
            "my_team": self.my_team,
            "my_champion": self.my_champion,
            "my_cs_per_min": self.my_cs_per_min,
            "gold_diff": self.gold_diff,
            "team_gold": self.team_gold,
            "active_player_gold": self.active_player.get("currentGold", 0),
            "active_player_level": self.active_player.get("level", 1),
            "enemy_spells": self.enemy_spell_trackers,
            "objectives": self.objectives,
            "enemy_count": len(self.enemy_players),
            "ally_count": len(self.ally_players)
        }


# 전역 싱글톤 인스턴스
live_game_tracker = LoLLiveGameTracker()


# =============================================================================
# 🌐 7. FastAPI 엔드포인트
# =============================================================================
@router.get("/status", summary="인게임 종합 라이브 데이터 조회")
def get_live_status():
    """스펠 쿨타임, 오브젝트 타이머, 골드 격차, CS/분을 실시간 반환합니다."""
    return live_game_tracker.get_full_live_status()

@router.post("/spell/use", summary="적 스펠 사용 등록 (쿨타임 시작)")
def mark_spell(req: SpellUseRequest):
    """
    적 챔피언의 점멸/텔포/점화 사용을 등록하고 카운트다운을 시작합니다.
    (단축키 또는 오버레이 HUD 원클릭 연동)
    """
    res = live_game_tracker.mark_spell_used(
        champion_query=req.champion_name,
        spell_query=req.spell_name,
        custom_cd=req.custom_cooldown_sec
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.post("/spell/reset", summary="스펠 쿨타임 초기화")
def reset_spell(req: SpellResetRequest):
    """적 챔피언의 스펠 쿨타임을 즉시 초기화합니다."""
    res = live_game_tracker.reset_spell(req.champion_name, req.spell_name)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res
