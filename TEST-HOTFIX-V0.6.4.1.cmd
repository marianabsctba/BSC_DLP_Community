@echo off
setlocal
cd /d "%~dp0"

echo.
echo BSC DLP v0.6.4.1 hotfix validation
echo.

git diff --check
if errorlevel 1 goto :fail

pushd agent
gofmt -w .
go test ./...
if errorlevel 1 (
  popd
  goto :fail
)
go build -o "%TEMP%\bsc-dlp-agent-v0641-test.exe" .
if errorlevel 1 (
  popd
  goto :fail
)
del /q "%TEMP%\bsc-dlp-agent-v0641-test.exe" >nul 2>&1
popd

py.exe -3.12 -m py_compile api\app.py
if errorlevel 1 goto :fail

findstr /c:"CF_BITMAP normalized to 24-bit BI_RGB" agent\screenshot_clipboard_windows.go >nul
if errorlevel 1 goto :fail

echo.
echo [BSC DLP] Validation OK.
echo Restart BSC DLP, then rerun TEST-SCREENSHOT-CLIPBOARD.cmd.
pause
exit /b 0

:fail
echo.
echo [BSC DLP] Validation FAILED. Do not commit yet.
pause
exit /b 1
