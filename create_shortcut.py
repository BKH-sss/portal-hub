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

if __name__ == "__main__":
    exe_candidate = os.path.join("dist", "JARVIS_Assistant", "JARVIS_Assistant.exe")
    target = exe_candidate if os.path.exists(exe_candidate) else "서버_켜기.bat"
    create_desktop_shortcut(target)
