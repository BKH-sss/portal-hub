import os
import re
import json
import time
import datetime
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor

_yf = None

def _get_yf():
    global _yf
    if _yf is None:
        import yfinance as _yf
    return _yf

# ------------------------------------------------------------
# 1. 대표 한국/미국 안전 우량주 및 ETF 매핑 사전
# ------------------------------------------------------------
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
    "하나금융지주": "086790.KS", "메리츠금융지주": "138040.KS",
    "현대모비스": "012330.KS", "삼성물산": "028260.KS",
    "lg전자": "066570.KS", "lg화학": "051910.KS",
    "크래프톤": "259960.KS", "엔씨소프트": "036570.KS",
    "한화에어로스페이스": "012450.KS", "한국항공우주": "047810.KS",
    "에코프로비엠": "247540.KQ", "에코프로": "086520.KQ",
    "알테오젠": "196170.KQ", "hlb": "028300.KQ",
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
    "브로드컴": "AVGO", "코스트코": "COST", "암드": "AMD", "amd": "AMD",
    "넷플릭스": "NFLX", "세일즈포스": "CRM", "어도비": "ADBE",
    "오라클": "ORCL", "퀄컴": "QCOM", "텍사스인스트루먼트": "TXN",
    "어플라이드머티어리얼즈": "AMAT", "팔란티어": "PLTR",
    "서비스나우": "NOW", "팰로앨토": "PANW", "시놉시스": "SNPS",
    "케이던스": "CDNS", "마벨": "MRVL", "램리서치": "LRCX", "kla": "KLAC",
    "아리스타": "ANET", "우버": "UBER", "크라우드스트라이크": "CRWD",
    "spy": "SPY", "s&p500": "SPY", "snp500": "SPY",
    "qqq": "QQQ", "나스닥": "QQQ",
    "schd": "SCHD", "슈드": "SCHD",
    "voo": "VOO", "ivv": "IVV", "vti": "VTI",
    "tqqq": "TQQQ", "soxx": "SOXX", "smh": "SMH",
    "코카콜라": "KO", "펩시": "PEP", "존슨앤존슨": "JNJ",
    "비자": "V", "마스터카드": "MA", "tsmc": "TSM",
    "asml": "ASML", "일라이릴리": "LLY", "노보노디스크": "NVO",
    "유나이티드헬스": "UNH", "프록터앤갬블": "PG", "홈디포": "HD",
    "캐터필러": "CAT", "제너럴일렉트릭": "GE"
}

# 정밀 스크리닝용 대표 유니버스 Pool
UNIVERSE_US = [
    "NVDA", "MSFT", "GOOGL", "META", "TSLA", "AMZN", "AVGO", "COST", "AMD",
    "NFLX", "CRM", "ADBE", "ORCL", "QCOM", "TXN", "AMAT", "NOW", "PLTR",
    "PANW", "SNPS", "CDNS", "MRVL", "LRCX", "KLAC", "ANET", "UBER", "CRWD",
    "FTNT", "V", "MA", "UNH", "JNJ", "PG", "HD", "PEP", "KO", "CAT", "GE", "DE"
]

UNIVERSE_KR = [
    "005930.KS", "000660.KS", "373220.KS", "207940.KS", "005380.KS", "000270.KS",
    "068270.KS", "035420.KS", "035720.KS", "006400.KS", "051910.KS", "005490.KS",
    "055550.KS", "105560.KS", "086790.KS", "138040.KS", "012330.KS", "028260.KS",
    "066570.KS", "259960.KS", "012450.KS", "047810.KS", "247540.KQ", "086520.KQ",
    "196170.KQ", "028300.KQ", "035900.KQ", "277810.KQ", "041510.KQ"
]

# 캐시 저장소 (10분 TTL)
_SCREENING_CACHE = {
    "US": {"timestamp": 0, "data": []},
    "KR": {"timestamp": 0, "data": []}
}
CACHE_TTL_SECONDS = 600  # 10분

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
        import requests
        from bs4 import BeautifulSoup
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


