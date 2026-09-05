@echo off
setlocal
cd /d "%~dp0"

echo.
echo BSC DLP v0.6.0 validation
echo.

echo [1/4] git diff check
git diff --check
if errorlevel 1 goto :fail

echo.
echo [2/4] Go format and tests
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
echo [3/4] Python tests
where py.exe >nul 2>&1
if not errorlevel 1 (
  py.exe -3.12 -m pytest -q
  if errorlevel 1 goto :fail
  goto :syntax
)
where python.exe >nul 2>&1
if not errorlevel 1 (
  python.exe -m pytest -q
  if errorlevel 1 goto :fail
)

:syntax
echo.
echo [4/4] Python compile check
where py.exe >nul 2>&1
if not errorlevel 1 (
  py.exe -3 -m py_compile api\app.py
  if errorlevel 1 goto :fail
)
echo.
echo [BSC DLP] Validation OK.
echo Now run START-BSC-DLP.cmd.
pause
exit /b 0

:fail
echo.
echo [BSC DLP] Validation FAILED. Do not commit yet.
pause
exit /b 1
