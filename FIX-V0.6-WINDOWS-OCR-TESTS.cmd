@echo off
setlocal
cd /d "%~dp0"

where py.exe >nul 2>&1
if not errorlevel 1 (
  py.exe -3 "%~dp0scripts\dev\fix_windows_ocr_tests.py"
  goto :done
)

where python.exe >nul 2>&1
if not errorlevel 1 (
  python.exe "%~dp0scripts\dev\fix_windows_ocr_tests.py"
  goto :done
)

echo [BSC DLP] Python 3 not found.
pause
exit /b 1

:done
if errorlevel 1 (
  echo.
  echo [BSC DLP] Hotfix failed.
  pause
  exit /b 1
)

echo.
echo Hotfix applied. Run TEST-V0.6.cmd again.
pause
