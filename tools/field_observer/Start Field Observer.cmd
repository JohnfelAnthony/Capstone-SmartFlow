@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo The field observer environment is missing. See README.md for setup.
  pause
  exit /b 1
)
echo Opening Field Observer in your browser...
echo Keep this helper window open while using the app.
".venv\Scripts\python.exe" -m field_observer gui
if errorlevel 1 pause
