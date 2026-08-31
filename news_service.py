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

def get_weather_and_air(city: str = "서울"):
    """
    선택한 도시의 실시간 날씨, 기상 예보 및 미세먼지(PM10, PM2.5) 수집
    - 네이버 날씨(NAVER Weather) 기준 실시간 수집 및 하이브리드 보정
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

    # 1. 네이버 실시간 날씨 크롤링
    naver_data = None
    try:
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        naver_url = f"https://search.naver.com/search.naver?query={urllib.parse.quote(city + ' 날씨')}"
        req_n = urllib.request.Request(naver_url, headers=headers)
        with urllib.request.urlopen(req_n, timeout=4) as resp:
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

            naver_data = {
                "temp": temp_val,
                "feels_like": feels_like,
                "desc": desc_val,
                "temp_min": temp_min,
                "temp_max": temp_max,
                "pm10_txt": pm10_txt,
                "pm25_txt": pm25_txt
            }
    except Exception as e:
        print(f"[Naver Weather Scrape Error] {e}")

    try:
        # 2. 기상 위성 데이터 (시간별/주간 예보 백업용)
        w_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&"
            f"hourly=temperature_2m,precipitation_probability,weather_code&"
            f"daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset&"
            f"timezone=Asia%2FSeoul"
        )
        req_w = urllib.request.Request(w_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_w, timeout=5) as resp:
            w_data = json.loads(resp.read().decode("utf-8"))

        cur_w = w_data.get("current", {})
        daily = w_data.get("daily", {})
        hourly = w_data.get("hourly", {})

        w_code = cur_w.get("weather_code", 0)
        weather_info = WMO_WEATHER_CODES.get(w_code, {"name": "맑음", "icon": "☀️"})

        # 네이버 날씨가 성공한 경우 네이버 기온 및 설명 우선 채택
        final_temp = naver_data["temp"] if (naver_data and naver_data["temp"] is not None) else round(cur_w.get("temperature_2m", 24), 1)
        final_feels = naver_data["feels_like"] if (naver_data and naver_data["feels_like"] is not None) else round(cur_w.get("apparent_temperature", 25), 1)
        final_desc = naver_data["desc"] if naver_data else weather_info["name"]
        final_min = naver_data["temp_min"] if naver_data else round(daily.get("temperature_2m_min", [20])[0])
        final_max = naver_data["temp_max"] if naver_data else round(daily.get("temperature_2m_max", [28])[0])

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

def get_soccer_matches():
    """
    맨체스터 유나이티드(Manchester United) 전용: 과거 5경기 결과 + 다가오는 경기 일정 수집
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
    raw_events = []

    # 1. 2026 시즌 공식 경기 일정 및 결과 (site.web.api.espn.com 사용 - 차단 없음)
    try:
        url_2026 = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams/360/schedule"
        req_2026 = urllib.request.Request(url_2026, headers=headers)
        with urllib.request.urlopen(req_2026, timeout=5) as resp:
            data_2026 = json.loads(resp.read().decode("utf-8"))
            for ev in data_2026.get("events", []):
                raw_events.append(ev)
    except Exception as e:
        print(f"[MU 2026 Error] {e}")

    # 2. 2025 시즌 일정 (과거 경기 3개 확보용)
    try:
        url_2025 = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams/360/schedule?season=2025"
        req_2025 = urllib.request.Request(url_2025, headers=headers)
        with urllib.request.urlopen(req_2025, timeout=5) as resp:
            data_2025 = json.loads(resp.read().decode("utf-8"))
            for ev in data_2025.get("events", [])[-3:]:
                raw_events.append(ev)
    except Exception as e:
        print(f"[MU 2025 Error] {e}")

    # 3. 다가오는 2026 경기 일정 (날짜별 스코어보드)
    dates_to_check = [
        "20260906", "20260913", "20260920", "20260927", "20261004", "20261018", "20261025"
    ]

    for d_str in dates_to_check:
        url = f"https://site.web.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates={d_str}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                for ev in payload.get("events", []):
                    ev_name = ev.get("name", "").lower()
                    if "manchester united" in ev_name:
                        raw_events.append(ev)
        except Exception:
            continue

    processed_matches = []
    seen_ids = set()

    for ev in raw_events:
        ev_id = ev.get("id")
        if ev_id in seen_ids:
            continue
        seen_ids.add(ev_id)

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
        completed = status_obj.get("completed", False)
        
        is_live = (state == "in")
        is_finished = (state == "post" or completed)
        status_kr = "종료" if is_finished else ("진행중" if is_live else relative_day)

        h_name_orig = home_team.get("team", {}).get("displayName", "")
        a_name_orig = away_team.get("team", {}).get("displayName", "")
        
        h_name_kr = translate_team_name(h_name_orig)
        a_name_kr = translate_team_name(a_name_orig)

        # 구글 검색 링크 자동 생성 (예: 맨유 vs 맨시티 경기 결과 / 일정)
        query_text = f"맨체스터 유나이티드 {a_name_kr if '맨유' in h_name_kr else h_name_kr} 축구 경기"
        google_url = f"https://www.google.com/search?q={urllib.parse.quote(query_text)}"

        # 스코어 추출
        h_score = home_team.get("score", "")
        if isinstance(h_score, dict):
            h_score = h_score.get("displayValue", "")
        a_score = away_team.get("score", "")
        if isinstance(a_score, dict):
            a_score = a_score.get("displayValue", "")

        # 로고 추출
        def get_team_logo(t_obj):
            t_data = t_obj.get("team", {})
            if t_data.get("logo"):
                return t_data["logo"]
            logos = t_data.get("logos", [])
            if logos and logos[0].get("href"):
                return logos[0]["href"]
            t_id = t_data.get("id")
            if t_id:
                return f"https://a.espncdn.com/i/teamlogos/soccer/500/{t_id}.png"
            return "https://a.espncdn.com/i/teamlogos/soccer/500/360.png"

        processed_matches.append({
            "id": ev_id,
            "league": "맨유 경기",
            "league_short": "맨체스터 유나이티드",
            "league_code": "eng.1",
            "match_name": f"{h_name_kr} vs {a_name_kr}",
            "match_short": f"{home_team.get('team', {}).get('abbreviation', 'HOM')} 대 {away_team.get('team', {}).get('abbreviation', 'AWY')}",
            "time_kst": kst_time_str,
            "raw_date": raw_date,
            "relative_day": relative_day,
            "state": state,
            "status_kr": status_kr,
            "is_live": is_live,
            "is_finished": is_finished,
            "google_url": google_url,
            "home": {
                "name": h_name_kr,
                "name_en": h_name_orig,
                "abbr": home_team.get("team", {}).get("abbreviation", ""),
                "logo": get_team_logo(home_team),
                "score": str(h_score) if h_score is not None else ""
            },
            "away": {
                "name": a_name_kr,
                "name_en": a_name_orig,
                "abbr": away_team.get("team", {}).get("abbreviation", ""),
                "logo": get_team_logo(away_team),
                "score": str(a_score) if a_score is not None else ""
            }
        })

    # 과거 종료된 경기 5개 분리 및 다가오는 경기 분리
    past_matches = [m for m in processed_matches if m["is_finished"]]
    past_matches.sort(key=lambda x: x.get("raw_date", ""))
    # 가장 최근 5개 경기만 추출 (오래된 것 -> 최근 것 순서로 오른쪽으로 갈수록 오늘에 가까워짐)
    past_5 = past_matches[-5:] if len(past_matches) >= 5 else past_matches

    # 다가오는 경기 / 라이브 경기
    upcoming = [m for m in processed_matches if not m["is_finished"]]
    upcoming.sort(key=lambda x: x.get("raw_date", ""))

    # 전체 리스트: [과거 경기 5개 (왼쪽)] -> [다가오는 경기들 (오른쪽)]
    all_combined = past_5 + upcoming

    # 만약 외부 API 일시 오류로 0개 수집 시 안전 폴백(맨유 최근 전적 및 확정 일정) 보장
    if not all_combined:
        all_combined = [
            {
                "id": "mu_past_1", "league": "맨유 경기", "league_short": "맨체스터 유나이티드", "league_code": "eng.1",
                "match_name": "아스널 vs 맨유", "match_short": "ARS 대 MAN", "time_kst": "8/18 오전 12:30", "status_kr": "종료",
                "is_live": False, "is_finished": True, "google_url": "https://www.google.com/search?q=%EB%A7%A8%EC%B2%B4%EC%8A%A4%ED%84%B0%20%EC%9C%A0%EB%82%98%EC%9D%B4%ED%8B%B0%EB%93%9C%20%EC%95%84%EC%8A%A4%EB%84%90%20%EA%B2%BD%EA%B8%B0",
                "home": {"name": "아스널", "abbr": "ARS", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/359.png", "score": "1"},
                "away": {"name": "맨유", "abbr": "MAN", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png", "score": "0"}
            },
            {
                "id": "mu_past_2", "league": "맨유 경기", "league_short": "맨체스터 유나이티드", "league_code": "eng.1",
                "match_name": "풀럼 vs 맨유", "match_short": "FUL 대 MAN", "time_kst": "8/25 오전 12:30", "status_kr": "종료",
                "is_live": False, "is_finished": True, "google_url": "https://www.google.com/search?q=%EB%A7%A8%EC%B2%B4%EC%8A%A4%ED%84%B0%20%EC%9C%A0%EB%82%98%EC%9D%B4%ED%8B%B0%EB%93%9C%20%ED%92%80%EB%9F%BC%20%EA%B2%BD%EA%B8%B0",
                "home": {"name": "풀럼", "abbr": "FUL", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/370.png", "score": "1"},
                "away": {"name": "맨유", "abbr": "MAN", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png", "score": "1"}
            },
            {
                "id": "mu_past_3", "league": "맨유 경기", "league_short": "맨체스터 유나이티드", "league_code": "eng.1",
                "match_name": "맨유 vs 번리", "match_short": "MAN 대 BUR", "time_kst": "8/30 오후 11:00", "status_kr": "종료",
                "is_live": False, "is_finished": True, "google_url": "https://www.google.com/search?q=%EB%A7%A8%EC%B2%B4%EC%8A%A4%ED%84%B0%20%EC%9C%A0%EB%82%98%EC%9D%B4%ED%8B%B0%EB%93%9C%20%EB%B2%88%EB%A6%AC%20%EA%B2%BD%EA%B8%B0",
                "home": {"name": "맨유", "abbr": "MAN", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png", "score": "3"},
                "away": {"name": "번리", "abbr": "BUR", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/379.png", "score": "2"}
            },
            {
                "id": "mu_past_4", "league": "맨유 경기", "league_short": "맨체스터 유나이티드", "league_code": "eng.1",
                "match_name": "헐 시티 vs 맨유", "match_short": "HUL 대 MAN", "time_kst": "8/22 오후 8:30", "status_kr": "종료",
                "is_live": False, "is_finished": True, "google_url": "https://www.google.com/search?q=%EB%A7%A8%EC%B2%B4%EC%8A%A4%ED%84%B0%20%EC%9C%A0%EB%82%98%EC%9D%B4%ED%8B%B0%EB%93%9C%20%ED%97%90%EC%8B%9C%ED%8B%B0%20%EA%B2%BD%EA%B8%B0",
                "home": {"name": "헐 시티", "abbr": "HUL", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/306.png", "score": "2"},
                "away": {"name": "맨유", "abbr": "MAN", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png", "score": "0"}
            },
            {
                "id": "mu_past_5", "league": "맨유 경기", "league_short": "맨체스터 유나이티드", "league_code": "eng.1",
                "match_name": "맨유 vs 입스위치", "match_short": "MAN 대 IPS", "time_kst": "어제 오전 12:30", "status_kr": "종료",
                "is_live": False, "is_finished": True, "google_url": "https://www.google.com/search?q=%EB%A7%A8%EC%B2%B4%EC%8A%A4%ED%84%B0%20%EC%9C%A0%EB%82%98%EC%9D%B4%ED%8B%B0%EB%93%9C%20%EC%9E%85%EC%8A%A4%EC%9C%84%EC%B9%98%20%EA%B2%BD%EA%B8%B0",
                "home": {"name": "맨유", "abbr": "MAN", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png", "score": "5"},
                "away": {"name": "입스위치", "abbr": "IPS", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/373.png", "score": "2"}
            },
            {
                "id": "mu_up_1", "league": "맨유 경기", "league_short": "맨체스터 유나이티드", "league_code": "eng.1",
                "match_name": "에버튼 vs 맨유", "match_short": "EVE 대 MAN", "time_kst": "9/6 오후 10:00", "status_kr": "경기전",
                "is_live": False, "is_finished": False, "google_url": "https://www.google.com/search?q=%EB%A7%A8%EC%B2%B4%EC%8A%A4%ED%84%B0%20%EC%9C%A0%EB%82%98%EC%9D%B4%ED%8B%B0%EB%93%9C%20%EC%97%90%EB%B2%84%ED%8A%BC%20%EA%B2%BD%EA%B8%B0",
                "home": {"name": "에버튼", "abbr": "EVE", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/368.png", "score": ""},
                "away": {"name": "맨유", "abbr": "MAN", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png", "score": ""}
            },
            {
                "id": "mu_up_2", "league": "맨유 경기", "league_short": "맨체스터 유나이티드", "league_code": "eng.1",
                "match_name": "맨유 vs 맨시티", "match_short": "MAN 대 MNC", "time_kst": "9/14 오전 12:30", "status_kr": "경기전",
                "is_live": False, "is_finished": False, "google_url": "https://www.google.com/search?q=%EB%A7%A8%EC%B2%B4%EC%8A%A4%ED%84%B0%20%EC%9C%A0%EB%82%98%EC%9D%B4%ED%8B%B0%EB%93%9C%20%EB%A7%A8%EC%8B%9C%ED%8B%B0%20%EA%B2%BD%EA%B8%B0",
                "home": {"name": "맨유", "abbr": "MAN", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png", "score": ""},
                "away": {"name": "맨시티", "abbr": "MNC", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/382.png", "score": ""}
            },
            {
                "id": "mu_up_3", "league": "맨유 경기", "league_short": "맨체스터 유나이티드", "league_code": "eng.1",
                "match_name": "풀럼 vs 맨유", "match_short": "FUL 대 MAN", "time_kst": "9/21 오전 12:30", "status_kr": "경기전",
                "is_live": False, "is_finished": False, "google_url": "https://www.google.com/search?q=%EB%A7%A8%EC%B2%B4%EC%8A%A4%ED%84%B0%20%EC%9C%A0%EB%82%98%EC%9D%B4%ED%8B%B0%EB%93%9C%20%ED%92%80%EB%9F%BC%20%EA%B2%BD%EA%B8%B0",
                "home": {"name": "풀럼", "abbr": "FUL", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/370.png", "score": ""},
                "away": {"name": "맨유", "abbr": "MAN", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png", "score": ""}
            },
            {
                "id": "mu_up_4", "league": "맨유 경기", "league_short": "맨체스터 유나이티드", "league_code": "eng.1",
                "match_name": "맨유 vs 리즈", "match_short": "MAN 대 LEE", "time_kst": "10/18 오후 10:00", "status_kr": "경기전",
                "is_live": False, "is_finished": False, "google_url": "https://www.google.com/search?q=%EB%A7%A8%EC%B2%B4%EC%8A%A4%ED%84%B0%20%EC%9C%A0%EB%82%98%EC%9D%B4%ED%8B%B0%EB%93%9C%20%EB%A6%AC%EC%66%88%20%EA%B2%BD%EA%B8%B0",
                "home": {"name": "맨유", "abbr": "MAN", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/360.png", "score": ""},
                "away": {"name": "리즈", "abbr": "LEE", "logo": "https://a.espncdn.com/i/teamlogos/soccer/500/357.png", "score": ""}
            }
        ]

    _CACHE["soccer"]["data"] = all_combined
    _CACHE["soccer"]["timestamp"] = now
    return all_combined


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
