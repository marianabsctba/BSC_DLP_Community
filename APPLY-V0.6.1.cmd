@echo off
setlocal
cd /d "%~dp0"

py.exe -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 (
  py.exe -3.12 "%~dp0scripts\dev\apply_v061.py"
  goto :done
)

where python.exe >nul 2>&1
if not errorlevel 1 (
  python.exe "%~dp0scripts\dev\apply_v061.py"
  goto :done
)

echo [BSC DLP] Python was not found.
pause
exit /b 1

:done
if errorlevel 1 (
  echo.
  echo [BSC DLP] Upgrade failed. Nothing was committed.
  pause
  exit /b 1
)

echo.
echo Upgrade applied. Run TEST-V0.6.1.cmd.
pause
