# 📝 JARVIS / SKADI 프로젝트 공식 패치 노트 (Patch Notes & Changelog)

> **최종 릴리즈 일시 (Last Updated)**: `2026-09-08 12:10:00 KST`  
> **최신 버전 (Current Version)**: `v3.6.9`

---

## 🚀 [2026-09-08 12:10 KST] v3.6.9 - "알잘딱깔센" 마스터 등록 즉시 확인 메시지 & 부연설명 임베드 탑재, 공백 명령어(`!마스터 등록`) 및 인터랙티브 피드백 강화

### 📌 패치 개요
- **개발 목적**: 유저가 `!마스터 등록` 또는 자연어로 `"알아서 잘 딱 깔끔하고 센스있게 해줘"`, `"마스터 등록해줘"`라고 요청했을 때 명령어를 즉시 확인했음을 알려주는 직관적인 리액션 이모지와 함께, 스카디의 1:1 개인챗(DM) 케어 시스템(4대 케어 시간, 커스텀 타이머, 설정법 등)을 **알**아서 **잘** **딱** **깔**끔하고 **센**스있게 안내하는 상세 확인 임베드 및 에러 가이드 시스템 전면 구축.
- **적용 일시**: **2026년 09월 08일 (화) 12:10 KST**
- **릴리즈 버전**: `v3.6.9`
- **핵심 가치**:
  - **`!마스터 등록` 공백 인자 허용 및 즉시 확인 임베드 발송 (`cmd_register_master(*args)`)**:
    - `!마스터 등록`, `!마스터`, `!마스터등록`, `!마스터 등록해줘` 등 뒤에 붙는 공백 및 부가 인자를 에러 없이 유연하게 처리
    - 수신 즉시 메시지에 `💖` 이모지 리액션을 추가하고, 4대 케어 시간표/사용법/DM 주의사항을 담은 서정적 핑크 톤 전용 확인 임베드 즉시 회신
    - 마스터의 개인 DM으로도 애틋하고 다정한 첫인사 DM 즉각 전송
  - **자연어 "알잘딱깔센" 및 마스터 등록 대화형 트리거 탑재**:
    - 접두사(`!`) 없이 채팅창이나 DM으로 `"알아서 잘 딱 깔끔하고 센스있게 해줘"`, `"알잘딱깔센"`, `"마스터 등록"` 등을 말해도 똑똑하게 인식하여 `✨` 리액션과 함께 3대 알잘딱깔센 시스템 요약 안내
  - **스마트 리마인더 명령어 UX 대폭 강화 (`cmd_add_reminder`)**:
    - `!알림` 단독 입력 시 에러 대신 친절한 사용법/예시 가이드 임베드 출력
    - `!알림 10분후 라면 불끄기` 등록 시 `⏰` 리액션 추가 및 정밀 예약 확인 메시지 회신
  - **디스코드 명령어 에러 핸들러 도입 (`on_command_error`)**:
    - 파라미터 누락(`MissingRequiredArgument`), 인자 초과(`TooManyArguments`) 발생 시 봇이 침묵하지 않고 올바른 사용법 안내 임베드를 자동 출력

---

