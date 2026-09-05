@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Start-Community.ps1"
if errorlevel 1 (
  echo.
  echo BSC DLP could not start. See the error above.
  pause
)