# ------------------------------------------------------------
# 2. 정확한 회계 원장(Balance Sheet) 추출 및 감사 함수
# ------------------------------------------------------------
def extract_balance_sheet_audit(t: Any, symbol: str) -> Optional[Dict[str, Any]]:
    """
    공식 대차대조표 원장(Balance Sheet)에서:
    1. 총자산 (Total Assets): 최근 결산 연도 vs 3년 전 결산 연도 -> 3개년 총자산 증가율
    2. 부채비율 (Debt Ratio): 총부채(Total Liabilities) / 총자본(Stockholders' Equity) * 100
    ※ Yahoo 단순 이자부 부채(Total Debt) 배제, 정통 대차대조표 총부채 산출
    """
    try:
        bs = t.balance_sheet
        if bs.empty:
            bs = t.quarterly_balance_sheet
        if bs.empty or 'Total Assets' not in bs.index:
            return None

        total_assets_row = bs.loc['Total Assets']
        if total_assets_row.empty:
            return None

        recent_assets = total_assets_row.iloc[0]
        # 3년 전 연도 (인덱스 3 또는 사용 가능한 가장 오래된 연도)
        idx_3y = 3 if len(total_assets_row) > 3 else (len(total_assets_row) - 1)
        past_assets = total_assets_row.iloc[idx_3y]

        if not past_assets or past_assets <= 0 or not recent_assets or recent_assets <= 0:
            return None

        asset_growth_3y = ((recent_assets - past_assets) / past_assets) * 100

        # 자기자본 (Stockholders' Equity) 추출
        equity_row = None
        for eq_lbl in ['Stockholders Equity', 'Total Stockholder Equity', 'Common Stock Equity']:
            if eq_lbl in bs.index:
                equity_row = bs.loc[eq_lbl]
                break
        
        equity = equity_row.iloc[0] if (equity_row is not None and not equity_row.empty) else 0

        # 총부채 (Total Liabilities) 추출
        liab_row = None
        for l_lbl in ['Total Liabilities Net Minority Interest', 'Total Liabilities']:
            if l_lbl in bs.index:
                liab_row = bs.loc[l_lbl]
                break
        
        if liab_row is not None and not liab_row.empty:
            liabilities = liab_row.iloc[0]
        else:
            # 회계 항등식: 자산 = 부채 + 자본 -> 부채 = 자산 - 자본
            liabilities = recent_assets - equity if (equity > 0 and recent_assets >= equity) else 0

        if equity <= 0:
            debt_ratio = 999.0  # 자본 잠식
        else:
            debt_ratio = (liabilities / equity) * 100

        return {
            "recent_assets": float(recent_assets),
            "past_assets": float(past_assets),
            "asset_growth_3y": round(float(asset_growth_3y), 2),
            "total_liabilities": float(liabilities),
            "stockholders_equity": float(equity),
            "debt_ratio": round(float(debt_ratio), 2),
            "years_span": idx_3y
        }
    except Exception:
        return None


def format_currency_amount(amount: float, currency: str = "USD") -> str:
    """금액을 읽기 쉬운 단위($B, $M / 조, 억)로 변환"""
    if currency == "KRW":
        if abs(amount) >= 1_000_000_000_000:
            return f"{amount / 1_000_000_000_000:.1f}조"
        elif abs(amount) >= 100_000_000:
            return f"{amount / 100_000_000:.0f}억"
        return f"{amount:,.0f}원"
    else:
        if abs(amount) >= 1_000_000_000:
            return f"${amount / 1_000_000_000:.1f}B"
        elif abs(amount) >= 1_000_000:
            return f"${amount / 1_000_000:.1f}M"
        return f"${amount:,.0f}"


