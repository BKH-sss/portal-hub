"""
maple_skill_tracker.py
=============================================================================
🍁 JARVIS / SKADI: 메이플스토리(MapleStory) 47+ 전 직업 스킬 쿨타임 & 보스 전술 브리핑 엔진
=============================================================================
- 기능:
    1. 메이플 실행(`MapleStory.exe`) 시 백그라운드 자동 감시 가동 (수동 조작 불필요)
    2. 전 직업(47+개) + 상위 8대 보스 레이드(검마, 세렌, 칼로스, 카링, 림보 등) 전술 프리셋 내장
    3. Windows GetAsyncKeyState 기반 0.00ms 무지연 단축키(Shift/Ctrl/Z/X/A/S/F1~F12/1~9/NumPad/마우스 등) 자동 감지
    4. 쿨타임 N초 전 스카디 AI 음성 사전 예고 및 쿨타임 완료 즉각 0ms 로컬 재생
    5. 카테고리별(무적기, 극딜기, 바인드, 버프, 보스패턴) 시각화 게이지 및 편집 모달
    6. 로컬 JSON (`data/maple_skills.json`, `data/maple_custom_presets.json`) 영구 저장
=============================================================================
"""

import io
import os
import math
import json
import time
import ctypes
import hashlib
import asyncio
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

try:
    import psutil
except ImportError:
    psutil = None

try:
    import edge_tts
except ImportError:
    edge_tts = None

# =============================================================================
# 🚀 1. FastAPI APIRouter 및 데이터 경로 설정
# =============================================================================
router = APIRouter(prefix="/api/maple/tracker", tags=["MapleStory Skill Tracker"])

MODULE_DIR = Path(__file__).parent
DATA_DIR = MODULE_DIR.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "maple_skills.json"
CUSTOM_PRESETS_FILE = DATA_DIR / "maple_custom_presets.json"


# =============================================================================
# ⌨️ 2. Windows 가상 키코드 (Virtual Key Codes) 완벽 매핑 테이블
# =============================================================================
KEY_MAP: Dict[str, List[int]] = {
    # 1) Modifier & Special Control Keys
    "shift": [0x10, 0xA0, 0xA1], "lshift": [0xA0], "rshift": [0xA1],
    "ctrl": [0x11, 0xA2, 0xA3], "lctrl": [0xA2], "rctrl": [0xA3],
    "alt": [0x12, 0xA4, 0xA5], "lalt": [0xA4], "ralt": [0xA5],
    "space": [0x20], "spacebar": [0x20], "tab": [0x09], "capslock": [0x14],
    "esc": [0x1B], "escape": [0x1B], "enter": [0x0D], "return": [0x0D],

    # 2) Navigation & Edit Cluster
    "ins": [0x2D], "insert": [0x2D], "del": [0x2E], "delete": [0x2E],
    "home": [0x24], "end": [0x23], "pgup": [0x21], "pageup": [0x21],
    "pgdn": [0x22], "pagedown": [0x22],
    "left": [0x25], "up": [0x26], "right": [0x27], "down": [0x28],

    # 3) Alphabet (A ~ Z)
    "a": [0x41], "b": [0x42], "c": [0x43], "d": [0x44], "e": [0x45],
    "f": [0x46], "g": [0x47], "h": [0x48], "i": [0x49], "j": [0x4A],
    "k": [0x4B], "l": [0x4C], "m": [0x4D], "n": [0x4E], "o": [0x4F],
    "p": [0x50], "q": [0x51], "r": [0x52], "s": [0x53], "t": [0x54],
    "u": [0x55], "v": [0x56], "w": [0x57], "x": [0x58], "y": [0x59], "z": [0x5A],

    # 4) Top-Row Numbers (0 ~ 9)
    "1": [0x31], "2": [0x32], "3": [0x33], "4": [0x34], "5": [0x35],
    "6": [0x36], "7": [0x37], "8": [0x38], "9": [0x39], "0": [0x30],

    # 5) NumPad Numbers & Operations
    "num0": [0x60], "numpad0": [0x60], "num1": [0x61], "numpad1": [0x61],
    "num2": [0x62], "numpad2": [0x62], "num3": [0x63], "numpad3": [0x63],
    "num4": [0x64], "numpad4": [0x64], "num5": [0x65], "numpad5": [0x65],
    "num6": [0x66], "numpad6": [0x66], "num7": [0x67], "numpad7": [0x67],
    "num8": [0x68], "numpad8": [0x68], "num9": [0x69], "numpad9": [0x69],
    "num*": [0x6A], "numpad*": [0x6A], "num+": [0x6B], "numpad+": [0x6B],
    "num-": [0x6D], "numpad-": [0x6D], "num.": [0x6E], "numpad.": [0x6E],
    "num/": [0x6F], "numpad/": [0x6F],

    # 6) Function Keys (F1 ~ F12)
    "f1": [0x70], "f2": [0x71], "f3": [0x72], "f4": [0x73],
    "f5": [0x74], "f6": [0x75], "f7": [0x76], "f8": [0x77],
    "f9": [0x78], "f10": [0x79], "f11": [0x7A], "f12": [0x7B],

    # 7) Punctuation & Symbols
    "`": [0xC0], "~": [0xC0], "tilde": [0xC0],
    "-": [0xBD], "=": [0xBB], "[": [0xDB], "]": [0xDD], "\\": [0xDC],
    ";": [0xBA], "'": [0xDE], ",": [0xBC], ".": [0xBE], "/": [0xBF],

    # 8) Mouse Buttons
    "lbutton": [0x01], "rbutton": [0x02], "mbutton": [0x04],
    "xbutton1": [0x05], "xbutton2": [0x06]
}


def is_key_pressed(key_name: Optional[str]) -> bool:
    """단축키 입력 여부를 대소문자/특수키 무관하게 0.00ms 오차 없이 정밀 감지"""
    if not key_name:
        return False
    clean = str(key_name).strip().lower()
    vks = KEY_MAP.get(clean)
    if not vks:
        if len(clean) == 1:
            vks = [ord(clean.upper())]
        else:
            return False
    for vk in vks:
        st = ctypes.windll.user32.GetAsyncKeyState(vk)
        if (st & 0x8000) != 0 or (st & 0x0001) != 0:
            return True
    return False


# =============================================================================
# 📦 3. Pydantic 요청 모델 정의
# =============================================================================
class SkillConfigItem(BaseModel):
    name: str = Field(..., description="스킬명 (예: 제네시스 무적기, 오리진 극딜)")
    category: str = Field("defense", description="분류 (defense: 무적/방어, burst: 극딜, bind: 바인드, buff: 버프/준극딜, boss: 보스패턴)")
    cooldown_sec: float = Field(..., ge=1.0, description="쿨타임 (초 단위, 예: 180)")
    warn_before: float = Field(5.0, ge=1.0, description="쿨타임 종료 몇 초 전에 말해줄지 (초 단위, 예: 5.0)")
    key_bind: Optional[str] = Field("shift", description="인게임 단축키 (예: shift, ctrl, z, x, a, s, d, 1, 2, ins, del)")
    voice_text: Optional[str] = Field(None, description="스카디가 말할 맞춤 대사 (미입력 시 기본 대사 자동 적용)")
    slot_id: int = Field(1, ge=1, le=12, description="퀵슬롯 번호 (1~12)")


class SkillEditRequest(BaseModel):
    original_name: str = Field(..., description="수정 전 기존 스킬명")
    item: SkillConfigItem = Field(..., description="수정할 새 스킬 설정")


# =============================================================================
# 🎮 4. 메이플스토리 전 직업(47+) & 상위 8대 보스 레이드 전술 프리셋 마스터 DB
# =============================================================================
PRESET_CATEGORIES: Dict[str, List[str]] = {
    "🌟 공통 & 추천": ["공통 (기본)", "공통 (5차/6차 오리진)"],
    "⚔️ 모험가 전사": ["히어로", "팔라딘", "다크나이트"],
    "🔮 모험가 마법사": ["아크메이지(불,독)", "아크메이지(썬,콜)", "비숍"],
    "🏹 모험가 궁수": ["보우마스터", "신궁", "패스파인더"],
    "🗡️ 모험가 도적": ["나이트로드", "섀도어", "듀얼블레이드"],
    "⚓ 모험가 해적": ["바이퍼", "캡틴", "캐논슈터"],
    "🦅 시그너스 기사단": ["소울마스터", "미하일", "플레임위자드", "윈드브레이커", "나이트워커", "스트라이커"],
    "👑 영웅": ["아란", "에반", "루미너스", "메르세데스", "팬텀", "은월"],
    "⚙️ 레지스탕스 / 데몬 / 제논": ["블래스터", "배틀메이지", "와일드헌터", "메카닉", "제논", "데몬슬레이어", "데몬어벤져"],
    "🐉 노바 / 레프 / 아니마": ["카이저", "카데나", "카인", "엔젤릭버스터", "아크", "일리움", "칼리", "호영", "라라"],
    "🌌 초월자 / 키네시스 / 린": ["제로", "키네시스", "린"],
    "👾 보스 레이드 전술 타이머": [
        "[보스] 검은 마법사", "[보스] 선택받은 세렌", "[보스] 감시자 칼로스", "[보스] 카링",
        "[보스] 림보", "[보스] 진 힐라", "[보스] 루시드", "[보스] 윌"
    ]
}

