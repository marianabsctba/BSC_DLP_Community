@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Install-Endpoint.ps1" %*
if errorlevel 1 (
  echo.
  echo BSC DLP endpoint installation failed. See the error above.
  pause
)
