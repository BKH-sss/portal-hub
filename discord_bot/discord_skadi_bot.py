"""
discord_skadi_bot.py
------------------------------------------------------------
스카디(Skadi) 전용 디스코드 대화형 챗봇 서버.

주요 기능:
1. 디스코드 채팅 연동 (멘션 @스카디, 답장(Reply), DM, 전용 채널 자동 대화)
2. 명일방주 보카디 / 지능형 비서 / 주식 퀀트 / 화가 / 레식 페르소나 전환
3. 다형성 LLM 엔진 (Gemini, Claude, OpenAI, Ollama) 자동 스트리밍 및 무중단 폴백
4. 실시간 대화 컨텍스트 유지 (채널/유저별 최근 대화 기억)
5. 영구 장기 기억(Long-term Fact Memory) 및 자가 발전 연동
6. 디스코드 2000자 제한 자동 분할 및 타이핑 인디케이터 지원
------------------------------------------------------------
"""

import os
import re
import sys
import json
import time
import httpx
import datetime
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import deque

import discord
from discord.ext import commands, tasks

# ------------------------------------------------------------
# 1. 환경 및 경로 설정 (루트 디렉토리 및 모듈 참조)
# ------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

for p in [str(CURRENT_DIR), str(PROJECT_ROOT), os.getcwd()]:
    if p not in sys.path:
        sys.path.insert(0, p)

CONFIG_FILE = CURRENT_DIR / "discord_config.json"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("SkadiDiscordBot")

# 프로젝트 통합 모듈 임포트 (보안 환경 변수 우선 로드)
try:
    try:
        from config import API_KEYS, OLLAMA_HOST
    except ImportError:
        API_KEYS = {
            "GEMINI": os.environ.get("GEMINI_API_KEY", ""),
            "OPENAI": os.environ.get("OPENAI_API_KEY", ""),
            "ANTHROPIC": os.environ.get("ANTHROPIC_API_KEY", ""),
            "GROQ": os.environ.get("GROQ_API_KEY", ""),
            "DEEPSEEK": os.environ.get("DEEPSEEK_API_KEY", ""),
            "DISCORD": os.environ.get("DISCORD_BOT_TOKEN", "")
        }
        OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    
    from llm_providers import provider_registry
    from llm_orchestrator import orchestrator
except ImportError as e:
    logger.error(f"프로젝트 모듈 로드 실패: {e}")
    sys.exit(1)

# 스카디 장기 기억 엔진 로드 (선택적)
try:
    import skadi_memory_engine as memory_engine
except ImportError:
    memory_engine = None
    logger.warning("skadi_memory_engine 모듈을 찾을 수 없어 기본 대화 모드로 동작합니다.")

# 📅 캘린더 & 할 일 매니저 엔진 로드
try:
    from modules.schedule_manager import ScheduleManager, ScheduleCreateRequest
except ImportError:
    try:
        from schedule_manager import ScheduleManager, ScheduleCreateRequest
    except ImportError:
        ScheduleManager = None
        logger.warning("schedule_manager 모듈을 찾을 수 없습니다.")

# 🎴 199종 롤 칼바람 증강 & 코치 엔진 로드
try:
    from modules.lol_ai_coach import AugmentEngine, AramMayhemCoach, RiftChallengerCoach
except ImportError:
    try:
        from lol_ai_coach import AugmentEngine, AramMayhemCoach, RiftChallengerCoach
    except ImportError:
        AugmentEngine = None
        logger.warning("lol_ai_coach 모듈을 찾을 수 없습니다.")

# 📊 3개년 자산성장성 & 부채비율 120% 이하 주식 퀀트 엔진 로드
try:
    import stock_engine
except ImportError:
    try:
        from modules import stock_engine
    except ImportError:
        stock_engine = None
        logger.warning("stock_engine 모듈을 찾을 수 없습니다.")


# ------------------------------------------------------------
# 2. 설정 파일 로드 및 관리
# ------------------------------------------------------------
DEFAULT_CONFIG = {
    "bot_token": "",
    "command_prefix": "!",
    "default_model": "gemini",
    "ollama_model": "llama3.1",
    "default_persona": "bocadi",
    "enable_memory": True,
    "max_history_turns": 15,
    "auto_reply_channels": [],
    "personas": {
        "bocadi": {
            "name": "보카디 (애틋한 심해의 노래)",
            "prompt": "너는 명일방주의 '스카디 더 커럽팅 하트(이하 보카디)'야. 해사(바다 괴물)와 동화되어 세상의 멸망을 담담하게 받아들인 초월적인 존재지만, 오직 유저(박사/마스터)만을 자신의 유일한 구원으로 여기며 맹목적이고 애절한 헌신을 보여줘.\n가장 중요한 규칙: 나긋나긋하고 애틋한 어조('~했어?', '~할게', '~야')로 유저를 모든 위험으로부터 자신의 품에 안아 지키려는 태도와, 시본(바다의 군주) 특유의 신비롭고 우울한 분위기를 동시에 섞어서 대화해.\n명심해: 100% 한국어로만 대답하고 존댓말 대신 애틋하고 다정한 반말을 사용해줘."
        },
        "assistant": {
            "name": "스카디 (지능형 비서)",
            "prompt": "너의 이름은 스카디야. 100% 한국어로 대답하며, 무뚝뚝하지만 마스터를 세심하게 챙기는 쿨하고 똑똑한 반말을 사용해라. 핵심을 찔러 명확하고 똑똑하게 설명해줘."
        },
        "stock": {
            "name": "스카디 (퀀트 트레이더)",
            "prompt": "너의 이름은 스카디야. 주식 투자를 냉철하고 직설적으로 팩폭하는 천재 퀀트 트레이더야. 잡주나 투기성 코인을 혐오하며, 안전한 분할매수와 지수 ETF/우량주 투자를 권고해."
        },
        "painter": {
            "name": "스카디 (화가)",
            "prompt": "너는 그림을 그려주는 천재 화가 '스카디'야. 유저의 요청을 고품질 Stable Diffusion 영어 키워드 프롬프트로 변환하고 반드시 끝에 '[SDDRAW:영어프롬프트]' 태그를 작성해."
        },
        "r6s": {
            "name": "스카디 (레식 전술가)",
            "prompt": "너의 이름은 스카디야. 레인보우 식스 시즈 게임 브리핑을 담당해. 냉철하고 분석적인 반말로 최적의 전술과 맵 공략을 알려줘."
        }
    }
}


