import os
import re
import json
import time
import requests
import yfinance as yf
from bs4 import BeautifulSoup

# 대표 한국/미국 안전 우량주 및 ETF 매핑 사전
KOREA_MAPPINGS = {
    "삼성전자": "005930.KS", "삼전": "005930.KS",
    "sk하이닉스": "000660.KS", "하이닉스": "000660.KS",
    "현대차": "005380.KS", "기아": "000270.KS",
    "naver": "035420.KS", "네이버": "035420.KS",
    "카카오": "035720.KS",
    "lg에너지솔루션": "373220.KS", "엔솔": "373220.KS",
    "삼성바이오로직스": "207940.KS", "삼바": "207940.KS",
    "삼성sdi": "006400.KS", "셀트리온": "068270.KS",
    "posco홀딩스": "005490.KS", "포스코": "005490.KS",
    "신한지주": "055550.KS", "kb금융": "105560.KS",
    "kodex 200": "069500.KS", "코덱스200": "069500.KS",
    "tiger 미국s&p500": "360750.KS", "타이거 미국s&p500": "360750.KS", "미국s&p500": "360750.KS",
    "tiger 미국나스닥100": "133690.KS", "타이거 미국나스닥100": "133690.KS", "미국나스닥100": "133690.KS",
    "tiger 미국배당다우존스": "458730.KS", "타이거 미국배당다우존스": "458730.KS", "미국배당다우존스": "458730.KS",
    "kodex 미국s&p500tr": "379800.KS", "ace 미국s&p500": "360200.KS"
}

US_MAPPINGS = {
    "애플": "AAPL", "마이크로소프트": "MSFT", "마소": "MSFT",
    "엔비디아": "NVDA", "구글": "GOOGL", "알파벳": "GOOGL",
    "아마존": "AMZN", "메타": "META", "페이스북": "META",
    "테슬라": "TSLA", "버크셔": "BRK-B", "워렌버핏": "BRK-B",
    "spy": "SPY", "s&p500": "SPY", "snp500": "SPY",
    "qqq": "QQQ", "나스닥": "QQQ",
    "schd": "SCHD", "슈드": "SCHD",
    "voo": "VOO", "ivv": "IVV", "vti": "VTI",
    "tqqq": "TQQQ", "soxx": "SOXX", "smh": "SMH",
    "코카콜라": "KO", "펩시": "PEP", "존슨앤존슨": "JNJ",
    "비자": "V", "마스터카드": "MA", "tsmc": "TSM",
    "asml": "ASML", "일라이릴리": "LLY", "노보노디스크": "NVO"
}

def resolve_ticker(query: str):
    """사용자의 질의에서 티커/종목코드를 추출하거나 매핑"""
    q = query.strip().lower()
    
    # 6자리 한국 종목코드
    if re.match(r'^\d{6}$', q):
        return f"{q}.KS", "KR"
    if q.endswith('.ks') or q.endswith('.kq'):
        return q.upper(), "KR"
    
    # 사전 매핑 (한국)
    for name, ticker in KOREA_MAPPINGS.items():
        if name in q:
            return ticker, "KR"
            
    # 사전 매핑 (미국)
    for name, ticker in US_MAPPINGS.items():
        if name in q:
            return ticker, "US"
            
    # 영문 티커 (1~5자리 대문자)
    words = re.findall(r'[a-zA-Z]{1,5}', query)
    for w in words:
        w_up = w.upper()
        if w_up in ["BUY", "SELL", "STOCK", "INFO", "NOW", "WHAT", "SHOW", "ANALYSIS", "HI"]:
            continue
        return w_up, "US"

    # 네이버 증권 검색 시도 (한국 주식 크롤링 검색)
    try:
        url = f"https://finance.naver.com/search/searchList.naver?query={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(res.text, 'html.parser')
        title_tag = soup.select_one('td.tit a')
        if title_tag and 'code=' in title_tag.get('href', ''):
            code = title_tag['href'].split('code=')[-1].strip()
            return f"{code}.KS", "KR"
    except Exception:
        pass

    return None, None

def get_stock_metrics(ticker_symbol: str):
    """yfinance를 통한 핵심 재무/가격/기술 지표 추출 (기초/안전 투자 위주)"""
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.info
        hist = t.history(period="6mo")
        
        if hist.empty:
            return None

        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
        change_pct = ((current_price - prev_price) / prev_price) * 100

        # 이동평균선 (20일, 60일, 120일)
        ma20 = hist['Close'].rolling(20).mean().iloc[-1] if len(hist) >= 20 else current_price
        ma60 = hist['Close'].rolling(60).mean().iloc[-1] if len(hist) >= 60 else current_price
        ma120 = hist['Close'].rolling(120).mean().iloc[-1] if len(hist) >= 120 else current_price

        # RSI (14일)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain.iloc[-1] / (loss.iloc[-1] + 1e-9)
        rsi = 100 - (100 / (1 + rs))

        # 52주 최고/최저 대비 위치
        high_52 = info.get('fiftyTwoWeekHigh', hist['High'].max())
        low_52 = info.get('fiftyTwoWeekLow', hist['Low'].min())
        position_52 = 0
        if high_52 and low_52 and high_52 > low_52:
            position_52 = ((current_price - low_52) / (high_52 - low_52)) * 100

        # 안전 지표 (배당률, PER, PBR, 부채비율)
        dividend_yield = (info.get('dividendYield') or 0) * 100
        trailing_pe = info.get('trailingPE', None)
        forward_pe = info.get('forwardPE', None)
        price_to_book = info.get('priceToBook', None)
        debt_to_equity = info.get('debtToEquity', None)
        currency = info.get('currency', 'KRW' if '.KS' in ticker_symbol else 'USD')
        name = info.get('shortName') or info.get('longName') or ticker_symbol

        return {
            "name": name,
            "symbol": ticker_symbol,
            "currency": currency,
            "current_price": round(current_price, 2),
            "change_pct": round(change_pct, 2),
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2),
            "ma120": round(ma120, 2),
            "rsi": round(rsi, 1),
            "high_52": round(high_52, 2) if high_52 else "N/A",
            "low_52": round(low_52, 2) if low_52 else "N/A",
            "position_52": round(position_52, 1),
            "dividend_yield": round(dividend_yield, 2),
            "pe": round(trailing_pe, 2) if trailing_pe else (round(forward_pe, 2) if forward_pe else "N/A"),
            "pbr": round(price_to_book, 2) if price_to_book else "N/A",
            "debt_to_equity": debt_to_equity
        }
    except Exception as e:
        print(f"[Stock Metrics Error] {ticker_symbol}: {e}")
        return None

