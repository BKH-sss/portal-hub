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

class NexonAPI:
    def __init__(self):
        self.api_key = load_saved_api_key()
        self.base_url = "https://open.api.nexon.com/maplestory/v1"
        self.cache = {}

    def set_api_key(self, key: str):
        if key:
            self.api_key = key.strip()
            save_api_key(self.api_key)

    @property
    def headers(self):
        return {
            "x-nxopen-api-key": self.api_key
        }
        
    def _get(self, endpoint, params):
        """넥슨 Open API 통신 헬퍼 함수"""
        if not self.api_key:
            return {"error": "넥슨 API 키가 설정되지 않았습니다. API 키를 먼저 입력해주세요."}
            
        url = f"{self.base_url}{endpoint}"
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        
        # 10분 캐시
        if full_url in self.cache:
            cache_time, data = self.cache[full_url]
            if (datetime.datetime.now() - cache_time).seconds < 600:
                return data
                
        try:
            res = requests.get(full_url, headers=self.headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                self.cache[full_url] = (datetime.datetime.now(), data)
                return data
            elif res.status_code == 400:
                return {"error": "캐릭터를 찾을 수 없습니다. 닉네임을 정확히 확인해주세요."}
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
        res = self._get("/id", {"character_name": character_name.strip()})
        if isinstance(res, dict) and "ocid" in res:
            return res["ocid"]
        return None

    def get_character_info(self, character_name, api_key=None):
        """캐릭터의 종합 정보(기본, 스탯)를 조회합니다."""
        if api_key:
            self.set_api_key(api_key)
            
        if not self.api_key:
            return {"status": "error", "message": "넥슨 API 키가 등록되지 않았습니다. API 키를 먼저 입력해주세요."}

        # 1. OCID 조회
        id_res = self._get("/id", {"character_name": character_name.strip()})
        if "error" in id_res:
            return {"status": "error", "message": id_res["error"]}
            
        ocid = id_res.get("ocid")
        if not ocid:
            return {"status": "error", "message": f"'{character_name}' 캐릭터를 찾을 수 없습니다."}
            
        # 2. 날짜 기준 (어제 날짜 / 오늘 날짜)
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        basic = self._get("/character/basic", {"ocid": ocid, "date": yesterday})
        if "error" in basic:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            basic = self._get("/character/basic", {"ocid": ocid, "date": today})
            if "error" in basic:
                return {"status": "error", "message": f"기본 정보 조회 실패: {basic['error']}"}
        
        stat = self._get("/character/stat", {"ocid": ocid, "date": yesterday})
        if "error" in stat:
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            stat = self._get("/character/stat", {"ocid": ocid, "date": today})

        # 전투력 추출
        combat_power = "0"
        if isinstance(stat, dict) and "final_stat" in stat:
            for s in stat["final_stat"]:
                if s.get("stat_name") == "전투력":
                    val = s.get("stat_value", "0")
                    try:
                        num = int(val)
                        if num >= 100000000:
                            combat_power = f"{num // 100000000}억 { (num % 100000000) // 10000 }만"
                        elif num >= 10000:
                            combat_power = f"{num // 10000}만"
                        else:
                            combat_power = str(num)
                    except Exception:
                        combat_power = str(val)
                    break
                    
        return {
            "status": "success",
            "name": basic.get("character_name", character_name),
            "level": basic.get("character_level", 0),
            "job": basic.get("character_class", "알수없음"),
            "world": basic.get("world_name", "알수없음"),
            "guild": basic.get("character_guild_name", "없음"),
            "combat_power": combat_power,
            "image": basic.get("character_image", "")
        }

    def search_market_item(self, item_name):
        """경매장에서 특정 아이템의 최저가 매물을 검색합니다."""
        if not self.api_key:
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
    print(nexon.get_character_info("타락파워전사"))
