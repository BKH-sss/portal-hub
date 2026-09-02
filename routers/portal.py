"""
routers/portal.py
------------------------------------------------------------
🏛️ NEXT PULSE 4차 산업 포털 & 외신 & 스포츠/날씨/주식 라우터.
- 포털 메인 웹 페이지 서빙 (/portal, /portal.html, /)
- 실시간 날씨 및 미세먼지 API (/api/portal/weather)
- 맨체스터 유나이티드 축구 일정 API (/api/portal/soccer)
- 4차 산업 / AI / 반도체 실시간 뉴스 API (/api/portal/news)
- 포털 종합 데이터 오버뷰 API (/api/portal/overview)
- 스카디 실시간 주식 퀀트 리포트 API (/api/stock/report)
------------------------------------------------------------
"""

import os
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

import news_service
import stock_engine

router = APIRouter(tags=["Portal & News & Stock"])

# ============================================================
# 1. Pydantic 요청 스키마 정의
# ============================================================
class StockQueryRequest(BaseModel):
    """주식 종목 분석 요청 모델"""
    query: str

# ============================================================
# 2. 웹 페이지 서빙 엔드포인트
# ============================================================
@router.get("/portal", summary="포털 메인 페이지")
@router.get("/portal.html", summary="포털 메인 페이지 (HTML)")
def read_portal():
    """국내 포털 메인 페이지(index.html 또는 portal.html)를 반환합니다."""
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    if os.path.exists("portal.html"):
        return FileResponse("portal.html")
    return FileResponse("chatbot.html")

# ============================================================
# 3. 4차 산업 포털 데이터 API
# ============================================================
@router.get("/api/portal/overview", summary="포털 종합 대시보드 데이터")
def get_portal_overview_api(city: str = "서울", category: str = "all"):
    """
    상단 축구 경기 일정 + 도시별 날씨/미세먼지 + 주요 4차 산업 뉴스를 
    한 번의 요청으로 모두 가져오는 고속 종합 엔드포인트입니다.
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
    """Open-Meteo 기반 도시별 실시간 기온, 체감온도, 미세먼지(PM10/PM2.5)를 반환합니다."""
    return news_service.get_weather_and_air(city)

@router.get("/api/portal/soccer", summary="맨유 축구 경기 일정 & 실시간 결과")
def get_portal_soccer_api():
    """ESPN Scoreboard API 기반 맨체스터 유나이티드 최신 경기 일정과 결과를 반환합니다."""
    return news_service.get_soccer_matches()

@router.get("/api/portal/news", summary="4차 산업 실시간 뉴스 피드")
def get_portal_news_api(category: str = "all", q: Optional[str] = None, limit: int = 25):
    """Google News RSS 및 주요 IT 언론사 기반 실시간 기술 뉴스를 반환합니다."""
    return news_service.get_4th_industry_news(category=category, query_keyword=q, limit=limit)

# ============================================================
# 4. 스카디 주식 퀀트 분석 리포트 API
# ============================================================
@router.post("/api/stock/report", summary="스카디 주식 퀀트 분석 리포트")
def get_stock_report_api(req: StockQueryRequest):
    """
    사용자가 입력한 종목명(예: 삼성전자, 엔비디아, 테슬라)의 실시간 주가, 재무제표,
    PER/PBR, 배당수익률 및 스카디의 직설적인 퀀트 투자 분석평을 반환합니다.
    """
    try:
        result = stock_engine.generate_skadi_stock_report(req.query)
        return result
    except Exception as e:
        return {"success": False, "message": f"주식 분석 중 오류 발생: {str(e)}"}