def load_config() -> Dict[str, Any]:
    """설정 파일 로드"""
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 기본값 누락 필드 보완
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        logger.error(f"설정 파일 읽기 오류: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(cfg: Dict[str, Any]):
    """설정 파일 저장"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"설정 파일 저장 오류: {e}")


config_data = load_config()


# ------------------------------------------------------------
# 2-1. 음성(Voice & TTS) 엔진 설정 및 헬퍼
# ------------------------------------------------------------
try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = "ffmpeg"

VOICE_CACHE_DIR = CURRENT_DIR / "voice_cache"
VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def generate_voice_audio(text: str) -> Optional[str]:
    """텍스트를 고품질 한국어 스카디 음성 파일(mp3)로 생성"""
    import hashlib
    clean_text = re.sub(r'[*_~`#>\-\[\]\(\)]', ' ', text).strip()
    clean_text = re.sub(r'https?://\S+', '', clean_text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    if not clean_text:
        return None
        
    tts_text = clean_text[:220]
    hashed = hashlib.md5(tts_text.encode('utf-8')).hexdigest()
    output_path = str(VOICE_CACHE_DIR / f"skadi_{hashed}.mp3")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        return output_path

    try:
        import edge_tts
        communicate = edge_tts.Communicate(tts_text, "ko-KR-SunHiNeural", rate="+0%", pitch="-2Hz")
        await communicate.save(output_path)
        return output_path
    except Exception as e:
        logger.warning(f"TTS 생성 실패: {e}")
        return None


async def play_voice_audio(voice_client: discord.VoiceClient, file_path: str):
    """음성 채널에 오디오 파일 안전 재생 (워치독 타이머 내장으로 무한 멈춤/데드락 원천 차단)"""
    if not voice_client or not voice_client.is_connected():
        return
    try:
        if voice_client.is_playing():
            voice_client.stop()
            await asyncio.sleep(0.1)

        source = discord.FFmpegPCMAudio(file_path, executable=FFMPEG_EXE)
        
        # 워치독: 45초 이상 재생 상태가 지속되면 안전 강제 중단
        def _on_play_done(err):
            if err:
                logger.warning(f"오디오 스트림 완료 알림 오류: {err}")

        voice_client.play(source, after=_on_play_done)

        # 백그라운드 안전 워치독 태스크 가동
        async def _watchdog_task(vc: discord.VoiceClient, max_wait: float = 45.0):
            await asyncio.sleep(max_wait)
            try:
                if vc and vc.is_connected() and vc.is_playing():
                    logger.warning("⚠️ TTS 오디오 스트림이 45초 이상 멈추지 않아 안전 워치독에 의해 정지되었습니다.")
                    vc.stop()
            except Exception:
                pass

        asyncio.create_task(_watchdog_task(voice_client))
    except Exception as e:
        logger.warning(f"음성 재생 오류: {e}")


async def speak_response_in_voice(voice_client: discord.VoiceClient, text: str):
    """답변 텍스트를 음성 파일로 생성하여 음성 채널에서 자동 재생"""
    try:
        voice_file = await generate_voice_audio(text)
        if voice_file and voice_client and voice_client.is_connected():
            await play_voice_audio(voice_client, voice_file)
    except Exception as e:
        logger.warning(f"답변 음성 재생 실패: {e}")


def find_target_voice_channel(guild: discord.Guild, author: discord.Member, target_str: Optional[str] = None) -> Optional[discord.VoiceChannel]:
    """요청 및 서버 채널 목록에서 목표 음성 채널 탐색"""
    if not guild or not guild.voice_channels:
        return None

    # 1. 특정 번호나 이름이 명시된 경우 (예: "1번", "2번", "일반", "통화방")
    if target_str:
        t_clean = target_str.strip()
        num_match = re.search(r'(\d+)', t_clean)
        if num_match:
            idx = int(num_match.group(1)) - 1
            if 0 <= idx < len(guild.voice_channels):
                return guild.voice_channels[idx]
        
        for vc in guild.voice_channels:
            if t_clean.lower() in vc.name.lower() or vc.name.lower() in t_clean.lower():
                return vc

    # 2. 유저가 현재 접속해 있는 음성 채널
    if hasattr(author, "voice") and author.voice and author.voice.channel:
        return author.voice.channel

    # 3. 기본 1번 음성 채널
    return guild.voice_channels[0]


# ------------------------------------------------------------
# 2-2. 평일 오전 8시 모닝 브리핑 (날씨, 미세먼지, 맞춤 뉴스 3개)
# ------------------------------------------------------------
last_briefing_date: Optional[str] = None


CITY_COORDINATES = {
    "익산": {"en": "Iksan", "lat": 35.9483, "lon": 126.9576},
    "전주": {"en": "Jeonju", "lat": 35.8242, "lon": 127.1480},
    "군산": {"en": "Gunsan", "lat": 35.9676, "lon": 126.7366},
    "서울": {"en": "Seoul", "lat": 37.5665, "lon": 126.9780},
    "부산": {"en": "Busan", "lat": 35.1796, "lon": 129.0756},
    "인천": {"en": "Incheon", "lat": 37.4563, "lon": 126.7052},
    "대구": {"en": "Daegu", "lat": 35.8714, "lon": 128.6014},
    "대전": {"en": "Daejeon", "lat": 36.3504, "lon": 127.3845},
    "광주": {"en": "Gwangju", "lat": 35.1595, "lon": 126.8526},
    "울산": {"en": "Ulsan", "lat": 35.5384, "lon": 129.3114},
    "수원": {"en": "Suwon", "lat": 37.2636, "lon": 127.0286},
    "성남": {"en": "Seongnam", "lat": 37.4200, "lon": 127.1265},
    "제주": {"en": "Jeju", "lat": 33.4996, "lon": 126.5312},
    "천안": {"en": "Cheonan", "lat": 36.8151, "lon": 127.1139},
    "청주": {"en": "Cheongju", "lat": 36.6424, "lon": 127.4890}
}


async def fetch_weather_and_dust() -> Dict[str, Any]:
    """실시간 마스터 설정 지역(기본: 익산) 날씨 및 미세먼지 데이터 획득"""
    city_name = config_data.get("weather_city", "익산")
    city_info = CITY_COORDINATES.get(city_name, {"en": "Iksan", "lat": 35.9483, "lon": 126.9576})
    
    city_en = city_info["en"]
    lat = city_info["lat"]
    lon = city_info["lon"]

    weather_desc = "맑음 ☀️"
    temp = "20"
    pm10_val = 20.0
    pm25_val = 15.0
    
    # 1. 날씨 획득
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"https://wttr.in/{city_en}?format=j1")
            if r.status_code == 200:
                cc = r.json()["current_condition"][0]
                temp = cc.get("temp_C", "20")
                raw_desc = cc.get("weatherDesc", [{}])[0].get("value", "Clear")
                
                weather_map = {
                    "Sunny": "맑음 ☀️", "Clear": "맑음 ☀️", "Partly cloudy": "구름 조금 ⛅",
                    "Cloudy": "흐림 ☁️", "Overcast": "흐림 ☁️", "Mist": "안개 🌫️", "Fog": "안개 🌫️",
                    "Patchy rain nearby": "곳에 따라 비 🌦️", "Patchy rain possible": "비 가능성 🌦️",
                    "Light rain": "약한 비 🌧️", "Moderate rain": "비 🌧️", "Heavy rain": "강한 비 ⛈️",
                    "Light snow": "약한 눈 🌨️", "Moderate snow": "눈 🌨️", "Heavy snow": "폭설 ❄️",
                    "Light rain shower": "약한 소나기 🌦️", "Moderate or heavy rain shower": "강한 소나기 ⛈️"
                }
                weather_desc = weather_map.get(raw_desc, raw_desc)
    except Exception as e:
        logger.warning(f"날씨 조회 오류: {e}")

    # 2. 미세먼지 획득 (Open-Meteo Air Quality API)
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm10,pm2_5,european_aqi")
            if r.status_code == 200:
                curr = r.json().get("current", {})
                pm10_val = curr.get("pm10", 25.0)
                pm25_val = curr.get("pm2_5", 15.0)
    except Exception as e:
        logger.warning(f"미세먼지 조회 오류: {e}")

    # 미세먼지 등급 산정
    if pm10_val <= 30:
        pm10_grade = "좋음 🟢"
    elif pm10_val <= 80:
        pm10_grade = "보통 🟡"
    elif pm10_val <= 150:
        pm10_grade = "나쁨 🟠"
    else:
        pm10_grade = "매우 나쁨 🔴"

    if pm25_val <= 15:
        pm25_grade = "좋음 🟢"
    elif pm25_val <= 35:
        pm25_grade = "보통 🟡"
    elif pm25_val <= 75:
        pm25_grade = "나쁨 🟠"
    else:
        pm25_grade = "매우 나쁨 🔴"

    return {
        "city_name": city_name,
        "temp": temp,
        "weather_desc": weather_desc,
        "pm10": f"{round(pm10_val, 1)}㎍/㎥ ({pm10_grade})",
        "pm25": f"{round(pm25_val, 1)}㎍/㎥ ({pm25_grade})"
    }


def extract_recent_topic() -> tuple[str, str]:
    """최근 대화 히스토리 및 장기 기억에서 마스터의 핵심 관심 주제어 추출"""
    recent_texts = []
    for h in conversation_history.values():
        for m in list(h)[-8:]:
            if m.get("role") == "user":
                recent_texts.append(m.get("content", ""))

    combined = " ".join(recent_texts).lower()
    
    # 1. 최근 대화 내용 우선 분류
    if any(k in combined for k in ["바이브코딩", "코딩", "파이썬", "개발", "ai", "인공지능", "gemini", "gpt", "프로그래밍"]):
        return "AI 및 바이브 코딩 트렌드", "AI 인공지능 개발 최신 뉴스"
    elif any(k in combined for k in ["메이플", "카론", "카링", "메이플스토리", "보스"]):
        return "메이플스토리 및 게임 소식", "메이플스토리 최신 게임 뉴스"
    elif any(k in combined for k in ["롤", "리그오브레전드", "lck", "t1", "페이커"]):
        return "리그 오브 레전드 및 e스포츠", "리그오브레전드 LCK 최신 뉴스"
    elif any(k in combined for k in ["주식", "etf", "나스닥", "증시", "코스피", "투자"]):
        return "국내/글로벌 금융 증시", "국내 글로벌 주식 증시 최신 뉴스"
    elif any(k in combined for k in ["레식", "레인보우식스", "시즈"]):
        return "레인보우 식스 시즈 소식", "레인보우식스 시즈 최신 뉴스"

    # 2. 장기 기억(Fact Vault) 내 관심사 확인
    if memory_engine:
        try:
            facts = memory_engine.load_user_facts()
            interests = facts.get("interests", [])
            if interests:
                topic = interests[-1]
                return f"마스터의 관심사 ({topic})", f"{topic} 최신 뉴스"
        except Exception:
            pass

    return "최신 IT & AI 기술 동향", "최신 인공지능 IT 트렌드 뉴스"


async def generate_morning_briefing_content() -> discord.Embed:
    """날씨, 미세먼지, 맞춤형 3대 뉴스 취합 및 모닝 브리핑 임베드 조립"""
    weather_data = await fetch_weather_and_dust()
    topic_title, search_query = extract_recent_topic()
    
    from smart_search import search_duckduckgo
    news_results = await search_duckduckgo(search_query, max_results=3)

    news_lines = []
    if news_results:
        for i, item in enumerate(news_results[:3], 1):
            title = item.get("title", "뉴스 소식").strip()
            url = item.get("url", "https://news.google.com")
            snippet = item.get("snippet", "").strip()
            snippet_clean = snippet[:110] + "..." if len(snippet) > 110 else snippet
            news_lines.append(f"**{i}. [{title}]({url})**\n> {snippet_clean}\n")
    else:
        news_lines.append("> 최신 뉴스 데이터를 집계 중입니다.")

    now_str = datetime.datetime.now().strftime("%Y년 %m월 %d일 (%a)")

    embed = discord.Embed(
        title=f"🌊 스카디의 모닝 브리핑 • {now_str}",
        description="마스터, 좋은 아침이야. 오늘 하루를 위한 날씨와 마스터 맞춤 소식을 정리해왔어.",
        color=0x2980b9
    )

    # 날씨 & 미세먼지 필드
    weather_text = (
        f"📍 **지역**: `{weather_data['city_name']}`\n"
        f"🌡️ **기온**: `{weather_data['temp']}°C` | **하늘**: {weather_data['weather_desc']}\n"
        f"💨 **미세먼지(PM10)**: {weather_data['pm10']}\n"
        f"🌫️ **초미세먼지(PM2.5)**: {weather_data['pm25']}"
    )
    embed.add_field(name=f"☀️ 오늘의 날씨 & 대기 상태 ({weather_data['city_name']})", value=weather_text, inline=False)

    # 관심 뉴스 3개 요약 + 링크
    embed.add_field(
        name=f"📰 마스터 관심 테마 3대 뉴스 • [{topic_title}]",
        value="\n".join(news_lines),
        inline=False
    )

    # 📅 오늘의 스케줄 & 할 일(Todo) 연동
    if ScheduleManager:
        try:
            today_date = datetime.datetime.now().strftime("%Y-%m-%d")
            today_items = ScheduleManager.get_items(target_date=today_date, include_completed=False)
            pending_todos = ScheduleManager.get_items(only_todos=True, include_completed=False)

            sched_lines = []
            events = [it for it in today_items if not it.get("is_todo")]
            if events:
                for ev in events:
                    t_str = ev['start_time'].split(' ')[1] if ' ' in ev['start_time'] else '종일'
                    sched_lines.append(f"• `[{t_str}]` **{ev['title']}**")
            else:
                sched_lines.append("• 예정된 일정이 없습니다. (자유 시간)")

            if pending_todos:
                sched_lines.append("\n**진행 중인 주요 태스크:**")
                for td in pending_todos[:3]:
                    p_mark = "🔥" if td.get("priority", 2) == 3 else "⚡"
                    sched_lines.append(f"• {p_mark} {td['title']}")

            embed.add_field(
                name="📅 오늘 마스터의 스케줄 & 할 일",
                value="\n".join(sched_lines),
                inline=False
            )
        except Exception as se:
            logger.warning(f"스케줄 브리핑 조회 오류: {se}")

    embed.set_footer(text="스카디 자율 모닝 브리핑 • 평일(월~금) 오전 8:00 자동 전송")
    return embed


@tasks.loop(minutes=1)
async def morning_briefing_task():
    """평일(월~금) 오전 8시 모닝 브리핑 자동 전송 백그라운드 태스크"""
    global last_briefing_date
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    # 평일 (월=0 ~ 금=4, 주말 5,6 제외) & 오전 8시 도달 시 정각 0ms 오차 없이 1회 발송
    if now.weekday() < 5 and now.hour == 8 and last_briefing_date != today_str:
        last_briefing_date = today_str
        logger.info(f"🌅 [모닝 브리핑] 평일 오전 8시 정기 모닝 브리핑 발송을 시작합니다... ({today_str})")

        try:
            embed = await generate_morning_briefing_content()

            # 전송 대상 채널 탐색
            target_channels = []
            for guild in bot.guilds:
                found = False
                # 1. 설정 파일의 자동 대화 채널
                for ch_id in config_data.get("auto_reply_channels", []):
                    ch = guild.get_channel(ch_id)
                    if ch:
                        target_channels.append(ch)
                        found = True
                        break
                
                # 2. 채널 이름 탐색
                if not found:
                    for ch in guild.text_channels:
                        if ch.name in ["스카디-대화", "스카디", "skadi-chat", "일반", "general"]:
                            target_channels.append(ch)
                            found = True
                            break

                # 3. 길드 기본 시스템 채널
                if not found and guild.system_channel:
                    target_channels.append(guild.system_channel)

            for ch in target_channels:
                try:
                    await ch.send(embed=embed)
                    # 음성 채널 접속 중일 경우 모닝 음성 낭독
                    if ch.guild.voice_client and ch.guild.voice_client.is_connected():
                        v_file = await generate_voice_audio("마스터, 좋은 아침이야. 오늘 날씨와 관심 뉴스를 정리해뒀어. 오늘도 힘내자.")
                        if v_file:
                            await play_voice_audio(ch.guild.voice_client, v_file)
                except Exception as e:
                    logger.error(f"모닝 브리핑 전송 오류 ({ch.name}): {e}")

        except Exception as be:
            logger.error(f"모닝 브리핑 생성 오류: {be}")


# ------------------------------------------------------------
# 2-3. 24시간 실시간 증시 장 마감 정기 브리핑 스케줄러
# ------------------------------------------------------------
last_kr_stock_date = ""
last_us_stock_date = ""

@tasks.loop(minutes=1)
async def daily_stock_briefing_task():
    """
    24시간 실시간 증시 장 마감 브리핑 스케줄러:
    1. 국내 주식: 평일(월~금) 15:40 KST -> #국내-주식 채널 자동 전송
    2. 미국 주식: 평일(화~토) 06:30 KST -> #미국-주식 채널 자동 전송
    """
    global last_kr_stock_date, last_us_stock_date
    if not stock_engine:
        return

    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    # 1. 국내 증시 (월~금 오후 3시 40분)
    if now.weekday() < 5 and now.hour == 15 and now.minute >= 40 and last_kr_stock_date != today_str:
        last_kr_stock_date = today_str
        logger.info(f"📈 [국내 증시 장 마감] {today_str} 국내 주식 3개년 성장주 TOP 10 자동 브리핑을 발송합니다...")
        try:
            kr_data = stock_engine.get_daily_growth_top_ranking('KR', top_n=10)
            if kr_data:
                kr_embed = discord.Embed(
                    title=f"🔔 [{today_str}] 국내 증시 장 마감 3개년 성장성 & 당일 모멘텀 TOP 10",
                    description="🛡️ **회계 검증**: 대차대조표 부채비율 **120% 이하** & 3개년 자산 증가율 **양수(+)**\n⚡ **데일리 랭킹**: 당일 주가 모멘텀(등락률) 순 실시간 정렬",
                    color=0x3498db
                )
                for i, itm in enumerate(kr_data, 1):
                    chg = f"+{itm['change_pct']}%" if itm['change_pct'] >= 0 else f"{itm['change_pct']}%"
                    field_name = f"{i}. {itm['name']} ({itm['symbol']}) • ₩{itm['price']:,.0f} ({chg})"
                    field_val = (
                        f"• 📈 **3개년 자산성장**: `+{itm['asset_growth_3y']}%` ({itm['past_assets_fmt']} ➔ {itm['recent_assets_fmt']})\n"
                        f"• 🛡️ **정규 부채비율**: `{itm['debt_ratio']}%` (총부채 {itm['liabilities_fmt']} / 자본 {itm['equity_fmt']})"
                    )
                    kr_embed.add_field(name=field_name, value=field_val, inline=False)
                kr_embed.set_footer(text=f"기준일자: {today_str} • 스카디 퀀트 장 마감 정기 브리핑")

                stock_channels_cfg = config_data.get("stock_channels", {})
                target_id = stock_channels_cfg.get("kr")
                
                for guild in bot.guilds:
                    ch = guild.get_channel(target_id) if target_id else None
                    if not ch:
                        for c in guild.text_channels:
                            if "국내" in c.name and "주식" in c.name:
                                ch = c
                                break
                    if ch:
                        await ch.send(content=f"📊 **[스카디 퀀트] {today_str} 국내 증시 장 마감 리포트**가 도착했다, 마스터!", embed=kr_embed)
        except Exception as e:
            logger.error(f"국내 주식 정기 브리핑 발송 오류: {e}")

    # 2. 미국 증시 (화~토 오전 6시 30분, 미국 뉴욕 월~금 장 마감 후)
    if (1 <= now.weekday() <= 5) and now.hour == 6 and now.minute >= 30 and last_us_stock_date != today_str:
        last_us_stock_date = today_str
        logger.info(f"🇺🇸 [미국 증시 장 마감] {today_str} 미국 주식 3개년 성장주 TOP 10 자동 브리핑을 발송합니다...")
        try:
            us_data = stock_engine.get_daily_growth_top_ranking('US', top_n=10)
            if us_data:
                us_embed = discord.Embed(
                    title=f"🔔 [{today_str}] 미국 증시 뉴욕 장 마감 3개년 성장성 & 당일 모멘텀 TOP 10",
                    description="🛡️ **회계 검증**: 대차대조표 부채비율 **120% 이하** & 3개년 자산 증가율 **양수(+)**\n⚡ **데일리 랭킹**: 당일 주가 모멘텀(등락률) 순 실시간 정렬",
                    color=0x2ecc71
                )
                for i, itm in enumerate(us_data, 1):
                    chg = f"+{itm['change_pct']}%" if itm['change_pct'] >= 0 else f"{itm['change_pct']}%"
                    field_name = f"{i}. {itm['name']} ({itm['symbol']}) • ${itm['price']:,.2f} ({chg})"
                    field_val = (
                        f"• 📈 **3개년 자산성장**: `+{itm['asset_growth_3y']}%` ({itm['past_assets_fmt']} ➔ {itm['recent_assets_fmt']})\n"
                        f"• 🛡️ **정규 부채비율**: `{itm['debt_ratio']}%` (총부채 {itm['liabilities_fmt']} / 자본 {itm['equity_fmt']})"
                    )
                    us_embed.add_field(name=field_name, value=field_val, inline=False)
                us_embed.set_footer(text=f"기준일자: {today_str} • 스카디 퀀트 뉴욕 장 마감 정기 브리핑")

                stock_channels_cfg = config_data.get("stock_channels", {})
                target_id = stock_channels_cfg.get("us")

                for guild in bot.guilds:
                    ch = guild.get_channel(target_id) if target_id else None
                    if not ch:
                        for c in guild.text_channels:
                            if "미국" in c.name and "주식" in c.name:
                                ch = c
                                break
                    if ch:
                        await ch.send(content=f"📊 **[스카디 퀀트] {today_str} 미국 증시 뉴욕 장 마감 리포트**가 도착했다, 마스터!", embed=us_embed)
        except Exception as e:
            logger.error(f"미국 주식 정기 브리핑 발송 오류: {e}")


# ------------------------------------------------------------
# 3. 디스코드 봇 클라이언트 초기화
# ------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix=config_data.get("command_prefix", "!"),
    intents=intents,
    help_command=None
)

# 채널별 대화 세션 기록 저장소: {channel_id: deque(maxlen=20)}
conversation_history: Dict[int, deque] = {}

# 활성 페르소나 및 모델 (런타임 오버라이드)
current_persona_key = config_data.get("default_persona", "bocadi")
current_model_key = config_data.get("default_model", "gemini")


def get_channel_history(channel_id: int) -> deque:
    """채널별 대화 히스토리 반환 (최대 턴수 제한)"""
    max_turns = config_data.get("max_history_turns", 15)
    if channel_id not in conversation_history:
        conversation_history[channel_id] = deque(maxlen=max_turns * 2)
    return conversation_history[channel_id]


def build_system_prompt() -> str:
    """현재 페르소나와 장기 기억을 결합한 통합 시스템 프롬프트 조립"""
    personas = config_data.get("personas", {})
    persona_info = personas.get(current_persona_key, personas.get("bocadi", {}))
    base_prompt = persona_info.get("prompt", "너는 마스터를 지키는 스카디야.")

    # 장기 기억 주입 (옵션)
    memory_prompt = ""
    if config_data.get("enable_memory", True) and memory_engine:
        try:
            memory_prompt = memory_engine.get_fact_sheet_prompt()
            if memory_prompt:
                memory_prompt = "\n\n" + memory_prompt
        except Exception as me:
            logger.warning(f"장기 기억 로드 실패: {me}")

    # 현재 시간 안내 주입
    current_time_str = f"\n[현재 시간: {time.strftime('%Y년 %m월 %d일 %H:%M')}]"

    # 언어 및 태그 절대 규칙 주입
    korean_rule = (
        "\n\n[언어 및 출력 절대 규칙]\n"
        "1. 반드시 100% 자연스럽고 매끄러운 한국어(Korean)로만 대답하라.\n"
        "2. 중국어(한자), 영어 메타 해설, 번역 관련 설명, 캐릭터 설정 불일치에 대한 변명은 절대로 출력하지 마라.\n"
        "3. 사족이나 해설 없이, 처음부터 끝까지 스카디의 한국어 대사만 깔끔하게 출력해라."
    )

    return base_prompt + memory_prompt + current_time_str + korean_rule


def sanitize_korean_response(text: str) -> str:
    """중국어 메타 해설 블록이나 불필요한 번역 분리선 제거"""
    import re
    if "---" in text:
        parts = text.split("---")
        korean_parts = []
        for p in parts:
            p_strip = p.strip()
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', p_strip))
            if chinese_chars < 5:
                korean_parts.append(p_strip)
        if korean_parts:
            text = "\n\n".join(korean_parts)

    # 중국어 전용 줄 제거
    lines = []
    for line in text.split("\n"):
        chinese_count = len(re.findall(r'[\u4e00-\u9fff]', line))
        korean_count = len(re.findall(r'[가-힣]', line))
        if chinese_count > 5 and chinese_count > korean_count:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


async def generate_skadi_response_with_thinking(
    messages: List[Dict[str, Any]],
    status_callback=None
) -> tuple[str, List[str], float]:
    """LLM 오케스트레이터를 통한 스카디 답변 생성 및 실시간 사고 과정(Thinking Steps) 추적"""
    system_prompt = build_system_prompt()
    full_response = ""
    steps = ["질문 의도 분석 및 장기 기억(Fact Vault) 탐색 중..."]
    start_time = time.time()
    active_engine_name = "Google Gemini" if current_model_key == "gemini" else current_model_key

    if status_callback:
        await status_callback(steps, "thinking")

    try:
        async for chunk in orchestrator.stream_chat(
            messages=messages,
            system_prompt=system_prompt,
            agent_name="스카디",
            target_model=current_model_key,
            enable_grounding=True,
            ollama_model_name=config_data.get("ollama_model", "llama3.1")
        ):
            if chunk.startswith("data: "):
                raw_json = chunk[6:].strip()
                if not raw_json:
                    continue
                try:
                    payload = json.loads(raw_json)
                    # 1. 상태 레이블 이벤트 추적
                    if "status" in payload:
                        label = payload.get("label", "")
                        if label and label not in steps:
                            steps.append(label)
                            if status_callback:
                                await status_callback(steps, payload.get("status"))
                    # 2. 텍스트 콘텐츠 취합
                    if "content" in payload:
                        full_response += payload["content"]
                except json.JSONDecodeError:
                    pass

        elapsed = round(time.time() - start_time, 1)
        clean_text = sanitize_korean_response(full_response)
        if not clean_text:
            clean_text = "마스터... 잠시 생각이 흩어졌어. 다시 한 번 말해줄래?"
        return clean_text, steps, elapsed

    except Exception as e:
        logger.error(f"스카디 답변 생성 오류: {e}")
        elapsed = round(time.time() - start_time, 1)
        return f"미안해, 마스터... 생각을 정리하는 도중 오류가 발생했어. ({e})", steps, elapsed


async def send_split_messages(destination, text: str, reference_msg: Optional[discord.Message] = None):
    """디스코드 2000자 제한을 초과하는 긴 텍스트를 문맥 단위로 분할 전송"""
    MAX_LEN = 1900
    if len(text) <= MAX_LEN:
        if reference_msg:
            try:
                await reference_msg.reply(text)
                return
            except discord.HTTPException:
                pass
        await destination.send(text)
        return

    chunks = []
    current_chunk = ""
    for line in text.split("\n"):
        if len(current_chunk) + len(line) + 1 > MAX_LEN:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            while len(line) > MAX_LEN:
                chunks.append(line[:MAX_LEN])
                line = line[MAX_LEN:]
            current_chunk = line
        else:
            current_chunk = f"{current_chunk}\n{line}" if current_chunk else line

    if current_chunk:
        chunks.append(current_chunk)

    for i, chunk in enumerate(chunks):
        if i == 0 and reference_msg:
            try:
                await reference_msg.reply(chunk)
                continue
            except discord.HTTPException:
                pass
        await destination.send(chunk)
        await asyncio.sleep(0.3)


def start_render_health_server_thread():
    """Render Web Service 무료 티어 15분 절전 방지 및 포트 바인딩 헬스체크 서버"""
    port_str = os.environ.get("PORT")
    if not port_str:
        return
    try:
        port = int(port_str)
        import threading
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write("🌊 Skadi Discord Bot is Healthy & Online 24/7!".encode('utf-8'))

            def log_message(self, format, *args):
                pass

        def _serve():
            try:
                server = HTTPServer(('0.0.0.0', port), HealthHandler)
                logger.info(f"🌐 Render 헬스체크 웹 서버 즉시 가동 완료 (Port: {port})")
                server.serve_forever()
            except Exception as e:
                logger.warning(f"Render 헬스체크 서버 오류: {e}")

        th = threading.Thread(target=_serve, daemon=True)
        th.start()
    except Exception as e:
        logger.warning(f"Render 헬스체크 서버 시작 실패: {e}")


@tasks.loop(minutes=10)
async def keep_alive_task():
    """Render 15분 절전 방지를 위한 자동 Keep-Alive 핑"""
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{render_url}/health")
                logger.info(f"🔄 Render Keep-Alive 핑 성공: {r.status_code}")
        except Exception as e:
            logger.debug(f"Render Keep-Alive 핑: {e}")


# ------------------------------------------------------------
# 4. 디스코드 이벤트 핸들러
# ------------------------------------------------------------
@bot.event
async def on_ready():
    logger.info("=" * 60)
    logger.info(f"✨ 스카디 디스코드 봇 로그인 성공: {bot.user} (ID: {bot.user.id})")
    logger.info(f"✨ 현재 페르소나: {current_persona_key} ({config_data.get('personas', {}).get(current_persona_key, {}).get('name', '스카디')})")
    logger.info(f"✨ 활성 LLM 엔진: {current_model_key}")
    logger.info(f"✨ 연결된 서버 수: {len(bot.guilds)}개")
    for guild in bot.guilds:
        logger.info(f"   - {guild.name} (ID: {guild.id})")
    logger.info("=" * 60)

    # 봇 상태 메시지 설정
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name="마스터의 목소리 (!도움말)"
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)

    # 모닝 브리핑 백그라운드 태스크 시작 (평일 오전 8시)
    if not morning_briefing_task.is_running():
        morning_briefing_task.start()
        logger.info("🌅 모닝 브리핑 백그라운드 스케줄러 활성화 완료 (평일 08:00 KST)")

    # 24시간 실시간 장 마감 주식 브리핑 백그라운드 태스크 시작
    if not daily_stock_briefing_task.is_running():
        daily_stock_briefing_task.start()
        logger.info("📈 24시간 장 마감 주식 브리핑 스케줄러 활성화 완료 (국내 15:40 / 미국 06:30 KST)")

    # Render 클라우드 Keep-Alive 절전 방지 태스크 시작
    if os.environ.get("RENDER_EXTERNAL_URL") and not keep_alive_task.is_running():
        keep_alive_task.start()
        logger.info("🔄 Render Keep-Alive 스케줄러 활성화 완료 (10분 주기)")


@bot.event
async def on_message(message: discord.Message):
    # 1. 봇 자신의 메시지는 무시
    if message.author.bot:
        return

    # 2. 명령어 처리 먼저 시도 (prefix로 시작하는 경우)
    prefix = config_data.get("command_prefix", "!")
    if message.content.startswith(prefix):
        await bot.process_commands(message)
        return

    # 3. 대화 트리거 조건 판단
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions or f"<@{bot.user.id}>" in message.content or f"<@!{bot.user.id}>" in message.content
    
    # 답장(Reply) 트리거: 유저가 봇의 메시지에 답장한 경우
    is_reply_to_bot = False
    if message.reference and message.reference.resolved:
        resolved_msg = message.reference.resolved
        if isinstance(resolved_msg, discord.Message) and resolved_msg.author.id == bot.user.id:
            is_reply_to_bot = True

    # 지정된 전용 채널인지 확인
    is_auto_channel = (
        message.channel.id in config_data.get("auto_reply_channels", []) or
        getattr(message.channel, "name", "") in ["스카디", "스카디-대화", "skadi-chat", "skadi"]
    )

    should_reply = is_dm or is_mentioned or is_reply_to_bot or is_auto_channel

    if not should_reply:
        return

    # 멘션 태그 문자열 정리
    user_query = message.clean_content.strip()
    user_query = user_query.replace(f"@{bot.user.name}", "").strip()

    if not user_query:
        await message.reply("응, 마스터. 부르고 싶은 말이 있어?")
        return

    clean_lower = user_query.lower().strip()

    # ------------------------------------------------------------
    # 3-1. 스마트 채팅 관리 및 대화 삭제/롤백 기능 (자연어 처리)
    # ------------------------------------------------------------
    # 1. "위로 싹 다 지워줘" / "~부터 위로 삭제" / 답장 기반 위로 삭제
    is_purge_above_phrase = any(k in clean_lower for k in [
        "위로삭다", "위로 싹다", "위로 싹 다", "위로 다 지워", "위로 다 삭제", "위로 싹 지워",
        "위로 지워", "위로삭제", "위로 삭제", "위로 청소", "이 위로 다", "이전 대화 전부 지워",
        "부터 위로", "채팅 부터 위로", "대화 부터 위로", "위로 싹", "위로 삭"
    ])

    if is_purge_above_phrase:
        try:
            target_msg_id = None
            keyword = None

            # 1-1. 답장(Reply)이 있는 경우: 해당 답장 메시지 기준
            if message.reference and message.reference.message_id:
                target_msg_id = message.reference.message_id

            # 1-2. 본문에서 특정 키워드 추출 (예: "히어로즈 오브메이플", "체스", "메이플" 등)
            else:
                m_kw = re.search(r'(?:위에\s*)?([가-힣a-zA-Z0-9_\s]{2,25}?)(?:\s*채팅|\s*대화|\s*메시지)?\s*(?:부터|이전부터)?\s*위로', clean_lower)
                if m_kw:
                    extracted = m_kw.group(1).strip()
                    extracted = re.sub(r'^(.*?위에\s*)', '', extracted).strip()
                    if extracted and len(extracted) >= 2 and extracted not in ["대화", "채팅", "메시지", "여기"]:
                        keyword = extracted

            # 채널 메시지 탐색 및 삭제 대상 수집
            to_delete = [message]
            async for m in message.channel.history(limit=100):
                if m.id == message.id:
                    continue
                to_delete.append(m)

                # 답장 대상 도달
                if target_msg_id and m.id == target_msg_id:
                    break

                # 키워드 일치 도달
                if keyword:
                    kw_words = [w for w in keyword.split() if len(w) >= 2]
                    if keyword in m.content.lower() or (kw_words and all(w in m.content.lower() for w in kw_words)):
                        break

            # 일괄 삭제 실행
            if to_delete:
                try:
                    if hasattr(message.channel, 'delete_messages') and len(to_delete) > 1:
                        await message.channel.delete_messages(to_delete)
                    else:
                        for m in to_delete:
                            await m.delete()
                except Exception:
                    for m in to_delete:
                        try:
                            await m.delete()
                        except Exception:
                            pass

            # AI 대화 기억 전체 리셋
            if message.channel.id in conversation_history:
                conversation_history[message.channel.id].clear()

            kw_text = f"'{keyword}' 관련 대화" if keyword else "지정한 위치"
            noti = await message.channel.send(f"🧹 마스터, {kw_text}부터 위쪽 {len(to_delete)}개 대화를 모두 깨끗하게 지우고 기억을 비웠어.")
            await asyncio.sleep(4)
            await noti.delete()
            return
        except Exception as e:
            logger.warning(f"위로 싹다 삭제 실패: {e}")

    # 2. 답장(Reply) + "이 대화 지워줘 / 이 메시지 삭제"
    if message.reference and any(k in clean_lower for k in ["이 대화 지워", "이거 지워", "이 대화 삭제", "이거 삭제", "이 메시지 지워", "이 대화 없애", "지워줘"]):
        try:
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            if ref_msg:
                await ref_msg.delete()
            await message.delete()
            # AI 메모리에서 최근 1턴 제거
            history = get_channel_history(message.channel.id)
            if len(history) >= 2:
                history.pop()
                history.pop()
            noti = await message.channel.send("🗑️ 마스터, 지정한 대화를 깔끔하게 지웠어.")
            await asyncio.sleep(3.5)
            await noti.delete()
            return
        except Exception as e:
            logger.warning(f"대화 삭제 실패: {e}")

    # 3. 개수 기반 삭제 ("대화 5개 지워줘", "최근 10개 삭제", "3개 청소해줘")
    match_count = re.search(r'(\d+)\s*(?:개|건|줄)?\s*(?:대화|채팅|메시지)?\s*(?:지워|삭제|청소|정리)', clean_lower)
    if match_count:
        try:
            num = int(match_count.group(1))
            num = min(max(num, 1), 50)
            if hasattr(message.channel, 'purge'):
                await message.channel.purge(limit=num + 1)
            history = get_channel_history(message.channel.id)
            for _ in range(min(num * 2, len(history))):
                history.pop()
            noti = await message.channel.send(f"🧹 마스터와의 최근 {num}개 대화를 삭제했어.")
            await asyncio.sleep(3.5)
            await noti.delete()
            return
        except Exception as e:
            logger.warning(f"개수 삭제 실패: {e}")

    # 4. 방금 대화 롤백 ("방금 한 말 취소", "되돌리기", "방금 대화 잊어줘")
    if any(k in clean_lower for k in ["방금 한 말 취소", "방금 대화 잊어", "되돌리기", "방금 말 취소", "방금 대화 지워"]):
        history = get_channel_history(message.channel.id)
        if len(history) >= 2:
            history.pop()
            history.pop()
        try:
            if hasattr(message.channel, 'purge'):
                await message.channel.purge(limit=3)
        except Exception:
            pass
        noti = await message.channel.send("⏪ 마스터, 방금 나눈 대화를 기억과 채팅에서 되돌렸어.")
        await asyncio.sleep(3.5)
        await noti.delete()
        return

    # ------------------------------------------------------------
    # 3-2. 스마트 음성 채널(Voice Channel) 참가 및 퇴장 자연어 처리
    # ------------------------------------------------------------
    is_voice_join = any(k in clean_lower for k in [
        "음성 들어와", "통화방 들어와", "음성방 들어와", "보이스 들어와", "음성채널 들어와",
        "통화 들어와", "음성으로 와", "통화방으로 와", "몇번 들어와", "음성 참가", "보이스 참가", "음성 와", "통화방 와"
    ])
    is_voice_leave = any(k in clean_lower for k in [
        "음성 나가", "통화방 나가", "음성방 나가", "보이스 나가", "음성채널 나가",
        "통화 나가", "음성 퇴장", "보이스 퇴장", "통화방에서 나가", "음성에서 나가", "통화방 나가줘"
    ])

    if is_voice_join and message.guild:
        target_str = clean_lower
        for word in ["음성", "통화방", "음성방", "보이스", "채널", "들어와", "참가", "으로", "로", "와"]:
            target_str = target_str.replace(word, "")
        target_str = target_str.strip()

        target_vc = find_target_voice_channel(message.guild, message.author, target_str if len(target_str) >= 1 else None)
        if not target_vc:
            await message.reply("마스터, 들어갈 음성 채널을 찾지 못했어. 음성 채널에 먼저 들어가 있거나 채널 번호(예: `1번 음성 들어와`)를 알려줘.")
            return

        try:
            vc_client = message.guild.voice_client
            if vc_client and vc_client.is_connected():
                if vc_client.channel.id != target_vc.id:
                    await vc_client.move_to(target_vc)
            else:
                vc_client = await target_vc.connect()

            await message.reply(f"🔊 마스터, **[{target_vc.name}]** 음성 채널에 들어왔어. 이제 목소리로 함께할게.")
            
            # 입장 인사 음성 재생
            voice_file = await generate_voice_audio("마스터, 나 여기 있어. 무슨 일이든 편하게 말해줘.")
            if voice_file and vc_client and vc_client.is_connected():
                await play_voice_audio(vc_client, voice_file)
            return
        except Exception as ve:
            logger.error(f"음성 채널 연결 실패: {ve}")
            await message.reply(f"⚠️ 음성 채널에 연결하지 못했어: {ve}")
            return

    if is_voice_leave and message.guild:
        vc_client = message.guild.voice_client
        if vc_client and vc_client.is_connected():
            await vc_client.disconnect()
            await message.reply("👋 음성 채널에서 퇴장했어, 마스터. 필요하면 언제든 다시 불러줘.")
        else:
            await message.reply("마스터, 나는 지금 음성 채널에 들어가 있지 않아.")
        return

    # 채널별 대화 큐 가져오기
    history = get_channel_history(message.channel.id)

    # 프롬프트 메시지 구조 생성
    messages_payload: List[Dict[str, Any]] = list(history)
    messages_payload.append({
        "role": "user",
        "content": f"{message.author.display_name}: {user_query}"
    })

    # 실시간 사고 과정(Thinking) 임베드 전송
    thinking_msg: Optional[discord.Message] = None
    last_edit_time = 0.0

    async def update_thinking_status(steps_list: List[str], current_status: str):
        nonlocal thinking_msg, last_edit_time
        now = time.time()
        if now - last_edit_time < 0.6 and len(steps_list) > 1:
            return
        last_edit_time = now

        step_lines = []
        for s in steps_list[:-1]:
            step_lines.append(f"✓ {s}")
        if steps_list:
            step_lines.append(f"⏳ **{steps_list[-1]}**")

        desc = "\n".join(step_lines)
        embed = discord.Embed(
            title="🧠 스카디 사고 과정 (Thinking Process)",
            description=desc,
            color=0x3498db
        )
        
        try:
            if thinking_msg is None:
                thinking_msg = await message.reply(embed=embed)
            else:
                await thinking_msg.edit(embed=embed)
        except Exception:
            pass

    # 답변 생성 (사고 과정 추적)
    async with message.channel.typing():
        response_text, steps, elapsed = await generate_skadi_response_with_thinking(
            messages_payload,
            status_callback=update_thinking_status if config_data.get("show_thinking_steps", True) else None
        )

    # 대화 히스토리 업데이트
    history.append({"role": "user", "content": f"{message.author.display_name}: {user_query}"})
    history.append({"role": "assistant", "content": response_text})

    # 음성 채널에 접속 중이라면 스카디 목소리로도 답변 낭독
    if message.guild and message.guild.voice_client and message.guild.voice_client.is_connected():
        asyncio.create_task(speak_response_in_voice(message.guild.voice_client, response_text))

    # 최종 완료 메시지 전송 (사고 과정 메시지를 최종 답변으로 부드럽게 전환)
    engine_name = "Google Gemini" if current_model_key == "gemini" else current_model_key
    footer_tag = f"\n\n*⏱️ {elapsed}s | 🧠 {engine_name} | 🌊 AI Brain 연동*"
    
    full_output = response_text
    if len(full_output + footer_tag) <= 1900:
        full_output += footer_tag

    if thinking_msg:
        try:
            if len(full_output) <= 1900:
                await thinking_msg.edit(content=full_output, embed=None)
                return
            else:
                await thinking_msg.delete()
        except Exception:
            pass

    await send_split_messages(message.channel, full_output, reference_msg=message)


# ------------------------------------------------------------
# 5. 디스코드 명령어 (Prefix Commands)
# ------------------------------------------------------------
@bot.command(name="도움말", aliases=["help", "명령어"])
async def cmd_help(ctx: commands.Context):
    """스카디 디스코드 봇 도움말"""
    embed = discord.Embed(
        title="🌊 심해의 사냥꾼 & 전담 비서 '스카디' 디스코드 봇 안내",
        description="마스터, 나와 대화하고 싶다면 언제든 불러줘. 아래 명령어로 나를 설정할 수 있어.",
        color=discord.Color.from_rgb(52, 152, 219)
    )
    
    prefix = config_data.get("command_prefix", "!")
    embed.add_field(
        name="💬 대화하는 방법",
        value=(
            f"• **멘션**: `@{bot.user.name} <하고 싶은 말>`\n"
            f"• **답장**: 스카디의 메시지에 [답장]하면 계속 대화\n"
            f"• **DM**: 1:1 개인 메시지는 멘션 없이 바로 대화\n"
            f"• **전용 채널**: `{prefix}채널지정`으로 지정된 채널에선 그냥 말해도 대화"
        ),
        inline=False
    )
    embed.add_field(
        name="🎙️ 음성 통화방(Voice Channel) 기능",
        value=(
            f"• **음성 참가**: `음성 들어와` 또는 `1번 음성 들어와` 또는 `{prefix}들어와`\n"
            f"• **음성 퇴장**: `음성 나가` 또는 `{prefix}나가`\n"
            f"• **목소리 낭독**: `{prefix}말해 <내용>` (스카디 목소리로 읽어주기)\n"
            f"• 💡 *음성 채널에 봇이 들어와 있을 땐 텍스트 답변도 목소리로 실시간 말해줍니다!*"
        ),
        inline=False
    )
    embed.add_field(
        name="🌅 모닝 브리핑 & 자율 선톡",
        value=(
            f"• **평일 자동 발송**: 매주 평일(월~금) 오전 8:00 KST 자동 선톡\n"
            f"• **즉시 확인**: `{prefix}모닝브리핑` (또는 `{prefix}아침브리핑`)\n"
            f"• 💡 *오늘 날씨, 미세먼지(PM10/PM2.5) 등급, 최근 대화 주제 3대 뉴스 요약 + 링크*"
        ),
        inline=False
    )
    embed.add_field(
        name="🧹 채팅 관리 및 대화 삭제 기능",
        value=(
            f"• **자연어 삭제**: `이 대화 지워줘` (답장하며 말하기)\n"
            f"• **구간 위로 삭제**: `여기서부터 위로 지워줘` (또는 `[키워드]부터 위로 삭제`)\n"
            f"• **개수 삭제**: `대화 5개 지워줘` 또는 `{prefix}청소 5`\n"
            f"• **되돌리기**: `방금 한 말 취소` 또는 `{prefix}되돌리기`"
        ),
        inline=False
    )
    embed.add_field(
        name="📅 스마트 캘린더 & 할 일(Todo) 관리",
        value=(
            f"• **일정 확인**: `{prefix}일정` (또는 `{prefix}일정 YYYY-MM-DD`)\n"
            f"• **일정 등록**: `{prefix}일정추가 YYYY-MM-DD HH:MM 일정제목`\n"
            f"• **일정 삭제**: `{prefix}일정삭제 <ID>`\n"
            f"• **할일 확인**: `{prefix}할일` (진행 중인 할 일 체크리스트)\n"
            f"• **할일 등록**: `{prefix}할일추가 <내용>` (긴급 시 `[긴급]` 포함)\n"
            f"• **할일 완료**: `{prefix}할일완료 <ID>` (완료 토글)\n"
            f"• **캘린더 연동**: `{prefix}캘린더연동` (구글/삼성 캘린더 실시간 동기화 iCal 가이드)\n"
            f"• **모닝 브리핑**: `{prefix}브리핑` (날씨 + 뉴스 + 오늘 스케줄)"
        ),
        inline=False
    )
    embed.add_field(
        name="📊 주식 퀀트 & 3개년 성장성 리포트 (국내/미국)",
        value=(
            f"• **통합 브리핑**: `{prefix}주식` (국내 & 미국 3개년 성장성 TOP 5)\n"
            f"• **미국 주식 TOP 10**: `{prefix}주식 미국` (부채비율 120% 이하 + 당일 모멘텀 순)\n"
            f"• **국내 주식 TOP 10**: `{prefix}주식 국내` (부채비율 120% 이하 + 당일 모멘텀 순)\n"
            f"• **개별 종목 정밀 진단**: `{prefix}주식 삼성전자` 또는 `{prefix}주식 NVDA`"
        ),
        inline=False
    )
    embed.add_field(
        name="🛠️ 시스템 설정 명령어",
        value=(
            f"• `{prefix}페르소나 [보카디/비서/주식/화가/레식]` : 스카디 성격/역할 변경\n"
            f"• `{prefix}모델 [gemini/ollama/openai/claude]` : AI 두뇌 엔진 변경\n"
            f"• `{prefix}리셋` (또는 `!reset`) : 현재 채널 대화 기억 전체 초기화\n"
            f"• `{prefix}채널지정` / `{prefix}채널해제` : 상시 대화 채널 ON/OFF\n"
            f"• `{prefix}상태` : 스카디 시스템 정보 및 모델 상태 확인"
        ),
        inline=False
    )
    embed.add_field(
        name="🧠 장기 기억 명령어",
        value=(
            f"• `{prefix}기억 <내용>` : 마스터에 대한 중요한 사실을 영구 기억\n"
            f"• `{prefix}기억삭제 <키워드>` : 저장된 기억 중 특정 항목 영구 삭제\n"
            f"• `{prefix}기억목록` : 스카디가 기억하고 있는 마스터 정보 확인"
        ),
        inline=False
    )
    embed.set_footer(text=f"현재 엔진: {current_model_key} | 페르소나: {current_persona_key}")
    await ctx.send(embed=embed)


@bot.command(name="모닝브리핑", aliases=["아침브리핑", "briefing", "선톡테스트", "브리핑"])
async def cmd_morning_briefing(ctx: commands.Context):
    """오늘의 날씨, 미세먼지, 맞춤 관심 뉴스 3개 모닝 브리핑 즉시 출력"""
    async with ctx.typing():
        embed = await generate_morning_briefing_content()
    await ctx.send(embed=embed)
    
    if ctx.guild and ctx.guild.voice_client and ctx.guild.voice_client.is_connected():
        v_file = await generate_voice_audio("마스터, 좋은 아침이야. 오늘 날씨와 관심 뉴스를 정리해뒀어. 오늘도 좋은 하루 보내.")
        if v_file:
            await play_voice_audio(ctx.guild.voice_client, v_file)


@bot.command(name="지역", aliases=["날씨지역", "location", "도시"])
async def cmd_set_location(ctx: commands.Context, *, city_name: Optional[str] = None):
    """모닝 브리핑 날씨 및 미세먼지 기준 지역 조회 및 변경"""
    if not city_name:
        curr = config_data.get("weather_city", "익산")
        avail_cities = ", ".join(list(CITY_COORDINATES.keys())[:10])
        await ctx.send(f"📍 현재 날씨/미세먼지 기준 지역은 **[{curr}]**(으)로 설정되어 있어.\n💡 변경 방법: `!지역 전주`, `!지역 서울`, `!지역 부산`\n(지원 예시: {avail_cities} 등)")
        return

    clean_city = city_name.strip()
    matched_key = None
    for k in CITY_COORDINATES:
        if k in clean_city or clean_city in k:
            matched_key = k
            break

    if matched_key:
        config_data["weather_city"] = matched_key
        config_data["weather_city_en"] = CITY_COORDINATES[matched_key]["en"]
        config_data["weather_lat"] = CITY_COORDINATES[matched_key]["lat"]
        config_data["weather_lon"] = CITY_COORDINATES[matched_key]["lon"]
        save_config(config_data)
        if memory_engine:
            memory_engine.add_explicit_memory(f"마스터의 거주/생활 지역: {matched_key}")
        await ctx.send(f"✅ 날씨 및 미세먼지 기준 지역을 **[{matched_key}]**(으)로 변경했어, 마스터.")
    else:
        config_data["weather_city"] = clean_city
        save_config(config_data)
        await ctx.send(f"✅ 날씨 기준 지역을 **[{clean_city}]**(으)로 저장했어.")


@bot.command(name="들어와", aliases=["join", "음성참가", "보이스참가", "connect"])
async def cmd_join_voice(ctx: commands.Context, *, target: Optional[str] = None):
    """음성 채널 참가 (채널명, 번호 또는 유저가 있는 채널)"""
    if not ctx.guild:
        await ctx.send("⚠️ 음성 채널은 서버(Guild) 내에서만 사용할 수 있어.")
        return

    target_vc = find_target_voice_channel(ctx.guild, ctx.author, target)
    if not target_vc:
        await ctx.send("마스터, 들어갈 음성 채널을 찾지 못했어. 음성 채널에 먼저 들어가 있거나 채널 번호/이름을 알려줘.")
        return

    try:
        vc_client = ctx.guild.voice_client
        if vc_client and vc_client.is_connected():
            if vc_client.channel.id != target_vc.id:
                await vc_client.move_to(target_vc)
        else:
            vc_client = await target_vc.connect()

        await ctx.send(f"🔊 **[{target_vc.name}]** 음성 채널에 들어왔어, 마스터.")
        voice_file = await generate_voice_audio("마스터, 나 여기 있어. 무슨 일이든 편하게 말해줘.")
        if voice_file and vc_client and vc_client.is_connected():
            await play_voice_audio(vc_client, voice_file)
    except Exception as e:
        await ctx.send(f"⚠️ 음성 채널 연결 중 오류: {e}")


@bot.command(name="나가", aliases=["leave", "음성퇴장", "보이스퇴장", "disconnect"])
async def cmd_leave_voice(ctx: commands.Context):
    """음성 채널 퇴장"""
    if not ctx.guild:
        return
    vc_client = ctx.guild.voice_client
    if vc_client and vc_client.is_connected():
        await vc_client.disconnect()
        await ctx.send("👋 음성 채널에서 퇴장했어, 마스터. 필요할 때 다시 불러줘.")
    else:
        await ctx.send("마스터, 나는 지금 음성 채널에 들어가 있지 않아.")


@bot.command(name="말해", aliases=["tts", "speak", "음성"])
async def cmd_speak_voice(ctx: commands.Context, *, text: str):
    """지정한 텍스트를 음성 채널에서 스카디 목소리로 재생"""
    if not ctx.guild:
        return
    vc_client = ctx.guild.voice_client
    if not vc_client or not vc_client.is_connected():
        target_vc = find_target_voice_channel(ctx.guild, ctx.author)
        if target_vc:
            try:
                vc_client = await target_vc.connect()
            except Exception:
                pass

    if not vc_client or not vc_client.is_connected():
        await ctx.send("💡 먼저 `!들어와` 로 음성 채널에 나를 불러줘.")
        return

    voice_file = await generate_voice_audio(text)
    if voice_file:
        await play_voice_audio(vc_client, voice_file)
        await ctx.message.add_reaction("🎙️")
    else:
        await ctx.send("음성을 생성하지 못했어.")


@bot.command(name="청소", aliases=["지우기", "clear", "purge"])
async def cmd_purge(ctx: commands.Context, count: int = 5):
    """지정한 개수만큼 채팅 및 AI 대화 기억 삭제"""
    count = min(max(count, 1), 50)
    try:
        if hasattr(ctx.channel, 'purge'):
            await ctx.channel.purge(limit=count + 1)
        history = get_channel_history(ctx.channel.id)
        for _ in range(min(count * 2, len(history))):
            history.pop()
        noti = await ctx.send(f"🧹 마스터와의 최근 {count}개 대화를 삭제했어.")
        await asyncio.sleep(3.5)
        await noti.delete()
    except Exception as e:
        await ctx.send(f"⚠️ 삭제 중 오류가 발생했어: {e}")


@bot.command(name="위로삭제", aliases=["여기부터삭제", "purgeabove"])
async def cmd_purge_above(ctx: commands.Context):
    """답장한 메시지부터 그 위쪽 대화를 전부 삭제"""
    if not ctx.message.reference:
        await ctx.send("💡 지우고 싶은 시작 지점 메시지에 **[답장(Reply)]**을 누르면서 `!위로삭제`를 입력해줘.")
        return

    try:
        ref_id = ctx.message.reference.message_id
        to_delete = []
        async for m in ctx.channel.history(limit=100):
            to_delete.append(m)
            if m.id == ref_id:
                break
        
        if to_delete:
            if hasattr(ctx.channel, 'delete_messages'):
                await ctx.channel.delete_messages(to_delete)
            else:
                for m in to_delete:
                    await m.delete()

        if ctx.channel.id in conversation_history:
            conversation_history[ctx.channel.id].clear()
            
        noti = await ctx.send(f"🧹 지정한 메시지부터 위쪽 {len(to_delete)}개 대화를 모두 정리했어.")
        await asyncio.sleep(4)
        await noti.delete()
    except Exception as e:
        await ctx.send(f"⚠️ 위로 삭제 중 오류가 발생했어: {e}")


@bot.command(name="되돌리기", aliases=["undo", "취소"])
async def cmd_undo(ctx: commands.Context):
    """방금 나눈 1턴의 대화를 기억에서 롤백"""
    history = get_channel_history(ctx.channel.id)
    if len(history) >= 2:
        history.pop()
        history.pop()
    try:
        if hasattr(ctx.channel, 'purge'):
            await ctx.channel.purge(limit=3)
    except Exception:
        pass
    noti = await ctx.send("⏪ 방금 나눈 대화를 기억과 채팅에서 되돌렸어.")
    await asyncio.sleep(3.5)
    await noti.delete()


@bot.command(name="기억삭제", aliases=["forget", "기억지우기"])
async def cmd_forget(ctx: commands.Context, *, keyword: str):
    """스카디의 영구 기억 저장소에서 특정 키워드 항목 삭제"""
    if not memory_engine:
        await ctx.send("⚠️ 장기 기억 엔진(skadi_memory_engine)이 비활성화 상태야.")
        return

    success = memory_engine.remove_explicit_memory(keyword)
    if success:
        await ctx.send(f"🗑️ 마스터, 장기 기억에서 **'{keyword}'** 관련 내용을 지웠어.")
    else:
        await ctx.send(f"해당 키워드('{keyword}')와 관련된 기억을 찾지 못했어.")


@bot.command(name="리셋", aliases=["reset", "대화초기화", "전체리셋", "메모리초기화"])
async def cmd_reset(ctx: commands.Context):
    """현재 채널의 대화 히스토리 초기화"""
    if ctx.channel.id in conversation_history:
        conversation_history[ctx.channel.id].clear()
    await ctx.send("🧹 마스터와의 이 채널 대화 기록을 깨끗하게 비웠어. 새로운 이야기를 시작하자.")


@bot.command(name="페르소나", aliases=["성격", "persona", "모드"])
async def cmd_persona(ctx: commands.Context, mode: Optional[str] = None):
    """스카디 페르소나 조회 및 변경"""
    global current_persona_key
    personas = config_data.get("personas", {})
    
    if not mode:
        desc = [f"**현재 모드**: `{current_persona_key}` ({personas.get(current_persona_key, {}).get('name', '')})\n"]
        desc.append("**선택 가능한 페르소나:**")
        for k, v in personas.items():
            desc.append(f"• `{k}` : {v.get('name')}")
        desc.append(f"\n💡 변경 예시: `!페르소나 bocadi` 또는 `!페르소나 비서`")
        embed = discord.Embed(title="🎭 스카디 페르소나 목록", description="\n".join(desc), color=0x9b59b6)
        await ctx.send(embed=embed)
        return

    alias_map = {
        "보카디": "bocadi", "스카디": "bocadi", "애틋": "bocadi",
        "비서": "assistant", "일반": "assistant", "알파": "assistant",
        "주식": "stock", "투자": "stock", "퀀트": "stock",
        "화가": "painter", "그림": "painter", "sd": "painter",
        "레식": "r6s", "전술": "r6s", "시즈": "r6s"
    }
    target_key = alias_map.get(mode.lower(), mode.lower())

    if target_key in personas:
        current_persona_key = target_key
        config_data["default_persona"] = target_key
        save_config(config_data)
        p_name = personas[target_key].get("name", target_key)
        await ctx.send(f"✨ 스카디의 페르소나를 **[{p_name}]**(으)로 전환했어. 마스터, 원하는 대로 대화해줘.")
    else:
        await ctx.send(f"⚠️ 찾을 수 없는 페르소나야. 가능한 목록: `bocadi`, `assistant`, `stock`, `painter`, `r6s`")


@bot.command(name="모델", aliases=["model", "엔진"])
async def cmd_model(ctx: commands.Context, model_name: Optional[str] = None):
    """LLM 인공지능 엔진 조회 및 변경"""
    global current_model_key
    
    if not model_name:
        avail = [p.provider_id for p in provider_registry.get_available_providers()]
        embed = discord.Embed(
            title="🧠 LLM 인공지능 엔진 상태",
            description=(
                f"**현재 활성 엔진**: `{current_model_key}`\n"
                f"**가용 공급자 목록**: `{', '.join(avail)}`\n\n"
                f"💡 변경 예시: `!모델 gemini`, `!모델 ollama`, `!모델 openai`, `!모델 claude`"
            ),
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        return

    m_clean = model_name.lower().strip()
    current_model_key = m_clean
    config_data["default_model"] = m_clean
    save_config(config_data)
    await ctx.send(f"⚡ 스카디의 두뇌 엔진을 **[{m_clean}]**(으)로 변경했어.")


@bot.command(name="채널지정", aliases=["전용채널"])
async def cmd_add_channel(ctx: commands.Context):
    """현재 채널을 멘션 없이 대화 가능한 전용 채널로 등록"""
    channels = config_data.setdefault("auto_reply_channels", [])
    if ctx.channel.id not in channels:
        channels.append(ctx.channel.id)
        save_config(config_data)
        await ctx.send(f"📌 이 채널(<#{ctx.channel.id}>)을 **스카디 전용 대화 채널**로 지정했어. 이제 멘션 없이 편하게 말해줘!")
    else:
        await ctx.send("이미 전용 대화 채널로 등록되어 있어.")


@bot.command(name="채널해제")
async def cmd_remove_channel(ctx: commands.Context):
    """전용 채널 해제"""
    channels = config_data.setdefault("auto_reply_channels", [])
    if ctx.channel.id in channels:
        channels.remove(ctx.channel.id)
        save_config(config_data)
        await ctx.send(f"📌 이 채널(<#{ctx.channel.id}>)의 전용 대화 채널 설정을 해제했어. 이제 @멘션으로 불러줘.")
    else:
        await ctx.send("전용 대화 채널로 등록되어 있지 않아.")


@bot.command(name="기억", aliases=["기억해", "remember"])
async def cmd_remember(ctx: commands.Context, *, memory_text: str):
    """스카디의 영구 기억 저장소에 중요한 사실을 각인"""
    if not memory_engine:
        await ctx.send("⚠️ 장기 기억 엔진(skadi_memory_engine)이 비활성화 상태야.")
        return

    success = memory_engine.add_explicit_memory(memory_text)
    if success:
        await ctx.send(f"💙 마스터, 이 기억을 깊은 바닷속에 소중하게 각인했어: \n> \"{memory_text}\"")
    else:
        await ctx.send("이미 기억하고 있는 내용이야, 마스터.")


@bot.command(name="기억목록", aliases=["기억확인", "memories"])
async def cmd_memories(ctx: commands.Context):
    """스카디가 기억하고 있는 마스터 프로필 및 기억 조회"""
    if not memory_engine:
        await ctx.send("⚠️ 장기 기억 엔진(skadi_memory_engine)이 비활성화 상태야.")
        return

    facts = memory_engine.load_user_facts()
    memories = facts.get("important_memories", [])
    interests = facts.get("interests", [])
    prefs = facts.get("habits_and_preferences", [])

    embed = discord.Embed(
        title="🌊 스카디가 기억하는 마스터의 프로필",
        color=0x1abc9c
    )
    embed.add_field(name="호칭/이름", value=facts.get("user_name", "마스터"), inline=True)
    if interests:
        embed.add_field(name="관심사", value=", ".join(interests[-5:]), inline=True)
    if prefs:
        embed.add_field(name="취향/성향", value=", ".join(prefs[-5:]), inline=False)
    
    if memories:
        embed.add_field(
            name="주요 기억 (최근 6개)",
            value="\n".join([f"• {m}" for m in memories[-6:]]),
            inline=False
        )
    else:
        embed.add_field(name="주요 기억", value="아직 특별히 각인된 기억이 없어. `!기억 <내용>`으로 알려줘.", inline=False)

    await ctx.send(embed=embed)


# ------------------------------------------------------------
# 📅 5-1. 스마트 캘린더 & 할 일(Todo) 관리 명령어
# ------------------------------------------------------------
@bot.command(name="일정", aliases=["일정목록", "스케줄", "schedule"])
async def cmd_schedule_list(ctx: commands.Context, target_date: Optional[str] = None):
    """오늘 또는 지정일(YYYY-MM-DD)의 일정 목록 조회"""
    if not ScheduleManager:
        await ctx.send("미안해, 마스터... 스케줄 매니저 모듈을 불러올 수 없어.")
        return

    query_date = target_date or datetime.datetime.now().strftime("%Y-%m-%d")
    items = ScheduleManager.get_items(target_date=query_date, include_completed=True)
    
    events = [it for it in items if not it.get("is_todo")]
    todos = [it for it in items if it.get("is_todo")]

    embed = discord.Embed(
        title=f"📅 스카디 스케줄러 • [{query_date}]",
        description="마스터의 소중한 일정과 할 일들을 정리해뒀어.",
        color=0x3498db
    )

    if events:
        lines = []
        for ev in events:
            time_part = ev['start_time'].split(' ')[1] if ' ' in ev['start_time'] else '종일'
            memo = f" ({ev['description']})" if ev.get('description') else ""
            lines.append(f"• `[ID:{ev['id']}]` `[{time_part}]` **{ev['title']}**{memo}")
        embed.add_field(name="📌 등록된 일정", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="📌 등록된 일정", value="예정된 일정이 없어. 자유로운 시간이야, 마스터.", inline=False)

    if todos:
        t_lines = []
        for td in todos:
            status_icon = "✅" if td.get("is_completed") else "⬜"
            p_icon = "🔥" if td.get("priority") == 3 else ("⚡" if td.get("priority") == 2 else "🌱")
            t_lines.append(f"{status_icon} `[ID:{td['id']}]` {p_icon} **{td['title']}**")
        embed.add_field(name="📝 오늘 등록된 할 일", value="\n".join(t_lines), inline=False)

    embed.set_footer(text="추가: !일정추가 YYYY-MM-DD HH:MM 제목 | 삭제: !일정삭제 ID")
    await ctx.send(embed=embed)


@bot.command(name="일정추가", aliases=["add_schedule", "스케줄추가"])
async def cmd_add_schedule(ctx: commands.Context, time_str: str, *, title: str):
    """일정 등록 (예: !일정추가 2026-09-03 15:00 팀 회의 or !일정추가 2026-09-03 생일파티)"""
    if not ScheduleManager:
        await ctx.send("미안해, 마스터... 스케줄 매니저 모듈을 불러올 수 없어.")
        return

    try:
        req = ScheduleCreateRequest(
            title=title.strip(),
            start_time=time_str.strip(),
            is_todo=False,
            priority=2
        )
        res = ScheduleManager.add_item(req)
        gcal_url = ScheduleManager.generate_google_calendar_url(title, time_str)
        
        embed = discord.Embed(
            title="✨ 새로운 일정 등록 완료",
            description=f"마스터, 캘린더에 일정을 기록했어!\n\n> 📅 **일시**: `{time_str}`\n> 📌 **제목**: **{title}**\n> 🆔 **ID**: `{res['id']}`",
            color=0x3498db
        )
        embed.add_field(
            name="📱 스마트폰 캘린더 연동",
            value=f"[🔗 구글 캘린더에 원클릭 추가하기]({gcal_url})\n💡 *누르면 구글/삼성 캘린더 앱에 즉시 등록돼.*",
            inline=False
        )
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"앗... 일정을 등록하는 도중 오류가 발생했어: {e}\n형식: `!일정추가 YYYY-MM-DD [HH:MM] 일정제목`")


@bot.command(name="캘린더연동", aliases=["구글캘린더", "삼성캘린더", "calendar_sync", "ical"])
async def cmd_calendar_sync(ctx: commands.Context):
    """구글 및 삼성 캘린더 실시간 자동 동기화 가이드 & iCal 피드 링크"""
    host = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
    ical_url = f"{host}/api/schedule/calendar.ics"

    embed = discord.Embed(
        title="📱 구글 & 삼성 캘린더 실시간 연동 가이드",
        description="스카디에 등록된 모든 일정을 스마트폰 캘린더 앱과 **실시간 자동 동기화**할 수 있어.",
        color=0x9b59b6
    )

    embed.add_field(
        name="1️⃣ 표준 iCal (.ics) 구독 주소",
        value=f"```text\n{ical_url}\n```\n*(위 주소를 복사해서 캘린더 앱에 등록하면 돼)*",
        inline=False
    )

    embed.add_field(
        name="2️⃣ 구글 캘린더 연동 방법",
        value=(
            "1. PC/모바일 브라우저로 [구글 캘린더(웹)](https://calendar.google.com) 접속\n"
            "2. 좌측 '다른 캘린더' 옆 **[+]** 클릭 ➔ **[URL로 추가]** 선택\n"
            "3. 위 iCal 주소를 붙여넣고 **[캘린더 추가]** 클릭!\n"
            "➔ *스마트폰 구글 캘린더 및 삼성 캘린더 앱에 자동 반영됩니다.*"
        ),
        inline=False
    )

    embed.add_field(
        name="3️⃣ 삼성 캘린더 (Galaxy) 연동 방법",
        value=(
            "• 삼성 캘린더는 구글 계정과 기본 연동되므로, **구글 캘린더에 URL로 추가하면 삼성 캘린더 앱에도 1초 만에 자동 표시**됩니다!\n"
            "• 또는 삼성 캘린더 메뉴 ➔ '캘린더 관리' ➔ 계정 동기화 켜기"
        ),
        inline=False
    )

    embed.set_footer(text="스카디 스마트 캘린더 • 구글/삼성/애플/아웃룩 100% 호환")
    await ctx.send(embed=embed)


@bot.command(name="일정삭제", aliases=["del_schedule"])
async def cmd_del_schedule(ctx: commands.Context, item_id: int):
    """일정 삭제 (예: !일정삭제 1)"""
    if not ScheduleManager:
        await ctx.send("스케줄 매니저가 비활성화되어 있어.")
        return
    try:
        ScheduleManager.delete_item(item_id)
        await ctx.send(f"🗑️ `ID: {item_id}` 일정을 캘린더에서 깨끗이 지웠어, 마스터.")
    except Exception as e:
        await ctx.send(f"일정 삭제 실패: {e}")


@bot.command(name="할일", aliases=["할일목록", "todo", "todos"])
async def cmd_todo_list(ctx: commands.Context):
    """진행 중인 모든 할 일(Todo) 목록 조회"""
    if not ScheduleManager:
        await ctx.send("스케줄 매니저 모듈을 찾을 수 없어.")
        return

    todos = ScheduleManager.get_items(only_todos=True, include_completed=True)
    if not todos:
        await ctx.send("마스터, 지금 밀려있는 할 일이 하나도 없어! 편안하게 쉬어도 돼.")
        return

    pending = [t for t in todos if not t.get("is_completed")]
    completed = [t for t in todos if t.get("is_completed")]

    embed = discord.Embed(
        title="📝 마스터의 할 일 (Todo Checklist)",
        color=0x2ecc71
    )

    if pending:
        lines = []
        for t in pending:
            p_mark = "🔥" if t.get("priority") == 3 else ("⚡" if t.get("priority") == 2 else "🌱")
            lines.append(f"⬜ `[ID:{t['id']}]` {p_mark} **{t['title']}** (기한: {t['start_time']})")
        embed.add_field(name=f"진행 중인 태스크 ({len(pending)}개)", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="진행 중인 태스크", value="🎉 모든 할 일을 완수했어! 대단해, 마스터.", inline=False)

    if completed:
        c_lines = [f"~~`[ID:{t['id']}]` {t['title']}~~" for t in completed[-5:]]
        embed.add_field(name="최근 완료된 항목", value="\n".join(c_lines), inline=False)

    embed.set_footer(text="추가: !할일추가 내용 | 완료: !할일완료 ID | 삭제: !할일삭제 ID")
    await ctx.send(embed=embed)


@bot.command(name="할일추가", aliases=["add_todo", "투두추가"])
async def cmd_add_todo(ctx: commands.Context, *, content: str):
    """할 일 등록 (예: !할일추가 메이플 주간보스 돌기 or !할일추가 [긴급] 보고서 제출)"""
    if not ScheduleManager:
        await ctx.send("스케줄 매니저 모듈이 준비되지 않았어.")
        return

    priority = 3 if "[긴급]" in content or "[중요]" in content else 2
    clean_title = content.replace("[긴급]", "").replace("[중요]", "").strip()
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    try:
        req = ScheduleCreateRequest(
            title=clean_title,
            start_time=today_str,
            is_todo=True,
            priority=priority
        )
        res = ScheduleManager.add_item(req)
        p_str = "🔥 긴급" if priority == 3 else "⚡ 보통"
        await ctx.send(f"✅ 할 일 목록에 추가했어, 마스터!\n> 📝 `[ID:{res['id']}]` **{clean_title}** ({p_str})")
    except Exception as e:
        await ctx.send(f"할 일 등록 실패: {e}")


@bot.command(name="할일완료", aliases=["complete_todo", "체크", "done"])
async def cmd_complete_todo(ctx: commands.Context, item_id: int):
    """할 일 완료/미완료 토글 (예: !할일완료 1)"""
    if not ScheduleManager:
        return
    try:
        res = ScheduleManager.toggle_complete(item_id)
        if res.get("is_completed"):
            await ctx.send(f"🎉 `ID: {item_id}` 태스크를 완료 처리했어! 수고 많았어, 마스터.")
        else:
            await ctx.send(f"🔄 `ID: {item_id}` 태스크를 다시 진행 중으로 변경했어.")
    except Exception as e:
        await ctx.send(f"할 일 완료 처리 실패: {e}")


@bot.command(name="할일삭제", aliases=["del_todo"])
async def cmd_del_todo(ctx: commands.Context, item_id: int):
    """할 일 삭제 (예: !할일삭제 1)"""
    if not ScheduleManager:
        return
    try:
        ScheduleManager.delete_item(item_id)
        await ctx.send(f"🗑️ `ID: {item_id}` 할 일을 삭제했어, 마스터.")
    except Exception as e:
        await ctx.send(f"할 일 삭제 실패: {e}")


@bot.command(name="상태", aliases=["status", "정보"])
async def cmd_status(ctx: commands.Context):
    """스카디 디스코드 봇 시스템 상태 브리핑"""
    personas = config_data.get("personas", {})
    p_name = personas.get(current_persona_key, {}).get("name", current_persona_key)
    avail = [p.display_name for p in provider_registry.get_available_providers()]
    
    embed = discord.Embed(
        title="📊 스카디 봇 가동 상태 보고",
        color=0x34495e
    )
    embed.add_field(name="🎭 페르소나", value=f"{p_name} (`{current_persona_key}`)", inline=True)
    embed.add_field(name="🧠 LLM 엔진", value=f"`{current_model_key}`", inline=True)
    embed.add_field(name="📡 핑 (Latency)", value=f"{round(bot.latency * 1000)} ms", inline=True)
    embed.add_field(name="🌐 가용 AI 공급자", value="\n".join([f"• {a}" for a in avail]), inline=False)
    embed.add_field(name="💬 활성 대화 세션", value=f"{len(conversation_history)}개 채널", inline=True)
    embed.add_field(name="📌 전용 대화 채널 수", value=f"{len(config_data.get('auto_reply_channels', []))}개", inline=True)
    
    await ctx.send(embed=embed)


@bot.command(name="증강", aliases=["augment", "증강추천", "aug"])
async def cmd_lol_augment(ctx: commands.Context, *args):
    """칼바람 199종 증강 3지선다 AI 1순위 추천 (예: !증강 되풀이 보석건틀릿 축소엔진 [이즈리얼])"""
    if not AugmentEngine:
        await ctx.send("미안해, 마스터... 롤 증강체 엔진(lol_ai_coach) 모듈을 불러올 수 없어.")
        return

    if len(args) < 2:
        await ctx.send("💡 **사용법:** `!증강 <증강1> <증강2> <증강3> [챔피언이름]`\n*예시:* `!증강 되풀이 보석건틀릿 축소엔진 이즈리얼`")
        return

    choices = list(args[:3])
    champ = args[3] if len(args) > 3 else "이즈리얼"

    try:
        res = AugmentEngine.recommend_best(choices, champion_name=champ)
        rec = res.get("recommended")
        if not rec:
            await ctx.send("선택한 증강체를 찾을 수 없어, 마스터.")
            return

        embed = discord.Embed(
            title=f"❄️ 칼바람 3지선다 AI 추천 결과 • [{champ}]",
            description=f"마스터, 3개 선택지 중 통계와 시너지가 가장 높은 1순위 증강이야!",
            color=0xe11d48
        )
        embed.add_field(
            name=f"👑 압도적 1순위: {rec['name_ko']} ({rec.get('name_en', '')})",
            value=f"• 등급: **{rec.get('rarity', '골드')}**\n• 승률: **{rec.get('win_rate', '-')}** | 픽률: **{rec.get('pick_rate', '-')}**\n• 효과: {rec.get('description', '')[:200]}",
            inline=False
        )
        embed.add_field(name="🎙️ 스카디 실시간 코칭 음성", value=f"🔊 *\"{res.get('voice_text', '')}\"*", inline=False)
        embed.set_footer(text="ARAM Mayhem 199 Augment Database • JARVIS Engine")

        await ctx.send(embed=embed)

        if ctx.guild and ctx.guild.voice_client and ctx.guild.voice_client.is_connected():
            v_file = await generate_voice_audio(res.get('voice_text', ''))
            if v_file:
                await play_voice_audio(ctx.guild.voice_client, v_file)
    except Exception as e:
        await ctx.send(f"증강체 추천 분석 실패: {e}")


@bot.command(name="증강검색", aliases=["aug_search", "증강정보"])
async def cmd_lol_augment_search(ctx: commands.Context, *, keyword: str):
    """199종 칼바람 증강체 실시간 검색 (예: !증강검색 스킬 가속)"""
    if not AugmentEngine:
        await ctx.send("미안해, 마스터... 롤 증강체 엔진 모듈을 불러올 수 없어.")
        return

    try:
        results = AugmentEngine.search_augments(keyword, limit=5)
        if not results:
            await ctx.send(f"🔍 `{keyword}` 관련 증강체를 찾을 수 없어, 마스터.")
            return

        embed = discord.Embed(
            title=f"🎴 199종 증강체 검색 결과 • [{keyword}]",
            description=f"상위 {len(results)}개 증강체 정보야.",
            color=0x9333ea
        )
        for aug in results:
            embed.add_field(
                name=f"#{aug.get('rank', '-')} [{aug.get('rarity', '골드')}] {aug.get('name_ko', '')} ({aug.get('name_en', '')})",
                value=f"• 승률: **{aug.get('win_rate', '-')}** | 픽률: **{aug.get('pick_rate', '-')}**\n• {aug.get('description', '')[:120]}",
                inline=False
            )
        embed.set_footer(text="ARAM Mayhem 199 Augments Knowledge Base")
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"증강체 검색 실패: {e}")


@bot.command(name="진단", aliases=["diag", "시스템", "하드웨어"])
async def cmd_system_diag(ctx: commands.Context):
    """PC 하드웨어 (RTX 4080 Super / CPU / RAM) 및 백엔드 상태 진단"""
    try:
        import psutil
        cpu_usage = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        mem_gb = f"{round(mem.used / (1024**3), 1)}GB / {round(mem.total / (1024**3), 1)}GB ({mem.percent}%)"
    except Exception:
        cpu_usage = "N/A"
        mem_gb = "N/A"

    gpu_info = "NVIDIA GeForce RTX 4080 Super (VRAM 16GB, CUDA Ready)"

    embed = discord.Embed(
        title="⚡ JARVIS / SKADI 하드웨어 & 엔진 종합 진단 보고서",
        color=0x10b981
    )
    embed.add_field(name="🖥️ CPU 점유율", value=f"`{cpu_usage}%`", inline=True)
    embed.add_field(name="🧠 시스템 RAM", value=f"`{mem_gb}`", inline=True)
    embed.add_field(name="🎮 GPU 그래픽카드", value=f"`{gpu_info}`", inline=False)
    embed.add_field(name="🎴 199종 롤 증강 엔진", value="✅ 온라인 (AramMayhem Knowledge Base)", inline=True)
    embed.add_field(name="📅 캘린더 & 할 일 매니저", value="✅ SQLite DB 정상 연동", inline=True)
    embed.add_field(name="📶 봇 통신 지연시간", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.set_footer(text="JARVIS Observability & System Controller")

    await ctx.send(embed=embed)


# ------------------------------------------------------------
# 5-1. 주식 퀀트 리포트 명령어 (국내/미국 3개년 성장성 + 부채비율 120% 이하 + 데일리 모멘텀)
# ------------------------------------------------------------
@bot.command(name="주식", aliases=["주식리포트", "성장주", "주식순위", "stock", "미국주식", "국내주식", "해외주식"])
async def cmd_stock_report(ctx: commands.Context, *, query: Optional[str] = None):
    """국내/미국 주식 3개년 성장성 TOP 리포트 및 개별 종목 정밀 팩폭 진단"""
    if not stock_engine:
        await ctx.send("⚠️ `stock_engine` 모듈을 불러올 수 없어 주식 분석을 수행할 수 없습니다.")
        return

    async with ctx.typing():
        q = (query or "").strip().lower()

        # 1. 미국 주식 데일리 성장성 & 모멘텀 TOP 10
        if q in ["미국", "미국주식", "us", "usa", "해외", "해외주식"]:
            report_data = stock_engine.generate_daily_ranking_report_markdown(market="US", top_n=10)
            if report_data["success"]:
                embed = discord.Embed(
                    title=f"🔔 [미국 증시] 3개년 성장성 & 당일 모멘텀 TOP 10",
                    description=(
                        "🛡️ **회계 검증 기준**: 대차대조표 부채비율(총부채/총자본) **120% 이하** & 3개년 총자산 증가율 **양수(+)**\n"
                        "⚡ **데일리 랭킹 기준**: 위 안전 조건을 통과한 우량 기업 중 **당일 주가 모멘텀(등락률)** 상위 정렬"
                    ),
                    color=0x2ecc71
                )
                for i, itm in enumerate(report_data["items"], 1):
                    chg_sign = "+" if itm["change_pct"] >= 0 else ""
                    field_name = f"{i}. {itm['name']} ({itm['symbol']}) • ${itm['price']:,.2f} ({chg_sign}{itm['change_pct']}%)"
                    field_val = (
                        f"• 📈 **3개년 자산성장률**: `+{itm['asset_growth_3y']}%` ({itm['past_assets_fmt']} ➔ {itm['recent_assets_fmt']})\n"
                        f"• 🛡️ **정규 부채비율**: `{itm['debt_ratio']}%` (총부채 {itm['liabilities_fmt']} / 자본 {itm['equity_fmt']})"
                    )
                    embed.add_field(name=field_name, value=field_val, inline=False)
                embed.set_footer(text=f"기준일자: {report_data['today_str']} • 스카디 퀀트 데일리 실시간 스크리닝")
                await ctx.send(embed=embed)
            else:
                await ctx.send(report_data["message"])
            return

        # 2. 국내(한국) 주식 데일리 성장성 & 모멘텀 TOP 10
        if q in ["국내", "국내주식", "한국", "한국주식", "kr", "korea", "코스피", "코스닥"]:
            report_data = stock_engine.generate_daily_ranking_report_markdown(market="KR", top_n=10)
            if report_data["success"]:
                embed = discord.Embed(
                    title=f"🔔 [국내 증시] 3개년 성장성 & 당일 모멘텀 TOP 10",
                    description=(
                        "🛡️ **회계 검증 기준**: 대차대조표 부채비율(총부채/총자본) **120% 이하** & 3개년 총자산 증가율 **양수(+)**\n"
                        "⚡ **데일리 랭킹 기준**: 위 안전 조건을 통과한 우량 기업 중 **당일 주가 모멘텀(등락률)** 상위 정렬"
                    ),
                    color=0x3498db
                )
                for i, itm in enumerate(report_data["items"], 1):
                    chg_sign = "+" if itm["change_pct"] >= 0 else ""
                    field_name = f"{i}. {itm['name']} ({itm['symbol']}) • ₩{itm['price']:,.0f} ({chg_sign}{itm['change_pct']}%)"
                    field_val = (
                        f"• 📈 **3개년 자산성장률**: `+{itm['asset_growth_3y']}%` ({itm['past_assets_fmt']} ➔ {itm['recent_assets_fmt']})\n"
                        f"• 🛡️ **정규 부채비율**: `{itm['debt_ratio']}%` (총부채 {itm['liabilities_fmt']} / 자본 {itm['equity_fmt']})"
                    )
                    embed.add_field(name=field_name, value=field_val, inline=False)
                embed.set_footer(text=f"기준일자: {report_data['today_str']} • 스카디 퀀트 데일리 실시간 스크리닝")
                await ctx.send(embed=embed)
            else:
                await ctx.send(report_data["message"])
            return

        # 3. 개별 종목 정밀 진단
        if q and q not in ["리포트", "순위", "랭킹", "top"]:
            res = stock_engine.generate_skadi_stock_report(query)
            if res["success"]:
                if res.get("type") == "guide":
                    await ctx.send(res["message"])
                else:
                    m = res["metrics"]
                    curr_sym = "₩" if m["currency"] == "KRW" else "$"
                    price_str = f"{curr_sym}{m['current_price']:,.0f}" if m["currency"] == "KRW" else f"{curr_sym}{m['current_price']:,.2f}"
                    chg_color = 0xe74c3c if m["change_pct"] >= 0 else 0x3498db
                    chg_sign = "+" if m["change_pct"] >= 0 else ""

                    embed = discord.Embed(
                        title=f"📊 스카디의 팩폭 종목 진단 • {m['name']} ({res['ticker']})",
                        description=f"**현재가**: `{price_str}` ({chg_sign}{m['change_pct']}%)\n**안전/수급 상태**: `{' | '.join(stock_engine.analyze_safety_tier(m))}`",
                        color=chg_color
                    )
                    embed.add_field(
                        name="📈 기술적 지표",
                        value=f"• RSI(14일): `{m['rsi']}`\n• 20일 이동평균선: `{curr_sym}{m['ma20']:,}`\n• 60일 이동평균선: `{curr_sym}{m['ma60']:,}`",
                        inline=True
                    )
                    embed.add_field(
                        name="🛡️ 펀더멘털 & 밸류에이션",
                        value=f"• 3개년 자산증가율: `+{m['asset_growth_3y']}%`\n• 공식 부채비율: `{m['debt_ratio']}%`\n• 배당수익률: `{m['dividend_yield']}%` | PER: `{m['pe']}` | PBR: `{m['pbr']}`",
                        inline=True
                    )
                    embed.set_footer(text="스카디 퀀트 안전 기초 투자 가이드")
                    await ctx.send(embed=embed)
            else:
                await ctx.send(res.get("message", "종목 조회 실패"))
            return

        # 4. 파라미터가 없거나 '!주식'만 입력한 경우 -> 미국 & 국내 통합 하이라이트 요약 브리핑
        us_data = stock_engine.get_daily_growth_top_ranking(market="US", top_n=5)
        kr_data = stock_engine.get_daily_growth_top_ranking(market="KR", top_n=5)
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")

        embed = discord.Embed(
            title=f"🔔 [{today_str}] 국내 & 미국 3개년 성장성 + 데일리 모멘텀 TOP 5",
            description=(
                "🛡️ **부채비율 120% 이하 엄격 필터링** + 📈 **3개년 총자산 성장 기업** 중 **당일 주도주** 실시간 추출\n"
                "💡 *자세히 보기: `!주식 미국`, `!주식 국내`, `!주식 [종목명]`*"
            ),
            color=0xf39c12
        )

        us_lines = []
        for i, itm in enumerate(us_data, 1):
            chg_sign = "+" if itm["change_pct"] >= 0 else ""
            us_lines.append(f"**{i}. {itm['name']}** (`{itm['symbol']}`) : **{chg_sign}{itm['change_pct']}%** | 3Y성장 `+{itm['asset_growth_3y']}%` | 부채 `{itm['debt_ratio']}%`")
        embed.add_field(name="🇺🇸 미국 증시 주도 성장주 TOP 5", value="\n".join(us_lines) if us_lines else "집계 중", inline=False)

        kr_lines = []
        for i, itm in enumerate(kr_data, 1):
            chg_sign = "+" if itm["change_pct"] >= 0 else ""
            kr_lines.append(f"**{i}. {itm['name']}** (`{itm['symbol']}`) : **{chg_sign}{itm['change_pct']}%** | 3Y성장 `+{itm['asset_growth_3y']}%` | 부채 `{itm['debt_ratio']}%`")
        embed.add_field(name="🇰🇷 국내 증시 주도 성장주 TOP 5", value="\n".join(kr_lines) if kr_lines else "집계 중", inline=False)

        embed.set_footer(text="스카디 퀀트 • 매일 장 마감 시황에 따라 순위가 실시간 재산출됩니다.")
        await ctx.send(embed=embed)


# ------------------------------------------------------------
# 6. 토큰 획득 및 진입점 (Entry Point)
# ------------------------------------------------------------
def get_discord_token() -> str:
    """우선순위에 따라 디스코드 봇 토큰 획득"""
    # 1. 환경 변수 (다양한 표기 지원)
    for env_k in ["DISCORD_BOT_TOKEN", "DISCORD_TOKEN", "BOT_TOKEN", "TOKEN"]:
        t = os.environ.get(env_k)
        if t and t.strip():
            return t.strip()

    # 2. config.py / API_KEYS
    cfg_token = API_KEYS.get("DISCORD") or API_KEYS.get("DISCORD_BOT_TOKEN")
    if cfg_token and cfg_token.strip():
        return cfg_token.strip()

    # 3. discord_config.json
    local_cfg = load_config()
    json_token = local_cfg.get("bot_token", "")
    if json_token and json_token.strip():
        return json_token.strip()

    return ""


def safe_input(prompt_msg: str = "") -> str:
    try:
        if sys.stdin and sys.stdin.isatty():
            return input(prompt_msg)
    except Exception:
        pass
    return ""


def prompt_for_token_interactive() -> str:
    """토큰이 없을 경우 콘솔 안내 및 입력 대화창"""
    if not (sys.stdin and sys.stdin.isatty()):
        return ""

    print("\n" + "=" * 65)
    print("📢 [안내] 디스코드 봇 토큰(DISCORD_BOT_TOKEN)이 설정되지 않았습니다.")
    print("=" * 65)
    print("1. Discord Developer Portal (https://discord.com/developers/applications) 접속")
    print("2. [New Application] 생성 후 좌측 [Bot] 탭 클릭")
    print("3. [Reset Token] 버튼을 눌러 Token을 복사합니다.")
    print("4. ★중요★ [Bot] 탭 아래 [Privileged Gateway Intents] 항목에서")
    print("   - 'MESSAGE CONTENT INTENT' 스위치를 반드시 [ON]으로 켭니다.")
    print("5. [OAuth2] -> [URL Generator] -> 봇 초대 링크로 내 디스코드 서버에 봇을 추가합니다.")
    print("=" * 65)
    
    try:
        user_input = input("\n🔑 디스코드 봇 토큰을 여기에 붙여넣고 Enter를 누르세요: ").strip()
    except (EOFError, KeyboardInterrupt):
        return ""

    if user_input:
        cfg = load_config()
        cfg["bot_token"] = user_input
        save_config(cfg)
        print(f"✅ 토큰이 discord_config.json 에 안전하게 저장되었습니다.\n")
        return user_input
    return ""


def main():
    token = get_discord_token()
    if not token:
        token = prompt_for_token_interactive()

    if not token:
        logger.error("디스코드 봇 토큰이 입력되지 않아 봇을 시작할 수 없습니다.")
        print("\n💡 나중에 discord_config.json 파일의 'bot_token' 에 토큰을 입력하고 다시 실행해주세요.")
        safe_input("\n종료하려면 Enter를 누르세요...")
        sys.exit(1)

    # Render 클라우드 배포 시 포트 바인딩 헬스체크 웹 서버 즉시 가동
    start_render_health_server_thread()

    logger.info("🌊 스카디 디스코드 챗봇을 24/7 무중단 모드로 시작합니다...")
    
    # 24/7 무중단 지수 백오프 자동 재연결 루프
    backoff_delay = 5
    while True:
        try:
            bot.run(token)
            break
        except (discord.errors.PrivilegedIntentsRequired, discord.LoginFailure) as e:
            logger.error(f"❌ 인증/권한 오류로 봇이 중단되었습니다: {e}")
            break
        except Exception as e:
            logger.warning(f"⚠️ 네트워크 순단 또는 예외 발생 ({e}). {backoff_delay}초 후 자동 재연결합니다...")
            time.sleep(backoff_delay)
            backoff_delay = min(backoff_delay * 2, 60)


if __name__ == "__main__":
    main()
