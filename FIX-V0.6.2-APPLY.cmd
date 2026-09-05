@echo off
setlocal
cd /d "%~dp0"

echo.
echo BSC DLP v0.6.2 apply hotfix
echo.

py.exe -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 (
  py.exe -3.12 "%~dp0scripts\dev\apply_v062.py"
  goto :done
)

where python.exe >nul 2>&1
if not errorlevel 1 (
  python.exe "%~dp0scripts\dev\apply_v062.py"
  goto :done
)

echo [BSC DLP] Python was not found.
pause
exit /b 1

:done
if errorlevel 1 (
  echo.
  echo [BSC DLP] Hotfix apply failed. Nothing was committed.
  pause
  exit /b 1
)

echo.
echo [BSC DLP] v0.6.2 apply completed.
echo Now run TEST-V0.6.2.cmd.
pause
