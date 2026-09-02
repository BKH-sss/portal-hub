import os
import sys
import json
import urllib.parse
from youtube_transcript_api import YouTubeTranscriptApi
from google import genai
from google.genai import types

# Windows cp949 인코딩 에러 방지용
sys.stdout.reconfigure(encoding='utf-8')

# =====================================================================
# 설정 부분
# =====================================================================
# 1. 사용할 영상 URL 목록 (쇼츠, 일반 영상 모두 가능)
YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=YOUR_VIDEO_ID_HERE",
    # 여러 개의 URL을 추가하세요.
]

# 2. 페르소나 (AI의 말투, 성격 설정)
# 이 프롬프트가 Gemini에게 "대화록의 답변(Assistant) 부분을 이 성격으로 바꿔줘!" 라고 지시합니다.
PERSONA_PROMPT = """
당신은 게임을 좋아하고 발랄하며 친근한 반말을 쓰는 20대 여성 스트리머입니다.
대화록의 내용을 기반으로 답변하되, 기계적인 말투를 완전히 버리고 
'~했어!', '~잖아 ㅋㅋㅋ', '완전 어이없어!' 와 같이 감정이 풍부한 친근한 말투로 모든 문장을 다시 작성하세요.
"""

try:
    from config import API_KEYS
    GEMINI_API_KEY = API_KEYS.get("GEMINI") or os.environ.get("GEMINI_API_KEY", "")
except Exception:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# 4. 저장할 JSONL 파일 이름
OUTPUT_JSONL = "persona_dataset.jsonl"

# 5. Whisper 사용 여부 (True: 자막이 없으면 yt-dlp + whisper로 음성 인식 진행)
# Whisper를 사용하려면 터미널에서 다음 패키지를 추가로 설치해야 합니다:
# pip install yt-dlp faster-whisper
USE_WHISPER_FALLBACK = False

# =====================================================================

def get_video_id(url):
    """유튜브 URL에서 고유 Video ID만 추출합니다."""
    parsed = urllib.parse.urlparse(url)
    video_id = urllib.parse.parse_qs(parsed.query).get('v', [None])[0]
    if not video_id:
        video_id = url.split('/')[-1].split('?')[0]
    return video_id

def extract_transcript(video_id):
    """1. 유튜브 자막 추출 (우선 시도)"""
    try:
        print(f"[{video_id}] 자체 자막 추출 시도...")
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko'])
        full_script = " ".join([item['text'] for item in transcript_list])
        print(f"[{video_id}] 자체 자막 추출 완료! (길이: {len(full_script)})")
        return full_script
    except Exception as e:
        print(f"[{video_id}] 자막 추출 실패: {e}")
        return None

def extract_with_whisper(url):
    """2. Whisper를 이용한 오디오 다운로드 및 필사 (자막 없을 시 대안)"""
    if not USE_WHISPER_FALLBACK:
        print("Whisper 폴백이 비활성화되어 있습니다. 건너뜁니다.")
        return None
        
    try:
        print(f"[{url}] yt-dlp로 오디오 다운로드 중...")
        import yt_dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'temp_audio.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        print("faster-whisper로 음성 인식(필사) 시작...")
        from faster_whisper import WhisperModel
        # 모델 사이즈 조절 가능 (tiny, base, small, medium, large-v3)
        model = WhisperModel("small", device="cpu", compute_type="int8") 
        segments, info = model.transcribe("temp_audio.wav", beam_size=5, language="ko")
        
        full_script = ""
        for segment in segments:
            full_script += segment.text + " "
            
        print("필사 완료!")
        # 임시 파일 삭제
        if os.path.exists("temp_audio.wav"):
            os.remove("temp_audio.wav")
            
        return full_script
    except ImportError:
        print("[에러] yt-dlp 또는 faster-whisper가 설치되지 않았습니다. pip install yt-dlp faster-whisper 명령어를 실행하세요.")
        return None
    except Exception as e:
        print(f"Whisper 필사 중 오류 발생: {e}")
        return None

