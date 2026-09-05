@echo off
setlocal
cd /d "%~dp0"

call "%~dp0scripts\windows\Resolve-PowerShell.cmd"
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo BSC DLP - WhatsApp Desktop clipboard test
echo.
echo Uses the standard Visa TEST number 4111 1111 1111 1111.
echo It does NOT send a message.
echo.
echo Keep BSC DLP running. During the countdown, switch to WhatsApp Desktop.
echo Do not paste anything.
echo.
pause

"%BSC_DLP_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$value='BSC DLP TEST - 4111 1111 1111 1111'; Set-Clipboard -Value $value; Write-Host 'Switch to WhatsApp Desktop NOW.' -ForegroundColor Magenta; 1..10 | ForEach-Object { Start-Sleep -Seconds 1 }; $current=Get-Clipboard -Raw -ErrorAction SilentlyContinue; if ([string]::IsNullOrWhiteSpace($current)) { Write-Host '[PASS] Clipboard was cleared by BSC DLP.' -ForegroundColor Green } else { Write-Host '[CHECK] Clipboard was not cleared. Confirm WhatsApp Desktop was foreground and the agent is running.' -ForegroundColor Yellow }"

echo.
echo Check BSC DLP Events / Incidents for channel=messaging.
pause