JOB_PRESETS: Dict[str, List[Dict[str, Any]]] = {
    # 1. 공통
    "공통 (기본)": [
        {"name": "방어 무적기", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "방어 스킬 쿨 5초 남았어.", "slot_id": 1},
        {"name": "극딜 버프기", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "ctrl", "voice_text": "극딜 버프 10초 전이야, 준비해.", "slot_id": 2},
        {"name": "에르다 노바 (바인드)", "category": "bind", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "바인드 준비 완료! 극딜 타이밍이야.", "slot_id": 3},
        {"name": "제네시스 무적기", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "key_bind": "x", "voice_text": "제네시스 무적 5초 전이야.", "slot_id": 4},
        {"name": "솔 야누스 (설치)", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "5", "voice_text": "야누스 재설치 5초 전.", "slot_id": 5},
    ],
    "공통 (5차/6차 오리진)": [
        {"name": "6차 오리진 극딜", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "6차 오리진 극딜 15초 전이야.", "slot_id": 1},
        {"name": "에르다 노바", "category": "bind", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "5차 바인드 5초 전.", "slot_id": 2},
        {"name": "스인미 / 크오솔", "category": "burst", "cooldown_sec": 240.0, "warn_before": 10.0, "key_bind": "f1", "voice_text": "스인미 크오솔 10초 전이야.", "slot_id": 3},
        {"name": "제네시스 무적기", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "key_bind": "x", "voice_text": "제네시스 무적 5초 전.", "slot_id": 4},
        {"name": "시드링 (웨펲/리레)", "category": "buff", "cooldown_sec": 180.0, "warn_before": 5.0, "key_bind": "c", "voice_text": "특수 링 쿨 5초 전.", "slot_id": 5},
    ],

    # 2. 모험가 전사
    "히어로": [
        {"name": "콤보 데스폴트", "category": "defense", "cooldown_sec": 20.0, "warn_before": 3.0, "key_bind": "a", "voice_text": "데스폴트 무적 3초 전.", "slot_id": 1},
        {"name": "소드 일루전", "category": "buff", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "일루전 5초 남았어.", "slot_id": 2},
        {"name": "콤보 인스팅트", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "인스팅트 극딜 10초 전이야.", "slot_id": 3},
        {"name": "발할라 & 오라", "category": "buff", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "r", "voice_text": "발할라 쿨 5초 전.", "slot_id": 4},
        {"name": "에르다 노바", "category": "bind", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "바인드 5초 전이야.", "slot_id": 5},
        {"name": "스피릿 칼리버", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "스피릿 칼리버 15초 전.", "slot_id": 6},
    ],
    "팔라딘": [
        {"name": "생크추어리", "category": "buff", "cooldown_sec": 14.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "생크추어리 쿨 돌았어.", "slot_id": 1},
        {"name": "블래스드 해머", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "블래스드 해머 5초 전이야.", "slot_id": 2},
        {"name": "그랜드 크로스", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "그랜드 크로스 10초 전이야.", "slot_id": 3},
        {"name": "홀리 유니티", "category": "buff", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "r", "voice_text": "홀리 유니티 5초 전.", "slot_id": 4},
        {"name": "새크로생티티", "category": "defense", "cooldown_sec": 300.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "새크로 무적 10초 전.", "slot_id": 5},
        {"name": "세크리드 바스티온", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "세크리드 바스티온 15초 전.", "slot_id": 6},
    ],
    "다크나이트": [
        {"name": "다크 스피어", "category": "buff", "cooldown_sec": 10.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "다크 스피어 쿨 돌았어.", "slot_id": 1},
        {"name": "비홀더 임팩트", "category": "buff", "cooldown_sec": 20.0, "warn_before": 3.0, "key_bind": "w", "voice_text": "비홀더 임팩트 준비 완료.", "slot_id": 2},
        {"name": "피어스 사이클론", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "피어스 사이클론 10초 전.", "slot_id": 3},
        {"name": "다크니스 오라", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "r", "voice_text": "다크니스 오라 10초 전이야.", "slot_id": 4},
        {"name": "리인카네이션", "category": "defense", "cooldown_sec": 540.0, "warn_before": 30.0, "key_bind": "shift", "voice_text": "리인카네이션 쿨 30초 전.", "slot_id": 5},
        {"name": "데드 스페이스", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "데드 스페이스 15초 전.", "slot_id": 6},
    ],

    # 3. 모험가 마법사
    "아크메이지(불,독)": [
        {"name": "도트 퍼니셔", "category": "buff", "cooldown_sec": 25.0, "warn_before": 3.0, "key_bind": "q", "voice_text": "도트 퍼니셔 쿨 돌았어.", "slot_id": 1},
        {"name": "포이즌 노바", "category": "buff", "cooldown_sec": 25.0, "warn_before": 3.0, "key_bind": "w", "voice_text": "포이즌 노바 준비 완료.", "slot_id": 2},
        {"name": "포이즌 체인", "category": "buff", "cooldown_sec": 25.0, "warn_before": 3.0, "key_bind": "e", "voice_text": "포이즌 체인 준비 완료.", "slot_id": 3},
        {"name": "퓨리 오브 이프리트", "category": "burst", "cooldown_sec": 75.0, "warn_before": 5.0, "key_bind": "r", "voice_text": "이프리트 극딜 5초 전.", "slot_id": 4},
        {"name": "메기도 플레임", "category": "buff", "cooldown_sec": 50.0, "warn_before": 5.0, "key_bind": "a", "voice_text": "메기도 플레임 5초 전.", "slot_id": 5},
        {"name": "인페르날 베놈", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "인페르날 베놈 15초 전.", "slot_id": 6},
    ],
    "아크메이지(썬,콜)": [
        {"name": "썬더 브레이크", "category": "buff", "cooldown_sec": 40.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "썬더 브레이크 5초 전이야.", "slot_id": 1},
        {"name": "쥬피터 썬더", "category": "buff", "cooldown_sec": 75.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "쥬피터 썬더 5초 전.", "slot_id": 2},
        {"name": "아이스 에이지", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "e", "voice_text": "아이스 에이지 5초 전이야.", "slot_id": 3},
        {"name": "프리징 브레스", "category": "bind", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "프리징 브레스 5초 전.", "slot_id": 4},
        {"name": "인피니티", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "인피니티 극딜 10초 전이야.", "slot_id": 5},
        {"name": "프로즌 라이트닝", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "프로즌 라이트닝 15초 전.", "slot_id": 6},
    ],
    "비숍": [
        {"name": "홀리 매직쉘", "category": "defense", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "a", "voice_text": "매직쉘 쿨 5초 전이야.", "slot_id": 1},
        {"name": "피스메이커", "category": "buff", "cooldown_sec": 10.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "피스메이커 쿨 돌았어.", "slot_id": 2},
        {"name": "프레이 & 리브라", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "s", "voice_text": "프레이 10초 전이야, 파티원 모여.", "slot_id": 3},
        {"name": "제네시스 무적기", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "제네시스 무적기 5초 전.", "slot_id": 4},
        {"name": "에르다 노바", "category": "bind", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "바인드 5초 전이야.", "slot_id": 5},
        {"name": "홀리 어드밴트", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "홀리 어드밴트 15초 전이야.", "slot_id": 6},
    ],

    # 4. 모험가 궁수
    "보우마스터": [
        {"name": "잔영의 시", "category": "buff", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "잔영의 시 5초 전이야.", "slot_id": 1},
        {"name": "애로우 레인", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "애로우 레인 10초 전이야.", "slot_id": 2},
        {"name": "퀴버 풀버스트", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "퀴버 풀버스트 10초 전.", "slot_id": 3},
        {"name": "실루엣 미라주", "category": "defense", "cooldown_sec": 50.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "실루엣 미라주 충전 완료.", "slot_id": 4},
        {"name": "어센던트 쉐이드", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "어센던트 쉐이드 15초 전.", "slot_id": 5},
    ],
    "신궁": [
        {"name": "트루 스나이핑", "category": "defense", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "트루 스나이핑 5초 전이야.", "slot_id": 1},
        {"name": "스플릿 애로우", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "스플릿 애로우 10초 전이야.", "slot_id": 2},
        {"name": "리피팅 카트리지", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "리피팅 카트리지 10초 전.", "slot_id": 3},
        {"name": "불스아이", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "r", "voice_text": "불스아이 쿨 5초 전.", "slot_id": 4},
        {"name": "신궁유전", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "신궁유전 극딜 15초 전.", "slot_id": 5},
    ],
    "패스파인더": [
        {"name": "얼티밋 블래스트", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "q", "voice_text": "얼티밋 블래스트 10초 전.", "slot_id": 1},
        {"name": "레이븐 템페스트", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "레이븐 템페스트 10초 전.", "slot_id": 2},
        {"name": "렐릭 언바운드", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "렐릭 언바운드 10초 전.", "slot_id": 3},
        {"name": "옵시디언 배리어", "category": "defense", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "옵시디언 배리어 5초 전.", "slot_id": 4},
        {"name": "포세이큰 렐릭", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "포세이큰 렐릭 15초 전.", "slot_id": 5},
    ],

    # 5. 모험가 도적
    "나이트로드": [
        {"name": "스프레드 스로우", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "s", "voice_text": "스프레드 극딜 10초 전이야.", "slot_id": 1},
        {"name": "스로우 블래스팅", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "스로우 블래스팅 10초 전.", "slot_id": 2},
        {"name": "풍마수리검", "category": "buff", "cooldown_sec": 25.0, "warn_before": 3.0, "key_bind": "w", "voice_text": "풍마 수리검 쿨 돌았어.", "slot_id": 3},
        {"name": "레디 투 다이", "category": "burst", "cooldown_sec": 75.0, "warn_before": 5.0, "key_bind": "d", "voice_text": "레투다 쿨 5초 전이야.", "slot_id": 4},
        {"name": "얼티밋 다크 사이트", "category": "buff", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "얼닼사 10초 전이야.", "slot_id": 5},
        {"name": "생사여탈", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "생사여탈 극딜 15초 전.", "slot_id": 6},
    ],
    "섀도어": [
        {"name": "절개 (무적)", "category": "defense", "cooldown_sec": 14.0, "warn_before": 2.0, "key_bind": "a", "voice_text": "절개 무적 준비 완료.", "slot_id": 1},
        {"name": "소닉 블로우", "category": "burst", "cooldown_sec": 45.0, "warn_before": 5.0, "key_bind": "s", "voice_text": "소닉 블로우 5초 전이야.", "slot_id": 2},
        {"name": "멸귀참영진", "category": "burst", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "d", "voice_text": "멸귀참영진 5초 전.", "slot_id": 3},
        {"name": "연막탄", "category": "defense", "cooldown_sec": 150.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "연막탄 10초 전이야.", "slot_id": 4},
        {"name": "베일 오브 섀도우", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "베일 오브 섀도우 5초 전.", "slot_id": 5},
        {"name": "일도양단", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "일도양단 극딜 15초 전.", "slot_id": 6},
    ],
    "듀얼블레이드": [
        {"name": "블레이드 토네이도", "category": "buff", "cooldown_sec": 12.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "블토 쿨 돌았어.", "slot_id": 1},
        {"name": "카르마 퓨리", "category": "buff", "cooldown_sec": 10.0, "warn_before": 2.0, "key_bind": "w", "voice_text": "카퓨 쿨 돌았어.", "slot_id": 2},
        {"name": "사슬지옥 (무적)", "category": "defense", "cooldown_sec": 45.0, "warn_before": 5.0, "key_bind": "a", "voice_text": "사슬지옥 무적 5초 전.", "slot_id": 3},
        {"name": "파이널 컷 (무적)", "category": "defense", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "s", "voice_text": "파이널 컷 5초 전이야.", "slot_id": 4},
        {"name": "블레이드 스톰", "category": "burst", "cooldown_sec": 90.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "블레이드 스톰 10초 전이야.", "slot_id": 5},
        {"name": "카르마 블레이드", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "카르마 블레이드 15초 전.", "slot_id": 6},
    ],

    # 6. 모험가 해적
    "바이퍼": [
        {"name": "하울링 피스트", "category": "burst", "cooldown_sec": 90.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "하울링 피스트 10초 전이야.", "slot_id": 1},
        {"name": "라이트닝 폼", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "r", "voice_text": "라이트닝 폼 10초 전.", "slot_id": 2},
        {"name": "서펜트 스크류", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "서펜트 스크류 확인.", "slot_id": 3},
        {"name": "에르다 노바", "category": "bind", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "바인드 5초 전이야.", "slot_id": 4},
        {"name": "리버레이트 넵투누스", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "넵투누스 극딜 15초 전.", "slot_id": 5},
    ],
    "캡틴": [
        {"name": "불릿 파티", "category": "burst", "cooldown_sec": 75.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "불릿 파티 5초 전이야.", "slot_id": 1},
        {"name": "데스 트리거", "category": "buff", "cooldown_sec": 45.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "데스 트리거 5초 전.", "slot_id": 2},
        {"name": "노틸러스 어썰트", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "노틸러스 어썰트 10초 전이야.", "slot_id": 3},
        {"name": "드루이드 캡틴", "category": "buff", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "r", "voice_text": "드루이드 캡틴 5초 전.", "slot_id": 4},
        {"name": "드레드노트", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "드레드노트 극딜 15초 전.", "slot_id": 5},
    ],
    "캐논슈터": [
        {"name": "빅 휴즈 캐논볼", "category": "burst", "cooldown_sec": 25.0, "warn_before": 3.0, "key_bind": "q", "voice_text": "코코볼 장전 완료.", "slot_id": 1},
        {"name": "ICBM (무적)", "category": "defense", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "a", "voice_text": "ICBM 무적 5초 전이야.", "slot_id": 2},
        {"name": "롤링 캐논 레인보우", "category": "buff", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "e", "voice_text": "레인보우 5초 전.", "slot_id": 3},
        {"name": "서포트 몽키 트윈스", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "몽키 트윈스 5초 전.", "slot_id": 4},
        {"name": "슈퍼 캐논 익스플로전", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "슈퍼 캐논 익스플로전 15초 전.", "slot_id": 5},
    ],

    # 7. 시그너스 기사단
    "소울마스터": [
        {"name": "코스모스", "category": "buff", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "코스모스 쿨 5초 전.", "slot_id": 1},
        {"name": "셀레스티얼 댄스", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "셀레스티얼 댄스 10초 전이야.", "slot_id": 2},
        {"name": "엘리시온", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "엘리시온 극딜 10초 전이야.", "slot_id": 3},
        {"name": "소울 이클립스", "category": "defense", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "이클립스 무적 10초 전.", "slot_id": 4},
        {"name": "아스트랄 블리츠", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "아스트랄 블리츠 15초 전.", "slot_id": 5},
    ],
    "미하일": [
        {"name": "로얄 가드", "category": "defense", "cooldown_sec": 6.0, "warn_before": 1.0, "key_bind": "a", "voice_text": "로얄 가드 준비.", "slot_id": 1},
        {"name": "클라우 솔라스", "category": "buff", "cooldown_sec": 12.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "클라우 솔라스 쿨 돌았어.", "slot_id": 2},
        {"name": "소드 오브 소울라이트", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "소울라이트 10초 전이야.", "slot_id": 3},
        {"name": "로 아이아스", "category": "defense", "cooldown_sec": 300.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "로 아이아스 10초 전이야.", "slot_id": 4},
        {"name": "듀란달", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "듀란달 극딜 15초 전.", "slot_id": 5},
    ],
    "플레임위자드": [
        {"name": "드래곤 슬레이브", "category": "buff", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "드래곤 슬레이브 5초 전이야.", "slot_id": 1},
        {"name": "인피니티 플 flame", "category": "burst", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "인피니티 플 flame 5초 전.", "slot_id": 2},
        {"name": "샐리맨더 미스칩", "category": "burst", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "e", "voice_text": "샐리맨더 미스칩 5초 전이야.", "slot_id": 3},
        {"name": "에르다 노바", "category": "bind", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "바인드 5초 전.", "slot_id": 4},
        {"name": "이터니티", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "이터니티 극딜 15초 전.", "slot_id": 5},
    ],
    "윈드브레이커": [
        {"name": "볼텍스 스피어", "category": "buff", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "볼텍스 스피어 5초 전이야.", "slot_id": 1},
        {"name": "하울링 게일", "category": "buff", "cooldown_sec": 20.0, "warn_before": 3.0, "key_bind": "w", "voice_text": "하울링 게일 스택 장전.", "slot_id": 2},
        {"name": "윈드 월 (보호막)", "category": "defense", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "윈드 월 쿨 5초 전이야.", "slot_id": 3},
        {"name": "시그너스 팔랑크스", "category": "buff", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "e", "voice_text": "팔랑크스 5초 전.", "slot_id": 4},
        {"name": "미스트랄 스프링", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "미스트랄 스프링 15초 전.", "slot_id": 5},
    ],
    "나이트워커": [
        {"name": "쉐도우 바이트", "category": "buff", "cooldown_sec": 15.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "쉐도우 바이트 쿨 돌았어.", "slot_id": 1},
        {"name": "쉐도우 서번트 익스텐드", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "서번트 익스텐드 5초 전.", "slot_id": 2},
        {"name": "쉐도우 스피어", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "쉐도우 스피어 10초 전이야.", "slot_id": 3},
        {"name": "도미니언 (무적)", "category": "defense", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "도미니언 무적 10초 전.", "slot_id": 4},
        {"name": "사일런스", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "사일런스 극딜 15초 전.", "slot_id": 5},
    ],
    "스트라이커": [
        {"name": "뇌신창격", "category": "buff", "cooldown_sec": 7.0, "warn_before": 1.0, "key_bind": "q", "voice_text": "뇌신창격 쿨 돌았어.", "slot_id": 1},
        {"name": "창뇌연격 (무적/극딜)", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "창뇌연격 10초 전이야.", "slot_id": 2},
        {"name": "교도", "category": "buff", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "교도 5초 전.", "slot_id": 3},
        {"name": "신뇌합일", "category": "burst", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "r", "voice_text": "신뇌합일 5초 전이야.", "slot_id": 4},
        {"name": "뇌명벽해", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "뇌명벽해 극딜 15초 전.", "slot_id": 5},
    ],

    # 8. 영웅
    "아란": [
        {"name": "브랜디쉬 마하", "category": "buff", "cooldown_sec": 20.0, "warn_before": 3.0, "key_bind": "q", "voice_text": "브랜디쉬 마하 준비.", "slot_id": 1},
        {"name": "인스톨 마하", "category": "burst", "cooldown_sec": 150.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "인스톨 마하 10초 전이야.", "slot_id": 2},
        {"name": "마하의 영역 (무적)", "category": "defense", "cooldown_sec": 150.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "마하의 영역 5초 전이야.", "slot_id": 3},
        {"name": "아드레날린 제너레이터", "category": "burst", "cooldown_sec": 240.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "아드레날린 10초 전.", "slot_id": 4},
        {"name": "아드레날린 서지", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "아드레날린 서지 15초 전.", "slot_id": 5},
    ],
    "에반": [
        {"name": "드래곤 브레이크", "category": "buff", "cooldown_sec": 20.0, "warn_before": 3.0, "key_bind": "q", "voice_text": "드래곤 브레이크 준비.", "slot_id": 1},
        {"name": "엘리멘탈 블래스트", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "엘리멘탈 블래스트 5초 전.", "slot_id": 2},
        {"name": "조디악 레이", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "조디악 레이 극딜 10초 전이야.", "slot_id": 3},
        {"name": "드래곤 마스터 (무적)", "category": "defense", "cooldown_sec": 240.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "드래곤 마스터 무적 10초 전.", "slot_id": 4},
        {"name": "조디악 버스트", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "조디악 버스트 15초 전이야.", "slot_id": 5},
    ],
    "루미너스": [
        {"name": "퍼니싱 리소네이터", "category": "buff", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "퍼니싱 리소네이터 5초 전.", "slot_id": 1},
        {"name": "빛과 어둠의 세례", "category": "buff", "cooldown_sec": 45.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "빛과 어둠의 세례 5초 전.", "slot_id": 2},
        {"name": "진리의 문", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "진리의 문 10초 전이야.", "slot_id": 3},
        {"name": "아마겟돈", "category": "bind", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "아마겟돈 5초 전이야.", "slot_id": 4},
        {"name": "하모닉 패러독스", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "하모닉 패러독스 15초 전.", "slot_id": 5},
    ],
    "메르세데스": [
        {"name": "이르칼라의 숨결", "category": "burst", "cooldown_sec": 150.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "이르칼라 10초 전이야.", "slot_id": 1},
        {"name": "엘리멘탈 고스트", "category": "burst", "cooldown_sec": 150.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "엘리멘탈 고스트 10초 전이야.", "slot_id": 2},
        {"name": "로얄 나이츠 (무적)", "category": "defense", "cooldown_sec": 150.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "로얄 나이츠 5초 전.", "slot_id": 3},
        {"name": "프리드의 가호", "category": "defense", "cooldown_sec": 360.0, "warn_before": 10.0, "key_bind": "f", "voice_text": "프리드 10초 전이야.", "slot_id": 4},
        {"name": "언페이딩 글로리", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "언페이딩 글로리 15초 전.", "slot_id": 5},
    ],
    "팬텀": [
        {"name": "블랙잭", "category": "buff", "cooldown_sec": 15.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "블랙잭 쿨 돌았어.", "slot_id": 1},
        {"name": "마크 오브 팬텀", "category": "defense", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "a", "voice_text": "마크 오브 팬텀 5초 전.", "slot_id": 2},
        {"name": "리프트 브레이크", "category": "defense", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "s", "voice_text": "리프트 브레이크 5초 전.", "slot_id": 3},
        {"name": "조커 (극딜)", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "조커 극딜 10초 전이야.", "slot_id": 4},
        {"name": "파이널 컷", "category": "defense", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "파이널 컷 5초 전.", "slot_id": 5},
        {"name": "디파잉 페이트", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "디파잉 페이트 15초 전.", "slot_id": 6},
    ],
    "은월": [
        {"name": "정령의 화신 (무적)", "category": "defense", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "end", "voice_text": "정령의 화신 5초 전.", "slot_id": 1},
        {"name": "소혼장막", "category": "buff", "cooldown_sec": 74.0, "warn_before": 5.0, "key_bind": "del", "voice_text": "소혼 재설치 5초 전.", "slot_id": 2},
        {"name": "연우격풍", "category": "burst", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "4", "voice_text": "연우격풍 5초 전이야.", "slot_id": 3},
        {"name": "극딜 (정령집속)", "category": "burst", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "1", "voice_text": "극딜 5초 전이야.", "slot_id": 4},
        {"name": "파쇄 연권", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "r", "voice_text": "파쇄 연권 10초 전이야.", "slot_id": 5},
        {"name": "프리드의 가호", "category": "defense", "cooldown_sec": 360.0, "warn_before": 10.0, "key_bind": "f", "voice_text": "프리드 10초 전이야.", "slot_id": 6},
        {"name": "크오솔 (공용극딜)", "category": "burst", "cooldown_sec": 240.0, "warn_before": 10.0, "key_bind": "f1", "voice_text": "크오솔 10초 전이야.", "slot_id": 7},
        {"name": "제네시스 무적기", "category": "defense", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "x", "voice_text": "제네 무적 5초 전.", "slot_id": 8},
        {"name": "준극딜", "category": "burst", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "준극 5초 전이야.", "slot_id": 9},
        {"name": "호선 투귀권", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "호선 투귀권 15초 전.", "slot_id": 10},
    ],

    # 9. 레지스탕스 & 데몬 & 제논
    "데몬슬레이어": [
        {"name": "데몬 어웨이크닝", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "데몬 어웨이크닝 10초 전이야.", "slot_id": 1},
        {"name": "요르문간드", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "요르문간드 10초 전이야.", "slot_id": 2},
        {"name": "오르트로스", "category": "buff", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "r", "voice_text": "오르트로스 10초 전.", "slot_id": 3},
        {"name": "데몬 바인드", "category": "bind", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "v", "voice_text": "데몬 바인드 5초 전.", "slot_id": 4},
        {"name": "레이븐 스톰 (무적)", "category": "defense", "cooldown_sec": 5.0, "warn_before": 1.0, "key_bind": "a", "voice_text": "레이븐 스톰 준비.", "slot_id": 5},
        {"name": "나이트메어", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "나이트메어 극딜 15초 전.", "slot_id": 6},
    ],
    "데몬어벤져": [
        {"name": "블러드 피스트", "category": "buff", "cooldown_sec": 10.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "블러드 피스트 쿨 돌았어.", "slot_id": 1},
        {"name": "디멘션 소드", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "디멘션 소드 10초 전이야.", "slot_id": 2},
        {"name": "레버넌트 (불사)", "category": "defense", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "레버넌트 불사 5초 전.", "slot_id": 3},
        {"name": "사우전드 소드", "category": "buff", "cooldown_sec": 8.0, "warn_before": 1.0, "key_bind": "w", "voice_text": "사우전드 소드 쿨 돌았어.", "slot_id": 4},
        {"name": "레퀴엠", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "레퀴엠 극딜 15초 전.", "slot_id": 5},
    ],
    "블래스터": [
        {"name": "발칸 펀치", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "발칸 펀치 5초 전이야.", "slot_id": 1},
        {"name": "벙커 버스터", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "벙커 버스터 10초 전이야.", "slot_id": 2},
        {"name": "버닝 브레이커", "category": "burst", "cooldown_sec": 100.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "버닝 브레이커 10초 전이야.", "slot_id": 3},
        {"name": "애프터미지 펀치", "category": "buff", "cooldown_sec": 15.0, "warn_before": 2.0, "key_bind": "a", "voice_text": "애프터미지 쿨 돌았어.", "slot_id": 4},
        {"name": "파이널 디스트로이어", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "파이널 디스트로이어 15초 전.", "slot_id": 5},
    ],
    "배틀메이지": [
        {"name": "블랙 매직 알터", "category": "buff", "cooldown_sec": 35.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "매직 알터 5초 전이야.", "slot_id": 1},
        {"name": "그림 리퍼", "category": "burst", "cooldown_sec": 100.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "그림 리퍼 10초 전이야.", "slot_id": 2},
        {"name": "유니온 오라", "category": "burst", "cooldown_sec": 100.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "유니온 오라 10초 전이야.", "slot_id": 3},
        {"name": "쉘터 (무적)", "category": "defense", "cooldown_sec": 180.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "쉘터 방어 5초 전.", "slot_id": 4},
        {"name": "크림슨 팩트", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "크림슨 팩트 15초 전.", "slot_id": 5},
    ],
    "와일드헌터": [
        {"name": "재규어 맥시멈", "category": "defense", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "a", "voice_text": "재규어 맥시멈 5초 전.", "slot_id": 1},
        {"name": "재규어 스톰", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "재규어 스톰 10초 전이야.", "slot_id": 2},
        {"name": "와일드 발칸 Type X", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "발칸 Type X 10초 전이야.", "slot_id": 3},
        {"name": "드릴 컨테이너", "category": "buff", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "드릴 컨테이너 5초 전.", "slot_id": 4},
        {"name": "네이처스 빌리프", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "네이처스 빌리프 15초 전.", "slot_id": 5},
    ],
    "메카닉": [
        {"name": "마이크로 미사일", "category": "buff", "cooldown_sec": 25.0, "warn_before": 3.0, "key_bind": "q", "voice_text": "마이크로 미사일 준비 완료.", "slot_id": 1},
        {"name": "메탈아머 전탄발사", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "전탄발사 극딜 10초 전이야.", "slot_id": 2},
        {"name": "메카 캐리어", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "메카 캐리어 10초 전.", "slot_id": 3},
        {"name": "워머신 타이탄", "category": "defense", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "워머신 타이탄 5초 전.", "slot_id": 4},
        {"name": "그라운드 제로", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "그라운드 제로 15초 전.", "slot_id": 5},
    ],
    "제논": [
        {"name": "포톤 레이", "category": "buff", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "포톤 레이 5초 전이야.", "slot_id": 1},
        {"name": "홀로그램 융합", "category": "buff", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "홀로그램 융합 5초 전.", "slot_id": 2},
        {"name": "메가 스매셔", "category": "burst", "cooldown_sec": 180.0, "warn_before": 15.0, "key_bind": "e", "voice_text": "메가 스매셔 15초 전이야, 차징 준비해.", "slot_id": 3},
        {"name": "오버로드 모드", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "r", "voice_text": "오버로드 모드 10초 전.", "slot_id": 4},
        {"name": "멜트다운 익스플로전", "category": "defense", "cooldown_sec": 50.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "멜트다운 무적 5초 전.", "slot_id": 5},
        {"name": "아티피셜 에볼루션", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "아티피셜 에볼루션 15초 전.", "slot_id": 6},
    ],

    # 10. 노바 & 레프 & 아니마
    "카이저": [
        {"name": "드라코 슬래셔", "category": "buff", "cooldown_sec": 5.0, "warn_before": 1.0, "key_bind": "q", "voice_text": "드라코 슬래셔 쿨 돌았어.", "slot_id": 1},
        {"name": "윌 오브 소드", "category": "buff", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "윌 오브 소드 5초 전.", "slot_id": 2},
        {"name": "가디언 오브 노바", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "가디언 오브 노바 10초 전이야.", "slot_id": 3},
        {"name": "드래곤 블레이즈", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "r", "voice_text": "드래곤 블레이즈 10초 전.", "slot_id": 4},
        {"name": "프로미넌스", "category": "defense", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "프로미넌스 무적 5초 전.", "slot_id": 5},
        {"name": "마이트 오브 노바", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "마이트 오브 노바 15초 전.", "slot_id": 6},
    ],
    "카데나": [
        {"name": "A.D 오드넌스", "category": "buff", "cooldown_sec": 25.0, "warn_before": 3.0, "key_bind": "q", "voice_text": "오드넌스 장전 완료.", "slot_id": 1},
        {"name": "체인아츠:메일스트롬", "category": "buff", "cooldown_sec": 10.0, "warn_before": 2.0, "key_bind": "w", "voice_text": "메일스트롬 준비.", "slot_id": 2},
        {"name": "체인아츠:퓨리", "category": "burst", "cooldown_sec": 150.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "체인아츠 퓨리 10초 전이야.", "slot_id": 3},
        {"name": "무기 버라이어티", "category": "buff", "cooldown_sec": 10.0, "warn_before": 2.0, "key_bind": "a", "voice_text": "피날레 쿨 돌았어.", "slot_id": 4},
        {"name": "체인아츠:마사커", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "체인아츠 마사커 15초 전.", "slot_id": 5},
    ],
    "카인": [
        {"name": "스니키 스나이핑", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "스니키 스나이핑 5초 전이야.", "slot_id": 1},
        {"name": "페이탈 블리츠", "category": "buff", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "페이탈 블리츠 5초 전.", "slot_id": 2},
        {"name": "드래곤 버스트", "category": "burst", "cooldown_sec": 90.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "드래곤 버스트 10초 전이야.", "slot_id": 3},
        {"name": "타나토스 디센트", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "r", "voice_text": "타나토스 디센트 10초 전이야.", "slot_id": 4},
        {"name": "어나이얼레이션", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "어나이얼레이션 15초 전.", "slot_id": 5},
    ],
    "엔젤릭버스터": [
        {"name": "트리니티 퓨전", "category": "buff", "cooldown_sec": 14.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "트리니티 퓨전 준비.", "slot_id": 1},
        {"name": "슈퍼 노바", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "슈퍼 노바 5초 전이야.", "slot_id": 2},
        {"name": "스포트라이트", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "스포트라이트 10초 전이야.", "slot_id": 3},
        {"name": "마스코트 패밀리어", "category": "burst", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "r", "voice_text": "마스코트 패밀리어 5초 전.", "slot_id": 4},
        {"name": "에너지 버스트", "category": "defense", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "에너지 버스트 5초 전이야.", "slot_id": 5},
        {"name": "그랜드 피날레", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "그랜드 피날레 극딜 15초 전.", "slot_id": 6},
    ],
    "아델": [
        {"name": "다이크 (무적기)", "category": "defense", "cooldown_sec": 30.0, "warn_before": 3.0, "key_bind": "shift", "voice_text": "다이크 무적기 쿨 돌았어.", "slot_id": 1},
        {"name": "리스토어 & 루인", "category": "burst", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "d", "voice_text": "루인 5초 전.", "slot_id": 2},
        {"name": "인피니트 (극딜)", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "s", "voice_text": "인피니트 극딜 10초 전이야.", "slot_id": 3},
        {"name": "매직 서킷 풀드라이브", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "풀드라이브 10초 전.", "slot_id": 4},
        {"name": "마에스트로", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "마에스트로 15초 전.", "slot_id": 5},
    ],
    "아크": [
        {"name": "끝나지 않는 흉몽", "category": "buff", "cooldown_sec": 20.0, "warn_before": 3.0, "key_bind": "e", "voice_text": "흉몽 쿨 돌았어.", "slot_id": 1},
        {"name": "영원히 굶주리는 짐승", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "q", "voice_text": "굶주리는 짐승 10초 전이야.", "slot_id": 2},
        {"name": "인피니티 스펠", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "인피니티 스펠 10초 전이야.", "slot_id": 3},
        {"name": "근원의 기억 (무적)", "category": "defense", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "근원의 기억 무적 10초 전이야.", "slot_id": 4},
        {"name": "새어 나오는 공포", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "새어 나오는 공포 15초 전.", "slot_id": 5},
    ],
    "일리움": [
        {"name": "소울 오브 크리스탈", "category": "buff", "cooldown_sec": 40.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "소울 오브 크리스탈 5초 전.", "slot_id": 1},
        {"name": "크리스탈 이그니션", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "크리스탈 이그니션 10초 전이야.", "slot_id": 2},
        {"name": "그람홀더", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "그람홀더 10초 전이야.", "slot_id": 3},
        {"name": "프라이멀 프로텍션", "category": "defense", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "프라이멀 프로텍션 10초 전.", "slot_id": 4},
        {"name": "언리미티드 크리스탈", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "언리미티드 크리스탈 15초 전.", "slot_id": 5},
    ],
    "칼리": [
        {"name": "보이드 블리츠", "category": "buff", "cooldown_sec": 12.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "보이드 블리츠 쿨 돌았어.", "slot_id": 1},
        {"name": "헥스:차크람 스플릿", "category": "buff", "cooldown_sec": 14.0, "warn_before": 2.0, "key_bind": "w", "voice_text": "차크람 스플릿 준비.", "slot_id": 2},
        {"name": "데스 블로섬", "category": "burst", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "e", "voice_text": "데스 블로섬 5초 전이야.", "slot_id": 3},
        {"name": "레조네이트:얼티메이텀", "category": "burst", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "r", "voice_text": "얼티메이텀 5초 전이야.", "slot_id": 4},
        {"name": "헥스:판데모니움 (무적)", "category": "defense", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "판데모니움 무적 10초 전.", "slot_id": 5},
        {"name": "헥스:산드롬", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "헥스 산드롬 15초 전이야.", "slot_id": 6},
    ],
    "호영": [
        {"name": "권술:미생강변", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "미생강변 5초 전이야.", "slot_id": 1},
        {"name": "선기:태을선인", "category": "buff", "cooldown_sec": 100.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "태을선인 5초 전.", "slot_id": 2},
        {"name": "산령소환", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "산령소환 10초 전이야.", "slot_id": 3},
        {"name": "선기:극대 분신난무", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "r", "voice_text": "분신난무 극딜 10초 전이야.", "slot_id": 4},
        {"name": "선기:괴력난신 (무적)", "category": "defense", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "괴력난신 10초 전이야.", "slot_id": 5},
        {"name": "선기:파천황", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "선기 파천황 15초 전.", "slot_id": 6},
    ],
    "라라": [
        {"name": "솟아라 용맥", "category": "buff", "cooldown_sec": 10.0, "warn_before": 2.0, "key_bind": "q", "voice_text": "용맥 준비 완료.", "slot_id": 1},
        {"name": "해 구출 작전", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "해 구출 작전 10초 전이야.", "slot_id": 2},
        {"name": "큰 기지개", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "큰 기지개 극딜 10초 전이야.", "slot_id": 3},
        {"name": "아름다운 드리움", "category": "defense", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "아름다운 드리움 10초 전.", "slot_id": 4},
        {"name": "새록새록 꽃피우는 마을", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "꽃피우는 마을 15초 전.", "slot_id": 5},
    ],

    # 11. 초월자 / 키네시스 / 린
    "제로": [
        {"name": "섀도우 플래시", "category": "buff", "cooldown_sec": 40.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "섀도우 플래시 5초 전이야.", "slot_id": 1},
        {"name": "에고 웨폰", "category": "buff", "cooldown_sec": 15.0, "warn_before": 2.0, "key_bind": "w", "voice_text": "에고 웨폰 준비 완료.", "slot_id": 2},
        {"name": "조인트 어택 (무적)", "category": "defense", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "조인트 어택 10초 전이야.", "slot_id": 3},
        {"name": "리미트 브레이크 (바인드)", "category": "bind", "cooldown_sec": 240.0, "warn_before": 10.0, "key_bind": "v", "voice_text": "리미트 브레이크 10초 전.", "slot_id": 4},
        {"name": "타임 홀딩 (무적)", "category": "defense", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "shift", "voice_text": "타임 홀딩 무적 10초 전.", "slot_id": 5},
        {"name": "크로노 트리거", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "크로노 트리거 15초 전이야.", "slot_id": 6},
    ],
    "키네시스": [
        {"name": "로 오브 그라비티", "category": "buff", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "q", "voice_text": "그라비티 5초 전이야.", "slot_id": 1},
        {"name": "무빙 매터", "category": "buff", "cooldown_sec": 90.0, "warn_before": 5.0, "key_bind": "w", "voice_text": "무빙 매터 5초 전.", "slot_id": 2},
        {"name": "싸이킥 토네이도", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "싸이킥 토네이도 10초 전이야.", "slot_id": 3},
        {"name": "에버싸이킥 (무적)", "category": "defense", "cooldown_sec": 120.0, "warn_before": 5.0, "key_bind": "shift", "voice_text": "에버싸이킥 무적 5초 전.", "slot_id": 4},
        {"name": "이계의 웅덩이", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "이계의 웅덩이 15초 전.", "slot_id": 5},
    ],
    "린": [
        {"name": "생명의 샘", "category": "defense", "cooldown_sec": 60.0, "warn_before": 5.0, "key_bind": "a", "voice_text": "생명의 샘 5초 전이야.", "slot_id": 1},
        {"name": "숲의 안식", "category": "buff", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "w", "voice_text": "숲의 안식 10초 전이야.", "slot_id": 2},
        {"name": "베어 스트라이크", "category": "burst", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "e", "voice_text": "베어 스트라이크 10초 전.", "slot_id": 3},
        {"name": "포레스트 가디언", "category": "burst", "cooldown_sec": 180.0, "warn_before": 10.0, "key_bind": "r", "voice_text": "포레스트 가디언 10초 전.", "slot_id": 4},
        {"name": "네이처 오리진", "category": "burst", "cooldown_sec": 360.0, "warn_before": 15.0, "key_bind": "6", "voice_text": "네이처 오리진 15초 전.", "slot_id": 5},
    ],

    # 12. 상위 8대 보스 레이드 전술 타이머
    "[보스] 검은 마법사": [
        {"name": "1페 권능 타이머", "category": "boss", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "1", "voice_text": "1페 권능 5초 전! 반대편 구석으로 피해.", "slot_id": 1},
        {"name": "2페 암흑 사선", "category": "boss", "cooldown_sec": 60.0, "warn_before": 10.0, "key_bind": "2", "voice_text": "2페 사선 10초 전! 보스 주변 사선 피해.", "slot_id": 2},
        {"name": "3페 대권능", "category": "boss", "cooldown_sec": 65.0, "warn_before": 10.0, "key_bind": "3", "voice_text": "3페 대권능 10초 전! 발판 위나 존 밖으로 피해.", "slot_id": 3},
        {"name": "3페 밀격 & 레이저", "category": "boss", "cooldown_sec": 15.0, "warn_before": 3.0, "key_bind": "4", "voice_text": "3페 밀격 주의, 슈스탠 대기.", "slot_id": 4},
        {"name": "4페 백/흑 탄막", "category": "boss", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "5", "voice_text": "4페 탄막 피하고 딜 집중해.", "slot_id": 5},
    ],
    "[보스] 선택받은 세렌": [
        {"name": "석양 권능", "category": "boss", "cooldown_sec": 100.0, "warn_before": 10.0, "key_bind": "1", "voice_text": "세렌 석양 권능 10초 전! 보호막 안으로 들어가.", "slot_id": 1},
        {"name": "자정 권능", "category": "boss", "cooldown_sec": 100.0, "warn_before": 10.0, "key_bind": "2", "voice_text": "세렌 자정 권능 10초 전! 검기 유도 조심해.", "slot_id": 2},
        {"name": "여명의 검 장판", "category": "boss", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "3", "voice_text": "여명의 검 5초 전, 장판 피해.", "slot_id": 3},
        {"name": "빛의 기둥 낙하", "category": "boss", "cooldown_sec": 15.0, "warn_before": 3.0, "key_bind": "4", "voice_text": "빛의 기둥 낙하 주의.", "slot_id": 4},
    ],
    "[보스] 감시자 칼로스": [
        {"name": "T-BOY 간섭 해제", "category": "boss", "cooldown_sec": 150.0, "warn_before": 15.0, "key_bind": "1", "voice_text": "칼로스 구속 해제 15초 전! 왼쪽 오른쪽 드론 해제해.", "slot_id": 1},
        {"name": "드론 광역 폭격", "category": "boss", "cooldown_sec": 40.0, "warn_before": 5.0, "key_bind": "2", "voice_text": "드론 폭격 5초 전, 안전 구역으로.", "slot_id": 2},
        {"name": "눈 레이저 발사", "category": "boss", "cooldown_sec": 25.0, "warn_before": 5.0, "key_bind": "3", "voice_text": "칼로스 눈 레이저 주의.", "slot_id": 3},
        {"name": "대권능 심판", "category": "boss", "cooldown_sec": 60.0, "warn_before": 10.0, "key_bind": "4", "voice_text": "칼로스 대권능 10초 전! 윗발판으로 대피.", "slot_id": 4},
    ],
    "[보스] 카링": [
        {"name": "사흉 밸런스 게이지", "category": "boss", "cooldown_sec": 60.0, "warn_before": 10.0, "key_bind": "1", "voice_text": "사흉 밸런스 게이지 10초 전! 게이지 조절해.", "slot_id": 1},
        {"name": "3페 합체 극딜", "category": "boss", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "2", "voice_text": "3페 합체 극딜 타이밍 10초 전!", "slot_id": 2},
        {"name": "벼락 장판", "category": "boss", "cooldown_sec": 20.0, "warn_before": 3.0, "key_bind": "3", "voice_text": "카링 벼락 장판 주의.", "slot_id": 3},
    ],
    "[보스] 림보": [
        {"name": "심연 침식 게이지", "category": "boss", "cooldown_sec": 60.0, "warn_before": 10.0, "key_bind": "1", "voice_text": "심연 침식 10초 전! 정화 발판 밟아.", "slot_id": 1},
        {"name": "근원의 폭발", "category": "boss", "cooldown_sec": 90.0, "warn_before": 10.0, "key_bind": "2", "voice_text": "근원의 폭발 10초 전! 무적기 준비.", "slot_id": 2},
        {"name": "촉수 강타", "category": "boss", "cooldown_sec": 15.0, "warn_before": 3.0, "key_bind": "3", "voice_text": "림보 촉수 강타 주의.", "slot_id": 3},
    ],
    "[보스] 진 힐라": [
        {"name": "영혼 낫베기", "category": "boss", "cooldown_sec": 150.0, "warn_before": 15.0, "key_bind": "1", "voice_text": "진힐라 낫베기 15초 전! 실 맞고 제단 풀어.", "slot_id": 1},
        {"name": "영혼 제단 생성", "category": "boss", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "2", "voice_text": "제단 생성 10초 전! 파티원 함께 채집해.", "slot_id": 2},
        {"name": "뼈 파동 & 유골", "category": "boss", "cooldown_sec": 30.0, "warn_before": 5.0, "key_bind": "3", "voice_text": "뼈 파동 주의, 뒤로 점프해.", "slot_id": 3},
        {"name": "독 구름 장판", "category": "boss", "cooldown_sec": 20.0, "warn_before": 3.0, "key_bind": "4", "voice_text": "독 장판 주의, 체력 관리해.", "slot_id": 4},
    ],
    "[보스] 루시드": [
        {"name": "1페 소환수/드래곤", "category": "boss", "cooldown_sec": 90.0, "warn_before": 10.0, "key_bind": "1", "voice_text": "루시드 소환수 10초 전! 나팔 불거나 발판 피해.", "slot_id": 1},
        {"name": "1페 강력한 폭탄", "category": "boss", "cooldown_sec": 45.0, "warn_before": 5.0, "key_bind": "2", "voice_text": "루시드 폭탄 5초 전! 파티원 모여서 같이 맞아.", "slot_id": 2},
        {"name": "2페 레이저 탄막", "category": "boss", "cooldown_sec": 90.0, "warn_before": 10.0, "key_bind": "3", "voice_text": "2페 레이저 탄막 10초 전! 외곽 발판으로 피해.", "slot_id": 3},
        {"name": "3페 45초 극딜", "category": "boss", "cooldown_sec": 45.0, "warn_before": 10.0, "key_bind": "4", "voice_text": "3페 극딜 10초 전! 시드링 켜고 올극딜!", "slot_id": 4},
    ],
    "[보스] 윌": [
        {"name": "1페 안경 거울 주시", "category": "boss", "cooldown_sec": 120.0, "warn_before": 15.0, "key_bind": "1", "voice_text": "1페 거울 주시 15초 전! 양쪽 방 체력 맞춰.", "slot_id": 1},
        {"name": "2페 달빛 거미 다리", "category": "boss", "cooldown_sec": 120.0, "warn_before": 10.0, "key_bind": "2", "voice_text": "2페 달빛 거미 다리 10초 전! 거울 보고 피해.", "slot_id": 2},
        {"name": "3페 흰눈/노란눈 밀격", "category": "boss", "cooldown_sec": 15.0, "warn_before": 3.0, "key_bind": "3", "voice_text": "윌 밀격 패턴! 노란눈은 가만히, 흰눈은 뒤로 피해.", "slot_id": 3},
        {"name": "3페 거미줄 정화", "category": "boss", "cooldown_sec": 60.0, "warn_before": 10.0, "key_bind": "4", "voice_text": "달빛으로 거미줄 지워.", "slot_id": 4},
    ]
}


