@echo off
setlocal
cd /d "%~dp0"

call "%~dp0scripts\windows\Resolve-PowerShell.cmd"
if errorlevel 1 (
  pause
  exit /b 1
)

set "TESTPORT=8877"
echo.
echo BSC DLP Browser Upload UI Test
echo.
echo 1. Make sure the unpacked Browser Guard extension was RELOADED.
echo 2. A local test page will open.
echo 3. Click "Executar teste sintetico".
echo 4. With CPF Browser Upload BLOCK, the page must NOT receive the file.
echo.

"%BSC_DLP_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Start-Process -FilePath py.exe -ArgumentList '-3.12','-m','http.server','%TESTPORT%','--bind','127.0.0.1','--directory','browser-extension' -WorkingDirectory '%CD%' -WindowStyle Hidden -PassThru; Set-Content -Path (Join-Path $env:TEMP 'bsc-dlp-upload-test-server.pid') -Value $p.Id -Encoding ASCII"

timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:%TESTPORT%/upload-test.html"

echo.
echo When finished, close this window and run:
echo   Stop-Process -Id (Get-Content "$env:TEMP\bsc-dlp-upload-test-server.pid")
pause
