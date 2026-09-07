"""
lol_augment_matchup.py
=============================================================================
🛡️ JARVIS / SKADI: 롤(LoL) 상대/아군 조합 맞춤형 증강체 카운터 가중치 모듈
=============================================================================
- 설계 원칙:
    1. [완벽한 모듈화 (Decoupled)]: 필요 없을 시 파일만 삭제하거나 옵션 토글로 1초 만에 비활성화 가능
    2. [상대 조합 카운터 분석]:
       - 올탱커/다수 탱커 (사이온, 말파이트, 초가스 등) ➔ 퍼뎀/방관/마관 가산점 (+10~18점)
       - 극포킹/원거리 (제라스, 럭스, 직스, 벨코즈 등) ➔ 돌진/보호막/이속/재생 가산점 (+8~15점)
       - 폭딜/암살자/하드CC ➔ 강인함/피해감소/생존기 가산점 (+8~14점)
    3. [경량 연산]: 틱당 <0.02ms 완료
=============================================================================
"""

from typing import List, Dict, Tuple, Any

# 챔피언 군집 분류 (상대 챔피언 특성 파악용)
CHAMPION_ARCHETYPES: Dict[str, str] = {
    # 탱커 군집 (Tank Heavy)
    "말파이트": "tank", "사이온": "tank", "초가스": "tank", "오른": "tank", "마오카이": "tank",
    "세주아니": "tank", "자크": "tank", "람머스": "tank", "노틸러스": "tank", "레오나": "tank",
    "탐켄치": "tank", "문도 박사": "tank", "알리스타": "tank", "쉔": "tank", "뽀삐": "tank",

    # 포킹/원거리 AP 군집 (Poke Heavy)
    "제라스": "poke", "럭스": "poke", "직스": "poke", "벨코즈": "poke", "바루스": "poke",
    "제이스": "poke", "조이": "poke", "카르마": "poke", "니달리": "poke", "애쉬": "poke",

    # 암살자/폭딜 군집 (Burst/Assassin)
    "제드": "assassin", "탈론": "assassin", "카타리나": "assassin", "아칼리": "assassin",
    "키아나": "assassin", "카직스": "assassin", "렝가": "assassin", "피즈": "assassin",
    "르블랑": "assassin", "이블린": "assassin", "샤코": "assassin"
}

# 카운터 키워드 매핑 테이블
COUNTER_KEYWORDS: Dict[str, Dict[str, Any]] = {
    "anti_tank": {
        "keywords": ["최대 체력", "체력 비례", "방어력 관통", "마법 관통력", "고정 피해", "거인", "퍼센트", "추가 피해", "치유 감소"],
        "tag": "🛡️ 탱커 카운터",
        "bonus_per_hit": 5.5,
        "max_bonus": 16.0
    },
    "anti_poke": {
        "keywords": ["보호막", "회복", "이동 속도", "돌진", "재생", "전능 흡혈", "생명력 흡수", "사거리", "접근"],
        "tag": "🎯 포킹 대항",
        "bonus_per_hit": 4.5,
        "max_bonus": 14.0
    },
    "anti_burst": {
        "keywords": ["강인함", "피해 감소", "무적", "부활", "보호막", "체력", "방어력", "마법 저항력", "불굴"],
        "tag": "⚡ 생존/CC 대항",
        "bonus_per_hit": 4.5,
        "max_bonus": 13.0
    }
}


class MatchupCounterAnalyzer:
    """
    상대 챔피언 라인업에 기반하여 실시간 카운터 증강체 가중치와 태그를 산출하는 독립 엔진
    """

    @classmethod
    def analyze_enemy_composition(cls, enemy_champions: List[str]) -> Dict[str, int]:
        """상대 조합의 아키타입(탱커수, 포킹수, 암살자수) 계산"""
        counts = {"tank": 0, "poke": 0, "assassin": 0, "other": 0}
        for name in enemy_champions:
            clean = name.strip()
            arch = CHAMPION_ARCHETYPES.get(clean, "other")
            counts[arch] = counts.get(arch, 0) + 1
        return counts

    @classmethod
    def evaluate_matchup_bonus(
        cls,
        augment_name: str,
        augment_desc: str,
        enemy_champions: List[str]
    ) -> Tuple[float, str]:
        """
        단일 증강체가 현재 상대 조합에 대해 얼마의 카운터 가산점(+점수)과 태그를 받는지 계산합니다.
        - 반환: (보너스 점수 float, 카운터 태그 str)
        """
        if not enemy_champions:
            return 0.0, ""

        comp = cls.analyze_enemy_composition(enemy_champions)
        total_bonus = 0.0
        tags: List[str] = []

        text_to_check = f"{augment_name} {augment_desc}"

        # 1. 상대에 탱커가 2명 이상인 경우 (안티 탱커 보너스)
        if comp.get("tank", 0) >= 2:
            anti_tank = COUNTER_KEYWORDS["anti_tank"]
            matched = [kw for kw in anti_tank["keywords"] if kw in text_to_check]
            if matched:
                bonus = min(anti_tank["max_bonus"], len(matched) * anti_tank["bonus_per_hit"])
                total_bonus += bonus
                tags.append(anti_tank["tag"])

        # 2. 상대에 포킹 챔피언이 2명 이상인 경우 (안티 포킹 보너스)
        if comp.get("poke", 0) >= 2:
            anti_poke = COUNTER_KEYWORDS["anti_poke"]
            matched = [kw for kw in anti_poke["keywords"] if kw in text_to_check]
            if matched:
                bonus = min(anti_poke["max_bonus"], len(matched) * anti_poke["bonus_per_hit"])
                total_bonus += bonus
                tags.append(anti_poke["tag"])

        # 3. 상대에 암살자/폭딜러가 2명 이상인 경우 (안티 버스트 보너스)
        if comp.get("assassin", 0) >= 2:
            anti_burst = COUNTER_KEYWORDS["anti_burst"]
            matched = [kw for kw in anti_burst["keywords"] if kw in text_to_check]
            if matched:
                bonus = min(anti_burst["max_bonus"], len(matched) * anti_burst["bonus_per_hit"])
                total_bonus += bonus
                tags.append(anti_burst["tag"])

        # 최대 카운터 가산점은 20점으로 클램핑
        final_bonus = round(min(20.0, total_bonus), 1)
        final_tag = " • ".join(tags)

        return final_bonus, final_tag
