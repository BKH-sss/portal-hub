# 🌊 Skadi (스카디) & JARVIS - 24/7 Cognitive AI & Modular ADE System

> **Google Gemini 2.5/3.5, Claude 3.7 Sonnet, OpenAI GPT-4o** 기반의 고지능 오케스트레이션과 실시간 멀티미디어(YouTube, 실시간 날씨, 미세먼지, 고화질 이미지) 그라운딩을 지원하는 **24시간 365일 무중단 디스코드 AI 비서 및 풀스택 에이전트 시스템**입니다.

---

## 🌟 주요 기능 (Core Features)

1. **🧠 Nexus Cognitive AI Engine (MoE 다형성 오케스트레이션)**:
   - 질문의 성격(코딩, 실시간 팩트, 주식/금융, 감성 대화)을 자동 분류하여 최적 모델(Gemini / Claude / GPT / Ollama)로 자동 라우팅
   - 429 할당량 초과 시 무중단 캐스케이딩 자동 폴백 지원
2. **🌅 자율 모닝 브리핑 (평일 오전 8시 자동 선톡)**:
   - 실시간 날씨 & 기온, 미세먼지(PM10) 및 초미세먼지(PM2.5) 농도 및 등급
   - 오늘의 캘린더 일정 및 마감 임박 태스크(Todo) 브리핑
   - 마스터의 최근 관심사 테마 3대 최신 뉴스 2줄 요약 및 링크 제공
3. **💻 시스템 OS & 하드웨어 제어 (`modules/system_os_controller.py`)**:
   - CPU, RAM, NVIDIA GPU(4080 Super), VRAM 실시간 진단
   - 윈도우 마스터 볼륨(0~100) 조절, 음소거, 미디어 재생/일시정지, 프로세스 강제 종료(Kill Switch)
4. **👁️ 스마트 화면 비전 코파일럿 (`modules/screen_vision_agent.py`)**:
   - 화면 초고속 캡처 & Gemini 2.5 Flash Vision 기반 실시간 코드 에러 디버깅 및 게임 화면 분석
5. **⚡ 초저지연 오디오 스트리머 (`modules/realtime_audio_streamer.py`)**:
   - WebSocket 기반 문장 단위 실시간 청킹으로 500ms 미만 즉각 음성 합성 및 스트리밍 재생
6. **📝 데일리 저널 & 옵시디언 자동화 (`modules/daily_journal_writer.py`)**:
   - 일일 대화/일정/개발 기록 자동 요약 및 옵시디언 호환 Markdown 저널 자동 생성
7. **🎮 게임 프로세스 자동 감지 & 코칭 브리퍼 (`modules/game_auto_coach.py`)**:
   - LoL, 발로란트, 메이플스토리 등 게임 실행 자동 감지 및 실시간 전술 코칭 가이드
8. **🔌 표준 MCP (Model Context Protocol) 지원 (`modules/mcp_server.py`)**:
   - Claude Desktop, VS Code, Cursor, Antigravity 등 외부 AI 도구와 JARVIS 기능 실시간 연동
9. **📊 JARVIS 사이버틱 관측성 대시보드 (`/admin`)**:
   - 실시간 하드웨어 게이지, LLM 모델별 호출 분배율 차트(Chart.js), 실시간 이벤트 터미널 로그

---

## 📂 프로젝트 구조 (Repository Structure)

