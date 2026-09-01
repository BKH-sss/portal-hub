# 🏛️ ERECHTHEION & 🌍 ORBIS (통합 인텔리전스 포털 허브)

> **국내 4차 산업·스포츠·기상 포털(ERECHTHEION)**과 **전 세계 주요 외신 전문 인텔리전스 포털(ORBIS)**을 한곳에서 제공하는 24시간 365일 무중단 반응형 웹 포털 서비스입니다.

---

## 🌐 서비스 라인업 (Two Specialized Hubs)

```
portal-hub (Repository)
│
├── 🏛️ ERECHTHEION (에레크테이온 코리아) ──> https://bkh-sss.github.io/portal-hub/
│    └── 국내 4차산업 뉴스 · 맨체스터 유나이티드 경기 허브 · 전국 실시간 날씨/미세먼지
│
└── 🌍 ORBIS (오르비스 글로벌) ────────────> https://bkh-sss.github.io/portal-hub/global/
     └── 150개+ 글로벌 외신 실시간 피드 · 한국어 AI 3줄 요약 · 세계 시계 · 금융 티커
```

---

## 🌟 핵심 기능 (Core Features)

### 1. 🏛️ ERECHTHEION KOREA (국내 종합 포털)
- ⚽ **맨체스터 유나이티드 전용 경기 허브**: 과거 5경기 스코어 결과 및 향후 경기 일정 반응형 가로 스크롤 캐러셀 (ESPN 연동)
- 🌤️ **실시간 날씨 & 미세먼지 위젯**: 서울, 수원, 익산, 부산 등 주요 도시 실시간 기온, 체감온도, PM10/PM2.5 등급 배지, 시간별 예보 (Open-Meteo 연동)
- 🤖 **국내 4차 산업 & 게임 뉴스 피드**: AI, 반도체, 컴퓨터, 로봇, 게임 업계 등 검증된 국내 30개+ 공신력 언론사 기사 큐레이션 및 AI 3줄 요약 모달
- 🔗 **ORBIS 바로가기 연동**: 상단 헤더 및 하단 푸터에서 원클릭으로 해외 외신 포털로 즉시 전환

---

### 2. 🌍 ORBIS GLOBAL (해외 외신 전문 포털 · `/global/`)
- 🚫 **외신 집중형 레이아웃**: 축구와 날씨 섹션을 과감히 제거하고 오직 글로벌 외신 인텔리전스에만 집중된 고성능 레이아웃
- 📰 **150개+ 대량 글로벌 외신 실시간 피드**:
  - **공신력 외신**: 로이터(Reuters), 블룸버그(Bloomberg), BBC World, 테크크런치(TechCrunch), 더 버지(The Verge), CNBC, 네이처(Nature), NASA 등
  - **카테고리 구성**:
    - ⚡ **All Breaking** (전체 글로벌 속보 50개)
    - 🤖 **AI & Silicon Valley** (생성형 AI, 프론티어 기술, 빅테크 30개)
    - 📈 **Global Economy & Markets** (월스트리트, 거시경제, 무역, 인플레이션 30개)
    - 💻 **Chips & Hardware** (2나노 파운드리, HBM4, 양자 컴퓨팅 30개)
    - 🚀 **Space & Science** (NASA 아르테미스, 우주망원경, 핵융합 청정에너지 30개)
    - 🌐 **World & Geopolitics** (국제 거버넌스, 안보, 외교 30개)
- ✨ **한국어 AI 3줄 요약 브리핑 모달**: 영문 기사를 한국어로 친절하게 해설하는 AI 핵심 포인트 3줄 요약 및 Google 번역본 / 원문 바로가기 제공
- 🌍 **세계 주요 도시 실시간 시계**: KST(서울), EST(뉴욕), GMT(런던) 시간대 실시간 초 단위 동기화
- 📊 **글로벌 마켓 & 테크 실시간 티커**: 나스닥, S&P 500, 엔비디아, 애플, 환율(USD/KRW), 비트코인 등 롤링 티커
- 🏛️ **31일 일자별 글로벌 랜드마크 배경화면**: 매일 자동으로 세계 유수 건축물과 대자연 배경이 로테이션되는 Hero 스포트라이트 배너

