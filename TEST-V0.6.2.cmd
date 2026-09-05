@echo off
setlocal
cd /d "%~dp0"

echo.
echo BSC DLP v0.6.2 validation
echo.

echo [1/5] git diff check
git diff --check
if errorlevel 1 goto :fail

echo.
echo [2/5] Go format and tests
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
echo [3/5] Windows build
where go.exe >nul 2>&1
if errorlevel 1 (
  echo Go not found - skipped.
) else (
  pushd agent
  go build -o "%TEMP%\bsc-dlp-agent-v062-test.exe" .
  if errorlevel 1 (
    popd
    goto :fail
  )
  del /q "%TEMP%\bsc-dlp-agent-v062-test.exe" >nul 2>&1
  popd
)

echo.
echo [4/5] Python tests
set "BSC_TEST_PY="
py.exe -3.12 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.12"
if not defined BSC_TEST_PY py.exe -3.11 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.11"
if not defined BSC_TEST_PY py.exe -3.10 -c "import sys" >nul 2>&1 && set "BSC_TEST_PY=py.exe -3.10"
if not defined BSC_TEST_PY goto :fail
%BSC_TEST_PY% -m pytest -q
if errorlevel 1 goto :fail

echo.
echo [5/5] Python compile check
%BSC_TEST_PY% -m py_compile api\app.py
if errorlevel 1 goto :fail

echo.
echo [BSC DLP] Validation OK.
echo Next: restart BSC DLP and load browser-extension as an unpacked extension.
pause
exit /b 0

:fail
echo.
echo [BSC DLP] Validation FAILED. Do not commit yet.
pause
exit /b 1
