@echo off
setlocal
cd /d "%~dp0"

echo BSC DLP Browser Guard v0.6.6.2 validation
echo.

findstr /c:"0.6.6.2" "browser-extension\manifest.json" >nul || goto :fail
findstr /c:"service_worker" "browser-extension\manifest.json" >nul || goto :fail
findstr /c:"scripts" "browser-extension\manifest.json" >nul || goto :fail
findstr /c:"bsc_dlp_file_start" "browser-extension\content.js" >nul || goto :fail
findstr /c:"/v1/upload/start" "browser-extension\service-worker.js" >nul || goto :fail
findstr /c:"/v1/upload/finish" "browser-extension\service-worker.js" >nul || goto :fail

where node.exe >nul 2>&1
if not errorlevel 1 (
  node --check "browser-extension\content.js" || goto :fail
  node --check "browser-extension\service-worker.js" || goto :fail
)

echo.
echo [PASS] Cross-browser Browser Guard structure validated.
echo        Runtime validation still required per browser.
pause
exit /b 0

:fail
echo.
echo [FAIL] Cross-browser Browser Guard validation failed.
pause
exit /b 1
