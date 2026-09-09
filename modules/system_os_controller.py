"""
system_os_controller.py
=============================================================================
💻 JARVIS OS & 하드웨어 통합 제어 및 사용자 설정 영구 보존 모듈
=============================================================================
- 기능:
    1. 하드웨어 상태 실시간 진단 (CPU, RAM, GPU(NVIDIA), VRAM, 디스크) - 0ms 즉시 응답
    2. Windows CoreAudio 오디오 마스터 볼륨 정밀 조회/조절 / 음소거 / 미디어 제어
    3. 사용자 대시보드 모든 설정(볼륨, 직업 프리셋, 해상도, 포커스 필터, 모니터링 상태) 영구 자동 복원
    4. 프로세스 모니터링 및 프로세스 종료(Kill Switch)
    5. 프로그램 원클릭 실행 및 시스템 전원 제어 (화면 잠금, 절전)
=============================================================================
"""

import os
import sys
import json
import time
import ctypes
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
try:
    from modules._safe_router import (
        APIRouter, HTTPException, Response, HTMLResponse, FileResponse,
        JSONResponse, Request, WebSocket, WebSocketDisconnect, FastAPI,
        CORSMiddleware, BaseModel, Field
    )
except ImportError:
    try:
        from _safe_router import (
            APIRouter, HTTPException, Response, HTMLResponse, FileResponse,
            JSONResponse, Request, WebSocket, WebSocketDisconnect, FastAPI,
            CORSMiddleware, BaseModel, Field
        )
    except ImportError:
        pass

try:
    import psutil
    # 초기 CPU 측정 웜업 (첫 번째 호출 0% 반환 방지)
    psutil.cpu_percent(interval=None)
except ImportError:
    psutil = None


# =============================================================================
# 🚀 1. FastAPI APIRouter 생성
# =============================================================================
router = APIRouter(prefix="/api/system", tags=["System & OS Controller"])

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
PREFERENCES_FILE = DATA_DIR / "user_preferences.json"


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

class PreferencesUpdateRequest(BaseModel):
    preferences: Dict[str, Any] = Field(..., description="저장할 사용자 환경설정 딕셔너리")


