"""
routers/portal.py
==============================================================================
🏛️ NEXT PULSE 4차 산업 포털 & 외신 & 스포츠/날씨/주식 라우터
==============================================================================
이 모듈은 웹 브라우저 접속자를 위한 국내 포털 페이지 서빙, 맨체스터 유나이티드 경기 일정,
전국 주요 도시 실시간 날씨 및 미세먼지 수치, 4차 산업 최신 IT 뉴스 및
스카디 실시간 주식 퀀트 분석 리포트를 제공하는 포털 전용 API 라우터입니다.

주요 엔드포인트:
  1) GET  /portal, /portal.html : 국내 포털 메인 UI (index.html) 서빙
  2) GET  /api/portal/overview  : 축구 일정 + 날씨 + 최신 뉴스를 한 번에 가져오는 통합 엔드포인트
  3) GET  /api/portal/weather   : 전국 도시별 실시간 기온/체감온도/미세먼지(PM10/PM2.5)
  4) GET  /api/portal/soccer    : ESPN API 기반 맨체스터 유나이티드 최신 경기 일정 & 결과
  5) GET  /api/portal/news      : 4차 산업(AI, 반도체, 로봇) 카테고리별 실시간 뉴스 피드
  6) POST /api/stock/report     : 스카디 퀀트의 종목별 팩폭 재무 분석 및 투자 진단
==============================================================================
"""

import os
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

# 포털 독립 패키지(portal/) 또는 로컬 모듈에서 news_service 안전 임포트
try:
    from portal import news_service
except Exception:
    import news_service
import stock_engine

router = APIRouter(tags=["Portal & News & Stock"])

# ==============================================================================
# 1. Pydantic 요청 스키마 정의
# ==============================================================================
class StockQueryRequest(BaseModel):
    """주식 종목 분석 요청 모델"""
    query: str                      # 분석할 종목명 또는 티커 (예: 삼성전자, NVDA, TSLA, SPY 등)

# ==============================================================================
# 2. 웹 페이지 서빙 엔드포인트
# ==============================================================================
@router.get("/portal", summary="포털 메인 페이지")
@router.get("/portal.html", summary="포털 메인 페이지 (HTML)")
def read_portal():
    """
    국내 포털 메인 페이지를 반환합니다.
    portal/index.html ➔ index.html ➔ portal/portal.html 순서로 파일 존재 여부를 탐색하여 안전하게 서빙합니다.
    """
    for cand in ["portal/index.html", "index.html", "portal/portal.html", "portal.html"]:
        if os.path.exists(cand):
            return FileResponse(cand)
    return FileResponse("chatbot.html")

# ==============================================================================
# 3. 4차 산업 포털 데이터 API
# ==============================================================================
@router.get("/api/portal/overview", summary="포털 종합 대시보드 데이터")
def get_portal_overview_api(city: str = "서울", category: str = "all"):
    """
    ⚡ [고속 종합 대시보드]
    1) 상단 맨체스터 유나이티드 경기 일정 및 최근 경기 결과
    2) 요청한 도시(서울/부산/인천 등)의 기온, 날씨 아이콘, 미세먼지 수치
    3) 선택된 카테고리(AI, 반도체, 로봇 등)의 최신 4차 산업 뉴스 헤드라인 20개
    를 단 1회의 HTTP 요청으로 취합하여 프론트엔드로 전달합니다.
    """
    try:
        weather_data = news_service.get_weather_and_air(city)
        soccer_data = news_service.get_soccer_matches()
        news_data = news_service.get_4th_industry_news(category=category, limit=20)
        return {
            "success": True,
            "weather": weather_data,
            "soccer": soccer_data,
            "news": news_data,
            "categories": [
                {"id": "all", "name": "전체 최신"},
                {"id": "ai", "name": "AI · 인공지능"},
                {"id": "semiconductor", "name": "반도체 · 컴퓨터"},
                {"id": "robotics", "name": "로봇 · 자율주행"},
                {"id": "industry", "name": "미래 산업 · 혁신"}
            ],
            "cities": list(news_service.KOREA_CITIES.keys())
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/api/portal/weather", summary="실시간 날씨 및 대기질")
def get_portal_weather_api(city: str = "서울"):
    """
    Open-Meteo 무료 글로벌 기상 API를 호출하여 지정된 도시의 
    현재 기온, 습도, 풍속, 미세먼지(PM10) 및 초미세먼지(PM2.5) 데이터를 반환합니다.
    """
    return news_service.get_weather_and_air(city)

@router.get("/api/portal/soccer", summary="맨유 축구 경기 일정 & 실시간 결과")
def get_portal_soccer_api():
    """
    ESPN 글로벌 축구 Scoreboard API를 실시간 조회하여 
    맨체스터 유나이티드(Manchester United)의 최근 종료 경기 스코어와 다가오는 경기 일정을 반환합니다.
    """
    return news_service.get_soccer_matches()

@router.get("/api/portal/news", summary="4차 산업 실시간 뉴스 피드")
def get_portal_news_api(category: str = "all", q: Optional[str] = None, limit: int = 25):
    """
    Google News RSS 및 국내 주요 IT 전문 매체로부터 수집된 4차 산업 뉴스를 
    카테고리별(AI, 반도체, 로봇)로 정렬하여 반환합니다.
    """
    return news_service.get_4th_industry_news(category=category, query_keyword=q, limit=limit)

# ==============================================================================
# 4. 스카디 주식 퀀트 분석 리포트 API
# ==============================================================================
@router.post("/api/stock/report", summary="스카디 주식 퀀트 분석 리포트")
def get_stock_report_api(req: StockQueryRequest):
    """
    yfinance 및 국내 금융 데이터 엔진을 통해 해당 종목의 실시간 시세,
    RSI 지표, 52주 고저점 위치, PER/배당률을 분석하고,
    스카디 퀀트 페르소나가 작성한 직설적인 안전 자산 배분 투자 진단서를 반환합니다.
    """
    try:
        result = stock_engine.generate_skadi_stock_report(req.query)
        return result
    except Exception as e:
        return {"success": False, "message": f"주식 분석 중 오류 발생: {str(e)}"}
