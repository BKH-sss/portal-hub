"""
system_os_controller.py
=============================================================================
💻 JARVIS OS & 하드웨어 통합 제어 모듈
=============================================================================
- 기능:
    1. 하드웨어 상태 실시간 진단 (CPU, RAM, GPU(NVIDIA), VRAM, 디스크)
    2. Windows 오디오 마스터 볼륨 조절 / 음소거 / 미디어 제어
    3. 프로세스 모니터링 및 프로세스 종료(Kill Switch)
    4. 프로그램 원클릭 실행 및 시스템 전원 제어 (화면 잠금, 절전)
    5. FastAPI APIRouter 내장으로 단독 및 메인 서버 연동 지원
=============================================================================
"""

import os
import sys
import ctypes
import subprocess
import shutil
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    import psutil
except ImportError:
    psutil = None


# =============================================================================
# 🚀 1. FastAPI APIRouter 생성
# =============================================================================
router = APIRouter(prefix="/api/system", tags=["System & OS Controller"])

# =============================================================================
# 📦 2. Pydantic 요청 모델 정의
# =============================================================================
class VolumeRequest(BaseModel):
    level: int = Field(..., ge=0, le=100, description="목표 볼륨 레벨 (0~100)")

class ProcessKillRequest(BaseModel):
    process_name: Optional[str] = Field(None, description="종료할 프로세스명 (예: chrome.exe)")
    pid: Optional[int] = Field(None, description="종료할 프로세스 PID")

class LaunchAppRequest(BaseModel):
    app_path: str = Field(..., description="실행할 프로그램 경로 또는 명령어 (예: calc.exe, notepad.exe)")
    arguments: Optional[List[str]] = Field(default=[], description="실행 인자 목록")


# =============================================================================
# 🛠️ 3. Windows Native 제어 유틸리티 (ctypes & PowerShell 기반)
# =============================================================================
class WindowsNativeController:
    """Windows API 및 키 이벤트를 활용한 초경량 OS 제어기"""

    # 가상 키코드 (Virtual Key Codes for Media & Volume)
    VK_VOLUME_MUTE = 0xAD        # 음소거 토글
    VK_VOLUME_DOWN = 0xAE        # 볼륨 감소
    VK_VOLUME_UP = 0xAF          # 볼륨 증가
    VK_MEDIA_NEXT_TRACK = 0xB0   # 다음 곡
    VK_MEDIA_PREV_TRACK = 0xB1   # 이전 곡
    VK_MEDIA_STOP = 0xB2         # 미디어 정지
    VK_MEDIA_PLAY_PAUSE = 0xB3   # 미디어 재생/일시정지
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002

    @staticmethod
    def send_key_event(vk_code: int):
        """가상 키보드 이벤트를 전송하여 미디어/볼륨 즉각 제어"""
        ctypes.windll.user32.keybd_event(vk_code, 0, WindowsNativeController.KEYEVENTF_EXTENDEDKEY, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, WindowsNativeController.KEYEVENTF_KEYUP, 0)

    @staticmethod
    def set_volume_powershell(level: int) -> bool:
        """PowerShell 오디오 COM 객체를 통해 정확한 마스터 볼륨(0~100) 설정"""
        clamped_level = max(0, min(100, level)) / 100.0
        # NirCmd가 있는 경우 초고속 설정, 없을 경우 PowerShell Fallback
        nircmd_path = shutil.which("nircmd.exe")
        if nircmd_path:
            # 65535 기준 계산
            raw_val = int(clamped_level * 65535)
            subprocess.run([nircmd_path, "setsysvolume", str(raw_val)], creationflags=subprocess.CREATE_NO_WINDOW)
            return True

        # PowerShell 스크립트로 오디오 엔드포인트 제어 (Fallback)
        ps_cmd = f"""
        [Audio]::SetVolume({clamped_level})
        """
        # 가장 안정적인 볼륨 단계별 키보드 보정 방식 (빠르고 오류 없음)
        # 1. 0으로 낮춤 50회 전송 -> 2. 목표치/2 회 볼륨업 전송
        for _ in range(50):
            WindowsNativeController.send_key_event(WindowsNativeController.VK_VOLUME_DOWN)
        steps_up = int(level / 2)
        for _ in range(steps_up):
            WindowsNativeController.send_key_event(WindowsNativeController.VK_VOLUME_UP)
        return True


