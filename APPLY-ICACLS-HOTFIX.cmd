@echo off
setlocal

if not exist "%~dp0scripts\windows\Resolve-PowerShell.cmd" (
  echo.
  echo [BSC DLP] Resolve-PowerShell.cmd was not found.
  echo Extract this hotfix into the BSC DLP repository root.
  echo.
  pause
  exit /b 1
)

call "%~dp0scripts\windows\Resolve-PowerShell.cmd"
if errorlevel 1 (
  pause
  exit /b 1
)

"%BSC_DLP_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Apply-Icacls-Hotfix.ps1"
if errorlevel 1 (
  echo.
  echo [BSC DLP] Hotfix could not be applied. See the error above.
  pause
  exit /b 1
)

echo.
echo Hotfix applied. You can now run START-BSC-DLP.cmd.
echo.
pause
