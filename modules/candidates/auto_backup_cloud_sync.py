"""
modules/candidates/auto_backup_cloud_sync.py
=============================================================================
📦 [후보 모듈 2] 시스템 자동 압축 백업 & 데이터 무결성 보존 모듈
=============================================================================
- 설명: 스케줄 DB, 유저 프로필, 대화 히스토리, 롤/메이플 설정 데이터를
        타임스탬프 기반 ZIP 아카이브로 자동 압축 백업합니다.
- 상태: [후보군 - 마스터 검토 및 승인 대기]
=============================================================================
"""

import os
import zipfile
import datetime
from pathlib import Path
from typing import Dict, Any

BACKUP_DIR = Path("data/backups")

class SystemAutoBackup:
    """핵심 데이터 디스크 스냅샷 & ZIP 자동 압축 매니저"""

    @classmethod
    def create_snapshot(cls) -> Dict[str, Any]:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = BACKUP_DIR / f"jarvis_snapshot_{now_str}.zip"
        
        target_paths = [
            Path("data/schedule.db"),
            Path("data/maple_skills.json"),
            Path("data/maple_custom_presets.json"),
            Path("data/aram_augments_1_to_199.json"),
            Path("data/lol_all_champions_guide.json"),
            Path("memory")
        ]
        
        saved_count = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in target_paths:
                if p.exists():
                    if p.is_file():
                        zf.write(p, arcname=p.name)
                        saved_count += 1
                    elif p.is_dir():
                        for root, _, files in os.walk(p):
                            for f in files:
                                f_path = Path(root) / f
                                zf.write(f_path, arcname=str(f_path.relative_to(p.parent)))
                                saved_count += 1
                                
        return {
            "status": "success",
            "backup_file": str(zip_path),
            "files_archived": saved_count,
            "size_bytes": zip_path.stat().st_size
        }
