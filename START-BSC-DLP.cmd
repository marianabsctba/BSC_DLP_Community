@echo off
setlocal

call "%~dp0scripts\windows\Resolve-PowerShell.cmd"
if errorlevel 1 (
  echo.
  echo BSC DLP could not start because PowerShell is unavailable.
  pause
  exit /b 1
)

"%BSC_DLP_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Start-Community.ps1"
if errorlevel 1 (
  echo.
  echo BSC DLP could not start. See the error above.
  pause
  exit /b 1
)
