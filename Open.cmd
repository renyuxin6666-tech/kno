@echo off
if not exist "%~dp0.runtime\venv\Scripts\python.exe" (
  echo Run Start.cmd first.
  pause
  exit /b 1
)
"%~dp0.runtime\venv\Scripts\python.exe" "%~dp0scripts\pipeline.py" open --config "%~dp0settings.local.json"
if errorlevel 1 pause