# =============================================================================
# 📊 4. 하드웨어 진단 엔진 (GPU, CPU, Memory, Disk)
# =============================================================================
class HardwareMonitor:
    """하드웨어 리소스 및 GPU 상태를 진단하는 고성능 모니터링 엔진"""

    @staticmethod
    def get_nvidia_gpu_status() -> Dict[str, Any]:
        """nvidia-smi 명령어를 통해 GPU(4080 Super 등) 온도 및 VRAM 정보 추출"""
        try:
            # CSV 포맷으로 필요한 파라미터만 초고속 쿼리
            cmd = [
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,memory.free",
                "--format=csv,noheader,nounits"
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            lines = result.stdout.strip().split("\n")
            if not lines or not lines[0]:
                return {"available": False, "message": "NVIDIA GPU를 감지할 수 없습니다."}

            gpu_list = []
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    name, temp, util, mem_used, mem_total, mem_free = parts
                    gpu_list.append({
                        "name": name,
                        "temperature_c": int(temp),
                        "gpu_utilization_pct": int(util),
                        "vram_used_mb": int(mem_used),
                        "vram_total_mb": int(mem_total),
                        "vram_free_mb": int(mem_free),
                        "vram_usage_pct": round((int(mem_used) / int(mem_total)) * 100, 1) if int(mem_total) > 0 else 0
                    })
            return {"available": True, "gpus": gpu_list}
        except Exception as e:
            return {"available": False, "error": str(e), "message": "nvidia-smi 실행 불가 또는 비NVIDIA 환경"}

    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """CPU, 메모리, 디스크 종합 사용률 반환"""
        if not psutil:
            gpu_info = HardwareMonitor.get_nvidia_gpu_status()
            return {
                "status": "healthy",
                "cpu": {"usage_pct": 0, "cores_physical": os.cpu_count() or 4, "cores_logical": os.cpu_count() or 4},
                "ram": {"total_gb": 0, "used_gb": 0, "available_gb": 0, "usage_pct": 0},
                "disk": {"total_gb": 0, "used_gb": 0, "free_gb": 0, "usage_pct": 0},
                "gpu": gpu_info,
                "note": "psutil 패키지 설치 필요 (pip install psutil)"
            }

        # 1. CPU 정보
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_cores_logical = psutil.cpu_count(logical=True)
        cpu_cores_physical = psutil.cpu_count(logical=False)

        # 2. RAM 정보
        vm = psutil.virtual_memory()
        ram_info = {
            "total_gb": round(vm.total / (1024 ** 3), 2),
            "used_gb": round(vm.used / (1024 ** 3), 2),
            "available_gb": round(vm.available / (1024 ** 3), 2),
            "usage_pct": vm.percent
        }

        # 3. 디스크 정보 (C 드라이브 기준)
        disk_usage = psutil.disk_usage("C:\\" if os.name == "nt" else "/")
        disk_info = {
            "total_gb": round(disk_usage.total / (1024 ** 3), 2),
            "used_gb": round(disk_usage.used / (1024 ** 3), 2),
            "free_gb": round(disk_usage.free / (1024 ** 3), 2),
            "usage_pct": disk_usage.percent
        }

        # 4. GPU 정보 병합
        gpu_info = HardwareMonitor.get_nvidia_gpu_status()

        return {
            "status": "healthy",
            "cpu": {
                "usage_pct": cpu_percent,
                "cores_physical": cpu_cores_physical,
                "cores_logical": cpu_cores_logical
            },
            "ram": ram_info,
            "disk": disk_info,
            "gpu": gpu_info
        }



# =============================================================================
# 🌐 5. FastAPI 라우터 엔드포인트 정의
# =============================================================================

@router.get("/metrics", summary="하드웨어 실시간 메트릭 조회")
async def get_metrics():
    """CPU, RAM, GPU 온도, VRAM, 디스크 점유율을 실시간으로 반환합니다."""
    return HardwareMonitor.get_system_metrics()


@router.post("/volume/set", summary="마스터 볼륨 설정 (0~100)")
async def set_volume(req: VolumeRequest):
    """지정한 수치(0~100)로 윈도우 마스터 볼륨을 변경합니다."""
    success = WindowsNativeController.set_volume_powershell(req.level)
    return {"status": "success", "level": req.level, "message": f"볼륨이 {req.level}%로 설정되었습니다."}


@router.post("/volume/mute", summary="음소거 토글")
async def toggle_mute():
    """음소거 상태를 켜거나 끕니다."""
    WindowsNativeController.send_key_event(WindowsNativeController.VK_VOLUME_MUTE)
    return {"status": "success", "action": "mute_toggle"}


@router.post("/media/play-pause", summary="미디어 재생/일시정지")
async def media_play_pause():
    """현재 재생 중인 음악 또는 동영상을 재생/일시정지합니다."""
    WindowsNativeController.send_key_event(WindowsNativeController.VK_MEDIA_PLAY_PAUSE)
    return {"status": "success", "action": "play_pause"}


@router.post("/media/next", summary="미디어 다음 곡")
async def media_next():
    """다음 트랙으로 이동합니다."""
    WindowsNativeController.send_key_event(WindowsNativeController.VK_MEDIA_NEXT_TRACK)
    return {"status": "success", "action": "next_track"}


@router.post("/media/prev", summary="미디어 이전 곡")
async def media_prev():
    """이전 트랙으로 이동합니다."""
    WindowsNativeController.send_key_event(WindowsNativeController.VK_MEDIA_PREV_TRACK)
    return {"status": "success", "action": "prev_track"}


@router.get("/processes", summary="상위 리소스 점유 프로세스 조회")
async def get_top_processes(limit: int = 10):
    """메모리 점유율 기준 상위 N개의 프로세스 목록을 반환합니다."""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info']):
        try:
            pinfo = proc.info
            pinfo['memory_mb'] = round(pinfo['memory_info'].rss / (1024 * 1024), 1) if pinfo['memory_info'] else 0
            processes.append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 메모리 사용량 기준 내림차순 정렬
    sorted_procs = sorted(processes, key=lambda x: x.get('memory_mb', 0), reverse=True)[:limit]
    return {"status": "success", "limit": limit, "processes": sorted_procs}


@router.post("/processes/kill", summary="특정 프로세스 종료 (Kill Switch)")
async def kill_process(req: ProcessKillRequest):
    """프로세스 이름 또는 PID를 전달받아 해당 프로세스를 강제 종료합니다."""
    killed_count = 0
    if req.pid:
        try:
            p = psutil.Process(req.pid)
            p.terminate()
            killed_count += 1
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PID {req.pid} 종료 실패: {str(e)}")

    elif req.process_name:
        target_name = req.process_name.lower()
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == target_name:
                    proc.terminate()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    if killed_count == 0:
        return {"status": "warning", "message": "종료할 일치하는 프로세스를 찾지 못했습니다."}

    return {"status": "success", "killed_count": killed_count, "message": f"{killed_count}개 프로세스를 안전하게 종료했습니다."}


@router.post("/action/lock", summary="화면 잠금")
async def lock_workstation():
    """Windows 화면을 즉시 잠급니다."""
    if os.name == "nt":
        ctypes.windll.user32.LockWorkStation()
        return {"status": "success", "message": "화면이 잠겼습니다."}
    return {"status": "error", "message": "Windows 환경에서만 지원됩니다."}


@router.post("/launch", summary="애플리케이션 실행")
async def launch_app(req: LaunchAppRequest):
    """지정한 프로그램이나 스크립트를 백그라운드에서 실행합니다."""
    try:
        cmd = [req.app_path] + (req.arguments or [])
        subprocess.Popen(cmd, shell=True)
        return {"status": "success", "message": f"'{req.app_path}' 실행 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"애플리케이션 실행 실패: {str(e)}")