# =============================================================================
# 📦 5. 런타임 추적 스킬 클래스
# =============================================================================
class TrackedSkill:
    """실시간 쿨타임 상태 머신"""
    def __init__(
        self,
        name: str,
        category: str,
        cooldown_sec: float,
        warn_before: float = 5.0,
        key_bind: Optional[str] = "shift",
        voice_text: Optional[str] = None,
        slot_id: int = 1
    ):
        self.name = name
        self.category = category
        self.cooldown_sec = float(cooldown_sec)
        self.warn_before = float(warn_before)
        self.key_bind = (key_bind or "").lower().strip()
        self.voice_text = voice_text or f"{name} 쿨 {int(warn_before)}초 남았어."
        self.slot_id = slot_id

        # 런타임 상태
        self.state = "READY"                  # READY | ON_COOLDOWN | WARNED
        self.cooldown_end_time = 0.0
        self.last_used_time = 0.0
        self.is_key_down = False              # 키 연타 중복 트리거 방지 플래그

    @property
    def remaining_sec(self) -> int:
        """남은 쿨타임(초) - 깔끔한 정수 단위"""
        if self.state == "READY":
            return 0
        rem = self.cooldown_end_time - time.time()
        return max(0, int(math.ceil(rem)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "cooldown_sec": self.cooldown_sec,
            "warn_before": self.warn_before,
            "key_bind": self.key_bind,
            "voice_text": self.voice_text,
            "remaining_sec": self.remaining_sec,
            "state": self.state,
            "slot_id": self.slot_id
        }


# =============================================================================
# 🔊 6. 스카디 음성 알림 발화기 (GPT-SoVITS / Edge-TTS 0ms 로컬 캐시 엔진)
# =============================================================================
class SkadiVoiceAnnouncer:
    GPT_SOVITS_URL = "http://127.0.0.1:9880"
    REF_AUDIO_PATH = MODULE_DIR.parent / "korean_skadi_voice" / "kor_skadi_ref_000.wav"
    REF_PROMPT_TEXT = "바닷물에서 떨어지면 우리 같은 건 살아남지 못할 줄 알았어?"
    VOICE_CACHE_DIR = MODULE_DIR.parent / "voice_cache" / "maple_skills"
    _speech_lock = threading.Lock()
    _init_done = False
    volume: int = 100  # 0 ~ 100%

    @classmethod
    def set_volume(cls, val: int):
        """음성 브리핑 볼륨 조절 (0~100%)"""
        cls.volume = max(0, min(100, int(val)))
        try:
            vol_16 = int((cls.volume / 100.0) * 0xFFFF)
            dw_volume = (vol_16 << 16) | vol_16
            ctypes.windll.winmm.waveOutSetVolume(0, dw_volume)
        except Exception:
            pass

    @classmethod
    def _ensure_dir(cls):
        if not cls._init_done:
            cls.VOICE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cls._init_done = True

    @classmethod
    def get_audio_path_for_text(cls, text: str) -> Path:
        """텍스트에 대한 고유 캐시 파일 경로 반환 (SoVITS WAV 우선)"""
        cls._ensure_dir()
        clean = text.strip()
        h = hashlib.md5(clean.encode('utf-8')).hexdigest()[:16]
        wav_p = cls.VOICE_CACHE_DIR / f"skadi_sovits_{h}.wav"
        if wav_p.exists() and wav_p.stat().st_size > 1000:
            return wav_p
        mp3_p = cls.VOICE_CACHE_DIR / f"skadi_edge_{h}.mp3"
        if mp3_p.exists() and mp3_p.stat().st_size > 1000:
            return mp3_p
        return wav_p

    @classmethod
    async def cache_audio(cls, text: str) -> Optional[str]:
        """스카디 AI 음성 모델로 사전 합성 및 영구 캐싱"""
        if not text or not text.strip():
            return None
        cls._ensure_dir()
        clean = text.strip()
        h = hashlib.md5(clean.encode('utf-8')).hexdigest()[:16]
        target_wav = cls.VOICE_CACHE_DIR / f"skadi_sovits_{h}.wav"

        if target_wav.exists() and target_wav.stat().st_size > 1000:
            return str(target_wav)

        # 1. 로컬 GPT-SoVITS AI 스카디 모델 호출
        try:
            import httpx
            ref_path_str = str(cls.REF_AUDIO_PATH.resolve()) if cls.REF_AUDIO_PATH.exists() else ""
            payload = {
                "text": clean,
                "text_lang": "ko",
                "ref_audio_path": ref_path_str,
                "prompt_text": cls.REF_PROMPT_TEXT,
                "prompt_lang": "ko",
                "top_k": 5,
                "top_p": 1,
                "temperature": 1,
                "speed": 1.0
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(f"{cls.GPT_SOVITS_URL}/tts", json=payload)
                if res.status_code == 200 and len(res.content) > 1000:
                    with open(target_wav, "wb") as f:
                        f.write(res.content)
                    return str(target_wav)
        except Exception:
            pass

        # 2. GPT-SoVITS 미가동 시 Edge-TTS 폴백
        target_mp3 = cls.VOICE_CACHE_DIR / f"skadi_edge_{h}.mp3"
        if target_mp3.exists() and target_mp3.stat().st_size > 1000:
            return str(target_mp3)

        try:
            if edge_tts:
                communicate = edge_tts.Communicate(clean, "ko-KR-SunHiNeural", rate="+0%", pitch="-2Hz")
                await communicate.save(str(target_mp3))
                return str(target_mp3)
        except Exception:
            pass
        return None

    @classmethod
    def stop_all_audio(cls):
        """재생 중인 모든 오디오 즉각 강제 중단"""
        try:
            ctypes.windll.winmm.mciSendStringW("stop all", None, 0, None)
            ctypes.windll.winmm.mciSendStringW("close all", None, 0, None)
        except Exception:
            pass

    @classmethod
    def play_file_sync(cls, file_path: str):
        """Windows Native MCI 엔진을 통해 0.00ms 오차 없이 즉각 재생"""
        if not file_path or not os.path.exists(file_path):
            return
        if cls.volume <= 0:
            return
        try:
            vol_16 = int((cls.volume / 100.0) * 0xFFFF)
            dw_volume = (vol_16 << 16) | vol_16
            ctypes.windll.winmm.waveOutSetVolume(0, dw_volume)

            abs_path = os.path.abspath(file_path)
            alias = f"skadi_maple_{int(time.time() * 1000) % 10000}"
            ext = os.path.splitext(abs_path)[1].lower()
            mci_type = "type waveaudio" if ext == ".wav" else "type mpegvideo"

            ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, None)
            ret = ctypes.windll.winmm.mciSendStringW(f'open "{abs_path}" {mci_type} alias {alias}', None, 0, None)
            if ret != 0:
                ret = ctypes.windll.winmm.mciSendStringW(f'open "{abs_path}" alias {alias}', None, 0, None)
            ctypes.windll.winmm.mciSendStringW(f'play {alias}', None, 0, None)
        except Exception as e:
            print(f"[스카디 음성 재생 오류]: {e}")

    @classmethod
    async def speak_text(cls, text: str):
        """사전 캐시된 오디오 파일을 즉시 꺼내어 0ms 로컬 재생"""
        if not text:
            return
        target_path = cls.get_audio_path_for_text(text)
        if target_path.exists() and target_path.stat().st_size > 1000:
            cls.play_file_sync(str(target_path))
        else:
            fpath = await cls.cache_audio(text)
            if fpath:
                cls.play_file_sync(fpath)

    @classmethod
    def preload_skills_background(cls, skills: List[Any]):
        """스킬 목록의 모든 예고 대사와 완료 대사를 백그라운드에서 사전 다운로드"""
        def _preload_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            for sk in skills:
                try:
                    if getattr(sk, 'voice_text', None):
                        loop.run_until_complete(cls.cache_audio(sk.voice_text))
                    name = getattr(sk, 'name', '')
                    if name:
                        loop.run_until_complete(cls.cache_audio(f"{name} 준비 완료!"))
                except Exception:
                    pass
            loop.close()

        t = threading.Thread(target=_preload_worker, daemon=True)
        t.start()


# =============================================================================
# 👁️ 7. 퀵슬롯 감시 & 쿨타임 자동 관리자
# =============================================================================
class MapleSkillWatcher:
    """게임 자동 감지 + 포커스 자율 활성화 + 단축키 0ms 트리거 + 쿨타임 실시간 관리 통합 엔진"""

    def __init__(self):
        self.is_running = True            # 기본 상시 감시 대기 (메이플 켜지고 포커스 시 즉시 작동)
        self.auto_manage = True           # 메이플 실행/포커스 시 완전 자동 시작 / 전환
        self.focus_filter_enabled = True  # 🔒 메이플스토리 활성창(포커스) 전용 감지 필터
        self.target_window_locked = False
        self.maple_pids = set()
        self._watcher_thread: Optional[threading.Thread] = None
        self.skills: List[TrackedSkill] = []
        self.current_preset_name: str = "공통 (기본)"
        self.load_custom_presets_from_file()
        self.load_skills_from_json()
        self._start_auto_lifecycle_watcher()
        self.start()                      # 백그라운드 리스너 루프 상시 시작 (포커스 필터로 안전 대기)

    def _start_auto_lifecycle_watcher(self):
        """메이플스토리 프로세스(MapleStory.exe) 실행 및 포커스 상태 상시 자동 감시 스레드"""
        def _lifecycle_loop():
            while True:
                try:
                    time.sleep(0.5)
                    # 1. 메이플 프로세스 PID 실시간 갱신 (모든 Maple 변종 프로세스 감지)
                    pids = set()
                    if psutil:
                        for p in psutil.process_iter(['pid', 'name']):
                            try:
                                pname = (p.info.get('name') or '').lower()
                                if 'maple' in pname:
                                    pids.add(p.info['pid'])
                            except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
                                pass
                    self.maple_pids = pids

                    if not self.auto_manage:
                        continue

                    running = len(self.maple_pids) > 0
                    if running and not self.is_running:
                        self.target_window_locked = True
                        self.start()
                        print("[🍁 Maple Auto] 메이플스토리 실행 감지! 스킬 쿨타임 & 음성 브리핑 자동 가동")
                    elif not running and self.is_running and self.target_window_locked:
                        self.target_window_locked = False
                except Exception:
                    pass

        t = threading.Thread(target=_lifecycle_loop, daemon=True, name="MapleLifecycleWatcher")
        t.start()

    def is_maple_active_window(self) -> bool:
        """현재 사용자가 메이플스토리 게임 창을 포커스(활성화)하고 있는지 0.00ms 초고속 검사"""
        if not self.focus_filter_enabled:
            return True
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False

            # 1. 활성 윈도우의 PID가 메이플 프로세스 PID인지 O(1) 초고속 확인
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if self.maple_pids and pid.value in self.maple_pids:
                return True

            # 2. 보조 윈도우 타이틀 및 클래스명 검사
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.lower()
                if "maplestory" in title or "메이플스토리" in title or "maple" in title:
                    if pid.value:
                        self.maple_pids.add(pid.value)
                    return True
        except Exception:
            pass
        return False

    def load_skills_from_json(self):
        """저장된 JSON 파일에서 스킬 목록 로드"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.skills = [
                        TrackedSkill(
                            name=s["name"],
                            category=s.get("category", "defense"),
                            cooldown_sec=s["cooldown_sec"],
                            warn_before=s.get("warn_before", 5.0),
                            key_bind=s.get("key_bind", "shift"),
                            voice_text=s.get("voice_text"),
                            slot_id=s.get("slot_id", 1)
                        ) for s in data
                    ]
                    SkadiVoiceAnnouncer.preload_skills_background(self.skills)
                    return
            except Exception:
                pass

        self.load_preset("공통 (기본)")

    def save_skills_to_json(self):
        """현재 스킬 설정을 JSON 파일로 영구 저장 및 음성 자동 프리캐싱"""
        data = [
            {
                "name": s.name,
                "category": s.category,
                "cooldown_sec": s.cooldown_sec,
                "warn_before": s.warn_before,
                "key_bind": s.key_bind,
                "voice_text": s.voice_text,
                "slot_id": s.slot_id
            } for s in self.skills
        ]
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        SkadiVoiceAnnouncer.preload_skills_background(self.skills)

    async def precache_current_skills(self) -> int:
        """현재 등록된 모든 스킬 음성 일괄 사전 합성 및 캐싱"""
        count = 0
        for sk in self.skills:
            if sk.voice_text:
                await SkadiVoiceAnnouncer.cache_audio(sk.voice_text)
                count += 1
            if sk.name:
                await SkadiVoiceAnnouncer.cache_audio(f"{sk.name} 준비 완료!")
                count += 1
        return count

    def load_preset(self, preset_name: str) -> bool:
        if preset_name not in JOB_PRESETS:
            return False
        preset_data = JOB_PRESETS[preset_name]
        self.current_preset_name = preset_name
        self.skills = [
            TrackedSkill(
                name=s["name"],
                category=s.get("category", "defense"),
                cooldown_sec=s["cooldown_sec"],
                warn_before=s.get("warn_before", 5.0),
                key_bind=s.get("key_bind", "shift"),
                voice_text=s.get("voice_text"),
                slot_id=s.get("slot_id", 1)
            ) for s in preset_data
        ]
        self.save_skills_to_json()
        return True

    def add_or_update_skill(self, item: SkillConfigItem):
        for i, sk in enumerate(self.skills):
            if sk.name == item.name:
                self.skills[i] = TrackedSkill(
                    name=item.name,
                    category=item.category,
                    cooldown_sec=item.cooldown_sec,
                    warn_before=item.warn_before,
                    key_bind=item.key_bind,
                    voice_text=item.voice_text,
                    slot_id=item.slot_id
                )
                self.save_skills_to_json()
                return

        self.skills.append(
            TrackedSkill(
                name=item.name,
                category=item.category,
                cooldown_sec=item.cooldown_sec,
                warn_before=item.warn_before,
                key_bind=item.key_bind,
                voice_text=item.voice_text,
                slot_id=item.slot_id
            )
        )
        self.save_skills_to_json()

    def delete_skill(self, skill_name: str) -> bool:
        original_len = len(self.skills)
        clean_target = skill_name.strip()
        self.skills = [s for s in self.skills if s.name.strip() != clean_target]
        if len(self.skills) < original_len:
            self.save_skills_to_json()
            SkadiVoiceAnnouncer.stop_all_audio()
            return True
        return False

    def edit_skill(self, original_name: str, item: SkillConfigItem) -> bool:
        """기존 스킬 정보 수정 (스킬명 변경 포함)"""
        target_idx = None
        for i, sk in enumerate(self.skills):
            if sk.name == original_name:
                target_idx = i
                break

        if target_idx is not None:
            self.skills[target_idx] = TrackedSkill(
                name=item.name,
                category=item.category,
                cooldown_sec=item.cooldown_sec,
                warn_before=item.warn_before,
                key_bind=item.key_bind,
                voice_text=item.voice_text,
                slot_id=item.slot_id
            )
            self.save_skills_to_json()
            return True
        return False

    def save_preset(self, preset_name: str) -> bool:
        """현재 스킬 구성을 새로운 직업/커스텀 프리셋으로 저장"""
        clean_name = preset_name.strip()
        if not clean_name:
            return False
        preset_data = [
            {
                "name": s.name,
                "category": s.category,
                "cooldown_sec": s.cooldown_sec,
                "warn_before": s.warn_before,
                "key_bind": s.key_bind,
                "voice_text": s.voice_text,
                "slot_id": s.slot_id
            } for s in self.skills
        ]
        JOB_PRESETS[clean_name] = preset_data
        self._save_custom_presets_to_file()
        return True

    def delete_preset(self, preset_name: str) -> bool:
        """지정한 프리셋 삭제"""
        if preset_name in JOB_PRESETS:
            del JOB_PRESETS[preset_name]
            self._save_custom_presets_to_file()
            return True
        return False

    def _save_custom_presets_to_file(self):
        """커스텀 프리셋 영구 저장"""
        try:
            with open(CUSTOM_PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump(JOB_PRESETS, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_custom_presets_from_file(self):
        """저장된 커스텀 프리셋 복원"""
        if CUSTOM_PRESETS_FILE.exists():
            try:
                with open(CUSTOM_PRESETS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    JOB_PRESETS.update(data)
            except Exception:
                pass

    def trigger_skill_used(self, skill_name: str):
        """스킬 쿨타임 시작"""
        for sk in self.skills:
            if sk.name == skill_name or skill_name.lower() in sk.name.lower():
                sk.state = "ON_COOLDOWN"
                sk.last_used_time = time.time()
                sk.cooldown_end_time = time.time() + sk.cooldown_sec
                return

    def is_maple_running(self) -> bool:
        """메이플스토리 프로세스 실행 여부 확인"""
        if self.maple_pids:
            return True
        if not psutil:
            return True
        try:
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    pname = (p.info.get('name') or '').lower()
                    if 'maple' in pname:
                        self.maple_pids.add(p.info['pid'])
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return False

    def get_engine_status(self) -> Dict[str, Any]:
        """엔진 상태, 프로세스/포커스 감지 상태 및 스킬 정보 일괄 반환"""
        is_admin = False
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            pass

        is_running_proc = self.is_maple_running()
        is_active_win = self.is_maple_active_window()

        if not self.is_running:
            state = "STOPPED"
            state_label = "감시 수동 정지됨"
        elif not is_running_proc:
            state = "WAIT_PROCESS"
            state_label = "메이플 실행 대기 중 (실행 시 자동 가동)"
        elif not is_active_win:
            state = "WAIT_FOCUS"
            state_label = "포커스 대기 중 (메이플 창 클릭 시 즉시 감시)"
        else:
            state = "ACTIVE"
            state_label = "실시간 감시 가동 중 (메이플 포커스)"

        return {
            "status": "success",
            "is_running": self.is_running,
            "auto_manage": self.auto_manage,
            "engine_state": state,
            "state_label": state_label,
            "focus_filter_enabled": self.focus_filter_enabled,
            "is_maple_running": is_running_proc,
            "is_maple_active": is_active_win,
            "maple_process_detected": is_running_proc,
            "target_window_locked": is_running_proc and is_active_win,
            "is_admin": is_admin,
            "current_preset": self.current_preset_name,
            "skills": [sk.to_dict() for sk in self.skills]
        }

    def start(self):
        if self.is_running and self._watcher_thread and self._watcher_thread.is_alive():
            return
        self.is_running = True
        self._watcher_thread = threading.Thread(target=self._run_loop, daemon=True, name="MapleSkillWatcherThread")
        self._watcher_thread.start()

    def stop(self):
        self.is_running = False
        for sk in self.skills:
            sk.state = "READY"
            sk.cooldown_end_time = 0.0
            sk.is_key_down = False
        SkadiVoiceAnnouncer.stop_all_audio()
        if self._watcher_thread:
            try:
                self._watcher_thread.join(timeout=0.5)
            except Exception:
                pass

    def _run_loop(self):
        """0.05초 초고속 핫키 감지 & 쿨타임 타이머 루프 (포커스 필터 적용)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.is_running:
            try:
                current_time = time.time()

                if not self.is_running:
                    break

                # 🔒 포커스 필터: 현재 활성화된 전면 창이 메이플스토리인지 검사
                is_maple_active = self.is_maple_active_window()

                # 1. 단축키 입력 감지 (Windows GetAsyncKeyState 기반, 0ms 레이턴시)
                for sk in self.skills:
                    if not self.is_running:
                        break
                    if sk.key_bind:
                        pressed = is_key_pressed(sk.key_bind)

                        if pressed and not sk.is_key_down:
                            sk.is_key_down = True
                            # 메이플 활성창일 때만 쿨타임 트리거 (오작동 0% 방지)
                            if is_maple_active and sk.state == "READY" and self.is_running:
                                sk.state = "ON_COOLDOWN"
                                sk.last_used_time = current_time
                                sk.cooldown_end_time = current_time + sk.cooldown_sec
                                print(f"⚡ [메이플 쿨타임] '{sk.name}' 단축키({sk.key_bind.upper()}) 감지 ➔ {sk.cooldown_sec}초 쿨타임 시작!")

                        elif not pressed and sk.is_key_down:
                            sk.is_key_down = False

                # 2. 쿨타임 카운트다운 및 음성 알림 발화
                for sk in self.skills:
                    if not self.is_running:
                        break
                    if sk.state == "ON_COOLDOWN":
                        rem = sk.cooldown_end_time - current_time

                        # ① N초 전 사전 브리핑 발화
                        if rem <= sk.warn_before:
                            sk.state = "WARNED"
                            if self.is_running and sk.voice_text:
                                loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(sk.voice_text))

                    elif sk.state == "WARNED":
                        rem = sk.cooldown_end_time - current_time

                        # ② 쿨타임 완료 발화
                        if rem <= 0:
                            sk.state = "READY"
                            if self.is_running:
                                loop.run_until_complete(SkadiVoiceAnnouncer.speak_text(f"{sk.name} 준비 완료!"))

                time.sleep(0.05)
            except Exception:
                time.sleep(0.1)

        loop.close()


