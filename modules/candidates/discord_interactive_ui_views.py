"""
modules/candidates/discord_interactive_ui_views.py
=============================================================================
🎮 [후보 모듈 4] 디스코드 봇 인터랙티브 버튼 & 드롭다운 뷰 모듈
=============================================================================
- 설명: 디스코드 봇에서 3지선다 증강 추천, 캘린더 할 일 완료 체크 등을
        클릭 가능한 버튼(Buttons) 및 드롭다운(Selects) 인터랙션으로 제공.
- 상태: [후보군 - 마스터 검토 및 승인 대기]
=============================================================================
"""

from typing import List, Dict, Any

class DiscordInteractiveViews:
    """디스코드 모던 UI 컴포넌트 팩토리"""

    @classmethod
    def build_augment_select_options(cls, choices: List[str]) -> List[Dict[str, str]]:
        return [
            {"label": c, "value": c, "description": f"{c} 증강체 세부 시너지 보기"}
            for c in choices[:25]
        ]

    @classmethod
    def build_todo_action_buttons(cls, item_id: int) -> List[Dict[str, str]]:
        return [
            {"id": f"todo_done_{item_id}", "label": "✅ 완료", "style": "success"},
            {"id": f"todo_del_{item_id}", "label": "🗑️ 삭제", "style": "danger"}
        ]
