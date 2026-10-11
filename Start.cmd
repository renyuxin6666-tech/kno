@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap.ps1" %*
if errorlevel 1 (
  echo Setup did not finish. Please read the message above.
)
pause
