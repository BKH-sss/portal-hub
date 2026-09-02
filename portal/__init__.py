"""
portal/__init__.py
------------------------------------------------------------
🏛️ NEXT PULSE & 🌍 ORBIS 포털 전용 독립 패키지.
- news_service: 국내 4차 산업 뉴스, 맨유 경기 일정, 실시간 날씨 수집 엔진
- global_news_service: 전 세계 150개+ 글로벌 외신 RSS 수집 및 AI 요약 엔진
- build_portal_data: 포털 데이터 자동 수집 및 JSON 빌더
------------------------------------------------------------
"""

from portal import news_service
from portal import global_news_service

__all__ = ["news_service", "global_news_service"]