# =============================================================================
# 🛠️ 3. Windows Native & CoreAudio 제어 유틸리티
# =============================================================================
class WindowsNativeController:
    """Windows API 및 CoreAudio/키 이벤트를 활용한 초경량 OS 제어기"""

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
    def _get_core_audio_endpoint():
        """Windows CoreAudio IAudioEndpointVolume COM 객체 획득"""
        try:
            import comtypes
            from comtypes import IUnknown, GUID, COMMETHOD, HRESULT
            from ctypes import POINTER, c_float, c_bool, c_ulong, c_void_p

            class IAudioEndpointVolume(IUnknown):
                _iid_ = GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')
                _methods_ = [
                    COMMETHOD([], HRESULT, 'RegisterControlChangeNotify', (['in'], c_void_p, 'pNotify')),
                    COMMETHOD([], HRESULT, 'UnregisterControlChangeNotify', (['in'], c_void_p, 'pNotify')),
                    COMMETHOD([], HRESULT, 'GetChannelCount', (['out'], POINTER(c_ulong), 'pnChannelCount')),
                    COMMETHOD([], HRESULT, 'SetMasterVolumeLevel', (['in'], c_float, 'fLevelDB'), (['in'], c_void_p, 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'SetMasterVolumeLevelScalar', (['in'], c_float, 'fLevel'), (['in'], c_void_p, 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'GetMasterVolumeLevel', (['out'], POINTER(c_float), 'pfLevelDB')),
                    COMMETHOD([], HRESULT, 'GetMasterVolumeLevelScalar', (['out'], POINTER(c_float), 'pfLevel')),
                    COMMETHOD([], HRESULT, 'SetChannelVolumeLevel'),
                    COMMETHOD([], HRESULT, 'SetChannelVolumeLevelScalar'),
                    COMMETHOD([], HRESULT, 'GetChannelVolumeLevel'),
                    COMMETHOD([], HRESULT, 'GetChannelVolumeLevelScalar'),
                    COMMETHOD([], HRESULT, 'SetMute', (['in'], c_bool, 'bMute'), (['in'], c_void_p, 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'GetMute', (['out'], POINTER(c_bool), 'pbMute')),
                ]

            class IMMDevice(IUnknown):
                _iid_ = GUID('{D666063F-1587-4E43-81F1-B948E807363F}')
                _methods_ = [
                    COMMETHOD([], HRESULT, 'Activate', (['in'], POINTER(GUID), 'iid'), (['in'], c_ulong, 'dwClsCtx'), (['in'], c_void_p, 'pActivationParams'), (['out'], POINTER(POINTER(IUnknown)), 'ppInterface')),
                ]

            class IMMDeviceEnumerator(IUnknown):
                _iid_ = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
                _methods_ = [
                    COMMETHOD([], HRESULT, 'EnumAudioEndpoints'),
                    COMMETHOD([], HRESULT, 'GetDefaultAudioEndpoint', (['in'], c_ulong, 'dataFlow'), (['in'], c_ulong, 'role'), (['out'], POINTER(POINTER(IMMDevice)), 'ppEndpoint')),
                ]

            enumerator = comtypes.CoCreateInstance(
                GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}'),
                IMMDeviceEnumerator,
                comtypes.CLSCTX_INPROC_SERVER
            )
            endpoint = enumerator.GetDefaultAudioEndpoint(0, 1) # eRender, eMultimedia
            volume_ptr = endpoint.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_INPROC_SERVER, None)
            return volume_ptr.QueryInterface(IAudioEndpointVolume)
        except Exception:
            return None

    @staticmethod
    def get_volume_info() -> Dict[str, Any]:
        """현재 윈도우 실제 마스터 볼륨(0~100) 및 음소거 상태를 실시간 조회"""
        ep = WindowsNativeController._get_core_audio_endpoint()
        if ep:
            try:
                scalar = ep.GetMasterVolumeLevelScalar()
                muted = ep.GetMute()
                return {
                    "level": int(round(scalar * 100)),
                    "muted": bool(muted),
                    "status": "success"
                }
            except Exception:
                pass
        return {"level": 50, "muted": False, "status": "fallback"}

    @staticmethod
    def set_volume_coreaudio(level: int) -> bool:
        """CoreAudio API를 통해 0ms 지연으로 완벽한 마스터 볼륨 설정"""
        clamped = max(0.0, min(1.0, level / 100.0))
        ep = WindowsNativeController._get_core_audio_endpoint()
        if ep:
            try:
                ep.SetMasterVolumeLevelScalar(clamped, None)
                return True
            except Exception:
                pass
        # Fallback to PowerShell / keybd_event
        return WindowsNativeController.set_volume_powershell(level)

    @staticmethod
    def send_key_event(vk_code: int):
        """가상 키보드 이벤트를 전송하여 미디어/볼륨 즉각 제어"""
        ctypes.windll.user32.keybd_event(vk_code, 0, WindowsNativeController.KEYEVENTF_EXTENDEDKEY, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, WindowsNativeController.KEYEVENTF_KEYUP, 0)

    @staticmethod
    def set_volume_powershell(level: int) -> bool:
        """Fallback 볼륨 설정"""
        clamped_level = max(0, min(100, level)) / 100.0
        nircmd_path = shutil.which("nircmd.exe")
        if nircmd_path:
            raw_val = int(clamped_level * 65535)
            subprocess.run([nircmd_path, "setsysvolume", str(raw_val)], creationflags=subprocess.CREATE_NO_WINDOW)
            return True

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

    _last_gpu_time: float = 0.0
    _cached_gpu_info: Dict[str, Any] = {"available": False}

    @staticmethod
    def get_nvidia_gpu_status() -> Dict[str, Any]:
        """nvidia-smi 명령어를 통해 GPU(4080 Super 등) 온도 및 VRAM 정보 추출 (1초 캐시)"""
        now = time.time()
        if (now - HardwareMonitor._last_gpu_time) < 1.0 and HardwareMonitor._cached_gpu_info.get("available"):
            return HardwareMonitor._cached_gpu_info

        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,memory.free",
                "--format=csv,noheader,nounits"
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            lines = result.stdout.strip().split("\n")
            if not lines or not lines[0]:
                HardwareMonitor._cached_gpu_info = {"available": False, "message": "NVIDIA GPU를 감지할 수 없습니다."}
                return HardwareMonitor._cached_gpu_info

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
            HardwareMonitor._cached_gpu_info = {"available": True, "gpus": gpu_list}
            HardwareMonitor._last_gpu_time = now
            return HardwareMonitor._cached_gpu_info
        except Exception as e:
            HardwareMonitor._cached_gpu_info = {"available": False, "error": str(e), "message": "nvidia-smi 실행 불가 또는 비NVIDIA 환경"}
            return HardwareMonitor._cached_gpu_info

    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """CPU, 메모리, 디스크 종합 사용률 반환 (즉시 응답)"""
        if not psutil:
            gpu_info = HardwareMonitor.get_nvidia_gpu_status()
            return {
                "status": "healthy",
                "cpu": {"usage_pct": 0, "cores_physical": os.cpu_count() or 4, "cores_logical": os.cpu_count() or 4},
                "ram": {"total_gb": 0, "used_gb": 0, "available_gb": 0, "usage_pct": 0},
                "disk": {"total_gb": 0, "used_gb": 0, "free_gb": 0, "usage_pct": 0},
                "gpu": gpu_info,
                "note": "psutil 패키지 설치 필요"
            }

        # 1. CPU 정보 (비차단 즉시 획득)
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_cores_logical = psutil.cpu_count(logical=True)
        cpu_cores_physical = psutil.cpu_count(logical=False) or cpu_cores_logical

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
# 💾 5. 사용자 환경설정 영구 보존 관리자 (PreferencesManager)
# =============================================================================
DEFAULT_PREFERENCES = {
    "master_volume": 100,
    "maple_voice_volume": 100,
    "lol_voice_volume": 100,
    "maple_preset": "은월 (Eunwol)",
    "maple_char_name": "",
    "maple_cancel_mode": "wall",
    "maple_focus_filter": True,
    "lol_resolution_preset": "FHD",
    "lol_focus_filter": True,
    "lol_map_mode": "AUTO",
    "auto_resume_tracking": True
}

class PreferencesManager:
    @staticmethod
    def get_preferences() -> Dict[str, Any]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if PREFERENCES_FILE.exists():
            try:
                with open(PREFERENCES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    merged = DEFAULT_PREFERENCES.copy()
                    merged.update(data)
                    return merged
            except Exception:
                pass
        return DEFAULT_PREFERENCES.copy()

    @staticmethod
    def update_preferences(new_prefs: Dict[str, Any]) -> Dict[str, Any]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        current = PreferencesManager.get_preferences()
        current.update(new_prefs)
        try:
            with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return current


# =============================================================================
# 🌐 6. FastAPI 라우터 엔드포인트 정의
# =============================================================================

@router.get("/metrics", summary="하드웨어 실시간 메트릭 조회")
async def get_metrics():
    """CPU, RAM, GPU 온도, VRAM, 디스크 점유율을 실시간으로 반환합니다."""
    return HardwareMonitor.get_system_metrics()


@router.get("/volume", summary="현재 실제 마스터 볼륨 조회")
async def get_volume():
    """Windows 실제 마스터 볼륨(0~100) 및 음소거 상태를 조회합니다."""
    return WindowsNativeController.get_volume_info()


@router.post("/volume/set", summary="마스터 볼륨 설정 (0~100)")
async def set_volume(req: VolumeRequest):
    """지정한 수치(0~100)로 윈도우 마스터 볼륨을 즉시 변경하고 환경설정에 보존합니다."""
    success = WindowsNativeController.set_volume_coreaudio(req.level)
    PreferencesManager.update_preferences({"master_volume": req.level})
    return {"status": "success", "level": req.level, "message": f"마스터 볼륨이 {req.level}%로 설정되었습니다."}


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


@router.get("/preferences", summary="사용자 환경설정 조회")
async def get_user_preferences():
    """대시보드 볼륨, 프리셋, 해상도 등 영구 저장된 사용자 설정을 반환합니다."""
    return {"status": "success", "preferences": PreferencesManager.get_preferences()}


@router.post("/preferences", summary="사용자 환경설정 업데이트")
async def update_user_preferences(req: PreferencesUpdateRequest):
    """대시보드 설정을 영구 저장하여 사이트 재접속 시 자동 복원되도록 합니다."""
    saved = PreferencesManager.update_preferences(req.preferences)
    return {"status": "success", "preferences": saved}


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
