@echo off
setlocal

echo.
echo BSC DLP LAN MODE
echo This listens on all network interfaces. Use only on a trusted LAN or behind TLS/reverse proxy.
echo.

call "%~dp0scripts\windows\Resolve-PowerShell.cmd"
if errorlevel 1 (
  echo.
  echo BSC DLP could not start because PowerShell is unavailable.
  pause
  exit /b 1
)

"%BSC_DLP_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Start-Community.ps1" -ListenAddress 0.0.0.0
if errorlevel 1 (
  echo.
  echo BSC DLP could not start. See the error above.
  pause
  exit /b 1
)