```
JARVIS-Assistant/
├── 🚀 모듈형 신규 확장 패키지 (modules/)
│   ├── modules/system_os_controller.py   # 💻 CPU/RAM/GPU(4080 Super) 모니터링 & OS/볼륨/미디어 제어
│   ├── modules/schedule_manager.py       # 📅 SQLite 기반 일정/할일(Todo) 관리 & 모닝 브리핑 엔진
│   ├── modules/native_tool_engine.py     # 🛠️ Gemini/Claude/GPT/Ollama 표준 Function Calling 엔진
│   ├── modules/mcp_server.py             # 🔌 Anthropic MCP 표준 JSON-RPC 서버 (Claude Desktop/Cursor 연동)
│   ├── modules/screen_vision_agent.py    # 👁️ 초고속 화면 캡처 및 실시간 비전(Vision) 코파일럿
│   ├── modules/realtime_audio_streamer.py# ⚡ WebSocket 문장 단위 초저지연 실시간 오디오 스트리머
│   ├── modules/daily_journal_writer.py   # 📝 일일 대화/업무 요약 및 옵시디언 마크다운 저널 생성기
│   ├── modules/game_auto_coach.py        # 🎮 게임 프로세스 자동 감지 및 실시간 인게임 코칭
│   ├── modules/admin.html                # 📊 다크 HUD 테마 실시간 시스템 & 관측성 대시보드 UI
│   ├── modules/jarvis_extension_router.py# 🌟 위 모든 모듈을 메인 서버에 원클릭 마운트하는 통합 라우터
│   └── modules/README.md                 # 📖 모듈 상세 가이드 문서
│
├── 🏛️ 백엔드 코어 & 메인 서버
│   ├── brain_server.py                   # FastAPI 메인 진입점 & 모듈형 APIRouter 등록
│   ├── routers/                          # 도메인별 API 라우터 (chat, portal, tts, lol, maple, memory, vision 등)
│   ├── llm_orchestrator.py               # 지능형 의도 분석 및 모델 오케스트레이터
│   ├── llm_providers.py                  # 다형성 LLM (Gemini, Claude, GPT, Ollama) 프로바이더
│   ├── smart_search.py                   # 실시간 웹, 유튜브, 이미지 검색 엔진
│   ├── tool_registry.py                  # 플러그인 & 도구 실행 레지스트리
│   ├── dream_engine.py                   # 자율 수면 학습(Dreaming) 엔진
│   ├── local_asr.py                      # Faster-Whisper 기반 로컬 STT
│   └── config.example.py                 # 중앙 환경 변수 설정 템플릿
│
├── 🤖 24/7 디스코드 봇 (discord_bot/)
│   ├── discord_bot/discord_skadi_bot.py  # 디스코드 봇 메인 서버 & 이벤트 루프
│   ├── discord_bot/discord_config.example.json # 페르소나 및 설정 템플릿
│   └── discord_bot/requirements.txt      # 디스코드 봇 전용 의존성 파일
│
├── 🌐 프론트엔드 UI
│   ├── chatbot.html                      # 실시간 스트리밍 대화 인터페이스
│   ├── portal.html / global.html         # 종합 포털 및 글로벌 뉴스 대시보드
│   └── skadi_chess.html/.js/.css         # 스카디 체스 AI 게임
│
└── ⚡ 원클릭 배치 스크립트
    ├── 서버_켜기.bat / 서버_끄기.bat
    ├── 포털_실행.bat / 디스코드_스카디_실행.bat
    └── 외부접속기_실행.bat
```

---

## 🔌 신규 모듈 (`modules/`) 연동 방법 (단 2줄)

`brain_server.py`에 아래 2줄만 추가하면 모든 확장 기능이 즉시 활성화됩니다:

```python
# 1. 상단 라우터 임포트
from modules.jarvis_extension_router import extension_router

# 2. FastAPI 메인 앱에 마운트
app.include_router(extension_router)
```

---

## ☁️ 24/7 배포 및 실행 방법

### 로컬 단독 테스트
```bash
# 확장 모듈 대시보드 단독 실행
python modules/jarvis_extension_router.py
```
* **관리자 대시보드:** `http://localhost:8000/admin`
* **Swagger API 문서:** `http://localhost:8000/docs`

### 디스코드 봇 클라우드(Render) 24/7 배포
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python discord_bot/discord_skadi_bot.py`
- **Environment Variables**:
  - `DISCORD_BOT_TOKEN`: 디스코드 봇 토큰
  - `GEMINI_API_KEY`: 구글 Gemini API 키