# 글로벌 단일 인스턴스
maple_watcher = MapleSkillWatcher()


# =============================================================================
# 🌐 8. FastAPI 라우터 엔드포인트
# =============================================================================

@router.get("/skills", summary="현재 등록된 스킬 목록 및 엔진 상태 조회")
async def get_skills():
    return maple_watcher.get_engine_status()

@router.get("/status", summary="메이플 엔진 상세 상태 조회")
async def get_status():
    return maple_watcher.get_engine_status()


@router.post("/focus-filter/{enable}", summary="포커스 필터(활성창 전용 감지) ON/OFF 토글")
async def set_focus_filter(enable: bool):
    maple_watcher.focus_filter_enabled = enable
    status_str = "활성화(메이플 창 포커스 시에만 단축키 감지)" if enable else "비활성화(모든 창에서 단축키 감지)"
    return {
        "status": "success",
        "focus_filter_enabled": maple_watcher.focus_filter_enabled,
        "message": f"메이플 포커스 필터가 {status_str}되었습니다."
    }


@router.get("/presets/grouped", summary="카테고리별 직업 & 보스 프리셋 목록")
async def get_grouped_presets():
    """모든 47+ 직업 및 보스 레이드 프리셋을 카테고리별로 정렬하여 반환"""
    maple_watcher.load_custom_presets_from_file()
    all_keys = set(JOB_PRESETS.keys())
    categorized = {}

    for cat_name, p_list in PRESET_CATEGORIES.items():
        existing = [p for p in p_list if p in all_keys]
        if existing:
            categorized[cat_name] = existing
            for p in existing:
                all_keys.discard(p)

    # 남은 커스텀 프리셋
    if all_keys:
        categorized["💾 내 커스텀 프리셋"] = sorted(list(all_keys))

    return {
        "status": "success",
        "current_preset": maple_watcher.current_preset_name,
        "categories": categorized
    }


