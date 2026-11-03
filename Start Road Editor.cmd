@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m tools.road_editor
) else (
    echo SmartFlow's Python environment was not found. Create .venv first; see README.md.
    pause
)
