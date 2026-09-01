# 🌊 스카디(Skadi) 디스코드 챗봇 모듈

스카디 인격과 다형성 LLM 엔진(Gemini, Claude, OpenAI, Ollama), 장기 기억(Long-term Memory) 시스템이 결합된 디스코드 대화 봇입니다.

---

## 📂 폴더 구조
```text
chat bot/
├── discord_bot/
│   ├── discord_skadi_bot.py      # 스카디 디스코드 봇 메인 실행 파일
│   ├── discord_config.json       # 봇 토큰, 페르소나, LLM 모델 설정 파일
│   ├── README.md                 # 봇 설명서 및 사용 가이드
│   └── 디스코드_스카디_실행.bat   # 폴더 내 실행 배치 파일
└── 디스코드_스카디_실행.bat        # 루트 디렉토리 실행 배치 파일
```

---

## ⚡ 빠른 시작 (3단계)

### 1단계: 디스코드 봇 토큰 발급
1. [Discord Developer Portal](https://discord.com/developers/applications)에 로그인합니다.
2. **New Application** 생성 후 좌측 **Bot** 탭 클릭
3. **Reset Token**으로 토큰을 복사합니다.
4. **★필수★** 하단 `Privileged Gateway Intents`에서 **`MESSAGE CONTENT INTENT`** 스위치를 **ON**으로 켭니다.

### 2단계: 봇 초대
1. 좌측 **OAuth2** -> **URL Generator**
2. `SCOPES`: `bot` 체크
3. `BOT PERMISSIONS`: `Send Messages`, `Read Messages/View Channels`, `Read Message History`, `Embed Links` 체크
4. 생성된 링크로 내 디스코드 서버에 봇을 초대합니다.

### 3단계: 토큰 등록 및 실행
`discord_config.json`의 `"bot_token"`에 토큰을 붙여넣거나, `디스코드_스카디_실행.bat`을 실행한 뒤 콘솔창에 토큰을 입력하면 자동 저장 후 실행됩니다.

---

## 💬 대화 방식
- **@멘션**: `@스카디 오늘 기분이 어때?`
- **답장(Reply)**: 스카디의 메시지에 디스코드 [답장]을 하면 자연스럽게 대화가 이어집니다.
- **개인 DM**: 봇과 1:1 대화방에서는 멘션 없이 자유롭게 대화합니다.
- **전용 채널**: 채널에서 `!채널지정`을 하면 멘션 없이 일반 채팅으로도 대화가 가능합니다.

---

## 🛠️ 주요 명령어

| 명령어 | 별칭 | 설명 |
| :--- | :--- | :--- |
| `!도움말` | `!help`, `!명령어` | 전체 명령어 안내 임베드 카드 출력 |
| `!페르소나 <모드>` | `!성격`, `!모드` | 성격 변경 (`보카디`, `비서`, `주식`, `화가`, `레식`) |
| `!모델 <엔진>` | `!model`, `!엔진` | LLM 엔진 변경 (`gemini`, `ollama`, `openai`, `claude`) |
| `!기억 <내용>` | `!기억해` | 마스터에 관한 정보를 스카디 장기 기억 DB에 영구 저장 |
| `!기억목록` | `!기억확인` | 스카디가 기억하는 마스터 프로필 및 기억 확인 |
| `!채널지정` | `!전용채널` | 현재 채널을 멘션 없이 상시 대화 가능한 채널로 등록 |
| `!채널해제` | - | 상시 대화 채널 해제 |
| `!리셋` | `!reset`, `!청소` | 현재 채널의 최근 대화 기억을 초기화 |
| `!상태` | `!status` | LLM 모델, 핑, 대화 세션 등 시스템 상태 확인 |
