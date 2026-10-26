@echo off
cd /d "%~dp0"
rem Prefer the GPU environment (.venv-gpu) when it exists; otherwise use the CPU environment (.venv).
set "FIELD_OBSERVER_PYTHON=.venv\Scripts\python.exe"
if exist ".venv-gpu\Scripts\python.exe" set "FIELD_OBSERVER_PYTHON=.venv-gpu\Scripts\python.exe"
if not exist "%FIELD_OBSERVER_PYTHON%" (
  echo The field observer environment is missing. See README.md for setup.
  pause
  exit /b 1
)
if "%FIELD_OBSERVER_PYTHON%"==".venv-gpu\Scripts\python.exe" (echo Using the GPU environment; analysis runs on the NVIDIA GPU when available.) else (echo Using the CPU environment.)
echo Opening Field Observer in your browser...
echo Keep this helper window open while using the app.
"%FIELD_OBSERVER_PYTHON%" -m field_observer gui
if errorlevel 1 pause