@router.get("/presets", summary="사용 가능한 전체 직업/보스 프리셋 목록")
async def get_presets():
    maple_watcher.load_custom_presets_from_file()
    preset_list = list(JOB_PRESETS.keys())
    return {
        "status": "success",
        "count": len(preset_list),
        "current_preset": maple_watcher.current_preset_name,
        "presets": preset_list
    }


@router.post("/presets/load/{job_name:path}", summary="직업/보스 프리셋 원클릭 적용")
async def load_job_preset(job_name: str):
    import urllib.parse
    decoded_job = urllib.parse.unquote(job_name).strip()
    success = maple_watcher.load_preset(decoded_job)
    if not success:
        success = maple_watcher.load_preset(job_name)
    if not success:
        raise HTTPException(status_code=400, detail=f"'{decoded_job}' 프리셋이 존재하지 않습니다.")
    return {
        "status": "success",
        "message": f"'{decoded_job}' 프리셋 로드 완료",
        "current_preset": maple_watcher.current_preset_name,
        "skills": [sk.to_dict() for sk in maple_watcher.skills]
    }


@router.post("/presets/save/{preset_name:path}", summary="현재 스킬 구성을 프리셋으로 저장")
async def save_custom_preset(preset_name: str):
    import urllib.parse
    decoded_name = urllib.parse.unquote(preset_name).strip()
    success = maple_watcher.save_preset(decoded_name)
    if not success:
        raise HTTPException(status_code=400, detail="프리셋 이름이 올바르지 않습니다.")
    return {"status": "success", "message": f"'{decoded_name}' 프리셋 저장 완료", "presets": list(JOB_PRESETS.keys())}