def refine_dataset_with_gemini(raw_text):
    """3. 추출된 원본 텍스트를 Gemini를 이용해 ShareGPT 형태의 멀티턴 대화로 정제"""
    # 텍스트가 너무 길면 자르기 (Gemini 2.5 Flash는 긴 컨텍스트도 지원하지만 토큰 제한 및 속도 고려)
    max_chars = 15000 
    if len(raw_text) > max_chars:
        raw_text = raw_text[:max_chars]

    prompt = f"""
다음은 유튜브 영상에서 추출한 음성 대화록 원본입니다. 
이 텍스트를 바탕으로, '질문자(사용자)'와 '답변자(당신)'가 티키타카를 주고받는 멀티턴(Multi-turn) 대화 형식으로 재구성해주세요.

[답변자 페르소나 설정]
{PERSONA_PROMPT}

[규칙]
1. 불필요한 유튜브 오프닝/엔딩(예: 구독, 좋아요)은 제거하세요.
2. 출력 형식은 반드시 아래의 JSON 포맷(ShareGPT 스키마)을 엄격하게 지켜주세요. JSON 코드 블록 안에 작성해야 합니다.
3. 최소 2~4번 정도 서로 대화를 주고받는(Turn) 형태로 구성하세요.

[출력 JSON 형식 예시]
{{
  "messages": [
    {{"role": "user", "content": "오늘 게임 패치 내용 어때?"}},
    {{"role": "assistant", "content": "완전 대박이잖아! ㅋㅋㅋ 이번 버프 미쳤어 진짜."}},
    {{"role": "user", "content": "진짜? 어떤 챔피언이 떡상했는데?"}},
    {{"role": "assistant", "content": "아칼리가 진짜 사기됐어! 너도 빨리 꿀 빨아!"}}
  ]
}}

[음성 대화록 원본]
{raw_text}
"""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("Gemini 2.5 Flash를 이용해 대화록 정제 및 페르소나 부여 중...")
        res = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
            )
        )
        
        response_text = res.text
        # Markdown JSON 블록 파싱
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].strip()
        else:
            json_str = response_text.strip()
            
        parsed_data = json.loads(json_str)
        return parsed_data
        
    except Exception as e:
        print(f"Gemini 정제 실패: {e}")
        return None

def main():
    print("="*50)
    print("🚀 로컬 LLM 파인 튜닝용 데이터셋 구축 자동화 스크립트 시작")
    print("="*50)
    
    successful_items = 0
    
    # 한국어 주석 (Always add comments to your code, using Korean where appropriate.)
    # 파일명은 w 모드(덮어쓰기) 대신 a 모드(이어쓰기)로 열어, 여러 번 실행해도 데이터가 누적되도록 합니다.
    with open(OUTPUT_JSONL, "a", encoding="utf-8") as f_out:
        for url in YOUTUBE_URLS:
            if "YOUR_VIDEO_ID_HERE" in url:
                print("⚠️ YOUTUBE_URLS에 유효한 영상 링크를 입력해주세요.")
                break
                
            video_id = get_video_id(url)
            print(f"\n▶ 처리 중: {url}")
            
            # 1. 스크립트 추출
            script = extract_transcript(video_id)
            if not script:
                script = extract_with_whisper(url)
                
            if not script:
                print(f"[{video_id}] 스크립트 추출에 실패하여 건너뜁니다.")
                continue
                
            # 2. LLM 정제 (ShareGPT 포맷으로 변환)
            refined_data = refine_dataset_with_gemini(script)
            
            if refined_data and "messages" in refined_data:
                # 3. ShareGPT 형식에 System 프롬프트 추가
                # 파인튜닝 시 AI가 어떤 역할을 수행해야 하는지 명시하는 부분입니다.
                system_message = {"role": "system", "content": PERSONA_PROMPT.strip()}
                messages = [system_message] + refined_data["messages"]
                
                final_json = {"messages": messages}
                
                # JSONL 파일에 한 줄씩 기록 (Unsloth 권장 포맷)
                f_out.write(json.dumps(final_json, ensure_ascii=False) + "\n")
                f_out.flush()
                successful_items += 1
                print(f"✅ [{video_id}] 정제 및 JSONL 저장 완료!")
            else:
                print(f"❌ [{video_id}] 정제된 데이터 포맷팅 오류")
                
    print("\n" + "="*50)
    print(f"🎉 모든 작업 완료! 총 {successful_items}개의 멀티턴 데이터셋이 '{OUTPUT_JSONL}'에 저장되었습니다.")
    print("="*50)

if __name__ == "__main__":
    main()
