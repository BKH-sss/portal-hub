import os
import time
import requests
import subprocess
import datetime
import random
import json

# 세션 학습 내역을 기록할 파일
SESSION_LOG_FILE = "session_log.json"

BASE_KEYWORDS = [
    {"keyword": "리그오브레전드 초보자 가이드", "category": "lol"},
    {"keyword": "롤 모든 챔피언 스킬 요약", "category": "lol"},
    {"keyword": "롤 14시즌 아이템 총정리", "category": "lol"},
    {"keyword": "메이플스토리 무자본 초보 가이드", "category": "maplestory"},
    {"keyword": "메이플 전 직업 스킬 요약", "category": "maplestory"},
    {"keyword": "메이플스토리 필수 아이템 템셋팅", "category": "maplestory"},
    {"keyword": "파이썬 기초 프로그래밍", "category": "coding"},
    {"keyword": "자바스크립트 비동기 처리 핵심", "category": "coding"},
    {"keyword": "리액트 실전 강좌", "category": "coding"},
    {"keyword": "모의해킹 기초 강좌", "category": "hacking"},
    {"keyword": "웹 해킹과 보안 취약점", "category": "hacking"},
    {"keyword": "칼리 리눅스 사용법", "category": "hacking"}
]

# 심화 랜덤 키워드 소스
LOL_KEYWORDS = ["롤 꿀팁", "롤 장인 강의", "롤 정글 메타", "리그오브레전드 패치 노트", "롤 브라이어 공략", "롤 티어 올리는 법", "롤 매드무비 피지컬", "롤 챔피언 콤보"]
MAPLE_KEYWORDS = ["메이플 최신 패치", "메이플 엔젤릭버스터 사냥", "메이플 보스 공략", "메이플스토리 메소 버는 법", "메이플스토리 직업 추천", "메이플 링크 스킬 유니온", "메이플 사냥터 추천"]
CODING_KEYWORDS = ["프론트엔드 최신 트렌드", "백엔드 아키텍처", "알고리즘 코딩 테스트", "깃허브 사용법", "파이썬 데이터 분석", "디자인 패턴 실무"]
HACKING_KEYWORDS = ["CTF 문제 풀이", "네트워크 보안 실습", "리버스 엔지니어링 기초", "사이버 보안 개론", "악성코드 분석 기법", "보안 컨설팅 실무"]

def init_session_log():
    with open(SESSION_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

def append_to_session_log(keyword, category, status):
    try:
        if os.path.exists(SESSION_LOG_FILE):
            with open(SESSION_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []
            
        logs.append({
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "keyword": keyword,
            "category": category,
            "status": status
        })
        
        with open(SESSION_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except:
        pass

def search_youtube(keyword):
    try:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 유튜브 검색 중: {keyword}")
        cmd = ["python", "-m", "yt_dlp", f"ytsearch1:{keyword}", "--get-id"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        video_id = result.stdout.strip().split("\n")[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        print(f"유튜브 검색 실패: {e}")
    return None

def trigger_brain_analyze(url, category):
    try:
        print(f"[전송] 뇌(Brain) 서버에 분석 요청 전송 ({category}): {url}")
        res = requests.post("http://localhost:8000/analyze", json={"url": url, "category": category}, timeout=300)
        if res.status_code == 200:
            print("=> 성공적으로 뇌에 지식이 주입되었습니다!")
            return True
        else:
            print(f"=> 뇌 주입 실패: {res.text}")
            return False
    except Exception as e:
        print(f"=> 뇌 서버 접속 오류: {e}")
        return False

def get_next_target(learn_count):
    # 기초 지식을 먼저 학습
    if learn_count < len(BASE_KEYWORDS):
        return BASE_KEYWORDS[learn_count]
    
    # 기초 학습이 끝나면 랜덤으로 심화 키워드 조합
    category = random.choice(["lol", "maplestory", "coding", "hacking"])
    if category == "lol":
        return {"keyword": random.choice(LOL_KEYWORDS) + " " + str(random.randint(1, 100)), "category": "lol"}
    elif category == "maplestory":
        return {"keyword": random.choice(MAPLE_KEYWORDS) + " " + str(random.randint(1, 100)), "category": "maplestory"}
    elif category == "coding":
        return {"keyword": random.choice(CODING_KEYWORDS) + " " + str(random.randint(1, 100)), "category": "coding"}
    else:
        return {"keyword": random.choice(HACKING_KEYWORDS) + " " + str(random.randint(1, 100)), "category": "hacking"}

def run_auto_learning():
    print("==================================================")
    print(f"[{datetime.datetime.now()}] 무한 자율 학습 에이전트 가동!")
    print("==================================================")
    
    init_session_log()
    learn_count = 0
    cycle_count = 0
    
    while True:
        target = get_next_target(learn_count)
        keyword = target["keyword"]
        category = target["category"]
        
        video_url = search_youtube(keyword)
        if video_url:
            success = trigger_brain_analyze(video_url, category)
            if success:
                append_to_session_log(keyword, category, "성공")
            else:
                append_to_session_log(keyword, category, "분석 실패")
        else:
            append_to_session_log(keyword, category, "검색 실패")
            
        learn_count += 1
        cycle_count += 1
        
        # 10개 채워지면 10분 휴식
        if cycle_count >= 10:
            print(f"\n[휴식] 10개 학습 사이클 완료. 과부하 방지를 위해 10분간 딥 슬립에 들어갑니다...\n")
            time.sleep(600) # 10분
            cycle_count = 0 # 사이클 초기화
        else:
            print(f"\n[휴식] 1개 학습 완료. 1분간 대기합니다...\n")
            time.sleep(60) # 1분

if __name__ == "__main__":
    run_auto_learning()
