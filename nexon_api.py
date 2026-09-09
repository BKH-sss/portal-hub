import os
import json
import requests
import datetime
import urllib.parse

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexon_config.json")

def load_saved_api_key():
    # 1. 환경 변수 및 .env 우선 로드
    env_key = os.environ.get("NEXON_API_KEY", "").strip()
    if env_key:
        return env_key
    # 2. 로컬 nexon_config.json fallback
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("nexon_api_key", "").strip()
        except Exception:
            pass
    return ""

def save_api_key(key: str):
    if not key or not key.strip():
        return
    try:
        data = {}
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["nexon_api_key"] = key.strip()
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[NexonAPI] Failed to save config: {e}")

def get_kst_date_candidates():
    """넥슨 Open API 조회용 KST 기준 날짜 후보군 목록 생성 (어제 -> 2일 전 -> 3일 전)"""
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now_kst = datetime.datetime.now(kst)
    
    # 00:00 ~ 01:30 KST 사이에는 넥슨 배치 작업 중이므로 2일 전을 1순위로 시도
    if now_kst.hour == 0 or (now_kst.hour == 1 and now_kst.minute < 30):
        dates = [
            (now_kst - datetime.timedelta(days=2)).strftime("%Y-%m-%d"),
            (now_kst - datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
            (now_kst - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        ]
    else:
        dates = [
            (now_kst - datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
            (now_kst - datetime.timedelta(days=2)).strftime("%Y-%m-%d"),
            (now_kst - datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        ]
    return dates

class NexonAPI:
    def __init__(self):
        self.api_key = load_saved_api_key()
        self.base_url = "https://open.api.nexon.com/maplestory/v1"
        self.cache = {}

    def set_api_key(self, key: str):
        if key and key.strip():
            self.api_key = key.strip()
            save_api_key(self.api_key)

    @property
    def headers(self):
        return {
            "x-nxopen-api-key": self.api_key or load_saved_api_key()
        }
        
    def _get(self, endpoint, params):
        """넥슨 Open API 통신 헬퍼 함수"""
        cur_key = self.api_key or load_saved_api_key()
        if not cur_key:
            return {"error": "넥슨 API 키가 설정되지 않았습니다. API 키를 먼저 입력해주세요."}
            
        url = f"{self.base_url}{endpoint}"
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        
        # 10분 캐시 (성공한 응답만 캐싱)
        if full_url in self.cache:
            cache_time, data = self.cache[full_url]
            if (datetime.datetime.now() - cache_time).seconds < 600:
                return data
                
        try:
            headers = {"x-nxopen-api-key": cur_key}
            res = requests.get(full_url, headers=headers, timeout=8)
            res.encoding = 'utf-8'
            
            if res.status_code == 200:
                data = res.json()
                self.cache[full_url] = (datetime.datetime.now(), data)
                return data
            elif res.status_code == 400:
                if endpoint == "/id":
                    return {"error": "캐릭터를 찾을 수 없습니다. 닉네임을 정확히 확인해주세요."}
                try:
                    err_data = res.json()
                    err_msg = err_data.get("error", {}).get("message", res.text)
                    return {"error": f"요청 파라미터 오류: {err_msg}"}
                except Exception:
                    return {"error": f"요청 오류 (400): {res.text}"}
            elif res.status_code in [401, 403]:
                return {"error": "넥슨 API 키가 올바르지 않거나 만료되었습니다."}
            elif res.status_code == 429:
                return {"error": "넥슨 API 호출 한도를 초과했습니다. 잠시 후 다시 시도해주세요."}
            else:
                return {"error": f"넥슨 API 오류 ({res.status_code}): {res.text}"}
        except Exception as e:
            return {"error": f"통신 오류: {str(e)}"}

    def get_ocid(self, character_name):
        """캐릭터 이름으로 OCID 조회"""
        if not character_name or not character_name.strip():
            return None
        res = self._get("/id", {"character_name": character_name.strip()})
        if isinstance(res, dict) and "ocid" in res:
            return res["ocid"]
        return None

    def get_character_info(self, character_name, api_key=None):
        """캐릭터의 종합 정보(기본, 스탯, 외형 이미지)를 조회합니다."""
        if api_key and api_key.strip():
            self.set_api_key(api_key.strip())
            
        cur_key = self.api_key or load_saved_api_key()
        if not cur_key:
            return {"status": "error", "message": "넥슨 API 키가 등록되지 않았습니다. API 키를 먼저 입력해주세요."}

        clean_name = character_name.strip()
        if not clean_name:
            return {"status": "error", "message": "캐릭터 닉네임을 입력해주세요."}

        # 1. OCID 조회
        id_res = self._get("/id", {"character_name": clean_name})
        if "error" in id_res:
            return {"status": "error", "message": id_res["error"]}
            
        ocid = id_res.get("ocid")
        if not ocid:
            return {"status": "error", "message": f"'{clean_name}' 캐릭터를 찾을 수 없습니다."}
            
        # 2. 날짜 기준 (KST 기준 어제/2일전/3일전 순차 시도)
        date_candidates = get_kst_date_candidates()
        basic = None
        stat = None
        valid_date = None
        
        for d in date_candidates:
            b_res = self._get("/character/basic", {"ocid": ocid, "date": d})
            if isinstance(b_res, dict) and "character_name" in b_res:
                basic = b_res
                valid_date = d
                break
                
        if not basic:
            return {"status": "error", "message": f"'{clean_name}' 캐릭터의 기본 정보를 조회할 수 없습니다. (최근 1년 내 미접속 캐릭터는 Open API 조회가 제한될 수 있습니다)"}
        
        # 3. 스탯 (전투력) 조회
        if valid_date:
            s_res = self._get("/character/stat", {"ocid": ocid, "date": valid_date})
            if isinstance(s_res, dict) and "final_stat" in s_res:
                stat = s_res

        # 전투력 추출 및 가독성 포맷팅 (억 / 만 단위)
        combat_power = "0"
        if isinstance(stat, dict) and "final_stat" in stat:
            for s in stat["final_stat"]:
                if s.get("stat_name") == "전투력":
                    val = s.get("stat_value", "0")
                    try:
                        num = int(val)
                        if num >= 100000000:
                            uk = num // 100000000
                            man = (num % 100000000) // 10000
                            combat_power = f"{uk}억 {man}만" if man > 0 else f"{uk}억"
                        elif num >= 10000:
                            combat_power = f"{num // 10000}만"
                        else:
                            combat_power = str(num)
                    except Exception:
                        combat_power = str(val)
                    break
                    
        return {
            "status": "success",
            "name": basic.get("character_name", clean_name),
            "level": basic.get("character_level", 0),
            "job": basic.get("character_class", "알수없음"),
            "world": basic.get("world_name", "알수없음"),
            "guild": basic.get("character_guild_name", "없음") or "없음",
            "combat_power": combat_power,
            "image": basic.get("character_image", "")
        }

    # Chuchu.gg 기준 23개 노작 장비 기본 단가 (메소 단위)
    DEFAULT_CLEAN_PRICES = {
        "골든 클로버 벨트": 500000,
        "데이브레이크 펜던트": 10000000,
        "도미네이터 펜던트": 1400000000,
        "마이스터링": 30000000,
        "트와일라이트 마크": 1000000,
        "가디언 엔젤 링": 1000000,
        "고통의 근원": 5300000000,
        "루즈 컨트롤 머신 마크": 1500000000,
        "마력이 깃든 안대": 3700000000,
        "에스텔라 이어링": 1000000,
        "거대한 공포": 4500000000,
        "몽환의 벨트": 4000000000,
        "아스트라 보조": 1000000000,
        "아케인": 5000000,
        "커맨더 포스 이어링": 1400000000,
        "컴플리트 언더컨트롤": 15000000000,
        "굶주리는 핏빛 원혼": 90000000000,
        "근원의 속삭임": 50000000000,
        "데티 무기": 10000000000,
        "에테 모상하견": 30000000,
        "에테 장신망": 1200000000,
        "죽음의 맹세": 70000000000,
        "황홀한 악몽": 50000000000
    }

    @staticmethod
    def get_default_clean_price(item_name: str) -> int:
        """아이템명으로 Chuchu.gg 기준 23개 프리셋에 매칭하여 기본 노작가를 반환"""
        if not item_name:
            return 0
        name = item_name.strip()
        
        # 1. 완전 일치
        if name in NexonAPI.DEFAULT_CLEAN_PRICES:
            return NexonAPI.DEFAULT_CLEAN_PRICES[name]
            
        # 2. 부위별 스마트 매칭
        if "골든 클로버" in name: return 500000
        if "데이브레이크" in name: return 10000000
        if "도미네이터" in name: return 1400000000
        if "마이스터링" in name: return 30000000
        if "트와일라이트" in name: return 1000000
        if "가디언 엔젤" in name: return 1000000
        if "고통의 근원" in name: return 5300000000
        if "루즈 컨트롤" in name: return 1500000000
        if "마력이 깃든" in name: return 3700000000
        if "에스텔라" in name: return 1000000
        if "거대한 공포" in name: return 4500000000
        if "몽환의 벨트" in name: return 4000000000
        if "아스트라" in name: return 1000000000
        if "커맨더 포스" in name: return 1400000000
        if "언더컨트롤" in name: return 15000000000
        if "핏빛 원혼" in name: return 90000000000
        if "근원의 속삭임" in name: return 50000000000
        if "데티" in name or "제네시스" in name: return 10000000000
        if "죽음의 맹세" in name: return 70000000000
        if "황홀한 악몽" in name: return 50000000000
        
        # 에테르넬 (모상하견 vs 장신망)
        if "에테르넬" in name:
            if any(x in name for x in ["부츠", "신발", "글러브", "장갑", "케이프", "망토"]):
                return 1200000000 # 에테 장신망
            return 30000000 # 에테 모상하견 (모자/상의/하의/견장)
            
        # 아케인셰이드
        if "아케인" in name:
            return 5000000
            
        return 0

    @staticmethod
    def is_special_world(world_name: str) -> bool:
        """스페셜 월드 (버닝, 챌린저스, 테스트 등) 여부 판별"""
        if not world_name:
            return False
        w = world_name.lower().strip()
        special_keywords = ["버닝", "챌린저스", "burning", "challenger", "테스트", "test"]
        return any(k in w for k in special_keywords)

    def get_starforce_history(self, count: int = 1000, date: str = None, cursor: str = None, api_key: str = None, exclude_special_worlds: bool = True, clean_prices: dict = None):
        """
        넥슨 공식 Open API로부터 유저의 실제 스타포스 강화 이력을 조회합니다.
        - GET /maplestory/v1/history/starforce
        - count: 1회 조회 건수 (최대 1000)
        - date: 조회 기준일 (KST 기준 YYYY-MM-DD, 최근 2년까지 지원)
        - cursor: 페이징 커서
        - exclude_special_worlds: 스페셜 월드(버닝/챌린저스 등) 제외 여부
        """
        if api_key and api_key.strip():
            self.set_api_key(api_key.strip())
            
        cur_key = self.api_key or load_saved_api_key()
        if not cur_key:
            return {"status": "error", "message": "넥슨 API 키가 설정되지 않았습니다. API 키를 먼저 입력해주세요."}

        params = {"count": min(1000, max(10, count))}
        if date:
            params["date"] = date
        if cursor:
            params["cursor"] = cursor

        res = self._get("/history/starforce", params)
        if isinstance(res, dict) and "error" in res:
            return {"status": "error", "message": res["error"]}

        history_list = res.get("starforce_history", []) if isinstance(res, dict) else []
        next_cursor = res.get("next_cursor") if isinstance(res, dict) else None

        # 통계 계산
        stats = self.analyze_starforce_stats(history_list, clean_prices=clean_prices, exclude_special_worlds=exclude_special_worlds)
        filtered_history = stats.get("filtered_history", history_list)

        return {
            "status": "success",
            "count": len(filtered_history),
            "raw_count": len(history_list),
            "next_cursor": next_cursor,
            "stats": stats,
            "history": filtered_history
        }

    @staticmethod
    def format_meso(cost: int) -> str:
        """메소 단위를 조/억/만 형식의 한국어 문자열로 변환"""
        if cost >= 1000000000000:
            jo = cost // 1000000000000
            rem = cost % 1000000000000
            uk = rem // 100000000
            return f"{jo}조 {uk:,}억 메소" if uk > 0 else f"{jo}조 메소"
        elif cost >= 100000000:
            uk = cost // 100000000
            man = (cost % 100000000) // 10000
            return f"{uk:,}억 {man:,}만 메소" if man > 0 else f"{uk:,}억 메소"
        elif cost >= 10000:
            return f"{cost // 10000:,}만 메소"
        return f"{cost:,} 메소"

    @staticmethod
    def analyze_starforce_stats(history_list: list, clean_prices: dict = None, exclude_special_worlds: bool = True) -> dict:
        """스타포스 강화 기록 리스트를 기반으로 종합 통계, 노작 비용, 손익, 운빨 지수 산출"""
        clean_prices = clean_prices or {}
        
        # 1. 스페셜 월드 필터링
        filtered_history = []
        special_world_count = 0
        for h in (history_list or []):
            world_name = h.get("world_name", "")
            if exclude_special_worlds and NexonAPI.is_special_world(world_name):
                special_world_count += 1
                continue
            filtered_history.append(h)

        if not filtered_history:
            return {
                "total_attempts": 0,
                "success_count": 0,
                "success_rate": 0.0,
                "fail_count": 0,
                "destroy_count": 0,
                "destroy_rate": 0.0,
                "total_cost": 0,
                "total_cost_formatted": "0 메소",
                "total_clean_cost": 0,
                "total_clean_cost_formatted": "0 메소",
                "total_grand_cost": 0,
                "total_grand_cost_formatted": "0 메소",
                "luck_score": 50,
                "luck_grade": "보통 (데이터 없음)",
                "ai_comment": "분석할 스타포스 강화 기록이 없습니다.",
                "tier_stats": {},
                "item_stats": [],
                "special_excluded_count": special_world_count,
                "filtered_history": []
            }

        total_attempts = len(filtered_history)
        success_count = 0
        fail_count = 0
        destroy_count = 0
        total_cost = 0
        total_clean_cost = 0
        starcatch_success = 0
        starcatch_total = 0

        tier_map = {}
        item_map = {}

        for h in filtered_history:
            cost = h.get("cost", 0) or 0
            total_cost += cost
            result = h.get("item_upgrade_result", "")
            before_star = h.get("before_starforce_count", 0)
            target_star = h.get("after_starforce_count", before_star + 1 if "성공" in result else before_star)
            item_name = h.get("target_item", "미확인 장비")
            sc_res = h.get("starcatch_result", "")
            world_name = h.get("world_name", "본서버")

            if sc_res in ["성공", "실패"]:
                starcatch_total += 1
                if sc_res == "성공":
                    starcatch_success += 1

            tier_key = f"{before_star}★ ➔ {before_star + 1}★"
            if tier_key not in tier_map:
                tier_map[tier_key] = {"tier": before_star, "target": before_star + 1, "attempts": 0, "success": 0, "fail": 0, "destroy": 0, "cost": 0}

            tier_map[tier_key]["attempts"] += 1
            tier_map[tier_key]["cost"] += cost

            # 장비별 집계 (노작값 포함)
            if item_name not in item_map:
                user_clean_price = clean_prices.get(item_name)
                clean_val = user_clean_price if user_clean_price is not None else NexonAPI.get_default_clean_price(item_name)
                item_map[item_name] = {
                    "item_name": item_name,
                    "item_level": h.get("item_level", 0),
                    "world_name": world_name,
                    "attempts": 0,
                    "success": 0,
                    "fail": 0,
                    "destroy": 0,
                    "cost": 0,
                    "clean_price": clean_val,
                    "clean_cost": 0,
                    "grand_cost": 0,
                    "start_star": before_star,
                    "max_star": before_star,
                    "final_star": target_star,
                    "history": [],
                    "journey": []
                }

            it = item_map[item_name]
            it["attempts"] += 1
            it["cost"] += cost
            it["history"].append(h)
            it["journey"].append({
                "from": before_star,
                "to": target_star,
                "result": result,
                "cost": cost,
                "starcatch": sc_res,
                "time": h.get("date_create", "")
            })

            if "성공" in result:
                success_count += 1
                tier_map[tier_key]["success"] += 1
                it["success"] += 1
                it["max_star"] = max(it["max_star"], target_star)
                it["final_star"] = target_star
            elif "파괴" in result:
                destroy_count += 1
                tier_map[tier_key]["destroy"] += 1
                it["destroy"] += 1
                it["final_star"] = 12
            else:
                fail_count += 1
                tier_map[tier_key]["fail"] += 1
                it["fail"] += 1
                it["final_star"] = target_star

        # 장비별 노작 비용 & 총합 계산
        for it in item_map.values():
            it["clean_cost"] = it["destroy"] * it["clean_price"]
            it["grand_cost"] = it["cost"] + it["clean_cost"]
            it["cost_formatted"] = NexonAPI.format_meso(it["cost"])
            it["clean_cost_formatted"] = NexonAPI.format_meso(it["clean_cost"])
            it["grand_cost_formatted"] = NexonAPI.format_meso(it["grand_cost"])
            total_clean_cost += it["clean_cost"]

        total_grand_cost = total_cost + total_clean_cost

        success_rate = round((success_count / total_attempts) * 100, 1) if total_attempts > 0 else 0.0
        destroy_rate = round((destroy_count / total_attempts) * 100, 2) if total_attempts > 0 else 0.0
        starcatch_rate = round((starcatch_success / starcatch_total) * 100, 1) if starcatch_total > 0 else 0.0

        formatted_cost = NexonAPI.format_meso(total_cost)
        formatted_clean_cost = NexonAPI.format_meso(total_clean_cost)
        formatted_grand_cost = NexonAPI.format_meso(total_grand_cost)

        # 운빨 지수 (Luck Score: 0 ~ 100)
        base_score = 50.0
        if total_attempts >= 10:
            expected_destroy_estimate = total_attempts * 0.015
            destroy_diff = expected_destroy_estimate - destroy_count
            base_score += destroy_diff * 8.0

            high_tier_tries = sum(v["attempts"] for k, v in tier_map.items() if v["tier"] >= 15)
            high_tier_succ = sum(v["success"] for k, v in tier_map.items() if v["tier"] >= 15)
            if high_tier_tries > 0:
                high_succ_rate = (high_tier_succ / high_tier_tries) * 100
                base_score += (high_succ_rate - 30.0) * 0.8

        luck_score = int(max(1, min(99, round(base_score))))
        
        if luck_score >= 85:
            luck_grade = "👑 초특급 비틱 (신의 손)"
            ai_comment = "확률을 거스른 압도적인 비틱입니다! 스타포스 파괴 확률을 기적적으로 피해 가며 노작 장비와 메소 기댓값 대비 수십~수백억 메소를 아끼셨습니다."
        elif luck_score >= 65:
            luck_grade = "✨ 상위권 (이득 구간)"
            ai_comment = "전반적으로 스타포스 운이 꽤 좋은 편입니다. 파괴율이 낮고 노작 장비 소모를 최소화하며 목표 성급에 도달했습니다."
        elif luck_score >= 45:
            luck_grade = "⚖️ 평범 (정규 확률 수렴)"
            ai_comment = "메이플스토리 공식 스타포스 기댓값과 거의 일치하는 통계입니다. 무난하게 평균적인 비용으로 진행되었습니다."
        elif luck_score >= 25:
            luck_grade = "🌧️ 하위권 (소폭 억까)"
            ai_comment = "아쉽게도 평균보다 파괴 횟수가 많아 노작 장비 스페어 비용 지출이 컸습니다. 오늘은 강화를 쉬어가는 것을 추천합니다."
        else:
            luck_grade = "💀 대참사 (극악의 억까)"
            ai_comment = "스카디 긴급 경보! 극악의 억까로 인해 장비가 연쇄 파괴되어 막대한 노작 비용과 메소 손실이 발생했습니다. 당분간 스타포스를 절대 금지하세요!"

        # 아이템 정렬 (총 비용 내림차순)
        sorted_items = sorted(item_map.values(), key=lambda x: x["grand_cost"], reverse=True)

        return {
            "total_attempts": total_attempts,
            "success_count": success_count,
            "success_rate": success_rate,
            "fail_count": fail_count,
            "destroy_count": destroy_count,
            "destroy_rate": destroy_rate,
            "starcatch_rate": starcatch_rate,
            "total_cost": total_cost,
            "total_cost_formatted": formatted_cost,
            "total_clean_cost": total_clean_cost,
            "total_clean_cost_formatted": formatted_clean_cost,
            "total_grand_cost": total_grand_cost,
            "total_grand_cost_formatted": formatted_grand_cost,
            "luck_score": luck_score,
            "luck_grade": luck_grade,
            "ai_comment": ai_comment,
            "tier_stats": tier_map,
            "item_stats": sorted_items,
            "special_excluded_count": special_world_count,
            "filtered_history": filtered_history
        }

    @staticmethod
    def generate_sample_starforce_data(exclude_special_worlds: bool = True, clean_prices: dict = None) -> dict:
        """테스트 및 시뮬레이션용 실감나는 22성 강화 기록 180회 샘플 데이터셋 생성 (노작값, 스페셜월드 포함)"""
        import random
        items = [
            ("에테르넬 나이트숄더", 250, 78000000, "스카니아", 1800000000),
            ("마력이 깃든 안대", 160, 31000000, "루나", 5500000000),
            ("루즈 컨트롤 머신 마크", 160, 31000000, "엘리시움", 5000000000),
            ("커맨더 포스 이어링", 160, 31000000, "스카니아", 3500000000),
            ("아케인셰이드 투구", 200, 52000000, "크로아", 60000000),
            ("아케인셰이드 나이트숄더", 200, 52000000, "오로라", 60000000),
            ("파프니르 이글아이", 150, 15000000, "버닝2", 10000000), # 스페셜 월드 샘플 1
            ("하이네스 워리어헬름", 150, 15000000, "챌린저스", 10000000) # 스페셜 월드 샘플 2
        ]
        
        history = []
        base_time = datetime.datetime.now() - datetime.timedelta(days=14)
        
        for item_name, req_level, cost_base, world, default_clean in items:
            cur_star = random.randint(12, 15)
            target_goal = 22 if "버닝" not in world and "챌린저스" not in world else 17
            tries = random.randint(15, 35)
            
            for _ in range(tries):
                base_time += datetime.timedelta(minutes=random.randint(1, 15))
                # 확률 모델
                if cur_star < 15:
                    succ_p = 0.45
                    dest_p = 0.0
                elif cur_star in [15, 16]:
                    succ_p = 0.30
                    dest_p = 0.021
                elif cur_star in [17, 18, 19]:
                    succ_p = 0.30
                    dest_p = 0.028
                elif cur_star in [20, 21]:
                    succ_p = 0.30
                    dest_p = 0.07
                else:
                    succ_p = 0.03
                    dest_p = 0.20
                    
                roll = random.random()
                starcatch = "성공" if random.random() < 0.85 else "실패"
                cost = int(cost_base * (1 + (cur_star * 0.15)))
                
                if roll < succ_p:
                    res = "성공"
                    new_star = cur_star + 1
                elif roll < succ_p + dest_p:
                    res = "파괴"
                    new_star = 12
                else:
                    res = "실패(하락)" if cur_star in [16, 17, 18, 19, 21] else "실패(유지)"
                    new_star = max(10, cur_star - 1) if "하락" in res else cur_star
                    
                history.append({
                    "id": f"sf_{len(history)+1:04d}",
                    "item_upgrade_result": res,
                    "before_starforce_count": cur_star,
                    "after_starforce_count": new_star if res == "성공" else cur_star,
                    "starcatch_result": starcatch,
                    "superior_item_flag": "미사용",
                    "destroy_defence": "적용" if cur_star in [15, 16] and random.random() < 0.5 else "미적용",
                    "chance_time": "미적용",
                    "target_item": item_name,
                    "item_level": req_level,
                    "world_name": world,
                    "character_name": f"{world}용사{random.randint(1, 99)}",
                    "cost": cost,
                    "date_create": base_time.strftime("%Y-%m-%dT%H:%M:%S+09:00")
                })
                cur_star = new_star
                if cur_star >= target_goal:
                    break

        # 최신순 정렬
        history.reverse()
        stats = NexonAPI.analyze_starforce_stats(history, clean_prices=clean_prices, exclude_special_worlds=exclude_special_worlds)
        return {
            "status": "success",
            "is_sample": True,
            "count": len(stats.get("filtered_history", history)),
            "raw_count": len(history),
            "stats": stats,
            "history": stats.get("filtered_history", history)
        }

    def search_market_item(self, item_name: str):
        """경매장에서 특정 아이템의 최저가 매물을 검색합니다."""
        cur_key = self.api_key or load_saved_api_key()
        if not cur_key:
            return {"status": "error", "message": "API 키가 설정되지 않아 실시간 경매장 조회가 불가능해!"}
            
        params = {"item_name": item_name, "page_index": 1}
        res = self._get("/market/item-search", params)
        
        if "error" in res:
            return {"status": "error", "message": f"경매장 조회 실패! ({res['error']})"}
            
        items = res.get("item", [])
        if not items:
            return {"status": "success", "message": f"{item_name} 매물이 지금 경매장에 없어!"}
            
        sorted_items = sorted(items, key=lambda x: x.get("item_price", float('inf')))
        cheapest = sorted_items[0]
        
        return {
            "status": "success",
            "item_name": item_name,
            "cheapest_price": cheapest.get("item_price", 0),
            "item_detail": cheapest,
            "raw_count": len(items)
        }

if __name__ == "__main__":
    nexon = NexonAPI()
    print("메이플 API 테스트 중...")
    print(nexon.get_character_info("re흔들린은월"))

