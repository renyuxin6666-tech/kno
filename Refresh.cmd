@echo off
chcp 65001 >nul
if not exist "%~dp0.runtime\venv\Scripts\python.exe" (
  echo 请先运行 Start.cmd 完成设置。 / Run Start.cmd to finish setup first.
  pause
  exit /b 1
)
"%~dp0.runtime\venv\Scripts\python.exe" "%~dp0scripts\pipeline.py" refresh --config "%~dp0settings.local.json"
pause
