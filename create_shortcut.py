import os
import sys

def create_desktop_shortcut(target_exe_or_bat, shortcut_name="J.A.R.V.I.S Assistant"):
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(curr_dir, "app_icon.ico")
    target_path = os.path.join(curr_dir, target_exe_or_bat)
    
    import subprocess
    ps_cmd = f"""
    $WshShell = New-Object -comObject WScript.Shell
    $DesktopPath = [System.Environment]::GetFolderPath('Desktop')
    $Shortcut = $WshShell.CreateShortcut("$DesktopPath\\{shortcut_name}.lnk")
    $Shortcut.TargetPath = "{target_path}"
    $Shortcut.WorkingDirectory = "{curr_dir}"
    $Shortcut.IconLocation = "{ico_path}"
    $Shortcut.Description = "J.A.R.V.I.S AI Assistant Desktop App"
    $Shortcut.Save()
    """
    subprocess.run(["powershell", "-Command", ps_cmd], check=True)
    print(f"Desktop shortcut created successfully -> {target_path}")

def create_all_desktop_shortcuts():
    exe_candidate = os.path.join("dist", "JARVIS_Assistant", "JARVIS_Assistant.exe")
    jarvis_target = exe_candidate if os.path.exists(exe_candidate) else "서버_켜기.bat"
    
    shortcuts = [
        (jarvis_target, "J.A.R.V.I.S Assistant", "J.A.R.V.I.S AI Assistant Desktop App"),
        ("AI_스튜디오_실행.bat", "스카디 AI 화가 스튜디오", "스카디 AI 화가 스튜디오 (RTX 4080 SUPER SDXL)"),
        ("포털_실행.bat", "4차 산업 포털 (ERECHTHEION)", "4차 산업 실시간 인텔리전스 & 스포츠 포털"),
        ("서버_끄기.bat", "AI 서버 및 스튜디오 종료", "모든 AI 백엔드 서버 및 WebUI 프로세스 완전 종료"),
    ]
    
    for target, name, desc in shortcuts:
        if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), target)):
            create_desktop_shortcut(target, name)

if __name__ == "__main__":
    create_all_desktop_shortcuts()
