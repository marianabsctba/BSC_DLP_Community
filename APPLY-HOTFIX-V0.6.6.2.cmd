@echo off
setlocal
cd /d "%~dp0"

echo BSC DLP Browser Guard v0.6.6.2 - Cross-Browser compatibility hotfix
echo.

if not exist "browser-extension\manifest.json" (
  echo [FAIL] browser-extension\manifest.json not found.
  pause
  exit /b 1
)

if not exist "browser-extension\content.js" (
  echo [FAIL] browser-extension\content.js not found.
  pause
  exit /b 1
)

if not exist "browser-extension\service-worker.js" (
  echo [FAIL] browser-extension\service-worker.js not found.
  pause
  exit /b 1
)

copy /y "browser-extension\manifest.json" "browser-extension\manifest.json.bak-v0662" >nul
if errorlevel 1 goto :fail

copy /y "files\manifest.json" "browser-extension\manifest.json" >nul
if errorlevel 1 goto :fail

echo.
echo [PASS] Browser Guard manifest upgraded to v0.6.6.2.
echo        Chrome/Edge: Manifest V3 service worker.
echo        Firefox: Manifest V3 background scripts fallback.
pause
exit /b 0

:fail
echo.
echo [FAIL] Could not apply Browser Guard v0.6.6.2 hotfix.
pause
exit /b 1
