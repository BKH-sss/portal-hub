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

# 한국 주요 도시 좌표
KOREA_CITIES = {
    "서울": {"lat": 37.5665, "lon": 126.9780, "sub": "수도권"},
    "경기(수원)": {"lat": 37.2636, "lon": 127.0286, "sub": "경기"},
    "인천": {"lat": 37.4563, "lon": 126.7052, "sub": "인천"},
    "부산": {"lat": 35.1796, "lon": 129.0756, "sub": "부산"},
    "대구": {"lat": 35.8714, "lon": 128.6014, "sub": "대구"},
    "대전": {"lat": 36.3504, "lon": 127.3845, "sub": "충청"},
    "광주": {"lat": 35.1595, "lon": 126.8526, "sub": "호남"},
    "울산": {"lat": 35.5384, "lon": 129.3114, "sub": "영남"},
    "강원(춘천)": {"lat": 37.8813, "lon": 127.7298, "sub": "강원"},
    "제주": {"lat": 33.4996, "lon": 126.5312, "sub": "제주"}
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
    "Hull City": "헐 시티", "Leeds United": "리즈", "Leeds": "리즈",
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

def get_weather_and_air(city: str = "서울"):
    """
    선택한 도시의 실시간 날씨, 기상 예보 및 미세먼지(PM10, PM2.5) 수집
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

    try:
        # 1. 기상청/Open-Meteo 실시간 기상 예보
        w_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&"
            f"hourly=temperature_2m,precipitation_probability,weather_code&"
            f"daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset&"
            f"timezone=Asia%2FSeoul"
        )
        req_w = urllib.request.Request(w_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req_w, timeout=6) as resp:
            w_data = json.loads(resp.read().decode("utf-8"))

        # 2. 실시간 대기질 & 미세먼지 (PM10, PM2.5, European AQI)
        air_url = (
            f"https://air-quality-api.open-meteo.com/v1/air-quality?"
            f"latitude={lat}&longitude={lon}&"
            f"current=pm10,pm2_5,european_aqi,carbon_monoxide,nitrogen_dioxide,ozone&"
            f"timezone=Asia%2FSeoul"
        )
        req_a = urllib.request.Request(air_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req_a, timeout=6) as resp:
            a_data = json.loads(resp.read().decode("utf-8"))

        cur_w = w_data.get("current", {})
        cur_a = a_data.get("current", {})
        daily = w_data.get("daily", {})
        hourly = w_data.get("hourly", {})

        w_code = cur_w.get("weather_code", 0)
        weather_info = WMO_WEATHER_CODES.get(w_code, {"name": "맑음", "icon": "☀️"})

        pm10_val = cur_a.get("pm10")
        pm25_val = cur_a.get("pm2_5")

        pm10_eval = evaluate_pm10(pm10_val)
        pm25_eval = evaluate_pm25(pm25_val)

        # 시간별 예보 가공 (향후 12시간)
        hourly_forecast = []
        cur_hour_str = cur_w.get("time", "")
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        codes = hourly.get("weather_code", [])
        pop = hourly.get("precipitation_probability", [])

        start_idx = 0
        if cur_hour_str and cur_hour_str in times:
            start_idx = times.index(cur_hour_str)
        elif len(times) > 0:
            start_idx = 0

        for i in range(start_idx, min(start_idx + 12, len(times))):
            t_obj = datetime.fromisoformat(times[i])
            c_code = codes[i] if i < len(codes) else 0
            c_meta = WMO_WEATHER_CODES.get(c_code, {"name": "맑음", "icon": "☀️"})
            hourly_forecast.append({
                "time": t_obj.strftime("%H시"),
                "temp": round(temps[i]) if i < len(temps) else "--",
                "icon": c_meta["icon"],
                "desc": c_meta["name"],
                "pop": pop[i] if i < len(pop) else 0
            })

        # 주간 일별 예보
        daily_forecast = []
        d_times = daily.get("time", [])
        d_max = daily.get("temperature_2m_max", [])
        d_min = daily.get("temperature_2m_min", [])
        d_codes = daily.get("weather_code", [])

        weekday_kr = ["월", "화", "수", "목", "금", "토", "일"]
        for i in range(min(5, len(d_times))):
            d_obj = datetime.fromisoformat(d_times[i])
            c_code = d_codes[i] if i < len(d_codes) else 0
            c_meta = WMO_WEATHER_CODES.get(c_code, {"name": "맑음", "icon": "☀️"})
            label = "오늘" if i == 0 else ("내일" if i == 1 else f"{d_obj.month}/{d_obj.day}({weekday_kr[d_obj.weekday()]})")
            daily_forecast.append({
                "day": label,
                "max": round(d_max[i]) if i < len(d_max) else "--",
                "min": round(d_min[i]) if i < len(d_min) else "--",
                "icon": c_meta["icon"],
                "desc": c_meta["name"]
            })

        result = {
            "city": city,
            "region": coords["sub"],
            "current": {
                "temp": round(cur_w.get("temperature_2m", 20), 1),
                "feels_like": round(cur_w.get("apparent_temperature", 20), 1),
                "humidity": cur_w.get("relative_humidity_2m", 50),
                "wind_speed": cur_w.get("wind_speed_10m", 0),
                "weather_desc": weather_info["name"],
                "weather_icon": weather_info["icon"],
                "weather_code": w_code,
                "temp_max": round(daily.get("temperature_2m_max", [25])[0]),
                "temp_min": round(daily.get("temperature_2m_min", [15])[0]),
                "time_kst": datetime.now().strftime("%H:%M")
            },
            "air": {
                "pm10": pm10_eval,
                "pm25": pm25_eval,
                "aqi": cur_a.get("european_aqi", 0),
                "tip": "미세먼지 상태가 좋아 야외활동하기 좋습니다." if pm10_eval["grade"] == "good" else (
                    "외출 시 마스크 착용을 권장합니다." if pm10_eval["grade"] in ["bad", "very-bad"] else "무난한 공기질입니다."
                )
            },
            "hourly": hourly_forecast,
            "daily": daily_forecast,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        _CACHE["weather"][city] = {"data": result, "timestamp": now}
        return result

    except Exception as e:
        print(f"[Portal Weather Error] {e}")
        return {
            "city": city,
            "region": "대한민국",
            "current": {
                "temp": 23.5,
                "feels_like": 24.0,
                "humidity": 55,
                "wind_speed": 2.1,
                "weather_desc": "맑음",
                "weather_icon": "☀️",
                "weather_code": 0,
                "temp_max": 28,
                "temp_min": 19,
                "time_kst": datetime.now().strftime("%H:%M")
            },
            "air": {
                "pm10": {"val": 22.0, "label": "좋음", "grade": "good", "color": "#3b82f6"},
                "pm25": {"val": 14.0, "label": "좋음", "grade": "good", "color": "#3b82f6"},
                "aqi": 20,
                "tip": "상쾌한 공기질입니다."
            },
            "hourly": [],
            "daily": [],
            "error": str(e)
        }

def get_soccer_matches():
    """
    맨체스터 유나이티드(Manchester United) 전용 경기 일정 및 최근 경기 결과 수집
    """
    global _CACHE
    now = time.time()
    if _CACHE["soccer"]["data"] and (now - _CACHE["soccer"]["timestamp"] < CACHE_TTL_SOCCER):
        return _CACHE["soccer"]["data"]

    # 맨체스터 유나이티드 경기 일정 수집 (최근 전적 + 다가오는 경기)
    dates_to_check = [
        "20260815", "20260822", "20260830", "20260906", "20260913", 
        "20260920", "20260927", "20261004", "20261018", "20261025"
    ]

    matches = []
    headers = {"User-Agent": "Mozilla/5.0"}

    # 1. 프리미어리그 날짜별 스코어보드에서 맨체스터 유나이티드 경기 추출
    for d_str in dates_to_check:
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates={d_str}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                for ev in payload.get("events", []):
                    ev_name = ev.get("name", "").lower()
                    if "manchester united" not in ev_name:
                        continue

                    comp = ev.get("competitions", [{}])[0]
                    teams = comp.get("competitors", [])
                    if len(teams) < 2:
                        continue

                    home_team = next((t for t in teams if t.get("homeAway") == "home"), teams[0])
                    away_team = next((t for t in teams if t.get("homeAway") == "away"), teams[1])

                    raw_date = ev.get("date", "")
                    kst_time_str = ""
                    relative_day = "일정"
                    try:
                        utc_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                        kst_dt = utc_dt.astimezone(timezone(timedelta(hours=9)))
                        now_kst = datetime.now(timezone(timedelta(hours=9)))
                        
                        diff_days = (kst_dt.date() - now_kst.date()).days
                        if diff_days == 0:
                            relative_day = "오늘"
                        elif diff_days == 1:
                            relative_day = "내일"
                        elif diff_days == -1:
                            relative_day = "어제"
                        elif diff_days > 1:
                            relative_day = f"{kst_dt.month}/{kst_dt.day}"
                        else:
                            relative_day = f"{kst_dt.month}/{kst_dt.day}"

                        ampm = "오전" if kst_dt.hour < 12 else "오후"
                        hour12 = kst_dt.hour % 12
                        if hour12 == 0:
                            hour12 = 12
                        kst_time_str = f"{relative_day} {ampm} {hour12}:{kst_dt.minute:02d}"
                    except Exception:
                        kst_time_str = raw_date

                    status_obj = comp.get("status", {}).get("type", {})
                    state = status_obj.get("state", "pre")
                    detail = status_obj.get("detail", "")
                    
                    status_kr = "경기전"
                    is_live = False
                    is_finished = False
                    if state == "post":
                        status_kr = "종료"
                        is_finished = True
                    elif state == "in":
                        status_kr = "진행중"
                        is_live = True
                    else:
                        status_kr = relative_day

                    h_name_orig = home_team.get("team", {}).get("displayName", "")
                    a_name_orig = away_team.get("team", {}).get("displayName", "")
                    
                    h_name_kr = translate_team_name(h_name_orig)
                    a_name_kr = translate_team_name(a_name_orig)

                    matches.append({
                        "id": ev.get("id"),
                        "league": "맨유 경기 일정",
                        "league_short": "맨체스터 유나이티드",
                        "league_code": "eng.1",
                        "match_name": f"{h_name_kr} vs {a_name_kr}",
                        "match_short": f"{home_team.get('team', {}).get('abbreviation', 'HOM')} vs {away_team.get('team', {}).get('abbreviation', 'AWY')}",
                        "time_kst": kst_time_str,
                        "raw_date": raw_date,
                        "relative_day": relative_day,
                        "state": state,
                        "status_kr": status_kr,
                        "is_live": is_live,
                        "is_finished": is_finished,
                        "home": {
                            "name": h_name_kr,
                            "name_en": h_name_orig,
                            "abbr": home_team.get("team", {}).get("abbreviation", ""),
                            "logo": home_team.get("team", {}).get("logo") or "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
                            "score": home_team.get("score", "")
                        },
                        "away": {
                            "name": a_name_kr,
                            "name_en": a_name_orig,
                            "abbr": away_team.get("team", {}).get("abbreviation", ""),
                            "logo": away_team.get("team", {}).get("logo") or "https://a.espncdn.com/i/teamlogos/soccer/500/360.png",
                            "score": away_team.get("score", "")
                        }
                    })
        except Exception:
            continue

    # 중복 제거
    seen = set()
    unique_matches = []
    for m in matches:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique_matches.append(m)

    # 정렬: 라이브 -> 다가오는 경기 (오름차순) -> 최근 종료 경기
    def sort_key(item):
        if item["is_live"]:
            return (0, item.get("raw_date", ""))
        elif not item["is_finished"]:
            return (1, item.get("raw_date", ""))
        else:
            return (2, item.get("raw_date", ""))

    unique_matches.sort(key=sort_key)
    _CACHE["soccer"]["data"] = unique_matches
    _CACHE["soccer"]["timestamp"] = now
    return unique_matches


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
    cache_key = f"{category}_{query_keyword or ''}_{limit}"
    now = time.time()
    if cache_key in _CACHE["news"] and (now - _CACHE["news"][cache_key]["timestamp"] < CACHE_TTL_NEWS):
        return _CACHE["news"][cache_key]["data"]

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
        with urllib.request.urlopen(req, timeout=7) as resp:
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
        result = news_list[:limit]
        _CACHE["news"][cache_key] = {"data": result, "timestamp": now}
        return result

    except Exception as e:
        print(f"[Portal News Error] {e}")
        return []
        return []