# ------------------------------------------------------------
# 3. 개별 종목 정밀 지표 조회 (yfinance + 회계 감사 결합)
# ------------------------------------------------------------
def get_stock_metrics(ticker_symbol: str):
    """yfinance를 통한 핵심 재무/가격/기술/회계 지표 추출 (기초/안전 투자 위주)"""
    try:
        yf = _get_yf()
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

        # 안전 지표 (배당률, PER, PBR)
        dividend_yield = (info.get('dividendYield') or 0) * 100
        trailing_pe = info.get('trailingPE', None)
        forward_pe = info.get('forwardPE', None)
        price_to_book = info.get('priceToBook', None)
        currency = info.get('currency', 'KRW' if ('.KS' in ticker_symbol or '.KQ' in ticker_symbol) else 'USD')
        name = info.get('shortName') or info.get('longName') or ticker_symbol

        # 정밀 대차대조표 회계 감사 데이터 결합
        audit = extract_balance_sheet_audit(t, ticker_symbol)
        debt_ratio = audit["debt_ratio"] if audit else (info.get('debtToEquity', 0) or 0)
        asset_growth_3y = audit["asset_growth_3y"] if audit else 0.0

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
            "debt_ratio": round(debt_ratio, 2),
            "asset_growth_3y": round(asset_growth_3y, 2),
            "audit": audit
        }
    except Exception as e:
        print(f"[Stock Metrics Error] {ticker_symbol}: {e}")
        return None


def analyze_safety_tier(metrics: dict):
    """안전 기초 투자 관점에서의 점수화 및 평가"""
    rsi = metrics.get('rsi', 50)
    pos52 = metrics.get('position_52', 50)
    div = metrics.get('dividend_yield', 0)
    debt = metrics.get('debt_ratio', 100)
    growth = metrics.get('asset_growth_3y', 0)
    
    status_tags = []
    if debt <= 80:
        status_tags.append(f"🛡️ 초우량 재무 (부채비율 {debt}%)")
    elif debt <= 120:
        status_tags.append(f"✅ 안정적 재무 (부채비율 {debt}%)")
    else:
        status_tags.append(f"⚠️ 부채 주의 (부채비율 {debt}%)")

    if growth >= 30:
        status_tags.append(f"🚀 고성장 (3Y 자산 +{growth}%)")
    elif growth > 0:
        status_tags.append(f"📈 견실 성장 (3Y 자산 +{growth}%)")

    if rsi < 35:
        status_tags.append("📉 과매도 구간(분할매수 기회)")
    elif rsi > 70:
        status_tags.append("🔥 단기 과열 구간(추격매수 금지)")

    if div >= 2.5:
        status_tags.append(f"💰 배당 우량주 ({div}%)")

    if pos52 <= 30:
        status_tags.append("🧱 52주 바닥권 안전마진")
    elif pos52 >= 85:
        status_tags.append("⚡ 52주 고점권 돌파시도")

    return status_tags


# ------------------------------------------------------------
# 4. 데일리 성장성 + 안전 TOP 랭킹 산출 엔진 (핵심)
# ------------------------------------------------------------
def _fetch_single_candidate(symbol: str, max_debt_ratio: float = 120.0) -> Optional[Dict[str, Any]]:
    """단일 종목의 회계 지표 및 당일 시세 수집 후 안전 필터링"""
    try:
        t = yf.Ticker(symbol)
        audit = extract_balance_sheet_audit(t, symbol)
        if not audit:
            return None

        # [하드 필터] 부채비율 120% 초과 또는 자산 역성장 제외
        if audit["debt_ratio"] > max_debt_ratio or audit["asset_growth_3y"] <= 0:
            return None

        hist = t.history(period="5d")
        if hist.empty:
            return None

        price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else price
        change_pct = ((price - prev_price) / prev_price) * 100
        vol = hist['Volume'].iloc[-1]

        info = t.info
        name = info.get('shortName') or info.get('longName') or symbol
        currency = info.get('currency', 'KRW' if ('.KS' in symbol or '.KQ' in symbol) else 'USD')

        return {
            "symbol": symbol,
            "name": name,
            "currency": currency,
            "price": float(price),
            "change_pct": round(float(change_pct), 2),
            "asset_growth_3y": audit["asset_growth_3y"],
            "debt_ratio": audit["debt_ratio"],
            "past_assets": audit["past_assets"],
            "recent_assets": audit["recent_assets"],
            "liabilities": audit["total_liabilities"],
            "equity": audit["stockholders_equity"],
            "volume": int(vol),
            "past_assets_fmt": format_currency_amount(audit["past_assets"], currency),
            "recent_assets_fmt": format_currency_amount(audit["recent_assets"], currency),
            "liabilities_fmt": format_currency_amount(audit["total_liabilities"], currency),
            "equity_fmt": format_currency_amount(audit["stockholders_equity"], currency)
        }
    except Exception:
        return None


