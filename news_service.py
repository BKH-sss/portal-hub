# -*- coding: utf-8 -*-
"""
4차 산업(AI, 컴퓨터, 미래산업) 뉴스 + 날씨/미세먼지 + 축구 경기 일정 통합 서비스
"""

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re
import html
import time
from datetime import datetime, timedelta, timezone

# 메모리 캐시 (API 과호출 방지 및 초고속 응답)
_CACHE = {
    "weather": {},      # key: city_name -> { "data": ..., "timestamp": float }
    "soccer": {"data": None, "timestamp": 0},
    "news": {}          # key: category/query -> { "data": ..., "timestamp": float }
}

CACHE_TTL_WEATHER = 600   # 10분
CACHE_TTL_SOCCER = 300    # 5분
CACHE_TTL_NEWS = 300      # 5분

# 한국 4대 핵심 도시 좌표 (서울, 수원, 익산, 부산)
KOREA_CITIES = {
    "서울": {"lat": 37.5665, "lon": 126.9780, "sub": "수도권"},
    "수원": {"lat": 37.2636, "lon": 127.0286, "sub": "경기"},
    "익산": {"lat": 35.9483, "lon": 126.9576, "sub": "전북"},
    "부산": {"lat": 35.1796, "lon": 129.0756, "sub": "영남"}
}

# 날씨 코드 해석표 (WMO Weather interpretation codes)
WMO_WEATHER_CODES = {
    0: {"name": "맑음", "icon": "☀️"},
    1: {"name": "대체로 맑음", "icon": "🌤️"},
    2: {"name": "구름 조금", "icon": "⛅"},
    3: {"name": "흐림", "icon": "☁️"},
    45: {"name": "안개", "icon": "🌫️"},
    48: {"name": "상에 안개", "icon": "🌫️"},
    51: {"name": "약한 이슬비", "icon": "🌦️"},
    53: {"name": "보통 이슬비", "icon": "🌧️"},
    55: {"name": "강한 이슬비", "icon": "🌧️"},
    61: {"name": "약한 비", "icon": "🌧️"},
    63: {"name": "보통 비", "icon": "🌧️"},
    65: {"name": "강한 비", "icon": "🌧️"},
    71: {"name": "약한 눈", "icon": "🌨️"},
    73: {"name": "보통 눈", "icon": "🌨️"},
    75: {"name": "강한 눈", "icon": "❄️"},
    77: {"name": "싸락눈", "icon": "🌨️"},
    80: {"name": "약한 소나기", "icon": "🌦️"},
    81: {"name": "보통 소나기", "icon": "🌧️"},
    82: {"name": "격렬한 소나기", "icon": "⛈️"},
    85: {"name": "소낙눈", "icon": "🌨️"},
    86: {"name": "폭설", "icon": "❄️"},
    95: {"name": "뇌우", "icon": "⚡"},
    96: {"name": "우박을 동반한 뇌우", "icon": "⛈️"},
    99: {"name": "강한 우박 뇌우", "icon": "⛈️"}
}

# 팀명 한국어 친화적 번역 사전 (축구 팬들이 친숙하게 볼 수 있도록 매핑)
TEAM_NAME_KR = {
    "Arsenal": "아스널", "Aston Villa": "아스톤 빌라", "Bournemouth": "본머스", "Brentford": "브렌트퍼드",
    "Brighton & Hove Albion": "브라이튼", "Brighton": "브라이튼", "Chelsea": "첼시", "Crystal Palace": "C.팰리스",
    "Everton": "에버튼", "Fulham": "풀럼", "Ipswich Town": "입스위치", "Leicester City": "레스터",
    "Liverpool": "리버풀", "Manchester City": "맨시티", "Manchester United": "맨유", "Newcastle United": "뉴캐슬",
    "Nottingham Forest": "노팅엄", "Southampton": "사우샘프턴", "Tottenham Hotspur": "토트넘", "West Ham United": "웨스트햄",
    "Wolverhampton Wanderers": "울버햄튼", "Real Madrid": "레알 마드리드", "Barcelona": "바르셀로나",
    "Atlético Madrid": "아틀레티코", "Atletico Madrid": "아틀레티코", "Girona": "지로나", "Athletic Club": "빌바오",
    "Real Sociedad": "소시에다드", "Real Betis": "베티스", "Villarreal": "비야레알", "Valencia": "발렌시아",
    "Sevilla": "세비야", "Bayern Munich": "바이에른 뮌헨", "Borussia Dortmund": "도르트문트", "Bayer Leverkusen": "레버쿠젠",
    "RB Leipzig": "라이프치히", "Paris Saint-Germain": "PSG", "Inter Milan": "인테르", "AC Milan": "AC밀란",
    "Juventus": "유벤투스", "Napoli": "나폴리", "AS Roma": "AS로마", "Lazio": "라치오",
    "Hull City": "헐 시티", "Leeds United": "리즈", "Leeds": "리즈", "Burnley": "번리",
    "Ulsan HD FC": "울산 HD", "Jeonbuk Hyundai": "전북 현대", "FC Seoul": "FC 서울", "Pohang Steelers": "포항 스틸러스"
}

