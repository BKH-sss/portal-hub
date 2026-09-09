"""
discord_lol_bot.py
-----------------------------------------------------------------------------
🏆 LoL(리그 오브 레전드) 전용 인텔리전스 & 전적/빌드/사후 복기 디스코드 봇 (Bot B)
-----------------------------------------------------------------------------
주요 기능:
1. 🛡️ 라이엇 서드파티 개발자 정책(Riot Third-Party Developer Guidelines) 100% 준수
2. 🗡️ !빌드 [챔피언] - 173개 전 챔피언 1~3코어 아이템, 시작템, 신발, 룬 통계 브리핑
3. 🎓 !스킬트리 [챔피언] - 스킬 마스터 순서(Q>E>W) 및 1~18 레벨링 트리 안내
4. 🎴 !증강체티어 [챔피언] [증강1, 증강2, 증강3] - 칼바람 아수라장 3지선다 시너지 티어 평가
5. 📋 !로딩화면 [소환사명#태그] - Spectator-V5 기반 10명 소환사 티어/전적/조합 브리핑
6. ❄️ !칼바람유물 [소환사명#태그] - 90초 결정론적 힐팩 리젠 카운트다운 타이머
7. 📜 !경기리뷰 [소환사명#태그] - 경기 종료 후(Post-Match) Match-V5 기반 데스/귀환/시야/CS 사후 오답노트
8. 📊 !전적 [소환사명#태그] - 솔로랭크 티어, 최근 5게임 승률, KDA, 모스트 챔피언 요약
9. 🌐 Render 클라우드 24/7 포트 바인딩 헬스체크 웹 서버 내장
-----------------------------------------------------------------------------
"""

import os
import re
import sys
import json
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import discord
from discord.ext import commands, tasks

# ---------------------------------------------------------------------------
# 1. 환경 및 경로 설정
# ---------------------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

for p in [str(CURRENT_DIR), str(PROJECT_ROOT), os.getcwd()]:
    if p not in sys.path:
        sys.path.insert(0, p)

CONFIG_FILE = CURRENT_DIR / "discord_lol_config.json"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [LoLBot] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("LoLDiscordBot")

# 프로젝트 설정 및 API 키 로드
try:
    from config import API_KEYS, RIOT_API_KEY
except ImportError:
    API_KEYS = {
        "DISCORD_LOL": os.environ.get("LOL_BOT_TOKEN", os.environ.get("DISCORD_BOT_TOKEN_LOL", "")),
        "DISCORD": os.environ.get("DISCORD_BOT_TOKEN", ""),
        "RIOT": os.environ.get("RIOT_API_KEY", "")
    }
    RIOT_API_KEY = os.environ.get("RIOT_API_KEY", "")

# LoL 원격 통계 및 사후 복기 엔진 임포트
try:
    from modules.lol_stats_engine import (
        RiotApiClient, LoLStatsCache, ChampionBuildEngine,
        LoadingScreenEngine, AramRelicTimerEngine, PostGameReviewEngine,
        CHAMPION_ID_TO_NAME, CHAMPION_ALIASES
    )
except ImportError:
    try:
        from lol_stats_engine import (
            RiotApiClient, LoLStatsCache, ChampionBuildEngine,
            LoadingScreenEngine, AramRelicTimerEngine, PostGameReviewEngine,
            CHAMPION_ID_TO_NAME, CHAMPION_ALIASES
        )
    except ImportError as e:
        logger.error(f"lol_stats_engine 모듈 로드 실패: {e}")
        sys.exit(1)

# 증강체 엔진 임포트
try:
    from modules.lol_ai_coach import AugmentEngine
except ImportError:
    try:
        from lol_ai_coach import AugmentEngine
    except ImportError:
        AugmentEngine = None
        logger.warning("lol_ai_coach.AugmentEngine 모듈을 찾을 수 없어 기본 증강체 모드로 동작합니다.")

