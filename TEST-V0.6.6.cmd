@echo off
setlocal
cd /d "%~dp0"

echo.
echo BSC DLP v0.6.6 validation
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
  go build -o "%TEMP%\bsc-dlp-agent-v066-test.exe" .
  if errorlevel 1 (
    popd
    goto :fail
  )
  del /q "%TEMP%\bsc-dlp-agent-v066-test.exe" >nul 2>&1
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
echo [5/7] Python compile
%BSC_TEST_PY% -m py_compile api\app.py scripts\dev\apply_v066.py
if errorlevel 1 goto :fail

echo.
echo [6/7] Catalog source checks
findstr /c:"semantic_required" agent\sensitive_catalog.go >nul
if errorlevel 1 goto :fail
findstr /c:"pii_bundle" agent\sensitive_catalog.go >nul
if errorlevel 1 goto :fail
findstr /c:"CARD_SECURITY_CODE" agent\sensitive_catalog.go >nul
if errorlevel 1 goto :fail

echo.
echo [7/7] Version and docs
findstr /c:"0.6.6" agent\main.go >nul
if errorlevel 1 goto :fail
if not exist docs\SENSITIVE-DATA-CATALOG.md goto :fail

echo.
echo [BSC DLP] Validation OK.
pause
exit /b 0

:fail
echo.
echo [BSC DLP] Validation FAILED. Do not commit yet.
pause
exit /b 1