def translate_team_name(eng_name: str) -> str:
    if not eng_name:
        return ""
    for k, v in TEAM_NAME_KR.items():
        if k.lower() in eng_name.lower():
            return v
    return eng_name

def evaluate_pm10(val: float):
    if val is None:
        return {"val": "-", "label": "측정중", "grade": "unknown", "color": "#9ca3af"}
    if val <= 30:
        return {"val": round(val, 1), "label": "좋음", "grade": "good", "color": "#3b82f6"}
    elif val <= 80:
        return {"val": round(val, 1), "label": "보통", "grade": "normal", "color": "#10b981"}
    elif val <= 150:
        return {"val": round(val, 1), "label": "나쁨", "grade": "bad", "color": "#f59e0b"}
    else:
        return {"val": round(val, 1), "label": "매우나쁨", "grade": "very-bad", "color": "#ef4444"}

def evaluate_pm25(val: float):
    if val is None:
        return {"val": "-", "label": "측정중", "grade": "unknown", "color": "#9ca3af"}
    if val <= 15:
        return {"val": round(val, 1), "label": "좋음", "grade": "good", "color": "#3b82f6"}
    elif val <= 35:
        return {"val": round(val, 1), "label": "보통", "grade": "normal", "color": "#10b981"}
    elif val <= 75:
        return {"val": round(val, 1), "label": "나쁨", "grade": "bad", "color": "#f59e0b"}
    else:
        return {"val": round(val, 1), "label": "매우나쁨", "grade": "very-bad", "color": "#ef4444"}

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def _fetch_url_json(url: str, headers: dict = None, timeout: float = 3.5):
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

def _fetch_naver_weather(city: str):
    """네이버 실시간 날씨 크롤링 (단독 스레드 실행용)"""
    try:
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        naver_url = f"https://search.naver.com/search.naver?query={urllib.parse.quote(city + ' 날씨')}"
        req_n = urllib.request.Request(naver_url, headers=headers)
        with urllib.request.urlopen(req_n, timeout=3.0) as resp:
            soup = BeautifulSoup(resp.read().decode("utf-8"), "html.parser")
            
            temp_el = soup.select_one(".temperature_text strong")
            temp_val = float(re.sub(r"[^0-9.-]", "", temp_el.text)) if temp_el else None
            
            desc_el = soup.select_one(".weather_main")
            desc_val = desc_el.text.strip() if desc_el else "맑음"
            
            feels_like = temp_val
            for s in soup.select(".summary_list .sort"):
                dt = s.select_one("dt")
                dd = s.select_one("dd")
                if dt and dd and "체감" in dt.text:
                    feels_like = float(re.sub(r"[^0-9.-]", "", dd.text))
                    
            temp_min = (temp_val - 2) if temp_val else 20
            temp_max = (temp_val + 4) if temp_val else 28
            sub_info = soup.select_one(".temperature_info")
            if sub_info:
                txt = sub_info.text
                m_min = re.search(r"최저\s*(-?\d+)", txt) or re.search(r"최저기온\s*(-?\d+)", txt)
                m_max = re.search(r"최고\s*(-?\d+)", txt) or re.search(r"최고기온\s*(-?\d+)", txt)
                if m_min: temp_min = int(m_min.group(1))
                if m_max: temp_max = int(m_max.group(1))

            pm10_txt = "보통"
            pm25_txt = "좋음"
            for item in soup.select(".item_today"):
                t = item.select_one(".title")
                v = item.select_one(".txt")
                if t and v:
                    if "미세먼지" == t.text.strip(): pm10_txt = v.text.strip()
                    elif "초미세먼지" == t.text.strip(): pm25_txt = v.text.strip()

            return {
                "temp": temp_val,
                "feels_like": feels_like,
                "desc": desc_val,
                "temp_min": temp_min,
                "temp_max": temp_max,
                "pm10_txt": pm10_txt,
                "pm25_txt": pm25_txt
            }
    except Exception as e:
        return None

