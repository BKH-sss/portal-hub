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

    def search_market_item(self, item_name):
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
