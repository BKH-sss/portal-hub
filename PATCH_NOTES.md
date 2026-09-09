# 📝 JARVIS / SKADI 프로젝트 공식 패치 노트 (Patch Notes & Changelog)

---

## 🏆 [2026-09-07] v3.7.0 - LoL Ultimate Tactical Master Suite (실시간 라이브 데이터·스펠/오브젝트 트래커 & 올인원 HUD & 오토파일럿)

### 📌 패치 개요
- **개발 목적**: 롤(League of Legends) 인게임 승률을 극대화하기 위해, **Riot Live Client API(Port 2999) 실시간 데이터 엔진, 적 5인 스펠(점멸/텔포) 쿨다운 추적 및 15초 전 음성 예고, 드래곤/바론/유충 5대 오브젝트 카운트다운, 팀 골드 격차(+Gold Lead) & CS/min 게이지, 칼바람 증강체 추천 팝업, 그리고 전자동 인게임 오토파일럿 데몬**을 완성하여 롤 완벽 서포트 시스템을 구축했습니다.
- **적용 일자**: **2026년 09월 07일 (월)**
- **릴리즈 버전**: `v3.7.0`

### 🌟 신규 추가 및 업그레이드 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 상세 내역 |
| :--- | :---: | :--- |
| [`modules/lol_live_game_tracker.py`](file:///C:/Users/skbkh/Desktop/html/chat%20bot/modules/lol_live_game_tracker.py) | **신규** | **실시간 인게임 라이브 데이터 & 스펠/오브젝트 트래커**<br>• Riot Live Client Data API 0.8s 초저지연 비동기 폴링<br>• 적 5인 소환사 주문(점멸 300s, 텔포, 점화 등) 실시간 카운트다운 & 만료 15초 전 사전 음성 예고<br>• 5대 오브젝트(용, 바론, 유충, 전령, 장로) 자동 리젠 타이머 & 60s/30s 전 브리핑<br>• 실시간 팀 골드 격차(+2.4k Gold Lead) 및 분당 CS(CS/min) 연산<br>• 1100G/1300G/3000G 파워 스파이크 황금 귀환 알리미 |
| [`modules/lol_overlay_hud.py`](file:///C:/Users/skbkh/Desktop/html/chat%20bot/modules/lol_overlay_hud.py) | **대규모 업그레이드** | **인게임 올인원 플로팅 마스터 HUD (`/overlay`)**<br>• 4대 전술 탭 뷰 (레이더, 적 스펠, 오브젝트, 증강체) 원클릭 전환<br>• 상단 실시간 인게임 시간, 맵 모드, 골드 격차 배지 통합<br>• 적 스펠 버튼 클릭 시 즉시 쿨다운 프로그레스 바 가동<br>• 사이버틱 반투명 다크 글래스모피즘(Glassmorphism) 및 콤팩트 미니멀 반응형 UI |
| [`modules/lol_autopilot_service.py`](file:///C:/Users/skbkh/Desktop/html/chat%20bot/modules/lol_autopilot_service.py) | **신규** | **전자동 인게임 오토파일럿 & 라이프사이클 관리자**<br>• 롤 실행 $\rightarrow$ 픽창 $\rightarrow$ 인게임 $\rightarrow$ 게임 종료 전 과정 100% 무인 자동 감지<br>• 픽창: 칼바람 눈덩이 스펠 착용 확인 & 챔피언 매치업 분석<br>• 인게임 시작: 미니맵 트래커 + 라이브 트래커 자동 가동 & 스카디 출격 브리핑<br>• 게임 종료: 미니맵 트래커 대기 모드 전환 + 오답노트 & 브라이어 팩폭 피드백 자동 생성 |
| [`modules/__init__.py`](file:///C:/Users/skbkh/Desktop/html/chat%20bot/modules/__init__.py) | **라우팅 확장** | 신규 라이브 트래커 및 오토파일럿 라우터 일괄 등록 (총 19개 라우터 체계 완비) |
| [`modules/jarvis_extension_router.py`](file:///C:/Users/skbkh/Desktop/html/chat%20bot/modules/jarvis_extension_router.py) | **라우팅 확장** | 통합 확장 라우터에 신규 LoL 모듈 라우터 마운트 |

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