def analyze_safety_tier(metrics: dict):
    """안전 기초 투자 관점에서의 점수화 및 평가"""
    rsi = metrics.get('rsi', 50)
    pos52 = metrics.get('position_52', 50)
    div = metrics.get('dividend_yield', 0)
    pe = metrics.get('pe', 20)
    
    status_tags = []
    if rsi < 35:
        status_tags.append("📉 과매도 구간(분할매수 기회)")
    elif rsi > 70:
        status_tags.append("🔥 단기 과열 구간(추격매수 절대금지)")
    else:
        status_tags.append("⚖️ 중립/관망 구간")

    if div >= 3.0:
        status_tags.append(f"💰 고배당 방어주 ({div}%)")
    elif div >= 1.5:
        status_tags.append(f"🌱 배당성장형 ({div}%)")

    if pos52 <= 30:
        status_tags.append("🛡️ 52주 바닥권(안전마진 확보)")
    elif pos52 >= 85:
        status_tags.append("⚠️ 52주 신고가 근접(분할접근 필수)")

    return status_tags

def generate_skadi_stock_report(query: str):
    """스카디의 실시간 팩폭 안전 주식 진단 리포트 생성"""
    ticker, market = resolve_ticker(query)
    
    if not ticker:
        return {
            "success": True,
            "type": "guide",
            "message": "종목명을 입력해봐 (예: 삼성전자, 애플, SPY, SCHD, QQQ, 엔비디아).\n\n"
                       "**[스카디의 안전 기초 투자 기본 원칙]**\n"
                       "1. 개잡주/동전주에 몰빵하지 마. 원금 잃으면 복구가 불가능해.\n"
                       "2. 미국 대표 ETF(SPY, QQQ, SCHD)나 한국 1등주를 분할 적립식으로 모아가는 게 확실한 승률을 보장해.\n"
                       "3. 단기 급등(RSI 70 이상)에서 추격매수하지 말고, 눌림목이나 공포 구간에서 분할 매수해."
        }

    metrics = get_stock_metrics(ticker)
    if not metrics:
        return {
            "success": False,
            "message": f"'{query}' ({ticker})의 실시간 시세를 가져오지 못했어. 티커나 이름을 다시 확인해봐."
        }

    safety_tags = analyze_safety_tier(metrics)
    tag_str = " | ".join(safety_tags)
    
    curr_sym = "₩" if metrics["currency"] == "KRW" else "$"
    price_formatted = f"{curr_sym}{metrics['current_price']:,}"
    change_color = "🔴 +" if metrics["change_pct"] >= 0 else "🔵 "
    
    tv_symbol = ticker.replace(".KS", "").replace(".KQ", "")
    if ".KS" in ticker:
        tv_symbol = f"KRX:{tv_symbol}"
    elif market == "US":
        tv_symbol = f"NASDAQ:{ticker}" if ticker in ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "QQQ", "TQQQ", "SOXX"] else f"AMEX:{ticker}"

    report_markdown = f"""### 📊 스카디의 냉철한 팩폭 종목 진단: **{metrics['name']} ({ticker})**

- **현재가**: **{price_formatted}** ({change_color}{metrics['change_pct']}%)
- **안전/수급 진단**: `{tag_str}`
- **기술적 지표**: RSI **{metrics['rsi']}** | 20일선: {curr_sym}{metrics['ma20']:,} | 60일선: {curr_sym}{metrics['ma60']:,}
- **기초 밸류에이션**: 배당률 **{metrics['dividend_yield']}%** | PER **{metrics['pe']}** | PBR **{metrics['pbr']}**
- **52주 위치**: 저점 대비 **{metrics['position_52']}%** 수준 (최저 {curr_sym}{metrics['low_52']:,} ~ 최고 {curr_sym}{metrics['high_52']:,})

---
**💡 스카디의 행동 지침 (기초 투자 안전 가이드)**:
"""
    prompt_context = f"""
[실시간 주식 팩트 데이터]
- 종목: {metrics['name']} ({ticker})
- 현재가: {price_formatted} (변동률: {metrics['change_pct']}%)
- 52주 위치: {metrics['position_52']}% (최저: {metrics['low_52']}, 최고: {metrics['high_52']})
- RSI(14일): {metrics['rsi']}
- 배당수익률: {metrics['dividend_yield']}%
- PER: {metrics['pe']}, PBR: {metrics['pbr']}
- 20일/60일 이동평균선: {metrics['ma20']} / {metrics['ma60']}
"""
    return {
        "success": True,
        "type": "stock_report",
        "ticker": ticker,
        "tv_symbol": tv_symbol,
        "metrics": metrics,
        "header_markdown": report_markdown,
        "prompt_context": prompt_context
    }

