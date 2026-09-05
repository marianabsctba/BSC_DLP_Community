@echo off
setlocal

call "%~dp0scripts\windows\Resolve-PowerShell.cmd"
if errorlevel 1 (
  pause
  exit /b 1
)

"%BSC_DLP_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Uninstall-Endpoint.ps1"
if errorlevel 1 (
  pause
  exit /b 1
)
