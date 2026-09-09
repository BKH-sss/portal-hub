# 🏛️ Portal-Hub (ERECHTHEION KOREA · ORBIS GLOBAL · SKADI CHESS)

> **GitHub Pages 기반 실시간 웹 인텔리전스 포털 & AI 체스 허브**  
> GitHub Pages URL: **https://bkh-sss.github.io/portal-hub/**

---

## 🌐 포털 구성 서비스 안내

### 1. 🇰🇷 [ERECHTHEION KOREA (국내 포털)](https://bkh-sss.github.io/portal-hub/)
- **메인 주소**: `https://bkh-sss.github.io/portal-hub/` (또는 `index.html`)
- **주요 기능**:
  - ⚽ **맨체스터 유나이티드 경기 일정 & 실시간 순위**: 최근 경기 결과 및 다음 경기 D-Day 카운트다운
  - 🌤️ **4대 도시 실시간 날씨 & 미세먼지**: 서울, 수원, 익산, 부산 실시간 기상/대기질 위젯
  - 📰 **4차 산업 핵심 뉴스 브리핑**: AI, 반도체, 로봇, 게임, IT 산업 6개 카테고리 실시간 RSS 큐레이션
  - 🔍 **Google 공식 검색창 연동**: 상단 원터치 구글 통합 검색

### 2. 🌍 [ORBIS GLOBAL (글로벌 외신 포털)](https://bkh-sss.github.io/portal-hub/global/)
- **메인 주소**: `https://bkh-sss.github.io/portal-hub/global/` (또는 `global/index.html`)
- **주요 기능**:
  - ⚡ **150+개 글로벌 주요 외신 실시간 수집**: 로이터(Reuters), 블룸버그(Bloomberg), BBC, TechCrunch, CNBC 등
  - 📈 **글로벌 금융 시장 실시간 지표**: 나스닥(NASDAQ), S&P500, 엔비디아(NVDA), 원/달러 환율 등
  - 🌐 **5대 외신 카테고리 탭**: All Breaking, AI & Silicon Valley, Global Economy & Markets, Chips & Hardware, Space & Science
  - 🕒 **세계 주요 도시 시계**: KST(서울), EST(뉴욕), GMT(런던) 실시간 동기화

### 3. ♟️ [SKADI CHESS (스카디 체스 코치)](https://bkh-sss.github.io/portal-hub/skadi_chess.html)
- **메인 주소**: `https://bkh-sss.github.io/portal-hub/skadi_chess.html` (또는 `chess.html`)
- **주요 기능**:
  - 🤖 **24시간 무중단 실시간 AI 체스 대전**: Minimax + Alpha-Beta 가지치기 기반 자체 AI 엔진 탑재
  - 📊 **실시간 승률 평가 바 (Eval Bar)**: 수마다 즉각적인 유리함/불리함 분석 및 점수 환산
  - 💬 **스카디 실시간 훈수 & 오프닝 전술 추천**: 시실리안 디펜스, 퀸즈 갬빗 등 추천 수 실시간 안내
  - 📱 **모바일 / PC 완벽 반응형 UI**: 터치 및 마우스 드래그 앤 드롭 완벽 지원

---

## 🤖 GitHub Actions 자동 데이터 수집 (CI/CD)

- `.github/workflows/update_data.yml` 워크플로우를 통해 **매시간 정각(0 * * * *)** 자동 실행됩니다.
- `build_portal_data.py`가 실행되어 최신 국내외 뉴스 및 지표 데이터를 수집하고 `data/portal_data.json`, `data/global_data.json`에 커밋/푸시하여 GitHub Pages에 즉시 반영됩니다.

---

## 🚀 로컬 실행 방법

1. 저장소를 클론합니다:
   ```bash
   git clone https://github.com/BKH-sss/portal-hub.git
   cd portal-hub
   ```
2. 포털 실행 배치파일(`포털_실행.bat`)을 더블클릭하거나 아래 명령어를 실행합니다:
   ```bash
   python launch_portal.py
   ```
3. 브라우저에서 `http://127.0.0.1:8080/`로 접속합니다.
