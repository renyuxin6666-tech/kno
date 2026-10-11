@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1" %*
if errorlevel 1 (
  echo 设置未完成，请查看上方提示。 / Setup did not finish. Please read the message above.
)
pause