@router.delete("/presets/{preset_name:path}", summary="프리셋 삭제")
async def delete_custom_preset(preset_name: str):
    import urllib.parse
    decoded_name = urllib.parse.unquote(preset_name).strip()
    success = maple_watcher.delete_preset(decoded_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"삭제할 프리셋 '{decoded_name}'이 존재하지 않습니다.")
    return {"status": "success", "message": f"'{decoded_name}' 프리셋 삭제 완료", "presets": list(JOB_PRESETS.keys())}


@router.post("/skills/quick-add", summary="스킬 빠른 추가/수정")
async def quick_add_skill(item: SkillConfigItem):
    maple_watcher.add_or_update_skill(item)
    return {"status": "success", "message": f"'{item.name}' 스킬 설정 저장 완료", "skill": item.dict()}


@router.put("/skills/edit", summary="스킬 설정 수정")
async def edit_skill_item(req: SkillEditRequest):
    success = maple_watcher.edit_skill(req.original_name, req.item)
    if not success:
        raise HTTPException(status_code=404, detail=f"수정할 스킬 '{req.original_name}'을 찾을 수 없습니다.")
    return {"status": "success", "message": f"'{req.item.name}' 스킬 수정 완료", "skill": req.item.dict()}


@router.delete("/skills/{skill_name:path}", summary="스킬 삭제")
async def delete_skill_item(skill_name: str):
    import urllib.parse
    decoded_name = urllib.parse.unquote(skill_name).strip()
    success = maple_watcher.delete_skill(decoded_name)
    if not success:
        success = maple_watcher.delete_skill(skill_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"삭제할 스킬 '{decoded_name}'을 찾을 수 없습니다.")
    return {"status": "success", "message": f"'{decoded_name}' 삭제 완료"}


