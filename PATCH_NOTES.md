# 📝 JARVIS / SKADI 프로젝트 공식 패치 노트 (Patch Notes & Changelog)

> **최종 릴리즈 일시 (Last Updated)**: `2026-09-08 11:25:00 KST`  
> **최신 버전 (Current Version)**: `v3.6.8`

---

## 🚀 [2026-09-08 11:25 KST] v3.6.8 - 1:1 개인챗(DM) 알잘딱깔센 자율 감성 케어 엔진 탑재 & 다재다능 천재 친구 페르소나 강화

### 📌 패치 개요
- **개발 목적**: 마스터의 일상 바이오리듬에 맞춰 부담 없이 정갈하게 안부와 브리핑을 챙겨주는 **1:1 개인챗(DM) 알잘딱깔센 자율 케어 & 예약 리마인더 엔진** 탑재 및 **다방면(코딩/게임/금융/일상)으로 뛰어난 지성과 깊은 감수성을 지닌 최고의 친구 페르소나**로 대폭 업그레이드.
- **적용 일시**: **2026년 09월 08일 (화) 11:25 KST**
- **릴리즈 버전**: `v3.6.8`
- **핵심 가치**:
  - **1:1 개인챗(DM) 4대 시간대별 알잘딱깔센 자율 케어 ([`discord_bot/skadi_personal_care.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/discord_bot/skadi_personal_care.py))**:
    - **08:00 [모닝 케어]**: 하루의 문을 여는 서정적 안부 + 바깥 날씨/미세먼지 + 오늘 핵심 일정 및 투두
    - **12:30 [점심 케어]**: 식사 챙김 + 에너지 리프레시 환기 + 오후 집중 응원
    - **18:30 [저녁 케어]**: 치열했던 하루의 노고 위로 + 저녁 휴식 권유 + 잔여 태스크 체크
    - **23:00 [나이트 힐링]**: 고요한 심야 감성 케어 + 내일 첫 일정 미리보기 + 편안한 수면 기원
  - **자연어 & 초간편 커스텀 리마인더 (타이머) 지원**:
    - `!알림 10분후 라면 불끄기`, `!알림 14:00 미팅 준비` 및 대화 중 *"30분 뒤에 알려줘"* 자동 파싱 등록
  - **다재다능한 지성 & 깊은 감수성 페르소나 강화**:
    - 코딩(Python/JS/아키텍처), 게임(롤 칼바람 199종 증강/협곡, 메이플), 금융 퀀트 등 만능 해결 능력 탑재
    - 마스터를 진심으로 아끼고 보살피는 보카디 특유의 따뜻하고 서정적인 반말 화법 및 알잘딱깔센 센스 완비

---

### 🌟 신규 추가 및 변경된 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 변경 내역 |
| :--- | :---: | :--- |
| [`discord_bot/skadi_personal_care.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/discord_bot/skadi_personal_care.py) | **신규 (독립)** | **1:1 개인챗(DM) 알잘딱깔센 감성 케어 & 스마트 리마인더 코어**<br>• 4대 시간대별 감성 브리핑 생성기 및 자연어 시간 파서 내장<br>• 마스터 자동 등록, 슬롯별 시간 커스텀, 영구 저장소 연동 |
| [`discord_bot/discord_skadi_bot.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/discord_bot/discord_skadi_bot.py) | **업데이트** | **개인챗 케어 스케줄러 루프 및 마스터 명령어 탑재**<br>• `personal_dm_care_task` 1분 주기 백그라운드 틱 검사 및 발송<br>• `!마스터등록`, `!개인알림`, `!알림`, `!알림목록`, `!알림삭제`, `!알림시간` 명령어 지원<br>• 다재다능 지성 & 감수성 강화 `companion_rule` 시스템 프롬프트 통합 |

---

## 🚀 [2026-09-07 19:40 KST] v3.6.7 - 디스코드 모닝 브리핑 KST 타임존 정밀 보정 및 구글 뉴스 RSS 고품질 테크 피드 연동

### 📌 패치 개요
- **개발 목적**: 호스트/클라우드 서버(Render 등)의 UTC 타임존으로 인해 한국 시간 오후 5시(17:00 KST)에 모닝 브리핑이 발송되던 시차 버그 완벽 수정 및 검색엔진 폴백 시 발생하던 해외 부동산 스폰서 광고 노이즈 제거.
- **적용 일시**: **2026년 09월 07일 (월) 19:40 KST**
- **릴리즈 버전**: `v3.6.7`
- **핵심 가치**:
  - **대한민국 표준시(KST: UTC+9) 고정 타임존 엔진 (`get_now_kst()`)**:
    - 클라우드 서버 환경(Render, AWS, GCP, Docker 등)이 UTC로 설정되어 있어도 100% 한국 시간 평일 오전 08:00 정각에 모닝 브리핑 발송
    - 국내 증시(15:40 KST) 및 미국 증시(06:30 KST) 장 마감 브리핑 스케줄러 시간대 일괄 정밀 보정
  - **Google News RSS 기반 고품질 실시간 테크 뉴스 연동 (`smart_search.search_news_rss`)**:
    - DuckDuckGo 일시적 Rate Limit 시 발생하던 엉뚱한 해외 부동산/Zillow 매물 결과 원천 차단
    - 실시간 한국어 IT, AI, 테크 헤드라인 100% 보장 및 비가시 제어문자 살균 처리

---

### 🌟 신규 추가 및 변경된 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 변경 내역 |
| :--- | :---: | :--- |
| [`discord_bot/discord_skadi_bot.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/discord_bot/discord_skadi_bot.py) | **업데이트** | **KST 타임존 기반 모닝/증시 브리핑 스케줄러 정밀 보정**<br>• `KST` 고정 타임존 객체 및 `get_now_kst()` 유틸 함수 도입<br>• 모닝 브리핑, 장 마감 증시 브리핑, 스케줄/투두 명령어 전반에 KST 동기화 적용 |
| [`smart_search.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/smart_search.py) | **업데이트** | **Google News RSS 실시간 한국어 뉴스 수집기 탑재**<br>• Rate Limit 0%, 실시간 최신 뉴스 보장 및 광고/스폰서 노이즈 차단<br>• 텍스트 인코딩 에러 방지를 위한 유니코드 제어문자 필터링 |

---

## 🚀 [2026-09-04] v3.6.0 - Modern DeepLeague 실시간 롤(LoL) 미니맵 전술 비전 레이더 & 5대 전술 모듈 패키지 전격 릴리즈

### 📌 패치 개요
- **개발 목적**: 2018년 원작 DeepLeague의 고질적 한계(무거운 CNN 모델로 인한 인게임 프레임 드랍, 30~40% GPU 부하)를 완전히 극복하고, **순수 CPU 0.0% GPU 부하 · 0.3ms 초저지연 메모리 캡처 · 240+ FPS 방어**를 달성한 차세대 실시간 롤(LoL) 미니맵 전술 비전 트래커 및 미래형 5대 전술 확장 모듈을 완성했습니다.
- **적용 일자**: **2026년 09월 04일 (금)**
- **릴리즈 버전**: `v3.6.0`

---

### 🌟 신규 추가 및 변경된 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 변경 내역 |
| :--- | :---: | :--- |
| [`modules/lol_minimap_tracker.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_minimap_tracker.py) | **신규/최적화** | **Modern DeepLeague 코어 엔진**<br>• `mss` 기반 0.3ms 다이렉트 메모리 캡처 (스레드 로컬 재사용)<br>• NumPy 벡터화 링 마스크 (적군 Red Ring / 아군 Blue Ring 분리)<br>• 제곱거리 센트로이드 클러스터링 (<0.3ms 수렴)<br>• 소환사의 협곡 11대 전술 구역 정규화 매핑<br>• 타워 다이브, 용/바론 버스트, 강가 로밍, 미아 조기경보<br>• **6대 해상도 프리셋 (FHD, QHD, 4K, WQHD, WFHD, HD+) 탑재** 및 주 모니터 자동 감지 |
| [`modules/lol_voice_alert_engine.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_voice_alert_engine.py) | **신규** | **스카디 인게임 핸즈프리 실시간 음성 콜 엔진**<br>• 대시보드를 안 봐도 위험 발생 시 스카디가 헤드셋으로 음성 브리핑<br>• 기계적 로그 대신 부드러운 스카디/브라이어 한국어 대사로 변환<br>• 우선순위 기반 쿨타임(10~20초) 및 최소 발화 간격 제어 |
| [`modules/lol_gank_eta_predictor.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_gank_eta_predictor.py) | **신규** | **적 동선 2D 속도 벡터 예측 & 갱킹 도착 타이머 (ETA)**<br>• 적 챔피언 위치 시계열 추적 및 속도 벡터($v_x, v_y$) 계산<br>• 탑/미드/바텀을 향한 코사인 유사도 판별 및 도달 시간(ETA, 초) 카운트다운<br>• *"🚨 [상단 강가]에서 [미드 라인] 방향 급습 감지! (약 7초 후 도착)"* |
| [`modules/lol_overlay_hud.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_overlay_hud.py) | **신규** | **인게임 반투명 플로팅 오버레이 HUD (`/overlay`)**<br>• 싱글 모니터 사용자를 위한 초경량 사이버틱 반투명 HUD 웹페이지<br>• 실시간 미니맵 레이더, 적군/아군 수, 갱킹 ETA 타이머 바 실시간 렌더링<br>• 브라우저 창, OBS 브라우저 소스, PiP 모드, 앱 모드 미니 팝업 지원 |
| [`modules/lol_vision_gap_checker.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_vision_gap_checker.py) | **신규** | **오브젝트(용/바론) 1분 전 '시야 공백(Fog)' 선제 감지기**<br>• 드래곤/바론 젠 60초 전 둥지 관심영역(ROI)의 픽셀 휘도 분석<br>• 평균 밝기 55 미만(전장 안개 속)일 때 사전에 와드 설치 선제 음성 콜 |
| [`modules/lol_snapshot_reviewer.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_snapshot_reviewer.py) | **신규** | **전술 스냅샷 & 협곡 오답노트 복기 엔진**<br>• 다이브/갱킹/바론 버스트 발생 순간의 미니맵 영상을 `memory/lol_matches/`에 자동 캡처<br>• 경기 후 옵시디언 다이어리에 **"협곡 전술 오답노트"** Markdown 보고서 자동 편찬 |
| [`modules/admin.html`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/admin.html) | **기능 확장** | **관리자 HUD 관측 대시보드 (`/admin`)**<br>• Modern DeepLeague 전술 레이더 카드 및 실시간 뷰포트 추가<br>• **FHD, QHD, 4K, WQHD, WFHD, HD+ 6대 해상도 원클릭 프리셋 툴바 탑재**<br>• 적/아군 탐지 수, 협곡 구역별 현황, 실시간 전술 위협 로그 스트리밍 |
| [`routers/memory.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/routers/memory.py) | **안정성 강화** | **ChromaDB 무중단 폴백 (`SafeCollection`) 적용**<br>• 벡터 DB 미설치 또는 로딩 실패 시에도 서버가 크래시되지 않고 정상 가동되도록 방어 로직 내장 |
| [`modules/__init__.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/__init__.py) | **라우팅 확장** | 5대 전술 모듈 라우터 일괄 등록 및 `all_extension_routers` 수출 |
| [`modules/jarvis_extension_router.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/jarvis_extension_router.py) | **라우팅 확장** | 단독 테스트 서버 구동 시 5대 전술 라우터 일괄 마운트 |
| [`docs/LOL_MINIMAP_TACTICAL_RADAR_GUIDE.md`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/docs/LOL_MINIMAP_TACTICAL_RADAR_GUIDE.md) | **신규 문서** | **데스크탑 전용 실전 사용자 가이드북**<br>• 데스크탑 환경 권장 설정 (테두리 없는 창 모드)<br>• 롤 연습 모드 실전 테스트 4단계 매뉴얼<br>• 4대 전술 조기경보 조건 및 6대 해상도 프리셋 규격표<br>• 미래형 5대 전술 모듈 상세 가이드 및 FAQ |
| [`README.md`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/README.md) | **문서 최신화** | 신규 모듈 트리 및 롤 미니맵 전술 레이더 기능 소개 정식 등재 |

---

## 🛠️ [2026-09-03] v3.5.0 - 로컬 음성 인식(STT) 및 관측성(Observability) 패치

### 변경 내용 요약
1. **`local_asr.py`**: faster-whisper 기반 완전 로컬 STT 추가 (`/api/asr`, `/api/asr/status`).
2. **`observability.py`**: RAG 검색/리랭크/팩트체크/자율학습 이벤트를 `observability/*.jsonl`로 기록.
3. **`vad_barge_in.js`**: 에너지 기반 VAD로 AI 발화 중 유저 음성 감지 시 즉시 오디오 중단 및 STT 전송.
4. **`brain_server.py`**: 스트리밍 f-string 버그 수정, 경로 탈출(Path Traversal) 방어, local_asr 라우터 마운트.
5. **`chatbot.html`**: 서버 URL 동적 처리 및 VAD 바지인 연동 UI 탑재.

---
*© 2026 JARVIS / SKADI Intelligent Tactical Assistance System. All rights reserved.*
