@echo off
setlocal
cd /d "%~dp0"

echo.
echo BSC DLP Browser Guard
echo.
echo Browser security prevents silent installation of unpacked extensions.
echo The extension folder is:
echo.
echo   %~dp0browser-extension
echo.
echo CHROME:
echo   1. Open chrome://extensions
echo   2. Enable Developer mode
echo   3. Click Load unpacked
echo   4. Select browser-extension
echo.
echo EDGE:
echo   1. Open edge://extensions
echo   2. Enable Developer mode
echo   3. Click Load unpacked
echo   4. Select browser-extension
echo.
start "" explorer.exe "%~dp0browser-extension"
pause
