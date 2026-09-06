@echo off
setlocal
cd /d "%~dp0"

echo.
echo BSC DLP v0.6.5 validation
echo.

echo [1/7] git diff check
git diff --check
if errorlevel 1 goto :fail

echo.
echo [2/7] Go format and tests
where go.exe >nul 2>&1
if errorlevel 1 (
  echo Go not found - skipped.
) else (
  pushd agent
  gofmt -w .
  go test ./...
  if errorlevel 1 (
    popd
    goto :fail
  )
  popd
)

echo.
echo [3/7] Windows agent build
where go.exe >nul 2>&1
if errorlevel 1 (
  echo Go not found - skipped.
) else (
  pushd agent
  go build -o "%TEMP%\bsc-dlp-agent-v065-test.exe" .
  if errorlevel 1 (
    popd
    goto :fail
  )
  del /q "%TEMP%\bsc-dlp-agent-v065-test.exe" >nul 2>&1
  popd
)

echo.
echo [4/7] Python tests
set "BSC_TEST_PY="
py.exe -3.12 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.12"
if not defined BSC_TEST_PY py.exe -3.11 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.11"
if not defined BSC_TEST_PY py.exe -3.10 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.10"
if not defined BSC_TEST_PY goto :fail
%BSC_TEST_PY% -m pytest -q
if errorlevel 1 goto :fail

echo.
echo [5/7] Python compile check
%BSC_TEST_PY% -m py_compile api\app.py scripts\dev\apply_v065.py
if errorlevel 1 goto :fail

echo.
echo [6/7] Browser JavaScript syntax
where node.exe >nul 2>&1
if errorlevel 1 (
  echo Node not found - syntax check skipped.
) else (
  node --check browser-extension\content.js
  if errorlevel 1 goto :fail
  node --check browser-extension\service-worker.js
  if errorlevel 1 goto :fail
)

echo.
echo [7/7] Generic upload source check
findstr /c:"/v1/upload/start" agent\browser_bridge.go >nul
if errorlevel 1 goto :fail
findstr /c:"bsc_dlp_file_start" browser-extension\content.js >nul
if errorlevel 1 goto :fail
findstr /c:"browser_upload" api\app.py >nul
if errorlevel 1 goto :fail

echo.
echo [BSC DLP] Validation OK.
echo Restart BSC DLP and reload the Browser Guard extension.
pause
exit /b 0

:fail
echo.
echo [BSC DLP] Validation FAILED. Do not commit yet.
pause
exit /b 1
