@echo off
setlocal
cd /d "%~dp0"

echo.
echo BSC DLP v0.6.4 validation
echo.

echo [1/6] git diff check
git diff --check
if errorlevel 1 goto :fail

echo.
echo [2/6] Go format and tests
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
echo [3/6] Windows build
where go.exe >nul 2>&1
if errorlevel 1 (
  echo Go not found - skipped.
) else (
  pushd agent
  go build -o "%TEMP%\bsc-dlp-agent-v064-test.exe" .
  if errorlevel 1 (
    popd
    goto :fail
  )
  del /q "%TEMP%\bsc-dlp-agent-v064-test.exe" >nul 2>&1
  popd
)

echo.
echo [4/6] Python tests
set "BSC_TEST_PY="
py.exe -3.12 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.12"
if not defined BSC_TEST_PY py.exe -3.11 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.11"
if not defined BSC_TEST_PY py.exe -3.10 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.10"
if not defined BSC_TEST_PY goto :fail
%BSC_TEST_PY% -m pytest -q
if errorlevel 1 goto :fail

echo.
echo [5/6] Python compile check
%BSC_TEST_PY% -m py_compile api\app.py
if errorlevel 1 goto :fail

echo.
echo [6/6] Clipboard screenshot source check
findstr /c:"clipboard_image_ocr" api\app.py >nul
if errorlevel 1 goto :fail
findstr /c:"startScreenshotClipboardSensor" agent\main.go >nul
if errorlevel 1 goto :fail

echo.
echo [BSC DLP] Validation OK.
echo Restart BSC DLP, then run TEST-SCREENSHOT-CLIPBOARD.cmd.
pause
exit /b 0

:fail
echo.
echo [BSC DLP] Validation FAILED. Do not commit yet.
pause
exit /b 1
