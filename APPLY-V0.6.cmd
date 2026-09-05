@echo off
setlocal
cd /d "%~dp0"

where py.exe >nul 2>&1
if not errorlevel 1 (
  py.exe -3 "%~dp0scripts\dev\apply_v060.py"
  goto :done
)

where python.exe >nul 2>&1
if not errorlevel 1 (
  python.exe "%~dp0scripts\dev\apply_v060.py"
  goto :done
)

echo.
echo [BSC DLP] Python 3 was not found.
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
echo Upgrade applied. Run TEST-V0.6.cmd.
pause
