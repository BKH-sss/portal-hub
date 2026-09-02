# 패치 노트 및 적용 가이드

## 1. 파일 교체 방법
아래 6개 파일을 기존 프로젝트 폴더(`brain_server.py`가 있는 위치)에 그대로 덮어쓰세요.
`local_asr.py`, `observability.py`, `vad_barge_in.js`는 새 파일이므로 같은 폴더에 추가만 하면 됩니다.

```
brain_server.py       (수정됨 - 덮어쓰기)
dream_engine.py        (수정됨 - 덮어쓰기)
chatbot.html            (수정됨 - 덮어쓰기)
observability.py       (신규)
local_asr.py            (신규)
vad_barge_in.js         (신규 - brain_server.py와 같은 폴더, 정적 파일로 서빙됨)
```

## 2. 환경변수 설정 (중요)
API 키 하드코딩을 제거했으므로, 서버 실행 전에 반드시 환경변수를 설정해야 Gemini 관련 기능이 동작합니다.

**Windows (PowerShell, 서버_켜기.bat에 추가 권장):**
```powershell
$env:GEMINI_API_KEY="여기에_실제_키_입력"
$env:WHISPER_MODEL_SIZE="small"      # 선택: tiny/base/small/medium/large-v3
$env:WHISPER_DEVICE="cuda"           # 4080 Super면 cuda 권장
uvicorn brain_server:app --port 8000
```

키를 설정하지 않으면 Gemini 관련 요청(그 자리에서 오류 메시지 반환)만 제한되고,
나머지 로컬 Ollama 기반 기능은 정상 동작합니다.

## 3. 새 패키지 설치 (로컬 STT용)
```bash
pip install faster-whisper
```
GPU 드라이버/CUDA가 이미 PyTorch용으로 설치돼 있다면 추가 설정 없이 바로 동작합니다.
로딩 실패 시 자동으로 CPU(int8)로 폴백하도록 만들어뒀습니다.

## 4. 무엇이 바뀌었는지 요약

| 파일 | 변경 내용 |
|---|---|
| brain_server.py | 스트리밍 f-string 버그 수정, SD payload TypeError 수정, reranker 변수명 버그 수정, API 키 하드코딩 제거, gemini_api_calls 카운터 작동, 경로 탈출(path traversal) 방어, observability 훅 삽입, local_asr 라우터 마운트 |
| dream_engine.py | brain_server.py와 동일한 ChromaDB 경로/컬렉션명/임베딩 함수 사용하도록 수정 (수면학습 → 실전코치 연결 복구) |
| chatbot.html | localhost:8000 하드코딩 3곳을 SERVER_URL 기반으로 수정 (모바일/외부 접속 지원), VAD 바지인 토글 UI 및 연동 로직 추가 |
| observability.py (신규) | RAG 검색/리랭크/팩트체크/자율학습 이벤트를 B:\AI_Brain\observability\*.jsonl 로 기록. `/admin/observability?event_type=rerank` 로 조회 가능 |
| local_asr.py (신규) | faster-whisper 기반 완전 로컬 STT. `/api/asr` (POST, multipart file), `/api/asr/status` (헬스체크) |
| vad_barge_in.js (신규) | 에너지 기반 VAD로 AI 발화 중 유저가 말하면 즉시 끊고 로컬 STT로 녹음 전송 |

## 5. 확인해볼 것 (제가 실행 환경이 없어 직접 테스트하지 못한 부분)
- `WHISPER_DEVICE=cuda`로 faster-whisper가 4080 Super에서 정상 로딩되는지
- ChromaDB 기존 컬렉션들이 이미 다른 임베딩 함수로 생성돼 있었다면, dream_engine.py가
  새 임베딩 함수로 접근할 때 에러가 나지 않는지 (기존 데이터가 있다면 최초 1회 확인 필요)
- VAD 에너지 임계값(`ENERGY_THRESHOLD = 0.02`, vad_barge_in.js 상단)이 실제 마이크/환경 소음에 맞는지 — 너무 예민하면 팬 소음에도 반응하고, 너무 둔하면 안 끊길 수 있어 실사용하면서 조정 필요

## 6. 아직 안 만든 것 (지난 리뷰에서 언급했지만 이번엔 범위에서 제외)
- LangGraph식 오케스트레이션 리팩토링 (지금 구조를 유지한 채 점진적으로 옮기는 걸 권장)
- `[SDDRAW:]` `[검색요청]` 같은 문자열 태그를 Ollama 구조화 출력(JSON mode)으로 완전히 대체하는 작업 — 이건 페르소나 프롬프트 전체를 다시 설계해야 해서 별도로 요청해주시면 진행하겠습니다
- admin.html이 프로젝트 파일에 없어서 observability 대시보드 UI는 API만 만들고 화면은 못 붙였습니다