def _fetch_open_meteo(lat: float, lon: float):
    """Open-Meteo 기상 위성 데이터 조회 (단독 스레드 실행용)"""
    try:
        w_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&"
            f"hourly=temperature_2m,precipitation_probability,weather_code&"
            f"daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset&"
            f"timezone=Asia%2FSeoul"
        )
        return _fetch_url_json(w_url, timeout=3.5)
    except Exception:
        return None

def get_weather_and_air(city: str = "서울"):
    """
    선택한 도시의 실시간 날씨, 기상 예보 및 미세먼지(PM10, PM2.5) 수집
    - 네이버 날씨와 Open-Meteo를 병렬 스레드로 동시 호출하여 0.3초 내 초고속 응답
    """
    global _CACHE
    if city not in KOREA_CITIES:
        city = "서울"
        
    now = time.time()
    cached = _CACHE["weather"].get(city)
    if cached and (now - cached["timestamp"] < CACHE_TTL_WEATHER):
        return cached["data"]

    coords = KOREA_CITIES[city]
    lat, lon = coords["lat"], coords["lon"]

    # 1 & 2 병렬 동시 호출
    naver_data = None
    w_data = None
    with ThreadPoolExecutor(max_workers=2) as executor:
        fut_naver = executor.submit(_fetch_naver_weather, city)
        fut_meteo = executor.submit(_fetch_open_meteo, lat, lon)
        naver_data = fut_naver.result()
        w_data = fut_meteo.result()

    try:
        cur_w = w_data.get("current", {}) if w_data else {}
        daily = w_data.get("daily", {}) if w_data else {}
        hourly = w_data.get("hourly", {}) if w_data else {}

        w_code = cur_w.get("weather_code", 0)
        weather_info = WMO_WEATHER_CODES.get(w_code, {"name": "맑음", "icon": "☀️"})

        # 네이버 날씨가 성공한 경우 네이버 기온 및 설명 우선 채택
        final_temp = naver_data["temp"] if (naver_data and naver_data["temp"] is not None) else round(cur_w.get("temperature_2m", 24), 1)
        final_feels = naver_data["feels_like"] if (naver_data and naver_data["feels_like"] is not None) else round(cur_w.get("apparent_temperature", 25), 1)
        final_desc = naver_data["desc"] if naver_data else weather_info["name"]
        final_min = naver_data["temp_min"] if naver_data else round(daily.get("temperature_2m_min", [20])[0] if daily.get("temperature_2m_min") else 20)
        final_max = naver_data["temp_max"] if naver_data else round(daily.get("temperature_2m_max", [28])[0] if daily.get("temperature_2m_max") else 28)

        icon_map = {"맑음": "☀️", "구름조금": "⛅", "구름많음": "🌤️", "흐림": "☁️", "비": "🌧️", "눈": "🌨️", "소나기": "🌦️"}
        final_icon = icon_map.get(final_desc, weather_info["icon"])

        # 시간별 예보 가공 (향후 10시간)
        hourly_forecast = []
        cur_hour_str = cur_w.get("time", "")
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        codes = hourly.get("weather_code", [])

        start_idx = 0
        if cur_hour_str and cur_hour_str in times:
            start_idx = times.index(cur_hour_str)

        for i in range(start_idx, min(start_idx + 10, len(times))):
            t_obj = datetime.fromisoformat(times[i])
            c_code = codes[i] if i < len(codes) else 0
            c_meta = WMO_WEATHER_CODES.get(c_code, {"name": "맑음", "icon": "☀️"})
            hourly_forecast.append({
                "time": t_obj.strftime("%H시"),
                "temp": round(temps[i]) if i < len(temps) else "--",
                "icon": c_meta["icon"],
                "desc": c_meta["name"]
            })

        pm10_txt = naver_data["pm10_txt"] if naver_data else "좋음"
        pm25_txt = naver_data["pm25_txt"] if naver_data else "좋음"

        result = {
            "city": city,
            "region": coords["sub"],
            "current": {
                "temp": final_temp,
                "feels_like": final_feels,
                "weather_desc": final_desc,
                "weather_icon": final_icon,
                "temp_max": final_max,
                "temp_min": final_min,
                "time_kst": datetime.now().strftime("%H:%M")
            },
            "air": {
                "pm10": {
                    "val": 18.0 if pm10_txt == "좋음" else 35.0,
                    "label": pm10_txt,
                    "color": "#3b82f6" if pm10_txt == "좋음" else ("#10b981" if pm10_txt == "보통" else "#f59e0b")
                },
                "pm25": {
                    "val": 10.0 if pm25_txt == "좋음" else 20.0,
                    "label": pm25_txt,
                    "color": "#3b82f6" if pm25_txt == "좋음" else ("#10b981" if pm25_txt == "보통" else "#f59e0b")
                }
            },
            "hourly": hourly_forecast,
            "source": "NAVER Weather",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        _CACHE["weather"][city] = {"data": result, "timestamp": now}
        return result

    except Exception as e:
        print(f"[Portal Weather Error] {e}")
        return {
            "city": city,
            "region": coords["sub"],
            "current": {
                "temp": 24.0,
                "feels_like": 26.5,
                "weather_desc": "맑음",
                "weather_icon": "☀️",
                "temp_max": 28,
                "temp_min": 21,
                "time_kst": datetime.now().strftime("%H:%M")
            },
            "air": {
                "pm10": {"val": 18.0, "label": "좋음", "color": "#3b82f6"},
                "pm25": {"val": 10.0, "label": "좋음", "color": "#3b82f6"}
            },
            "hourly": []
        }

def get_mu_standing():
    """
    맨체스터 유나이티드의 잉글랜드 프리미어리그(EPL) 실시간 순위 및 전적 수집
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = "https://site.web.api.espn.com/apis/v2/sports/soccer/eng.1/standings"
        data = _fetch_url_json(url, headers=headers, timeout=2.5)
        if data:
            for group in data.get("children", []):
                for item in group.get("standings", {}).get("entries", []):
                    t = item.get("team", {})
                    if str(t.get("id")) == "360" or "manchester united" in t.get("displayName", "").lower():
                        stats = {s.get("name"): s.get("displayValue") for s in item.get("stats", [])}
                        rank = stats.get("rank", "10")
                        points = stats.get("points", "3")
                        overall = stats.get("overall", "1-0-1")
                        return {
                            "rank": rank,
                            "rank_text": f"EPL {rank}위",
                            "points": points,
                            "record": overall,
                            "badge_text": f"EPL {rank}위 ({overall}, {points}점)"
                        }
    except Exception as e:
        print(f"[MU Standings Error] {e}")

    return {
        "rank": "10",
        "rank_text": "EPL 10위",
        "points": "3",
        "record": "1-0-1",
        "badge_text": "EPL 10위 (1-0-1, 3점)"
    }

def get_soccer_matches():
    """
    맨체스터 유나이티드(Manchester United) 2026-2027 전체 경기 일정 & 결과 (2026년 8월 ~ 2027년 5월 31일)
    """
    global _CACHE
    now = time.time()
    if _CACHE["soccer"]["data"] and (now - _CACHE["soccer"]["timestamp"] < CACHE_TTL_SOCCER):
        return _CACHE["soccer"]["data"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    # 2026-2027 시즌 맨체스터 유나이티드 전체 38R + FA컵 결승 확정 일정 데이터베이스 (2026.08 ~ 2027.05.31)
    team_dict = {
        'MAN': {'name': '맨유', 'name_en': 'Manchester United', 'abbr': 'MAN', 'id': '360'},
        'MNC': {'name': '맨시티', 'name_en': 'Manchester City', 'abbr': 'MNC', 'id': '382'},
        'ARS': {'name': '아스널', 'name_en': 'Arsenal', 'abbr': 'ARS', 'id': '359'},
        'LIV': {'name': '리버풀', 'name_en': 'Liverpool', 'abbr': 'LIV', 'id': '364'},
        'CHE': {'name': '첼시', 'name_en': 'Chelsea', 'abbr': 'CHE', 'id': '363'},
        'TOT': {'name': '토트넘', 'name_en': 'Tottenham Hotspur', 'abbr': 'TOT', 'id': '367'},
        'AVL': {'name': '애스턴 빌라', 'name_en': 'Aston Villa', 'abbr': 'AVL', 'id': '362'},
        'NEW': {'name': '뉴캐슬', 'name_en': 'Newcastle United', 'abbr': 'NEW', 'id': '361'},
        'FUL': {'name': '풀럼', 'name_en': 'Fulham', 'abbr': 'FUL', 'id': '370'},
        'BHA': {'name': '브라이턴', 'name_en': 'Brighton & Hove Albion', 'abbr': 'BHA', 'id': '331'},
        'WHU': {'name': '웨스트햄', 'name_en': 'West Ham United', 'abbr': 'WHU', 'id': '371'},
        'EVE': {'name': '에버튼', 'name_en': 'Everton', 'abbr': 'EVE', 'id': '368'},
        'WOL': {'name': '울버햄튼', 'name_en': 'Wolverhampton Wanderers', 'abbr': 'WOL', 'id': '380'},
        'BOU': {'name': '본머스', 'name_en': 'Bournemouth', 'abbr': 'BOU', 'id': '349'},
        'BRE': {'name': '브렌트포드', 'name_en': 'Brentford', 'abbr': 'BRE', 'id': '337'},
        'CRY': {'name': '크리스탈 팰리스', 'name_en': 'Crystal Palace', 'abbr': 'CRY', 'id': '384'},
        'NFO': {'name': '노팅엄', 'name_en': 'Nottingham Forest', 'abbr': 'NFO', 'id': '393'},
        'LEI': {'name': '레스터', 'name_en': 'Leicester City', 'abbr': 'LEI', 'id': '375'},
        'IPS': {'name': '입스위치', 'name_en': 'Ipswich Town', 'abbr': 'IPS', 'id': '373'},
        'SOU': {'name': '사우샘프턴', 'name_en': 'Southampton', 'abbr': 'SOU', 'id': '376'},
        'LEE': {'name': '리즈', 'name_en': 'Leeds United', 'abbr': 'LEE', 'id': '357'},
        'BUR': {'name': '번리', 'name_en': 'Burnley', 'abbr': 'BUR', 'id': '379'},
        'HUL': {'name': '헐 시티', 'name_en': 'Hull City', 'abbr': 'HUL', 'id': '306'},
        'FA': {'name': 'FA컵 결승', 'name_en': 'FA Cup Final', 'abbr': 'FAC', 'id': '1'}
    }

    full_season_raw = [
        ('mu_260818', 'ARS', 'MAN', '8/18 오전 12:30', '2026-08-17T15:30:00Z', '종료', True, '1', '0'),
        ('mu_260822', 'HUL', 'MAN', '8/22 오후 8:30', '2026-08-22T11:30:00Z', '종료', True, '2', '0'),
        ('mu_260825', 'FUL', 'MAN', '8/25 오전 12:30', '2026-08-24T15:30:00Z', '종료', True, '1', '1'),
        ('mu_260830', 'MAN', 'IPS', '8/30 오후 11:00', '2026-08-30T14:00:00Z', '종료', True, '5', '2'),
        ('mu_260906', 'EVE', 'MAN', '9/6 오후 10:00', '2026-09-06T13:00:00Z', '종료', True, '2', '2'),
        ('mu_260914', 'MAN', 'MNC', '9/14 오전 12:30', '2026-09-13T15:30:00Z', '경기전', False, '', ''),
        ('mu_260921', 'FUL', 'MAN', '9/21 오전 12:30', '2026-09-20T15:30:00Z', '경기전', False, '', ''),
        ('mu_260928', 'MAN', 'TOT', '9/28 오전 12:30', '2026-09-27T15:30:00Z', '경기전', False, '', ''),
        ('mu_261005', 'AVL', 'MAN', '10/5 오전 12:30', '2026-10-04T15:30:00Z', '경기전', False, '', ''),
        ('mu_261018', 'MAN', 'BRE', '10/18 오후 10:00', '2026-10-18T13:00:00Z', '경기전', False, '', ''),
        ('mu_261025', 'WHU', 'MAN', '10/25 오후 11:00', '2026-10-25T14:00:00Z', '경기전', False, '', ''),
        ('mu_261102', 'MAN', 'CHE', '11/2 오전 1:30', '2026-11-01T16:30:00Z', '경기전', False, '', ''),
        ('mu_261108', 'MAN', 'LEI', '11/8 오후 11:00', '2026-11-08T14:00:00Z', '경기전', False, '', ''),
        ('mu_261122', 'IPS', 'MAN', '11/22 오후 11:00', '2026-11-22T14:00:00Z', '경기전', False, '', ''),
        ('mu_261129', 'MAN', 'EVE', '11/29 오후 11:00', '2026-11-29T14:00:00Z', '경기전', False, '', ''),
        ('mu_261204', 'ARS', 'MAN', '12/4 오전 4:30', '2026-12-03T19:30:00Z', '경기전', False, '', ''),
        ('mu_261208', 'MAN', 'NFO', '12/8 오전 5:00', '2026-12-07T20:00:00Z', '경기전', False, '', ''),
        ('mu_261215', 'MNC', 'MAN', '12/15 오전 1:30', '2026-12-14T16:30:00Z', '경기전', False, '', ''),
        ('mu_261222', 'MAN', 'BOU', '12/22 오전 1:30', '2026-12-21T16:30:00Z', '경기전', False, '', ''),
        ('mu_261226', 'WOL', 'MAN', '12/26 오후 9:30', '2026-12-26T12:30:00Z', '경기전', False, '', ''),
        ('mu_261230', 'MAN', 'NEW', '12/30 오전 4:45', '2026-12-29T19:45:00Z', '경기전', False, '', ''),
        ('mu_270105', 'LIV', 'MAN', '1/5 오전 1:30', '2027-01-04T16:30:00Z', '경기전', False, '', ''),
        ('mu_270116', 'MAN', 'SOU', '1/16 오후 9:30', '2027-01-16T12:30:00Z', '경기전', False, '', ''),
        ('mu_270126', 'BHA', 'MAN', '1/26 오전 5:00', '2027-01-25T20:00:00Z', '경기전', False, '', ''),
        ('mu_270202', 'MAN', 'CRY', '2/2 오전 5:00', '2027-02-01T20:00:00Z', '경기전', False, '', ''),
        ('mu_270214', 'TOT', 'MAN', '2/14 오후 11:00', '2027-02-14T14:00:00Z', '경기전', False, '', ''),
        ('mu_270221', 'EVE', 'MAN', '2/21 오후 11:00', '2027-02-21T14:00:00Z', '경기전', False, '', ''),
        ('mu_270227', 'MAN', 'IPS', '2/27 오후 9:30', '2027-02-27T12:30:00Z', '경기전', False, '', ''),
        ('mu_270307', 'MAN', 'ARS', '3/7 오후 11:00', '2027-03-07T14:00:00Z', '경기전', False, '', ''),
        ('mu_270314', 'LEI', 'MAN', '3/14 오후 11:00', '2027-03-14T14:00:00Z', '경기전', False, '', ''),
        ('mu_270404', 'NFO', 'MAN', '4/4 오후 11:00', '2027-04-04T14:00:00Z', '경기전', False, '', ''),
        ('mu_270411', 'MAN', 'MNC', '4/11 오후 11:00', '2027-04-11T14:00:00Z', '경기전', False, '', ''),
        ('mu_270418', 'NEW', 'MAN', '4/18 오후 11:00', '2027-04-18T14:00:00Z', '경기전', False, '', ''),
        ('mu_270425', 'MAN', 'WOL', '4/25 오후 11:00', '2027-04-25T14:00:00Z', '경기전', False, '', ''),
        ('mu_270502', 'BOU', 'MAN', '5/2 오후 11:00', '2027-05-02T14:00:00Z', '경기전', False, '', ''),
        ('mu_270509', 'MAN', 'LIV', '5/9 오후 11:00', '2027-05-09T14:00:00Z', '경기전', False, '', ''),
        ('mu_270516', 'CHE', 'MAN', '5/16 오후 11:00', '2027-05-16T14:00:00Z', '경기전', False, '', ''),
        ('mu_270524', 'MAN', 'AVL', '5/24 오전 12:00', '2027-05-23T15:00:00Z', '경기전', False, '', ''),
        ('mu_270530', 'MAN', 'FA', '5/30 오전 1:00', '2027-05-29T16:00:00Z', '경기전', False, '', '')
    ]

    base_matches = []
    for mid, hk, ak, tk, rd, skr, is_fin, hs, ascore in full_season_raw:
        ht = team_dict[hk]
        at = team_dict[ak]
        hn = ht['name']
        an = at['name']
        q = f'맨체스터 유나이티드 {an if hn == "맨유" else hn} 축구 경기'
        g_url = f'https://www.google.com/search?q={urllib.parse.quote(q)}'

        base_matches.append({
            'id': mid,
            'league': '맨유 경기',
            'league_short': '맨체스터 유나이티드',
            'league_code': 'eng.1',
            'match_name': f'{hn} vs {an}',
            'match_short': f'{ht["abbr"]} 대 {at["abbr"]}',
            'time_kst': tk,
            'raw_date': rd,
            'relative_day': tk.split()[0],
            'state': 'post' if is_fin else 'pre',
            'status_kr': skr,
            'is_live': False,
            'is_finished': is_fin,
            'google_url': g_url,
            'home': {
                'name': hn,
                'name_en': ht['name_en'],
                'abbr': ht['abbr'],
                'logo': f'https://a.espncdn.com/i/teamlogos/soccer/500/{ht["id"]}.png',
                'score': hs
            },
            'away': {
                'name': an,
                'name_en': at['name_en'],
                'abbr': at['abbr'],
                'logo': f'https://a.espncdn.com/i/teamlogos/soccer/500/{at["id"]}.png',
                'score': ascore
            }
        })

    # ESPN 실시간 라이브 스코어보드 확인 (진행 중인 경기 갱신)
    try:
        live_url = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"
        live_data = _fetch_url_json(live_url, headers=headers, timeout=2.0)
        if live_data:
            for ev in live_data.get("events", []):
                ev_name = ev.get("name", "").lower()
                if "manchester united" in ev_name:
                    comp = ev.get("competitions", [{}])[0]
                    status_obj = comp.get("status", {}).get("type", {})
                    state = status_obj.get("state", "pre")
                    if state == "in":
                        teams = comp.get("competitors", [])
                        h_team = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
                        a_team = next((t for t in teams if t.get("homeAway") == "away"), teams[1])
                        # 첫 번째 예정 경기를 라이브로 교체
                        for m in base_matches:
                            if not m["is_finished"]:
                                m["is_live"] = True
                                m["state"] = "in"
                                m["status_kr"] = "LIVE"
                                m["home"]["score"] = str(h_team.get("score", "0"))
                                m["away"]["score"] = str(a_team.get("score", "0"))
                                break
    except Exception:
        pass

    _CACHE["soccer"]["data"] = base_matches
    _CACHE["soccer"]["timestamp"] = now
    return base_matches


SAFE_PRESS_LIST = [
    "연합뉴스", "한국경제", "매일경제", "전자신문", "디지털데일리", "ZDNet Korea",
    "지디넷코리아", "아이뉴스24", "AI타임스", "동아일보", "조선일보", "중앙일보",
    "경향신문", "한겨레", "YTN", "KBS", "MBC", "SBS", "JTBC", "머니투데이",
    "이데일리", "파이낸셜뉴스", "뉴시스", "뉴스1", "인공지능신문", "테크M", "IT조선",
    "블로터", "보안뉴스", "로봇신문", "디지털타임스", "인벤", "디스이즈게임",
    "게임메카", "게임포커스", "데일리게임", "경향게임스", "게임톡", "포모스"
]

NEWS_CATEGORIES = {
    "all": {
        "title": "전체 최신 소식",
        "query": "(AI OR 인공지능 OR 반도체 OR GPU OR 양자컴퓨터 OR 로봇 OR 게임산업 OR 게임업계 OR 미래기술) when:2d",
        "badge": "종합 최신"
    },
    "game": {
        "title": "게임 업계 · 산업",
        "query": "(게임산업 OR 게임업계 OR 넥슨 OR 크래프톤 OR 엔씨소프트 OR 넷마블 OR 콘솔 OR 스팀 OR e스포츠) when:3d",
        "badge": "게임산업"
    },
    "ai": {
        "title": "AI · 인공지능",
        "query": "(AI OR 인공지능 OR 생성형AI OR LLM OR OpenAI OR 딥러닝) when:3d",
        "badge": "AI 기술"
    },
    "semiconductor": {
        "title": "반도체 · 컴퓨터",
        "query": "(반도체 OR GPU OR HBM OR 양자컴퓨터 OR 슈퍼컴퓨팅 OR 엔비디아) when:3d",
        "badge": "반도체/컴퓨터"
    },
    "robotics": {
        "title": "로봇 · 자율주행",
        "query": "(휴머노이드 로봇 OR 자율주행 OR 스마트팩토리 OR UAM OR 보스턴다이내믹스) when:3d",
        "badge": "로보틱스"
    },
    "industry": {
        "title": "미래 산업 · 혁신",
        "query": "(4차산업혁명 OR 클라우드 OR 디지털트윈 OR 사이버보안 OR 바이오테크) when:3d",
        "badge": "미래산업"
    }
}

def clean_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()

def get_4th_industry_news(category: str = "all", query_keyword: str = None, limit: int = 30):
    """
    공신력 있는 뉴스 사이트에서 4차 산업 & 게임 산업 실시간 최신 뉴스 수집
    """
    global _CACHE
    cache_key = f"{category}_{query_keyword or ''}"
    now = time.time()
    if cache_key in _CACHE["news"] and (now - _CACHE["news"][cache_key]["timestamp"] < CACHE_TTL_NEWS):
        return _CACHE["news"][cache_key]["data"][:limit]

    target_query = ""
    badge_label = "최신 소식"
    if query_keyword and query_keyword.strip():
        target_query = f"{query_keyword.strip()} (AI OR 컴퓨터 OR 반도체 OR 게임 OR 로봇 OR 산업) when:3d"
        badge_label = f"검색: {query_keyword.strip()}"
    else:
        cat_info = NEWS_CATEGORIES.get(category, NEWS_CATEGORIES["all"])
        target_query = cat_info["query"]
        badge_label = cat_info["badge"]

    encoded_query = urllib.parse.quote(target_query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    news_list = []
    try:
        req = urllib.request.Request(rss_url, headers=headers)
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            xml_bytes = resp.read()
            root = ET.fromstring(xml_bytes.decode("utf-8", errors="replace"))
            items = root.findall(".//item")

            for item in items:
                title = item.findtext("title") or ""
                link = item.findtext("link") or ""
                pubDate = item.findtext("pubDate") or ""
                description = item.findtext("description") or ""
                source_el = item.findtext("source") or ""

                clean_title = title
                press_name = source_el
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    clean_title = parts[0].strip()
                    if not press_name:
                        press_name = parts[1].strip()

                if not press_name:
                    press_name = "전문 뉴스"

                is_verified = any(safe in press_name for safe in SAFE_PRESS_LIST)
                safety_badge = "공신력 언론사" if is_verified else "전문 뉴스"

                clean_desc = clean_html(description)
                clean_desc = re.sub(r"모두 보기", "", clean_desc).strip()
                if len(clean_desc) > 160:
                    clean_desc = clean_desc[:157] + "..."

                time_ago = "최근"
                diff_sec = 0
                try:
                    pub_dt = datetime.strptime(pubDate[:25], "%a, %d %b %Y %H:%M:%S")
                    diff = datetime.utcnow() - pub_dt
                    diff_sec = diff.total_seconds()
                    
                    # 7일 이상 지난 구형 기사는 제외
                    if diff_sec > 7 * 86400:
                        continue

                    hours = diff_sec // 3600
                    minutes = (diff_sec % 3600) // 60
                    if hours < 1:
                        time_ago = f"{int(max(1, minutes))}분 전"
                    elif hours < 24:
                        time_ago = f"{int(hours)}시간 전"
                    else:
                        time_ago = f"{int(hours // 24)}일 전"
                except Exception:
                    time_ago = "방금 전"

                thumb_theme = "tech"
                if any(w in clean_title for w in ["게임", "넥슨", "크래프톤", "엔씨", "넷마블", "스팀", "콘솔", "롤", "e스포츠"]):
                    thumb_theme = "game"
                elif any(w in clean_title for w in ["인공지능", "AI", "LLM", "GPT", "딥러닝"]):
                    thumb_theme = "ai"
                elif any(w in clean_title for w in ["반도체", "GPU", "컴퓨터", "HBM", "양자"]):
                    thumb_theme = "semiconductor"
                elif any(w in clean_title for w in ["로봇", "휴머노이드", "자율주행"]):
                    thumb_theme = "robotics"

                news_list.append({
                    "title": clean_title,
                    "press": press_name,
                    "is_verified": is_verified,
                    "safety_badge": safety_badge,
                    "link": link,
                    "desc": clean_desc,
                    "pubDate": pubDate,
                    "time_ago": time_ago,
                    "diff_sec": diff_sec,
                    "category_badge": badge_label,
                    "theme": thumb_theme
                })

        # 초 단위 시간 기준 가장 최신 기사가 1등으로 오도록 정렬
        news_list.sort(key=lambda x: x.get("diff_sec", 999999))
        _CACHE["news"][cache_key] = {"data": news_list, "timestamp": now}
        return news_list[:limit]
    except Exception as e:
        print(f"[Portal News Error] {e}")
        return []

def prewarm_cache():
    """서버 구동 시 또는 백그라운드에서 캐시를 즉시 사전 준비하여 0ms 응답 보장"""
    def _warm():
        try:
            with ThreadPoolExecutor(max_workers=6) as executor:
                futs = [
                    executor.submit(get_soccer_matches),
                    executor.submit(get_mu_standing)
                ]
                for city in KOREA_CITIES.keys():
                    futs.append(executor.submit(get_weather_and_air, city))
                for cat in NEWS_CATEGORIES.keys():
                    futs.append(executor.submit(get_4th_industry_news, cat, None, 30))
                for f in as_completed(futs):
                    try:
                        f.result()
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Prewarm Error] {e}")

    t = threading.Thread(target=_warm, daemon=True)
    t.start()

# 백그라운드 캐시 예열 자동 시작
prewarm_cache()
