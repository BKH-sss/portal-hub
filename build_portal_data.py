import os
import json
import time
from datetime import datetime
import news_service
import global_news_service

def build_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    print("==================================================")
    print("  [1] ERECHTHEION KOREA (국내 포털 데이터 수집)")
    print("==================================================")
    print("[1/3] 맨체스터 유나이티드 경기 일정 및 순위 수집 중...")
    soccer = news_service.get_soccer_matches()
    standing = news_service.get_mu_standing()
    print(f" -> {len(soccer)}개 경기 및 순위({standing['badge_text']}) 수집 완료")

    print("[2/3] 4개 도시(서울, 수원, 익산, 부산) 실시간 날씨 및 미세먼지 수집 중...")
    weather = {}
    for city in ["서울", "수원", "익산", "부산"]:
        weather[city] = news_service.get_weather_and_air(city)
    print(" -> 날씨 수집 완료")

    print("[3/3] 4차 산업 및 게임 산업 6개 카테고리 핵심 뉴스 수집 중...")
    news = {
        "all": news_service.get_4th_industry_news("all", limit=30),
        "game": news_service.get_4th_industry_news("game", limit=30),
        "ai": news_service.get_4th_industry_news("ai", limit=30),
        "semiconductor": news_service.get_4th_industry_news("semiconductor", limit=30),
        "robotics": news_service.get_4th_industry_news("robotics", limit=30),
        "industry": news_service.get_4th_industry_news("industry", limit=30),
    }
    print(" -> 국내 뉴스 수집 완료")

    portal_output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "soccer": soccer,
        "mu_standing": standing,
        "weather": weather,
        "news": news
    }

    target_path = os.path.join(data_dir, "portal_data.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(portal_output, f, ensure_ascii=False, indent=2)
    print(f"[SUCCESS] data/portal_data.json saved! (크기: {os.path.getsize(target_path)} bytes)")

    print("\n==================================================")
    print("  [2] ORBIS GLOBAL (해외 주요 외신 인텔리전스 수집)")
    print("==================================================")
    global_news = global_news_service.get_all_global_news(limit_per_category=30)
    
    global_output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": sum(len(v) for k, v in global_news.items() if k != "all"),
        "news": global_news
    }

    global_target_path = os.path.join(data_dir, "global_data.json")
    with open(global_target_path, "w", encoding="utf-8") as f:
        json.dump(global_output, f, ensure_ascii=False, indent=2)
    print(f"[SUCCESS] data/global_data.json saved! (총 {global_output['total_count']}개 외신 기사, 크기: {os.path.getsize(global_target_path)} bytes)")

if __name__ == "__main__":
    build_data()
