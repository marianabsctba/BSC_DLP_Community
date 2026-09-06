@echo off
setlocal
cd /d "%~dp0"

echo.
echo BSC DLP v0.6.6.3 validation
echo.

echo [1/8] git diff check
git diff --check
if errorlevel 1 goto :fail

echo.
echo [2/8] Browser Guard presence source checks
findstr /c:"BROWSER_GUARD_DISABLED_OR_MISSING" agent\browser_guard_presence.go >nul || goto :fail
findstr /c:"browser_running+extension_heartbeat_missing" agent\browser_guard_presence.go >nul || goto :fail
findstr /c:"tasklist.exe" agent\browser_guard_presence_windows.go >nul || goto :fail

echo.
echo [3/8] Local bridge heartbeat route
findstr /c:"/v1/guard/heartbeat" agent\browser_bridge.go >nul || goto :fail
findstr /c:"startBrowserGuardPresenceWatch" agent\browser_bridge.go >nul || goto :fail

echo.
echo [4/8] Browser extension heartbeat
findstr /c:"bsc_dlp_guard_heartbeat" browser-extension\service-worker.js >nul || goto :fail
findstr /c:"/v1/guard/heartbeat" browser-extension\service-worker.js >nul || goto :fail
findstr /c:"alarms" browser-extension\manifest.json >nul || goto :fail
findstr /c:"0.6.6.3" browser-extension\manifest.json >nul || goto :fail

echo.
echo [5/8] API and dashboard integration
findstr /c:"browser_guard" api\app.py >nul || goto :fail
findstr /c:"Browser Guard protection disabled or missing" api\app.py >nul || goto :fail
findstr /c:"browser_guard" dashboard\index.html >nul || goto :fail

echo.
echo [6/8] JavaScript syntax
where node.exe >nul 2>&1
if not errorlevel 1 (
  node --check "browser-extension\service-worker.js" || goto :fail
  node --check "browser-extension\content.js" || goto :fail
) else (
  echo Node not found - skipped.
)

echo.
echo [7/8] Go format/tests/build
where go.exe >nul 2>&1
if not errorlevel 1 (
  pushd agent
  gofmt -w .
  go test ./...
  if errorlevel 1 (
    popd
    goto :fail
  )
  go build -o "%TEMP%\bsc-dlp-agent-v0663-test.exe" .
  if errorlevel 1 (
    popd
    goto :fail
  )
  del /q "%TEMP%\bsc-dlp-agent-v0663-test.exe" >nul 2>&1
  popd
) else (
  echo Go not found - skipped.
)

echo.
echo [8/8] Python compile
set "BSC_TEST_PY="
py.exe -3.12 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.12"
if not defined BSC_TEST_PY py.exe -3.11 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.11"
if not defined BSC_TEST_PY py.exe -3.10 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.10"
if defined BSC_TEST_PY (
  %BSC_TEST_PY% -m py_compile api\app.py scripts\dev\apply_v0663.py
  if errorlevel 1 goto :fail
) else (
  echo Python 3.10-3.12 not found - compile skipped.
)

echo.
echo [PASS] Browser Guard Presence ^& Tamper Detection validated.
pause
exit /b 0

:fail
echo.
echo [FAIL] BSC DLP v0.6.6.3 validation failed.
pause
exit /b 1
