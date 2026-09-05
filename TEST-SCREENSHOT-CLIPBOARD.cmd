@echo off
setlocal
cd /d "%~dp0"

call "%~dp0scripts\windows\Resolve-PowerShell.cmd"
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo BSC DLP - Clipboard Screenshot OCR test
echo.
echo This creates a LOCAL synthetic image containing the TEST CPF:
echo   123.456.789-09
echo It places the image in the Windows clipboard and does not send it anywhere.
echo.
pause

"%BSC_DLP_POWERSHELL%" -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -Command ^
  "Add-Type -AssemblyName System.Drawing; Add-Type -AssemblyName System.Windows.Forms; $bmp=New-Object System.Drawing.Bitmap 1200,360; $g=[System.Drawing.Graphics]::FromImage($bmp); $g.Clear([System.Drawing.Color]::White); $font=New-Object System.Drawing.Font('Arial',44,[System.Drawing.FontStyle]::Bold); $brush=[System.Drawing.Brushes]::Black; $g.DrawString('BSC DLP SCREENSHOT TEST',$font,$brush,40,45); $g.DrawString('CPF: 123.456.789-09',$font,$brush,40,150); [System.Windows.Forms.Clipboard]::SetImage($bmp); $g.Dispose(); $bmp.Dispose(); Write-Host ''; Write-Host 'Synthetic screenshot copied to clipboard. Waiting for BSC DLP OCR...' -ForegroundColor Magenta; Start-Sleep -Seconds 12; if ([System.Windows.Forms.Clipboard]::ContainsImage()) { Write-Host '[CHECK] Image is still in the clipboard. Check agent OCR/Tesseract logs and screenshot policy.' -ForegroundColor Yellow } else { Write-Host '[PASS] Sensitive screenshot was detected and cleared from the clipboard.' -ForegroundColor Green }"

echo.
echo Check BSC DLP Events / Incidents for:
echo   channel=screenshot
echo   destination=clipboard
echo   evidence=clipboard_image_ocr
pause
