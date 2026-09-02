import psutil
import requests
import urllib3
import re
import json

# LCU API 인증 시 발생하는 자체 서명 인증서 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import time

class RiotLCU:
    def __init__(self):
        self.port = None
        self.auth_token = None
        self.base_url = None
        self._last_scan_time = 0
        self._cached_found = False
        
    def _find_lcu_process(self):
        """백그라운드에서 실행 중인 롤 클라이언트(LeagueClientUx.exe)를 찾아 포트와 비밀번호를 빼옵니다."""
        now = time.time()
        # 3초 이내에 스캔한 결과가 있고 오프라인 상태였다면 즉시 반환
        if now - self._last_scan_time < 3.0:
            return self._cached_found

        self._last_scan_time = now
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] == 'LeagueClientUx.exe':
                    cmdline = proc.cmdline()
                    if cmdline:
                        cmd_str = " ".join(cmdline)
                        port_match = re.search(r'--app-port=([0-9]+)', cmd_str)
                        auth_match = re.search(r'--remoting-auth-token=([\w-]+)', cmd_str)
                        
                        if port_match and auth_match:
                            self.port = port_match.group(1)
                            self.auth_token = auth_match.group(1)
                            self.base_url = f"https://127.0.0.1:{self.port}"
                            self._cached_found = True
                            return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        self.port = None
        self.auth_token = None
        self.base_url = None
        self._cached_found = False
        return False

    def request(self, method, endpoint):
        """LCU API에 요청을 보냅니다."""
        if not self.base_url:
            return None
            
        url = f"{self.base_url}{endpoint}"
        try:
            # LCU는 'riot' 아이디와 토큰으로 Basic Auth를 수행합니다.
            response = requests.request(
                method=method,
                url=url,
                auth=('riot', self.auth_token),
                verify=False, # 자체 인증서 무시
                timeout=2
            )
            if response.status_code == 200:
                return response.json()
            return None
        except requests.exceptions.RequestException:
            return None

    def get_current_status(self):
        """롤 클라이언트 상태와 현재 로그인된 소환사 정보를 반환합니다."""
        if not self._find_lcu_process():
            return {"status": "offline", "message": "롤 클라이언트가 실행 중이 아닙니다."}
            
        # 1. 현재 접속 중인 소환사 정보 조회
        summoner_info = self.request('GET', '/lol-summoner/v1/current-summoner')
        
        if not summoner_info:
            return {"status": "offline", "message": "롤 클라이언트와 통신할 수 없거나 로그인이 안 되어 있습니다."}
            
        game_name = summoner_info.get('gameName')
        tag_line = summoner_info.get('tagLine')
        display_name = summoner_info.get('displayName')
        
        if game_name and tag_line:
            final_name = f"{game_name}#{tag_line}"
        elif display_name:
            final_name = display_name
        else:
            final_name = "알수없음"
            
        puuid = summoner_info.get('puuid', '')
        summoner_level = summoner_info.get('summonerLevel', 0)
        
        # 1.5. 티어 정보 조회
        tier_info = "Unranked"
        ranked_stats = self.request('GET', '/lol-ranked/v1/current-ranked-stats')
        if ranked_stats and 'queues' in ranked_stats:
            for queue in ranked_stats['queues']:
                if queue.get('queueType') == 'RANKED_SOLO_5x5':
                    tier = queue.get('tier', 'UNRANKED')
                    division = queue.get('division', '')
                    if tier not in ['UNRANKED', 'NONE', '']:
                        tier_info = f"{tier.capitalize()} {division}"
                        break
        
        # 2. 현재 상태 (로비, 픽창, 인게임 등) 조회
        # /lol-gameflow/v1/gameflow-phase 반환값: None, Lobby, Matchmaking, ReadyCheck, ChampSelect, InProgress, PreEndOfGame, EndOfGame
        gameflow = self.request('GET', '/lol-gameflow/v1/gameflow-phase')
        phase = gameflow if gameflow else "Unknown"
        
        # 3. 픽창일 경우 추가 정보 조회
        champ_select_info = None
        picked_champion = ""
        if phase == "ChampSelect":
            cs_data = self.request('GET', '/lol-champ-select/v1/session')
            if cs_data:
                champ_select_info = "챔피언 선택 중"
                local_player_cell_id = cs_data.get("localPlayerCellId", -1)
                my_team = cs_data.get("myTeam", [])
                
                champ_id = 0
                has_snowball = False
                is_aram = False
                
                lobby = self.request('GET', '/lol-lobby/v2/lobby')
                if lobby and lobby.get('gameConfig', {}).get('queueId') == 450:
                    is_aram = True

                for teammate in my_team:
                    if teammate.get("cellId") == local_player_cell_id:
                        champ_id = teammate.get("championId", 0)
                        spell1 = teammate.get("spell1Id", 0)
                        spell2 = teammate.get("spell2Id", 0)
                        if spell1 == 32 or spell2 == 32:
                            has_snowball = True
                        break
                        
                if is_aram and not has_snowball:
                    champ_select_info = "칼바람 눈덩이 경고"

                
                if champ_id > 0:
                    try:
                        champions_dict = self.request('GET', '/lol-game-data/assets/v1/champion-summary.json')
                        if champions_dict:
                            for champ in champions_dict:
                                if champ.get('id') == champ_id:
                                    picked_champion = champ.get('name', '')
                                    break
                    except:
                        pass
        
        # 4. 인게임(로딩창 포함)일 경우 라인 상대 분석
        enemy_laner = ""
        my_position = ""
        if phase == "InProgress":
            session = self.request('GET', '/lol-gameflow/v1/session')
            if session and session.get('gameData'):
                game_data = session.get('gameData')
                team_one = game_data.get('teamOne', [])
                team_two = game_data.get('teamTwo', [])
                
                my_player = None
                my_team_list = []
                enemy_team_list = []
                
                # puuid 기반으로 내 소환사 찾기
                for p in team_one:
                    if p.get('puuid') == puuid:
                        my_player = p
                        my_team_list = team_one
                        enemy_team_list = team_two
                        break
                if not my_player:
                    for p in team_two:
                        if p.get('puuid') == puuid:
                            my_player = p
                            my_team_list = team_two
                            enemy_team_list = team_one
                            break
                            
                if my_player:
                    # 포지션 확인 (TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY)
                    my_position = my_player.get('selectedPosition', '')
                    
                    # 내 챔피언 정보가 아직 없다면(클라이언트 재접속 등) 보강
                    if not picked_champion:
                        my_champ_id = my_player.get('championId', 0)
                        if my_champ_id > 0:
                            try:
                                champions_dict = self.request('GET', '/lol-game-data/assets/v1/champion-summary.json')
                                if champions_dict:
                                    for champ in champions_dict:
                                        if champ.get('id') == my_champ_id:
                                            picked_champion = champ.get('name', '')
                                            break
                            except:
                                pass
                                
                    # 상대 라이너 찾기
                    if my_position and my_position not in ["", "NONE"]:
                        enemy_champ_id = 0
                        for p in enemy_team_list:
                            if p.get('selectedPosition', '') == my_position:
                                enemy_champ_id = p.get('championId', 0)
                                break
                                
                        if enemy_champ_id > 0:
                            try:
                                champions_dict = self.request('GET', '/lol-game-data/assets/v1/champion-summary.json')
                                if champions_dict:
                                    for champ in champions_dict:
                                        if champ.get('id') == enemy_champ_id:
                                            enemy_laner = champ.get('name', '')
                                            break
                            except:
                                pass

        return {
            "status": "online",
            "summoner_name": final_name,
            "level": summoner_level,
            "tier": tier_info,
            "phase": phase,
            "champ_select_info": champ_select_info,
            "picked_champion": picked_champion,
            "my_position": my_position,
            "enemy_laner": enemy_laner
        }

    def get_active_session_details(self):
        """인게임 중일 때 게임 모드와 선택한 챔피언 이름을 가져옵니다."""
        if not self._find_lcu_process():
            return {"mode": "Unknown", "champion": "Unknown"}
            
        session = self.request('GET', '/lol-gameflow/v1/session')
        if not session:
            return {"mode": "Unknown", "champion": "Unknown"}
            
        mode = "Unknown"
        champion = "Unknown"
        
        try:
            # 맵/모드 파싱
            map_data = session.get('map', {})
            if map_data:
                map_name = map_data.get('name', '')
                if 'HowlingAbyss' in map_name:
                    mode = "무작위 총력전"
                    # 게임 모드가 아수라장인지 확인
                    game_data = session.get('gameData', {})
                    queue_data = game_data.get('queue', {})
                    if queue_data.get('gameMode') == 'URF':
                        mode = "무작위 총력전: 아수라장"
                elif 'SummonersRift' in map_name:
                    mode = "소환사의 협곡"
                else:
                    mode = map_name

            # 챔피언 아이디 가져오기 (챔피언 이름 대신 ID가 나오면 이름으로 변환해야 하지만, 
            # 일단 라이브 클라이언트 데이터 API를 쓰면 가장 정확함. LCU로는 로컬 플레이어의 챔피언 찾기가 복잡할 수 있음.
            # LCU session에서 localPlayer 가져오기
            try:
                champions_dict = self.request('GET', '/lol-game-data/assets/v1/champion-summary.json')
            except:
                champions_dict = []
                
            local_player = session.get('localPlayer', {})
            champ_id = local_player.get('championId', 0)
            
            if champ_id > 0 and champions_dict:
                for champ in champions_dict:
                    if champ.get('id') == champ_id:
                        champion = champ.get('name', 'Unknown')
                        break
        except Exception as e:
            print(f"세션 상세 정보 파싱 에러: {e}")
            
        return {"mode": mode, "champion": champion}

    def get_match_history(self, count=10):
        """최근 매치 히스토리를 LCU를 통해 가져옵니다."""
        if not self._find_lcu_process():
            return {"status": "error", "message": "롤 클라이언트가 실행 중이 아닙니다."}
        
        summoner_info = self.request('GET', '/lol-summoner/v1/current-summoner')
        if not summoner_info:
            return {"status": "error", "message": "소환사 정보를 가져올 수 없습니다."}
            
        puuid = summoner_info.get('puuid')
        if not puuid:
            return {"status": "error", "message": "puuid를 찾을 수 없습니다."}
            
        history = self.request('GET', f'/lol-match-history/v1/products/lol/{puuid}/matches')
        if not history or 'games' not in history or 'games' not in history['games']:
            return {"status": "error", "message": "전적을 불러올 수 없습니다."}
            
        matches = history['games']['games'][:count]
        
        # 간략화된 데이터 추출
        parsed_matches = []
        for match in matches:
            game_mode = match.get('gameMode', 'Unknown')
            game_duration = match.get('gameDuration', 0)
            
            participant = None
            if 'participants' in match and len(match['participants']) > 0:
                participant = match['participants'][0]
                
            if participant and 'stats' in participant:
                stats = participant['stats']
                win = stats.get('win', False)
                kills = stats.get('kills', 0)
                deaths = stats.get('deaths', 0)
                assists = stats.get('assists', 0)
                champ_id = participant.get('championId', 0)
                
                # 추가 스탯
                cs = stats.get('totalMinionsKilled', 0) + stats.get('neutralMinionsKilled', 0)
                vision_score = stats.get('visionScore', 0)
                damage = stats.get('totalDamageDealtToChampions', 0)
                gold = stats.get('goldEarned', 0)
                
                # 뱃지 계산
                kda = (kills + assists) / max(deaths, 1)
                if win:
                    if kda >= 4.0: badge = "버스기사"
                    elif kda >= 2.0: badge = "1인분"
                    else: badge = "버스승객"
                else:
                    if kda >= 3.0: badge = "고통받는 에이스"
                    elif kda >= 1.5: badge = "평범한 패배자"
                    else: badge = "민폐 트롤"
                
                parsed_matches.append({
                    "mode": game_mode,
                    "duration_sec": game_duration,
                    "win": win,
                    "kills": kills,
                    "deaths": deaths,
                    "assists": assists,
                    "champion_id": champ_id,
                    "cs": cs,
                    "vision_score": vision_score,
                    "damage": damage,
                    "gold": gold,
                    "badge": badge
                })
                
        return {
            "status": "success",
            "summoner_name": summoner_info.get('displayName', summoner_info.get('gameName', 'Unknown')),
            "matches": parsed_matches
        }

# 단독 실행 테스트용
if __name__ == "__main__":
    lcu = RiotLCU()
    print("롤 상태 확인 중...")
    print(json.dumps(lcu.get_current_status(), indent=2, ensure_ascii=False))
    print("\n최근 전적 3게임:")
    print(json.dumps(lcu.get_match_history(3), indent=2, ensure_ascii=False))