---

## 🏗️ 시스템 아키텍처 (Architecture)

```mermaid
graph TD
    subgraph GitHub Actions [🤖 GitHub Actions CI/CD (2시간 주기 자동 실행)]
        cron[⏰ Cron Schedule 2h] --> runner[GitHub Ubuntu Runner]
        runner --> build[python build_portal_data.py]
        build --> engine1[news_service.py<br/>국내 뉴스/맨유/날씨 수집]
        build --> engine2[global_news_service.py<br/>글로벌 외신 150개+ RSS 수집]
        engine1 --> data1[(data/portal_data.json)]
        engine2 --> data2[(data/global_data.json)]
        data1 & data2 --> git_push[자동 Git Commit & Push]
    end

    subgraph GitHub Pages [🚀 GitHub Pages 24/7 Hosting]
        git_push --> pages_kr[🏛️ ERECHTHEION KOREA<br/>portal-hub/index.html]
        git_push --> pages_global[🌍 ORBIS GLOBAL<br/>portal-hub/global/index.html]
    end
```

1. **⚽ 스포츠 & 날씨 파이프라인 (`news_service.py`)**
   - ESPN Scoreboard API 및 Open-Meteo API를 통해 맨유 경기 일정과 실시간 기상/미세먼지 정보를 수집합니다.
2. **📰 글로벌 외신 수집 엔진 (`global_news_service.py`)**
   - Google News Global RSS 및 공신력 외신 피드를 연동하여 150개 이상의 최신 기사를 카테고리별로 정제하고 한국어 AI 맥락 포인트를 자동 생성합니다.
3. **🤖 24시간 자동 빌드 로봇 (`.github/workflows/update_data.yml`)**
   - 2시간마다 GitHub Actions가 실행되어 `data/portal_data.json`과 `data/global_data.json`을 최신 상태로 자동 갱신합니다.

---

## 🚀 접속 및 이용 방법

### 1. 실시간 웹사이트 접속 (추천)
스마트폰, 태블릿, PC 어디서든 브라우저로 24시간 바로 접속할 수 있습니다.
- 🏛️ **국내 포털 (ERECHTHEION | 국내 뉴스 · 맨유 축구 · 날씨)**: **[https://bkh-sss.github.io/portal-hub/](https://bkh-sss.github.io/portal-hub/)**
- 🌍 **해외 외신 포털 (ORBIS | 실시간 글로벌 외신 · 24/7 AI 요약)**: **[https://bkh-sss.github.io/portal-hub/global/](https://bkh-sss.github.io/portal-hub/global/)**

### 2. 로컬 개발 환경에서 실행 시
```bash
# 1. 저장소 클론
git clone https://github.com/BKH-sss/portal-hub.git
cd portal-hub

# 2. 국내 및 글로벌 외신 데이터 로컬 빌드 (150개+ 최신 수집)
python build_portal_data.py

# 3. 로컬 웹 서버 실행
python -m http.server 8000
# 브라우저 접속:
# - 국내 포털: http://localhost:8000/
# - 해외 외신(ORBIS): http://localhost:8000/global/
```

---

## 🛠️ 기술 스택 (Tech Stack)

- **Frontend**: HTML5, Tailwind CSS (CDN), Vanilla JavaScript (ES6+), Pretendard & Inter Font
- **Backend & Crawler**: Python 3.11, urllib, xml.etree, BeautifulSoup
- **CI/CD & Automation**: GitHub Actions (2시간 주기 자동 데이터 갱신)
- **Hosting**: GitHub Pages (무중단 24/7 호스팅)
