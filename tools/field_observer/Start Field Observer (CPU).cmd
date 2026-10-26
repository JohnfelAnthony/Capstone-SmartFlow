@echo off
cd /d "%~dp0"
rem Fallback: the original CPU-only environment, with analysis forced onto the CPU.
if not exist ".venv\Scripts\python.exe" (
  echo The field observer environment is missing. See README.md for setup.
  pause
  exit /b 1
)
set "FIELD_OBSERVER_DEVICE=cpu"
echo Using the CPU environment.
echo Opening Field Observer in your browser...
echo Keep this helper window open while using the app.
".venv\Scripts\python.exe" -m field_observer gui
if errorlevel 1 pause