@router.post("/start", summary="실시간 감시 수동 시작")
async def start_tracker():
    maple_watcher.start()
    return {"status": "success", "message": "스킬 감시 시작됨"}


@router.post("/stop", summary="실시간 감시 수동 정지")
async def stop_tracker():
    maple_watcher.stop()
    return {"status": "success", "message": "스킬 감시 정지됨"}


@router.post("/trigger/{skill_name:path}", summary="스킬 쿨타임 즉시 시작 트리거")
async def trigger_skill(skill_name: str):
    import urllib.parse
    decoded_name = urllib.parse.unquote(skill_name).strip()
    maple_watcher.trigger_skill_used(decoded_name)
    return {"status": "success", "message": f"'{decoded_name}' 쿨타임 시작됨"}


@router.post("/precache-all", summary="모든 스킬 음성 일괄 사전 합성 및 다운로드")
async def precache_all_voices():
    cached_count = await maple_watcher.precache_current_skills()
    return {
        "status": "success",
        "message": f"스카디 AI 음성 {cached_count}개 사전 다운로드 및 캐싱 완료 (0ms 즉시 발화 준비 완료)",
        "cached_count": cached_count
    }


@router.post("/test-voice", summary="스카디 음성 알림 즉각 테스트")
async def test_skadi_voice(message: Optional[str] = "방어 스킬 쿨 5초 남았어."):
    asyncio.create_task(SkadiVoiceAnnouncer.speak_text(message))
    return {"status": "success", "speaking_text": message}


@router.get("/volume", summary="음성 브리핑 볼륨 조회 (0~100)")
async def get_voice_volume():
    return {"status": "success", "volume": SkadiVoiceAnnouncer.volume}


@router.post("/volume/{level:int}", summary="음성 브리핑 볼륨 조절 (0~100)")
async def set_voice_volume(level: int):
    SkadiVoiceAnnouncer.set_volume(level)
    return {"status": "success", "volume": SkadiVoiceAnnouncer.volume}