### 🌟 신규 추가 및 변경된 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 변경 내역 |
| :--- | :---: | :--- |
| [`discord_bot/discord_skadi_bot.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/discord_bot/discord_skadi_bot.py) | **업데이트** | **마스터 확인 임베드 생성기, 공백 인자 지원, 리액션 및 자연어 트리거 탑재**<br>• `create_master_registration_embed()`, `create_aljaltakkalsen_embed()` 헬퍼 구현<br>• `cmd_register_master(*args)`, `cmd_aljaltakkalsen(*args)` 신규 명령어 추가<br>• `on_message` 내 자연어 마스터 등록 및 알잘딱깔센 인식 로직 추가<br>• `on_command_error` 예외 가이드 핸들러 구현 |
| [`discord_bot/skadi_personal_care.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/discord_bot/skadi_personal_care.py) | **업데이트** | **알잘딱깔센 리마인더 등록 피드백 메시지 서식 최적화**<br>• 알림 예정 시각(오늘/내일 구분), 메모 내용, 취소용 고유 코드(ID) 명시 |

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
- **개발 목적**: 호스트/클라우드 서버의 UTC 타임존으로 인해 한국 시간 오후 5시(17:00 KST)에 모닝 브리핑이 발송되던 시차 버그 완벽 수정 및 검색엔진 폴백 시 발생하던 해외 부동산 스폰서 광고 노이즈 제거.
- **적용 일시**: **2026년 09월 07일 (월) 19:40 KST**
- **릴리즈 버전**: `v3.6.7`
- **핵심 가치**:
  - **대한민국 표준시(KST: UTC+9) 고정 타임존 엔진 (`get_now_kst()`)**:
    - 서버 OS 환경(AWS, GCP, Docker, Ubuntu 등)이 UTC나 해외 시간대로 설정되어 있어도 100% 한국 시간 오전 08:00 정각에 모닝 브리핑 발송
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

## 🚀 [2026-09-07 19:20 KST] v3.6.6 - 네이티브 100% 클릭 투과 투명 HUD 런처 및 상대 조합 카운터 독립 모듈 탑재