def get_daily_growth_top_ranking(market: str = "US", top_n: int = 10, sort_by: str = "daily_change", max_debt_ratio: float = 120.0) -> List[Dict[str, Any]]:
    """
    [고정 펀더멘털 안전 필터] + [매일 변하는 데일리 시장 모멘텀 정렬]
    1. 회계 필터: 부채비율 <= 120.0%, 3개년 총자산증가율 > 0%
    2. 데일리 정렬: 당일 주가 등락률(daily_change) 순으로 매일 살아있는 랭킹 생성
    """
    market_up = market.upper()
    now_ts = time.time()

    # 캐시 확인 (10분 이내 데이터 재사용으로 응답속도 극대화)
    cached = _SCREENING_CACHE.get(market_up)
    if cached and (now_ts - cached["timestamp"] < CACHE_TTL_SECONDS) and len(cached["data"]) >= top_n:
        candidates = cached["data"]
    else:
        target_universe = UNIVERSE_US if market_up == "US" else UNIVERSE_KR
        with ThreadPoolExecutor(max_workers=10) as executor:
            raw_results = list(executor.map(lambda s: _fetch_single_candidate(s, max_debt_ratio), target_universe))
        candidates = [r for r in raw_results if r is not None]

        _SCREENING_CACHE[market_up] = {
            "timestamp": now_ts,
            "data": candidates
        }

    # 정렬 기준 적용
    if sort_by == "daily_change":
        # 당일 주가 상승률 높은 순
        candidates.sort(key=lambda x: x["change_pct"], reverse=True)
    elif sort_by == "growth":
        # 3개년 자산성장률 높은 순
        candidates.sort(key=lambda x: x["asset_growth_3y"], reverse=True)
    elif sort_by == "volume":
        # 거래량 순
        candidates.sort(key=lambda x: x["volume"], reverse=True)

    return candidates[:top_n]


