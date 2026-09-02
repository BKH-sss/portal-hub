# 🌊 Skadi (스카디) - 24/7 Cognitive AI Discord Assistant

> **Google Gemini 2.5/3.5, Claude 3.7 Sonnet, OpenAI GPT-4o** 기반의 고지능 오케스트레이션과 실시간 멀티미디어(YouTube, 실시간 날씨, 미세먼지, 고화질 이미지) 그라운딩을 지원하는 **24시간 365일 무중단 디스코드 AI 비서**입니다.

---

## 🌟 주요 기능 (Core Features)

1. **🧠 Nexus Cognitive AI Engine (MoE 다형성 오케스트레이션)**:
   - 질문의 성격(코딩, 실시간 팩트, 주식/금융, 감성 대화)을 자동 분류하여 최적 모델(Gemini / Claude / GPT)로 자동 라우팅
   - 429 할당량 초과 시 무중단 캐스케이딩 자동 폴백 지원
2. **🌅 자율 모닝 브리핑 (평일 오전 8시 자동 선톡)**:
   - 실시간 익산시 관측소 기준 날씨 & 기온
   - 실시간 미세먼지(PM10) & 초미세먼지(PM2.5) 농도 및 등급
   - 마스터의 최근 관심사 테마 3대 최신 뉴스 2줄 요약 및 링크 제공
3. **🎬 실시간 YouTube 공식 영상 & MV 검색**:
   - 노래, 음악, 영상 요청 시 실제 작동하는 YouTube 링크 자동 첨부 및 디스코드 임베드 재생
4. **🖼️ 실시간 고화질 사진 & 이미지 검색**:
   - 실시간 이미지 검색 연동으로 디스코드 채팅창에 사진 바로 렌더링
5. **🧹 지능형 채팅 관리**:
   - 자연어 삭제("여기서부터 위로 지워줘", "이 대화 지워줘"), `!청소 [N]`, `!되돌리기` 지원
6. **🎙️ 음성 채널 TTS 연동**:
   - `!들어와`, `!나가`, `!말해` 명령어를 통한 음성 채널 대화 지원

---

## 📂 프로젝트 구조 (Repository Structure)

```
skadi-discord-bot/
├── discord_bot/
│   ├── discord_skadi_bot.py           # 디스코드 봇 메인 서버 & 이벤트 루프
│   ├── discord_config.example.json    # 페르소나 및 설정 템플릿
│   └── requirements.txt               # 필수 라이브러리 목록
├── llm_orchestrator.py                # 지능형 의도 분석 및 모델 오케스트레이터
├── llm_providers.py                   # 다형성 LLM (Gemini, Claude, GPT) 프로바이더
├── smart_search.py                    # 실시간 웹, 유튜브, 이미지 검색 엔진
├── tool_registry.py                   # 플러그인 & 도구 실행 레지스트리
├── config.example.py                  # 중앙 환경 변수 설정 템플릿
├── requirements.txt                   # 루트 의존성 파일
└── .gitignore                         # 보안 및 개인정보 차단 필터
```

---

## ☁️ 클라우드(Render) 24/7 배포 방법

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python discord_bot/discord_skadi_bot.py`
- **Environment Variables**:
  - `DISCORD_BOT_TOKEN`: 디스코드 봇 토큰
  - `GEMINI_API_KEY`: 구글 Gemini API 키
