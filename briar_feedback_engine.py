import json
import os
from google import genai
from google.genai import types

def generate_briar_feedback(matches, summoner_name):
    """
    최근 전적 데이터를 기반으로 브라이어의 거친 피드백 텍스트를 생성합니다.
    """
    if not matches:
        return "전적 데이터가 없어! 피 냄새를 맡을 수가 없잖아. 게임이나 한 판 돌리고 오라고!"

    total_games = len(matches)
    wins = sum(1 for m in matches if m['win'])
    losses = total_games - wins
    win_rate = int((wins / total_games) * 100) if total_games > 0 else 0
    
    total_kills = sum(m['kills'] for m in matches)
    total_deaths = sum(m['deaths'] for m in matches)
    total_assists = sum(m['assists'] for m in matches)
    
    avg_k = total_kills / total_games
    avg_d = total_deaths / total_games
    avg_a = total_assists / total_games

    # 추가 스탯 처리
    avg_cs = int(sum(m.get('cs', 0) for m in matches) / total_games)
    avg_vision = int(sum(m.get('vision_score', 0) for m in matches) / total_games)
    avg_dmg = int(sum(m.get('damage', 0) for m in matches) / total_games)
    avg_gold = int(sum(m.get('gold', 0) for m in matches) / total_games)

    # 뱃지 카운트하여 가장 많이 받은 뱃지 선정
    badges = [m.get('badge', '평범') for m in matches if 'badge' in m]
    primary_badge = max(set(badges), key=badges.count) if badges else "분석 불가"

    # HTML 성적표 생성
    win_color = "#3b82f6" if win_rate >= 50 else "#ef4444"
    html_card = f"<div style='background:rgba(0,0,0,0.3); border-left:4px solid #e11d48; padding:15px; border-radius:8px; margin-bottom:15px; color:#f8fafc;'>" \
                f"<div style='font-size:15px; font-weight:bold; margin-bottom:10px; color:#fecaca;'>📊 최근 {total_games}전 요약 리포트 (유저: {summoner_name})</div>" \
                f"<div style='display:flex; justify-content:space-between; margin-bottom:8px;'>" \
                f"<span>승률: <b style='color:{win_color}'>{win_rate}%</b> ({wins}승 {losses}패)</span>" \
                f"<span>KDA: <b>{avg_k:.1f} / {avg_d:.1f} / {avg_a:.1f}</b></span></div>" \
                f"<div style='display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px; color:#cbd5e1;'>" \
                f"<span>평균 CS: {avg_cs} | 평균 골드: {avg_gold}</span>" \
                f"<span>가한 피해량: {avg_dmg} | 시야 점수: {avg_vision}</span></div>" \
                f"<div style='margin-top:10px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.1);'>" \
                f"주요 플레이 스타일: <span style='background:#be123c; padding:2px 8px; border-radius:12px; font-size:12px; font-weight:bold; margin-left:5px;'>{primary_badge}</span>" \
                f"</div></div>"

    prompt = f"""
[명령] 너는 통제 불능의 뱀파이어 '브라이어(Briar)'다.
너는 지금 마스터(유저 '{summoner_name}')의 최근 리그오브레전드 전적을 보고 피드백을 해줘야 해.
절대로 뻔한 AI나 설명충처럼 길게 말하지 마. 불릿포인트(*, -) 절대 금지.
마치 Your.gg의 'AI 멤버십 피드백'처럼 매섭고 날카롭게 팩트 폭력을 날리되, 브라이어 특유의 미친 텐션과 피에 굶주린 반말로 4~5문장으로 아주 거칠게 조언해.

[최근 전적 통계 ({total_games}게임)]
- 승률: {win_rate}% ({wins}승 {losses}패)
- 평균 KDA: {avg_k:.1f} / {avg_d:.1f} / {avg_a:.1f}
- 주요 뱃지(스타일): {primary_badge}
- 평균 CS: {avg_cs}, 평균 시야 점수: {avg_vision}

위 데이터를 보고 브라이어의 목소리로 피드백을 해봐! 특히 '{primary_badge}' 뱃지와 시야 점수, CS 등을 꼬투리 잡아서 물어뜯거나 칭찬해!
    """

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        return "GEMINI_API_KEY가 없어! 피드백을 만들 수 없다고!"

    try:
        client = genai.Client(api_key=gemini_key)
        config = types.GenerateContentConfig(
            temperature=0.8,
            safety_settings=[
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            ]
        )
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt, config=config)
        return html_card + "\n<br>\n" + res.text.strip()
    except Exception as e:
        return f"피드백 생성 중 에러가 발생했어: {e}"

if __name__ == "__main__":
    test_matches = [
        {"win": False, "kills": 2, "deaths": 8, "assists": 4},
        {"win": False, "kills": 1, "deaths": 10, "assists": 2},
        {"win": True, "kills": 10, "deaths": 2, "assists": 8},
        {"win": False, "kills": 0, "deaths": 5, "assists": 1},
        {"win": False, "kills": 3, "deaths": 9, "assists": 3},
    ]
    print(generate_briar_feedback(test_matches, "테스트유저"))
