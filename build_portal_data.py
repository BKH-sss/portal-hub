# -*- coding: utf-8 -*-
"""
GitHub Actions 및 정적 배포용 포털 데이터 생성기 (data/portal_data.json)
"""

import os
import json
import time
from datetime import datetime
import news_service

def build_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    print("[1/3] 맨체스터 유나이티드 경기 일정 수집 중...")
    soccer = news_service.get_soccer_matches()
    print(f" -> {len(soccer)}개 경기 수집 완료")

    print("[2/3] 주요 도시 실시간 날씨 및 미세먼지 수집 중...")
    weather = {}
    for city in ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "제주"]:
        weather[city] = news_service.get_weather_and_air(city)
    print(" -> 날씨 수집 완료")

    print("[3/3] 4차 산업 5개 카테고리 핵심 뉴스 수집 중...")
    news = {
        "all": news_service.get_4th_industry_news("all", limit=25),
        "ai": news_service.get_4th_industry_news("ai", limit=25),
        "semiconductor": news_service.get_4th_industry_news("semiconductor", limit=25),
        "robotics": news_service.get_4th_industry_news("robotics", limit=25),
        "industry": news_service.get_4th_industry_news("industry", limit=25),
    }
    print(" -> 뉴스 수집 완료")

    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "soccer": soccer,
        "weather": weather,
        "news": news
    }

    target_path = os.path.join(data_dir, "portal_data.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] data/portal_data.json saved! (크기: {os.path.getsize(target_path)} bytes)")

if __name__ == "__main__":
    build_data()