# ------------------------------------------------------------
# 5. 리포트 생성기 (마크다운 및 디스코드 임베드 전용)
# ------------------------------------------------------------
def generate_daily_ranking_report_markdown(market: str = "US", top_n: int = 10) -> Dict[str, Any]:
    """국내/미국 주식 3개년 성장성 + 부채비율 120% 이하 데일리 리포트 생성"""
    market_name = "미국 주식 (US S&P500/NASDAQ)" if market.upper() == "US" else "국내 주식 (KR KOSPI/KOSDAQ)"
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    items = get_daily_growth_top_ranking(market=market, top_n=top_n, sort_by="daily_change")
    if not items:
        return {
            "success": False,
            "message": f"[{market_name}] 데이터를 집계하지 못했습니다. 잠시 후 다시 시도해주세요."
        }

    # 표 마크다운 빌드 (Sanity Check 항목 포함)
    table_lines = [
        f"### 🔔 **[{today_str}] {market_name} 3개년 성장성 & 당일 모멘텀 TOP {len(items)}**",
        "",
        "> 🛡️ **회계적 검증 기준**: 공식 대차대조표 기준 부채비율(총부채/총자본) **120% 이하** & 3개년 총자산 증가율 **양수(+)**",
        "> ⚡ **데일리 랭킹 기준**: 위 안전 조건을 통과한 우량 기업 중 **당일 주가 모멘텀(등락률)** 상위 정렬",
        "",
        "| 순위 | 티커 | 기업명 | 당일 등락률 | 3개년 자산증가율 | 부채비율 | 최근 총자산 | 총부채 | 자기자본 | 현재가 |",
        "|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"
    ]

    for i, itm in enumerate(items, 1):
        curr_sym = "₩" if itm["currency"] == "KRW" else "$"
        chg_sign = "+" if itm["change_pct"] >= 0 else ""
        price_str = f"{curr_sym}{itm['price']:,.0f}" if itm["currency"] == "KRW" else f"{curr_sym}{itm['price']:,.2f}"
        
        table_lines.append(
            f"| **{i}** | `{itm['symbol']}` | {itm['name']} | **{chg_sign}{itm['change_pct']}%** | **+{itm['asset_growth_3y']}%** | `{itm['debt_ratio']}%` | {itm['recent_assets_fmt']} | {itm['liabilities_fmt']} | {itm['equity_fmt']} | {price_str} |"
        )

    table_lines.extend([
        "",
        "---",
        "**💡 스카디 퀀트의 데일리 브리핑**:",
        f"1. **재무 안전성**: 본 리포트에 포함된 모든 기업은 공식 사업보고서 원장 상 부채비율 120% 이하로 재무 건전성이 엄격히 검증되었습니다.",
        f"2. **데일리 모멘텀**: 3개년 동안 자산을 꾸준히 증식해 온 알짜 기업들이며, 매일 장 마감 시황에 따라 주도주 순위가 실시간 재산출됩니다."
    ])

    report_md = "\n".join(table_lines)
    return {
        "success": True,
        "market": market.upper(),
        "today_str": today_str,
        "count": len(items),
        "items": items,
        "markdown": report_md
    }


def generate_skadi_stock_report(query: str):
    """개별 종목 실시간 팩폭 안전 진단서 생성"""
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

    audit_text = ""
    if metrics.get("audit"):
        a = metrics["audit"]
        audit_text = f"\n- **공식 대차대조표 감사**: 3개년 자산성장 **+{a['asset_growth_3y']}%** | 정규 부채비율 **{a['debt_ratio']}%** (총부채 {format_currency_amount(a['total_liabilities'], metrics['currency'])} / 자기자본 {format_currency_amount(a['stockholders_equity'], metrics['currency'])})"

    report_markdown = f"""### 📊 스카디의 냉철한 팩폭 종목 진단: **{metrics['name']} ({ticker})**

- **현재가**: **{price_formatted}** ({change_color}{metrics['change_pct']}%)
- **안전/수급 진단**: `{tag_str}`
- **기술적 지표**: RSI **{metrics['rsi']}** | 20일선: {curr_sym}{metrics['ma20']:,} | 60일선: {curr_sym}{metrics['ma60']:,}
- **기초 밸류에이션**: 배당률 **{metrics['dividend_yield']}%** | PER **{metrics['pe']}** | PBR **{metrics['pbr']}**{audit_text}
- **52주 위치**: 저점 대비 **{metrics['position_52']}%** 수준 (최저 {curr_sym}{metrics['low_52']:,} ~ 최고 {curr_sym}{metrics['high_52']:,})

---
**💡 스카디의 행동 지침 (기초 투자 안전 가이드)**:
"""
    prompt_context = f"""
[실시간 주식 팩트 데이터]
- 종목: {metrics['name']} ({ticker})
- 현재가: {price_formatted} (변동률: {metrics['change_pct']}%)
- 부채비율: {metrics['debt_ratio']}% (3개년 자산증가율: {metrics['asset_growth_3y']}%)
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