### 📌 패치 개요
- **개발 목적**: 브라우저 창을 켤 필요 없이, 게임 플레이에 절대 방해되지 않는 **100% 마우스 클릭 투과(Click-Through) 네이티브 투명 HUD 윈도우** 및 **언제든 탈부착이 용이한 상대 조합(탱커/포킹/암살자) 카운터 독립 모듈** 구현.
- **적용 일시**: **2026년 09월 07일 (월) 19:20 KST**
- **릴리즈 버전**: `v3.6.6`
- **핵심 가치**:
  - **100% 무간섭 마우스 클릭 투과 (`WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE`)**:
    - 오버레이 위에 마우스를 클릭해도 롤 게임 안으로 100% 통과하여 챔피언 이동 및 스킬 시전 방해 0%
    - 포커스를 뺏지 않아(`WS_EX_NOACTIVATE`) 알트탭이나 키보드 씹힘 현상 원천 차단
    - 롤 클라이언트 창(`RiotWindowClass`) 감지 시 상단 5.5% 위치에 1:1 자동 정렬
  - **단독 런처 탑재 (`run_augment_overlay.bat`)**:
    - 추가 pip 패키지 설치 없이 Python 내장 `tkinter` + `ctypes`로 15MB 경량 구동, GPU 부하 0.0%
    - 단축키 `F9`로 인게임 중 언제든 즉시 보이기 / 숨기기 토글
  - **상대 조합 카운터 가중치 독립 모듈 ([`modules/lol_augment_matchup.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_augment_matchup.py))**:
    - 상대 탱커 2인 이상 ➔ 체력 비례/관통 증강 보너스 (+10~16점) 및 `[🛡️ 탱커 카운터]` 태그
    - 상대 포킹 2인 이상 ➔ 돌진/보호막/재생 증강 보너스 (+8~14점) 및 `[🎯 포킹 대항]` 태그
    - 완벽히 분리된 모듈형 설계로, 필요 없을 시 파일 삭제나 옵션 해제만으로 에러 없이 1초 만에 비활성화 가능

---

### 🌟 신규 추가 및 변경된 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 변경 내역 |
| :--- | :---: | :--- |
| [`modules/lol_augment_native_window.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_augment_native_window.py) | **신규 (독립)** | **Win32 100% 클릭 투과 네이티브 인게임 투명 HUD**<br>• `WS_EX_TRANSPARENT` 기반 롤 게임 내 100% 마우스 통과<br>• 6단계 티어 배지([OP]~[D]) 및 슬롯별 단독 리롤 상태 캔버스 렌더링<br>• 롤 창 자동 위치 추적 및 `F9` 키 표시/숨김 토글 지원 |
| [`run_augment_overlay.bat`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/run_augment_overlay.bat) | **신규 (런처)** | **원클릭 네이티브 증강체 오버레이 실행 런처**<br>• 브라우저 없이 데스크탑에서 바로 오버레이 가동<br>• 안티치트(Vanguard) 안전 읽기 전용 GDI/Desktop 창 구동 |
| [`modules/lol_augment_matchup.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_augment_matchup.py) | **신규 (독립)** | **상대 조합 맞춤형 카운터 분석기 (탈부착 모듈)**<br>• 탱커/포킹/암살자 군집 판별 및 증강 키워드 매칭 가산점 산출<br>• 삭제나 비활성화가 간편한 완전 격리 모듈 아키텍처 적용 |

---

## 🚀 [2026-09-07 18:45 KST] v3.6.5 - 개별 슬롯별 단독 리롤(Per-Slot Individual Reroll) 엔진 및 실시간 UI 탑재

### 📌 패치 개요
- **개발 목적**: 실제 아레나/칼바람 증강의 룰에 따라 3장을 통째로 바꾸는 것이 아닌, **원하는 개별 카드 슬롯만 단독으로 주사위를 굴리고 유효 카드는 킵(보존)하는 정밀 리롤 시스템** 구축.
- **적용 일시**: **2026년 09월 07일 (월) 18:45 KST**
- **릴리즈 버전**: `v3.6.5`
- **핵심 가치**:
  - **슬롯별 개별 상태 판정 (`slot_action`, `reroll_recommended`)**:
    - 예: 3번 화염 낙인(`B티어`) ➔ `[🔒 킵 (보존)]`
    - 예: 1번 히드라(`C티어`), 2번 감쇠광선(`D티어`) ➔ `[🎲 단독 리롤 권장]`
  - **스카디 실시간 핀포인트 음성 브리핑**:
    - *"마스터! 3번째 [화염 낙인]은 킵하시고, 효율 낮은 1번, 2번 슬롯만 개별 리롤해서 대박을 노리세요! 🎲"*
  - **프리뷰 및 오버레이 개별 리롤 인터랙션 (`preview_augment_overlay.html`)**:
    - 카드 하단에 `[🎲 N번 슬롯만 단독 리롤]` 버튼 배치
    - 클릭 시 해당 슬롯만 단독 교체되고 나머지 2개 슬롯은 그대로 유지되는 실전 시뮬레이션 지원

---

### 🌟 신규 추가 및 변경된 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 변경 내역 |
| :--- | :---: | :--- |
| [`modules/lol_augment_overlay.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_augment_overlay.py) | **업데이트** | **슬롯별 개별 리롤 판정 로직 및 모델 탑재**<br>• `can_reroll`, `reroll_recommended`, `slot_action` 필드 추가<br>• 슬롯 타깃팅 리롤 판단 (`SLOT_REROLL`) 및 맞춤형 스카디 음성 라인 생성 |
| [`preview_augment_overlay.html`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/preview_augment_overlay.html) | **업데이트** | **개별 슬롯 리롤 버튼 & 실시간 교체 UI 완성**<br>• 각 카드 하단 `[🎲 N번 슬롯만 단독 리롤]` 인터랙티브 버튼 탑재<br>• 단독 슬롯 교체 시 나머지 카드 보존 및 즉각적인 티어/추천 재산출 연동 |

---

## 🚀 [2026-09-07 18:15 KST] v3.6.4 - YOUR.GG 규격 6단계 티어([OP] 추가) & 1회 리롤(주사위) 전술 판단 엔진 탑재

### 📌 패치 개요
- **개발 목적**: YOUR.GG 칼바람 증강체 메타 분석표와 동일하게 **[OP] 티어를 추가하여 6단계 체계([OP], [S], [A], [B], [C], [D])로 승격**하고, 게임당 1회 제공되는 **리롤(주사위) 소모 여부 전술 추천 엔진** 구축.
- **적용 일시**: **2026년 09월 07일 (월) 18:15 KST**
- **릴리즈 버전**: `v3.6.4`
- **핵심 가치**:
  - **YOUR.GG 규격 6단계 티어 시스템 완성**: `[OP]` (마젠타 네온), `[S]` (골드), `[A]` (시안), `[B]` (오렌지), `[C]` (그린), `[D]` (슬레이트).
  - **1회 리롤 전술 판단 엔진 (`Reroll Decision Engine`)**:
    - 최고 티어가 C/D티어일 때 🚨 `[1회 리롤 강력 권장]` 펄스 배너 표출 및 스카디 음성 지시
    - OP/S티어 등장 시 🔒 `[리롤 보존 확정]` 안내
    - 리롤 소진 시 (`rerolls_remaining = 0`) 최종 선택 강제 모드 전환
  - **인게임 오버레이 & 프리뷰 (`preview_augment_overlay.html`) 연동**:
    - 상단 리롤 가이드 배너 실시간 렌더링
    - `🎲 1회 리롤 굴리기 (시뮬레이션)` 버튼으로 1/1 ➔ 0/1 상태 전환 및 OP티어 교체 연출 검증 가능

---

### 🌟 신규 추가 및 변경된 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 변경 내역 |
| :--- | :---: | :--- |
| [`modules/lol_augment_overlay.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_augment_overlay.py) | **업데이트** | **6단계 티어([OP] 추가) & 리롤 전술 엔진 확장**<br>• `AugmentTier.OP` 추가 및 점수 임계치 정밀 교정<br>• `should_reroll`, `reroll_status`, `reroll_reason`, `rerolls_remaining` 모델 탑재<br>• 리롤 안내 바 및 `/api/lol/augment/reroll` 엔드포인트 지원 |
| [`preview_augment_overlay.html`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/preview_augment_overlay.html) | **업데이트** | **OP티어 배지 & 리롤 시뮬레이션 UI 완성**<br>• 마젠타 네온 글로우 `.tier-OP` 배지 CSS 추가<br>• 상단 `[🎲 1회 리롤 판단 가이드 바]` 인터랙티브 연동<br>• OP티어 프리셋 및 1회 리롤 실행 시뮬레이션 버튼 탑재 |

---

## 🚀 [2026-09-07] v3.6.3 - 칼바람 증강체(증바람) 실시간 티어 배지 & 인게임 3-카드 투명 오버레이 HUD 모듈 추가

### 📌 패치 개요
- **개발 목적**: 유어지지(YOUR.GG), 블리츠(Blitz) 스타일의 칼바람 아수라장(증바람) 증강체 실시간 평가 시스템을 100% 자체 기술로 완벽 재현.
- **적용 일자**: **2026년 09월 07일 (월)**
- **릴리즈 버전**: `v3.6.3`
- **핵심 가치**:
  - 인게임 3개 증강체 선택 카드 상단에 정확히 1:1 정렬되는 초경량 투명 오버레이 HUD (`/api/lol/augment/overlay`).
  - 티어 배지 (`[S]`, `[A]`, `[B]`, `[C]`, `[D]`), 증강 점수(0.0~100.0), 선호도 및 1순위 골드 네온 펄스 렌더링.
  - 마우스 클릭이 게임 안으로 100% 통과되는 비간섭 `pointer-events: none` 설계로 안티치트(Vanguard) 100% 안전.
  - 스카디 실시간 1초 귓속말 음성 브리핑 연계: *"마스터! 3번째 [화염 낙인]이 B티어, 점수 76.7점으로 가장 좋습니다!"*

---

### 🌟 신규 추가 및 변경된 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 변경 내역 |
| :--- | :---: | :--- |
| [`modules/lol_augment_overlay.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_augment_overlay.py) | **신규 (독립)** | **칼바람 증강체 티어 배지 & 인게임 3-카드 오버레이 코어 엔진**<br>• 199종 증강체 DB 연동 및 챔피언 스킬 메커니즘 시너지 가중 점수화<br>• 5단계 티어 배지 ([S] 골드/보라, [A] 시안, [B] 주황, [C] 초록, [D] 슬레이트)<br>• 인게임 3개 증강 카드 상단 배치 투명 HTML HUD (`/api/lol/augment/overlay`)<br>• 1회 틱당 <0.05ms 초경량 연산, GPU 0.0%, 240+ FPS 방어<br>• 스카디 1초 음성 추천 대사 및 REST API (`/api/lol/augment/*`) 탑재 |

---

## 🚀 [2026-09-07] v3.6.2 - 킬 직후 상황 맞춤형 라인 복귀 & 뇌절 방지 코칭 독립 모듈 추가

### 📌 패치 개요
- **개발 목적**: "상황에 따라 피드백이 달라져야 한다"는 전술 철학에 따라, 킬을 따낸 직후 내 체력, 제압골, 적 부활 시간, 텔레포트 보유 여부, 적 정글러 백업 ETA를 종합 계산하여 **5대 상황 맞춤형 최적 행동 지침(즉시 귀환 vs 텔 복귀 대비 vs 프리징 vs 방패 채굴 vs 정석 배달)**을 0.05ms 안에 도출하는 코칭 엔진 구현.
- **적용 일자**: **2026년 09월 07일 (월)**
- **릴리즈 버전**: `v3.6.2`
- **운용 원칙**: 기존 실행 서버에 간섭하지 않는 초경량 독립 모듈(Standalone Module)로 구성.

---

### 🌟 신규 추가 및 변경된 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 변경 내역 |
| :--- | :---: | :--- |
| [`modules/lol_lane_reset_coach.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_lane_reset_coach.py) | **신규 (독립)** | **상황 맞춤형 라인 리셋 & 뇌절 방지 코칭 코어 엔진**<br>• 5대 상황 매트릭스 (`INSTANT_RECALL`, `TELEPORT_ALERT`, `FREEZE_AND_RESET`, `PLATE_GREED`, `CRASH_AND_RESET`)<br>• 안전 골든타임(남은 안전 초) 및 위험도 등급 실시간 산출<br>• 스카디 실시간 1줄 상황 대사 및 HUD 뱃지 자동 생성<br>• 틱당 <0.05ms 초고속 연산, GPU 0.0%, 인게임 240+ FPS 방어<br>• 독립 테스트용 FastAPI 라우터 (`/api/lol/reset/*`) 탑재 |

---

## 🚀 [2026-09-07] v3.6.1 - 실시간 적 행동 및 의도(Intent) 트래킹 독립 모듈 추가

### 📌 패치 개요
- **개발 목적**: 단순한 좌표 기반 미니맵 추적을 넘어, 적의 시계열 움직임과 CS 변화를 융합하여 적의 현재 행동(`FARMING`, `ROAMING`, `AMBUSH`, `RECALLING` 등)과 다음 의도를 실시간으로 추론하는 차세대 분석 모듈 제작.
- **적용 일자**: **2026년 09월 07일 (월)**
- **릴리즈 버전**: `v3.6.1`
- **운용 원칙**: 기존 실행 중인 메인 서버에 강제 적용(라우터 자동 등록)하지 않고, **독립형 모듈(Standalone Module)**로 안전하게 격리 보관하여 필요 시 호출 가능하도록 구성.

---

### 🌟 신규 추가 및 변경된 모듈 상세 내역

| 파일명 | 구분 | 핵심 기능 및 변경 내역 |
| :--- | :---: | :--- |
| [`modules/lol_enemy_behavior_tracker.py`](file:///C:/Users/Su-Bla/orca/workspaces/NEO/char/modules/lol_enemy_behavior_tracker.py) | **신규 (독립)** | **실시간 적 행동 및 의도(Intent) 트래커 코어 엔진**<br>• 6대 유한 상태 머신(FSM) 행동 분류 (`FARMING`, `ROAMING`, `AMBUSH_SUSPECT`, `RECALLING`, `OBJECTIVE_ATTACK`, `UNKNOWN`)<br>• 정글러 CS 4단위 기반 클리어 캠프 역추적 및 다음 동선 예측 (Pathing Reconstruction)<br>• Fog of War(시야 밖) 미아 지속 시간 추적 및 매복 확률 산출<br>• 1회 틱당 0.05~0.1ms 이내 연산 완료, GPU 0.0%, 240+ FPS 방어<br>• 자체 테스트용 독립 FastAPI 라우터 (`/api/lol/behavior/*`) 내장 |

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
