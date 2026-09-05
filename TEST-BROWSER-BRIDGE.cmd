@echo off
setlocal

echo.
echo BSC DLP Browser Bridge test
echo.

powershell -NoLogo -NoProfile -Command "try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/v1/health' -TimeoutSec 3; $r | ConvertTo-Json -Compress } catch { Write-Host '[FAIL] Browser bridge is not reachable. Restart BSC DLP first.' -ForegroundColor Red; exit 1 }"

if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo [PASS] Browser bridge is online.
pause