# ---------------------------------------------------------------------------
# 2. 설정 파일 로드 및 관리
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "bot_token": "",
    "command_prefix": "!",
    "riot_api_key": "",
    "master_discord_id": "",
    "auto_reply_channels": [],
    "enable_natural_language_routing": True
}


def load_config() -> Dict[str, Any]:
    """설정 파일 로드"""
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            return data
    except Exception as e:
        logger.error(f"LoL 봇 설정 파일 읽기 오류: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(cfg: Dict[str, Any]):
    """설정 파일 저장"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"LoL 봇 설정 파일 저장 오류: {e}")


config_data = load_config()


def get_discord_token() -> str:
    """LoL 봇 토큰 우선순위 획득"""
    # 1. LoL 전용 환경 변수 우선
    for env_k in ["LOL_BOT_TOKEN", "DISCORD_BOT_TOKEN_LOL", "DISCORD_LOL_TOKEN", "DISCORD_BOT_TOKEN", "BOT_TOKEN", "TOKEN"]:
        t = os.environ.get(env_k)
        if t and t.strip():
            return t.strip()

    # 2. config.py / API_KEYS
    cfg_token = API_KEYS.get("DISCORD_LOL") or API_KEYS.get("DISCORD")
    if cfg_token and cfg_token.strip():
        return cfg_token.strip()

    # 3. discord_lol_config.json
    local_cfg = load_config()
    json_token = local_cfg.get("bot_token", "")
    if json_token and json_token.strip():
        return json_token.strip()

    return ""


def get_master_id() -> Optional[int]:
    """마스터 Discord 유저 ID 조회"""
    env_id = os.environ.get("MASTER_DISCORD_ID") or os.environ.get("MASTER_ID")
    if env_id:
        try:
            return int(env_id.strip())
        except ValueError:
            pass
    cfg_id = config_data.get("master_discord_id")
    if cfg_id:
        try:
            return int(str(cfg_id).strip())
        except ValueError:
            pass
    return None


def is_master(user_id: int) -> bool:
    """마스터 권한 여부 확인"""
    m_id = get_master_id()
    if m_id is None:
        return True  # 설정되지 않은 경우 허용
    return user_id == m_id


# ---------------------------------------------------------------------------
# 3. Render 포트 바인딩 헬스체크 웹 서버
# ---------------------------------------------------------------------------
def start_render_health_server_thread():
    """Render Web Service 포트 바인딩 헬스체크 서버 (무료 티어 절전 방지)"""
    port_str = os.environ.get("LOL_PORT") or os.environ.get("PORT")
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
                self.wfile.write("🏆 League of Legends Companion Bot is Healthy & Online 24/7!".encode('utf-8'))

            def log_message(self, format, *args):
                pass

        def _serve():
            try:
                server = HTTPServer(('0.0.0.0', port), HealthHandler)
                logger.info(f"🌐 Render 헬스체크 웹 서버 가동 완료 (Port: {port})")
                server.serve_forever()
            except Exception as e:
                logger.warning(f"Render 헬스체크 서버 오류: {e}")

        th = threading.Thread(target=_serve, daemon=True)
        th.start()
    except Exception as e:
        logger.warning(f"Render 헬스체크 서버 시작 실패: {e}")


# ---------------------------------------------------------------------------
# 4. 디스코드 봇 클라이언트 초기화
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(
    command_prefix=config_data.get("command_prefix", "!"),
    intents=intents,
    help_command=None
)


@bot.event
async def on_ready():
    logger.info("=" * 60)
    logger.info(f"🏆 LoL 컴패니언 봇 로그인 성공: {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"⚙️ 명령어 접두사: {bot.command_prefix}")
    logger.info(f"🌐 참여 서버 수: {len(bot.guilds)}개")
    logger.info("=" * 60)

    # 챔피언 가이드 데이터 사전 로드
    ChampionBuildEngine.load()
    if AugmentEngine:
        AugmentEngine.load_data()

    # 봇 상태 메시지 설정
    activity = discord.Activity(type=discord.ActivityType.watching, name="소환사의 협곡 & 칼바람 나락 (!도움말)")
    await bot.change_presence(status=discord.Status.online, activity=activity)


# ---------------------------------------------------------------------------
# 5. 디스코드 명령어 핸들러 (8개 공인 명령어)
# ---------------------------------------------------------------------------

@bot.command(name="도움말", aliases=["help", "명령어", "lol"])
async def cmd_help(ctx: commands.Context):
    """LoL 봇 전체 명령어 목록 안내"""
    embed = discord.Embed(
        title="🏆 리그 오브 레전드 인텔리전스 봇 명령어 안내",
        description=(
            "라이엇 서드파티 개발자 정책을 100% 준수하는 **롤 전적, 아이템 빌드, 칼바람 증강체, 사후 복기 전문 봇**입니다.\n"
            "접두사 `!`를 붙여 명령어를 실행하거나 자연어로 질문할 수 있습니다."
        ),
        color=0x00b4d8
    )

    embed.add_field(
        name="🗡️ `!빌드 [챔피언명]`",
        value="173개 전 챔피언 1~3코어 추천 아이템, 시작 아이템, 추천 신발, 룬, 라인전 팁을 안내합니다.\n*예: `!빌드 그레이브즈`, `!빌드 이즈리얼`*",
        inline=False
    )
    embed.add_field(
        name="🎓 `!스킬트리 [챔피언명]`",
        value="스킬 마스터 순서(Q>E>W)와 1~18레벨 정규 스킬 레벨링 트리, 파워스파이크를 안내합니다.\n*예: `!스킬트리 사일러스`, `!스킬 아리`*",
        inline=False
    )
    embed.add_field(
        name="🎴 `!증강체티어 [챔피언] [증강1, 증강2, 증강3]`",
        value="칼바람 아수라장 3지선다 카드별 시너지 점수와 티어(👑OP / 🔮S / 🥇A / 🥈B / 🥉C) 및 1순위 추천을 브리핑합니다.\n*예: `!증강체티어 다리우스 갈라진하늘,신성한중재,무력파편`*",
        inline=False
    )
    embed.add_field(
        name="📊 `!전적 [소환사명#태그]`",
        value="소환사의 솔로랭크 티어, 최근 5게임 승률, KDA, 평균 킬/데스, 모스트 챔피언을 조회합니다.\n*예: `!전적 Hide on bush#KR1`*",
        inline=False
    )
    embed.add_field(
        name="📋 `!로딩화면 [소환사명#태그]`",
        value="현재 진행 중인 실시간 게임(Spectator-V5) 양 팀 10명의 티어, 최근 전적, 스펠, 챔피언 정보를 브리핑합니다.\n*예: `!로딩화면 소환사#KR1`*",
        inline=False
    )
    embed.add_field(
        name="❄️ `!칼바람유물 [소환사명#태그]`",
        value="칼바람 나락 회복 유물(Health Relics)의 90초 결정론적 리젠 카운트다운 타이머를 계산합니다.\n*예: `!칼바람유물 소환사#KR1`*",
        inline=False
    )
    embed.add_field(
        name="📜 `!경기리뷰 [소환사명#태그]`",
        value=(
            "최근 종료된 게임의 Match-V5 상세 데이터를 분석하여 데스 관리/귀환 타이밍/시야/CS 사후 오답노트를 코칭합니다.\n"
            "*(※ 공정성 정책 준수를 위해 실시간 게임 중에는 실행되지 않으며 경기 종료 후에만 분석됩니다)*\n"
            "*예: `!경기리뷰 소환사#KR1`*"
        ),
        inline=False
    )

    embed.set_footer(text="LoL Intelligence Bot • Riot Games Third-Party Policy Compliant")
    await ctx.send(embed=embed)


@bot.command(name="빌드", aliases=["아이템", "템트리", "item", "build"])
async def cmd_build(ctx: commands.Context, *, champion_name: str = ""):
    """챔피언 1티어 아이템 빌드 & 룬 추천"""
    if not champion_name.strip():
        await ctx.send("❓ 조회할 챔피언 이름을 입력해주세요. (예: `!빌드 그레이브즈`, `!빌드 사일러스`)")
        return

    data = ChampionBuildEngine.get_build_recommendation(champion_name)
    champ = data["champion"]
    role = data["role"]
    core_items = " ➔ ".join([f"**{it}**" for it in data["core_items"]])

    embed = discord.Embed(
        title=f"🗡️ [{champ}] 추천 아이템 빌드 & 룬 가이드",
        description=f"포지션: **{role}** | 챔피언 유형: **{data['type']}** | 추천 티어: **{data['tier']}**",
        color=0xe67e22
    )

    embed.add_field(name="📦 시작 아이템", value=f"`{data['starting_items']}`", inline=True)
    embed.add_field(name="👢 추천 신발", value=f"`{data['boots']}`", inline=True)
    embed.add_field(name="⚔️ 핵심 1~3코어 빌드", value=core_items, inline=False)
    embed.add_field(name="🔮 추천 룬 세팅", value=f"`{data['runes']}`", inline=False)
    embed.add_field(name="💡 플레이 팁", value=f"• {data['tips']}", inline=False)

    embed.set_footer(text="LoL Stats Engine • OP.GG / Riot Data 기반 최적화")
    await ctx.send(embed=embed)


@bot.command(name="스킬트리", aliases=["스킬", "skill", "skills"])
async def cmd_skill(ctx: commands.Context, *, champion_name: str = ""):
    """스킬 마스터 순서 및 1~18레벨 스킬트리 안내"""
    if not champion_name.strip():
        await ctx.send("❓ 조회할 챔피언 이름을 입력해주세요. (예: `!스킬트리 그레이브즈`, `!스킬 아리`)")
        return

    data = ChampionBuildEngine.get_skill_recommendation(champion_name)
    champ = data["champion"]
    order = data["skill_order"]
    tree = data["leveling_tree"]

    # 1~18레벨 시각화 포맷
    lv1_9 = " ".join([f"`{lv}:{s}`" for lv, s in enumerate(tree[:9], 1)])
    lv10_18 = " ".join([f"`{lv}:{s}`" for lv, s in enumerate(tree[9:], 10)])

    embed = discord.Embed(
        title=f"🎓 [{champ}] 스킬 마스터 순서 & 레벨링 트리",
        description=f"스킬 마스터 우선순위: 🔥 **{order}**",
        color=0x9b59b6
    )

    embed.add_field(name="📈 1~9레벨 레벨링", value=lv1_9, inline=False)
    embed.add_field(name="📈 10~18레벨 레벨링", value=lv10_18, inline=False)
    embed.add_field(name="⚡ 파워스파이크", value=f"• {data['power_spike']}", inline=False)
    embed.add_field(name="💡 스킬 활용 팁", value=f"• {data['tips']}", inline=False)

    embed.set_footer(text="LoL Intelligence Engine • 1~18 Leveling Sequence")
    await ctx.send(embed=embed)


@bot.command(name="증강체티어", aliases=["증강", "증강체", "augment", "augments"])
async def cmd_augment(ctx: commands.Context, champion_name: str = "", *, choices_str: str = ""):
    """칼바람 아수라장 3지선다 증강체 시너지 티어 평가"""
    if not champion_name.strip() or not choices_str.strip():
        await ctx.send("❓ 챔피언 이름과 증강체 3개를 쉼표(,) 또는 공백으로 입력해주세요.\n*예: `!증강체티어 다리우스 갈라진 하늘, 신성한 중재, 무력 파편`*")
        return

    # 쉼표나 슬래시로 증강체 리스트 분리
    raw_choices = [c.strip() for c in re.split(r'[,/|]', choices_str) if c.strip()]
    if len(raw_choices) == 1 and " " in raw_choices[0]:
        raw_choices = raw_choices[0].split()

    if not raw_choices:
        await ctx.send("❓ 평가할 증강체 이름을 입력해주세요.")
        return

    if not AugmentEngine:
        await ctx.send("⚠️ 증강체 평가 엔진을 초기화하는 중입니다. 잠시 후 다시 시도해주세요.")
        return

    res = AugmentEngine.evaluate_augment_tiers(raw_choices, champion_name=champion_name)
    augments = res.get("augments", [])
    best = res.get("best_augment")

    embed = discord.Embed(
        title=f"🎴 [{champion_name}] 칼바람 아수라장 3지선다 증강체 티어 분석",
        description=f"역할군 분석: **{res.get('role', 'bruiser').upper()}** | 평가 대상: **{len(augments)}개 증강체**",
        color=0xf1c40f
    )

    for itm in augments:
        rank_idx = itm.get('rank_in_selection', 1)
        rank_badge = f"👑 {rank_idx}위" if rank_idx == 1 else f"{rank_idx}위"
        field_name = f"{rank_badge} | {itm.get('tier_label', itm.get('tier', ''))} • {itm['name_ko']} ({itm['rarity']})"
        field_val = (
            f"• 📊 **시너지 점수**: `{itm.get('synergy_score', 0)}점` (승률 {itm.get('win_rate', '50%')} / 픽률 {itm.get('pick_rate', '50%')})\n"
            f"• 📜 **효과**: {itm.get('description', '')}\n"
            f"• 💡 **추천 사유**: {itm.get('champ_synergy_reason', '')}"
        )
        embed.add_field(name=field_name, value=field_val, inline=False)

    if best:
        embed.add_field(
            name="🏆 최우선 추천 선택",
            value=f"👉 **[{best['name_ko']}]** 선택을 강력 권장합니다! ({best.get('champ_synergy_reason', '')})",
            inline=False
        )

    embed.set_footer(text="LoL ARAM Mayhem Engine • 199종 증강체 완벽 인덱싱")
    await ctx.send(embed=embed)


@bot.command(name="전적", aliases=["전적검색", "stats", "record"])
async def cmd_stats(ctx: commands.Context, *, summoner_query: str = ""):
    """소환사 솔로랭크 티어 및 최근 5게임 전적 브리핑"""
    if not summoner_query.strip():
        await ctx.send("❓ 소환사명과 태그를 입력해주세요. (예: `!전적 Hide on bush#KR1`)")
        return

    parts = summoner_query.split("#")
    game_name = parts[0].strip()
    tag_line = parts[1].strip() if len(parts) > 1 else "KR1"

    async with ctx.typing():
        ok, acc_data, msg = RiotApiClient.get_account_by_riot_id(game_name, tag_line)
        if not ok or not acc_data:
            await ctx.send(f"❌ 소환사 `[{game_name}#{tag_line}]` 조회 실패: {msg}")
            return

        puuid = acc_data["puuid"]
        riot_id_str = f"{acc_data.get('gameName', game_name)}#{acc_data.get('tagLine', tag_line)}"

        # 랭크 티어 조회
        league_entries = RiotApiClient.get_league_entries_by_puuid(puuid)
        solo_tier = "UNRANKED"
        flex_tier = "UNRANKED"
        for entry in league_entries:
            q_type = entry.get("queueType")
            tier_line = f"{entry.get('tier', '')} {entry.get('rank', '')} ({entry.get('leaguePoints', 0)} LP / {entry.get('wins', 0)}승 {entry.get('losses', 0)}패)"
            if q_type == "RANKED_SOLO_5x5":
                solo_tier = tier_line
            elif q_type == "RANKED_FLEX_SR":
                flex_tier = tier_line

        # 최근 5게임 전적 조회
        stats = RiotApiClient.get_recent_match_stats(puuid, count=5)

    embed = discord.Embed(
        title=f"📊 [{riot_id_str}] 소환사 전적 브리핑",
        color=0x2ecc71
    )
    embed.add_field(name="🏆 솔로랭크", value=f"`{solo_tier}`", inline=False)
    if flex_tier != "UNRANKED":
        embed.add_field(name="🛡️ 자유랭크", value=f"`{flex_tier}`", inline=False)

    total_g = stats.get("total_games", 0)
    if total_g > 0:
        win_rate = stats.get("winrate", 0.0)
        kda = stats.get("kda", 0.0)
        avg_k = stats.get("avg_kills", 0.0)
        avg_d = stats.get("avg_deaths", 0.0)
        avg_a = stats.get("avg_assists", 0.0)
        most_c = stats.get("most_champion", "Unknown")

        summary_val = (
            f"• 📈 **승률**: `{win_rate}%` ({stats.get('wins', 0)}승 {stats.get('losses', 0)}패)\n"
            f"• ⚔️ **평균 KDA**: `{kda} KDA` ({avg_k} / {avg_d} / {avg_a})\n"
            f"• 👑 **주 챔피언**: `{most_c}`"
        )
        embed.add_field(name=f"🔥 최근 {total_g}게임 통계", value=summary_val, inline=False)
    else:
        embed.add_field(name="🔥 최근 매치 기록", value="최근 매치 데이터를 불러올 수 없습니다.", inline=False)

    embed.set_footer(text="LoL Remote Stats Engine • Riot Games API")
    await ctx.send(embed=embed)


@bot.command(name="로딩화면", aliases=["인게임", "loading", "spectator"])
async def cmd_loading(ctx: commands.Context, *, summoner_query: str = ""):
    """진행 중인 실시간 게임(Spectator-V5) 10명 소환사 브리핑"""
    if not summoner_query.strip():
        await ctx.send("❓ 소환사명과 태그를 입력해주세요. (예: `!로딩화면 소환사#KR1`)")
        return

    async with ctx.typing():
        summary = LoadingScreenEngine.get_loading_summary(summoner_query)

    if summary.get("status") == "not_in_game":
        await ctx.send(f"ℹ️ 소환사 `[{summoner_query}]`님은 현재 진행 중인 게임이 없습니다 (게임 중이 아니거나 로딩 전).")
        return
    elif summary.get("status") != "success":
        await ctx.send(f"❌ {summary.get('message', '로딩 화면 조회 실패')}")
        return

    embed = discord.Embed(
        title=f"📋 [{summary['target_summoner']}] 인게임 로딩 화면 요약",
        description=f"게임 모드: **{summary['game_mode']}** | 경과 시간: **{summary['game_time']}**",
        color=0x3498db
    )

    # 블루팀 (100)
    blue_lines = []
    for p in summary.get("blue_team", []):
        line = f"• **{p['champion']}** ({p['riot_id']}) - `{p['tier']}` | {p['winrate']} ({p['kda']})"
        blue_lines.append(line)
    embed.add_field(name="🔷 블루팀 (Blue Team)", value="\n".join(blue_lines) or "정보 없음", inline=False)

    # 레드팀 (200)
    red_lines = []
    for p in summary.get("red_team", []):
        line = f"• **{p['champion']}** ({p['riot_id']}) - `{p['tier']}` | {p['winrate']} ({p['kda']})"
        red_lines.append(line)
    embed.add_field(name="🔴 레드팀 (Red Team)", value="\n".join(red_lines) or "정보 없음", inline=False)

    embed.set_footer(text="LoL Spectator-V5 Engine • 10-Player Matchup Intelligence")
    await ctx.send(embed=embed)


@bot.command(name="칼바람유물", aliases=["유물", "힐팩", "relic", "aram"])
async def cmd_relic(ctx: commands.Context, *, summoner_query: str = ""):
    """칼바람 나락 90초 주기 힐팩 리젠 카운트다운 계산기"""
    if not summoner_query.strip():
        await ctx.send("❓ 소환사명과 태그를 입력해주세요. (예: `!칼바람유물 소환사#KR1`)")
        return

    async with ctx.typing():
        timer_data = AramRelicTimerEngine.calculate_timer(summoner_query)

    if timer_data.get("status") == "not_in_game":
        await ctx.send(f"ℹ️ 소환사 `[{summoner_query}]`님은 현재 칼바람 게임 중이 아닙니다.")
        return
    elif timer_data.get("status") != "success":
        await ctx.send(f"❌ {timer_data.get('message', '유물 타이머 계산 실패')}")
        return

    embed = discord.Embed(
        title=f"❄️ [{summoner_query}] 칼바람 나락 회복 유물 카운트다운",
        description=f"현재 게임 시간: **{timer_data['game_time']}**",
        color=0x1abc9c
    )
    embed.add_field(name="⏳ 유물 생성 상태", value=f"**{timer_data['relic_status']}**", inline=False)
    embed.add_field(name="⏰ 다음 스폰 시각", value=f"`{timer_data['next_spawn_time']}` (남은 시간: `{timer_data['remain_seconds']}초`)", inline=False)
    embed.add_field(name="💡 전술 브리핑", value=f"• {timer_data['tactical_tip']}", inline=False)

    embed.set_footer(text="LoL ARAM Relic Engine • Deterministic 90s Cycle")
    await ctx.send(embed=embed)


@bot.command(name="경기리뷰", aliases=["오답노트", "리뷰", "review", "postmatch"])
async def cmd_review(ctx: commands.Context, *, summoner_query: str = ""):
    """최근 종료된 경기 Match-V5 사후 전술 복기 및 오답노트 코칭"""
    if not summoner_query.strip():
        await ctx.send("❓ 소환사명과 태그를 입력해주세요. (예: `!경기리뷰 소환사#KR1`)")
        return

    async with ctx.typing():
        review = PostGameReviewEngine.get_post_match_review(summoner_query)

    # 🚨 라이엇 공정성 정책 가드: 실시간 게임 중 거절 처리
    if review.get("status") == "in_game_rejected":
        embed = discord.Embed(
            title="🛡️ 라이엇 제3자 정책 준수 안내",
            description=review["message"],
            color=0xe74c3c
        )
        embed.set_footer(text="Riot Developer Policy Article 3 • Competitive Integrity Guard")
        await ctx.send(embed=embed)
        return
    elif review.get("status") != "success":
        await ctx.send(f"❌ {review.get('message', '경기 리뷰 생성 실패')}")
        return

    is_win = review.get("win", False)
    color = 0x2ecc71 if is_win else 0xe74c3c

    embed = discord.Embed(
        title=f"📜 [{review['summoner']}] 최근 경기 사후 전술 복기 리포트",
        description=f"결과: **{review['result_str']}** | 챔피언: **{review['champion']}** | 게임 시간: **{review['duration']}**",
        color=color
    )

    stats_summary = (
        f"• ⚔️ **KDA**: `{review['kda']}`\n"
        f"• 🌾 **CS**: `{review['cs']}`\n"
        f"• 💥 **가한 피해량**: `{review['damage']}` G\n"
        f"• 💰 **획득 골드**: `{review['gold']}`\n"
        f"• 👁️ **시야 점수**: `{review['vision']}`"
    )
    embed.add_field(name="📊 매치 핵심 지표", value=stats_summary, inline=False)

    feedback_points = review.get("review_feedback", [])
    if feedback_points:
        embed.add_field(name="📝 사후 오답노트 & 개선 포인트", value="\n\n".join(feedback_points), inline=False)

    embed.set_footer(text="LoL Post-Match Review Engine • Legal Post-Game Analysis Only")
    await ctx.send(embed=embed)


@bot.command(name="캐시초기화", aliases=["reload_cache", "reload"])
async def cmd_reload_cache(ctx: commands.Context):
    """(관리자 전용) SQLite 캐시 및 지식베이스 리로드"""
    if not is_master(ctx.author.id):
        await ctx.send("⛔ 마스터 관리자만 실행할 수 있는 명령어입니다.")
        return

    ChampionBuildEngine._is_loaded = False
    ChampionBuildEngine.load()
    if AugmentEngine:
        AugmentEngine._is_loaded = False
        AugmentEngine.load_data()

    await ctx.send("✅ LoL 지식베이스 및 챔피언 가이드 캐시가 성공적으로 리로드되었습니다.")


# ---------------------------------------------------------------------------
# 6. 자연어 질문 자동 라우팅 (on_message)
# ---------------------------------------------------------------------------
@bot.event
async def on_message(message: discord.Message):
    # 봇 자신의 메시지는 무시
    if message.author.bot:
        return

    # 1. 접두사로 시작하는 일반 명령어 처리
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    # 2. 자연어 질문 자동 감지 및 라우팅
    if not config_data.get("enable_natural_language_routing", True):
        return

    content = message.content.strip()
    is_mentioned = bot.user in message.mentions

    # 봇 멘션이 있거나 전용 키워드 감지 시
    if is_mentioned or any(k in content for k in ["빌드", "템트리", "스킬트리", "증강체", "전적", "칼바람", "오답노트", "경기리뷰"]):
        # 멘션 문자열 제거
        clean_text = re.sub(r'<@!?\d+>', '', content).strip()

        # A. 챔피언 빌드/템트리 질문 (예: "그브 템트리 알려줘", "이즈리얼 빌드")
        build_match = re.search(r'([가-힣a-zA-Z0-9]+)\s*(?:템트리|빌드|아이템|템)', clean_text)
        if build_match:
            champ_q = build_match.group(1).strip()
            ctx = await bot.get_context(message)
            await cmd_build(ctx, champion_name=champ_q)
            return

        # B. 챔피언 스킬트리 질문 (예: "사일러스 스킬 뭐 찍어?", "아리 스킬트리")
        skill_match = re.search(r'([가-힣a-zA-Z0-9]+)\s*(?:스킬트리|스킬 순서|스킬 마스터|스킬)', clean_text)
        if skill_match:
            champ_q = skill_match.group(1).strip()
            ctx = await bot.get_context(message)
            await cmd_skill(ctx, champion_name=champ_q)
            return

        # C. 소환사 전적 질문 (예: "Hide on bush#KR1 전적", "소환사#KR1 전적 보여줘")
        stats_match = re.search(r'([^\s#]+#[^\s]+)\s*(?:전적|승률|티어)', clean_text)
        if stats_match:
            sum_q = stats_match.group(1).strip()
            ctx = await bot.get_context(message)
            await cmd_stats(ctx, summoner_query=sum_q)
            return

        # D. 경기 리뷰/오답노트 질문 (예: "소환사#KR1 경기리뷰", "소환사#KR1 오답노트")
        review_match = re.search(r'([^\s#]+#[^\s]+)\s*(?:경기리뷰|오답노트|리뷰|복기)', clean_text)
        if review_match:
            sum_q = review_match.group(1).strip()
            ctx = await bot.get_context(message)
            await cmd_review(ctx, summoner_query=sum_q)
            return

        # E. 단순 멘션 시 도움말 안내
        if is_mentioned and len(clean_text) < 5:
            ctx = await bot.get_context(message)
            await cmd_help(ctx)
            return


# ---------------------------------------------------------------------------
# 7. 봇 실행 진입점 (Entry Point)
# ---------------------------------------------------------------------------
def main():
    token = get_discord_token()
    if not token:
        logger.error("❌ LoL 디스코드 봇 토큰(LOL_BOT_TOKEN)이 설정되지 않았습니다.")
        print("\n" + "=" * 65)
        print("📢 [안내] LoL 디스코드 봇 토큰(LOL_BOT_TOKEN)이 없습니다.")
        print("=" * 65)
        print("1. Discord Developer Portal에서 LoL 전용 봇 어플리케이션 생성")
        print("2. [Bot] 탭 -> [Reset Token]으로 토큰 복사")
        print("3. [Privileged Gateway Intents] -> MESSAGE CONTENT INTENT [ON]")
        print("4. .env 또는 discord_lol_config.json 파일의 'bot_token' 에 입력하세요.")
        print("=" * 65 + "\n")
        sys.exit(1)

    # Render 클라우드 배포 시 포트 바인딩 헬스체크 웹 서버 가동
    start_render_health_server_thread()

    logger.info("🏆 LoL 디스코드 인텔리전스 봇을 24/7 무중단 모드로 시작합니다...")

    # 24/7 무중단 자동 재연결 루프
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
