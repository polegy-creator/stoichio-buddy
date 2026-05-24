# Lab Computer Version

This version keeps the full Streamlit app, because it is the most complete lab workflow right now. The improvement is the launcher: it creates a real lab-computer app/shortcut with the Stoichio Buddy icon and starts Streamlit in local-network mode.

## Create The Launcher

Run this once on the lab computer from the project folder:

```bash
python3 tools/create_lab_launcher.py
```

Generated files are written to `dist/`.

## macOS

Use:

```text
dist/Stoichio Buddy.app
```

You can drag that app to the Desktop or Dock. It uses the Stoichio Buddy icon and opens `http://localhost:8501`.

## Windows

Use:

```text
dist/Open Stoichio Buddy.cmd
```

To make a desktop shortcut with the icon, right-click this script and run it with PowerShell:

```text
dist/Create Stoichio Buddy Desktop Shortcut.ps1
```

## Lab Network Access

The launcher starts Streamlit with:

```bash
--server.address 0.0.0.0 --server.port 8501
```

That means other computers on the same lab network can open the Network URL printed by Streamlit. Keep one lab computer as the data source if you want everyone to share the same local JSON database.

## Install/Update

```bash
pip install -r requirements-lab.txt
python3 tools/create_lab_launcher.py
```

If the lab computer uses Windows, run:

```powershell
py -m pip install -r requirements-lab.txt
py tools\create_lab_launcher.py
```
