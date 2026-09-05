@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\Test-OcrDownload.ps1"
if errorlevel 1 (
  echo.
  echo BSC DLP OCR test failed. See the error above.
  pause
)
