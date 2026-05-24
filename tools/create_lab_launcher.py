"""Create lab-computer launchers for Stoichio Buddy.

The generated files live in ``dist/`` so they can be copied to a desktop
without changing the source app. Run from the project root:

    python3 tools/create_lab_launcher.py
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
APP_NAME = "Stoichio Buddy"
APP_URL = "http://localhost:8501"
ICON_SOURCE = ROOT / "assets" / "stoichio_icon_app.png"
MAC_APP = DIST / f"{APP_NAME}.app"
MAC_ICON = MAC_APP / "Contents" / "Resources" / "stoichio_buddy.icns"
WIN_ICON = DIST / "stoichio_buddy.ico"


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_text(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        make_executable(path)


def write_icons() -> None:
    DIST.mkdir(exist_ok=True)
    if not ICON_SOURCE.exists():
        raise FileNotFoundError(f"Missing icon source: {ICON_SOURCE}")

    image = Image.open(ICON_SOURCE).convert("RGBA")
    image.save(WIN_ICON, sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)])

    MAC_ICON.parent.mkdir(parents=True, exist_ok=True)
    image.save(MAC_ICON)


def mac_launcher_script() -> str:
    return f"""#!/bin/zsh
PROJECT_DIR="{ROOT}"
APP_URL="{APP_URL}"

cd "$PROJECT_DIR" || {{
  echo "Could not find Stoichio Buddy at: $PROJECT_DIR"
  read "reply?Press Enter to close..."
  exit 1
}}

if [[ -x ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
else
  PYTHON="python3"
fi

echo "Starting Stoichio Buddy for the lab computer..."
echo "This computer: $APP_URL"
echo "Other lab computers can use the Network URL printed below."
echo ""

(
  sleep 2
  open "$APP_URL"
) &

"$PYTHON" -m streamlit run stochio_buddy.py --server.address 0.0.0.0 --server.port 8501

echo ""
read "reply?Stoichio Buddy stopped. Press Enter to close..."
"""


def write_macos_app() -> None:
    contents = MAC_APP / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    macos.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)

    write_text(
        contents / "Info.plist",
        f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>{APP_NAME}</string>
  <key>CFBundleDisplayName</key>
  <string>{APP_NAME}</string>
  <key>CFBundleIdentifier</key>
  <string>lab.stoichio-buddy.launcher</string>
  <key>CFBundleVersion</key>
  <string>1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleExecutable</key>
  <string>stoichio_buddy_launcher</string>
  <key>CFBundleIconFile</key>
  <string>stoichio_buddy</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.13</string>
</dict>
</plist>
""",
    )
    write_text(macos / "stoichio_buddy_launcher", mac_launcher_script(), executable=True)
    write_text(DIST / f"Open {APP_NAME}.command", mac_launcher_script(), executable=True)


def write_windows_launchers() -> None:
    project_dir = str(ROOT).replace("\\", "\\\\")
    ps1 = DIST / f"Open {APP_NAME}.ps1"
    cmd = DIST / f"Open {APP_NAME}.cmd"
    shortcut_ps1 = DIST / f"Create {APP_NAME} Desktop Shortcut.ps1"

    write_text(
        ps1,
        f"""$ProjectDir = "{project_dir}"
$AppUrl = "{APP_URL}"
Set-Location $ProjectDir

$Python = "python"
if (Test-Path ".venv\\Scripts\\python.exe") {{
  $Python = ".venv\\Scripts\\python.exe"
}} elseif (Get-Command py -ErrorAction SilentlyContinue) {{
  $Python = "py"
}}

Write-Host "Starting Stoichio Buddy for the lab computer..."
Write-Host "This computer: $AppUrl"
Write-Host "Other lab computers can use the Network URL printed below."
Start-Job -ScriptBlock {{
  Start-Sleep -Seconds 2
  Start-Process $using:AppUrl
}} | Out-Null

& $Python -m streamlit run stochio_buddy.py --server.address 0.0.0.0 --server.port 8501
Read-Host "Stoichio Buddy stopped. Press Enter to close"
""",
    )
    write_text(
        cmd,
        f"""@echo off
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0Open {APP_NAME}.ps1"
""",
    )
    write_text(
        shortcut_ps1,
        f"""$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "{APP_NAME}.lnk"
$TargetPath = Join-Path "{DIST}" "Open {APP_NAME}.cmd"
$IconPath = Join-Path "{DIST}" "stoichio_buddy.ico"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = "{ROOT}"
$Shortcut.IconLocation = $IconPath
$Shortcut.Save()

Write-Host "Created shortcut: $ShortcutPath"
""",
    )


def main() -> None:
    write_icons()
    write_macos_app()
    write_windows_launchers()
    print(f"Created lab launchers in: {DIST}")
    print(f"macOS app: {MAC_APP}")
    print(f"Windows shortcut helper: {DIST / f'Create {APP_NAME} Desktop Shortcut.ps1'}")


if __name__ == "__main__":
    main()
