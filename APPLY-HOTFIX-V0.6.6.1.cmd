@echo off
setlocal
cd /d "%~dp0"

if not exist "browser-extension" (
  echo [ERROR] Execute este hotfix na raiz do repositorio BSC DLP.
  pause
  exit /b 1
)

if exist "browser-extension\content.js" copy /y "browser-extension\content.js" "browser-extension\content.js.bak-v0661" >nul
if exist "browser-extension\service-worker.js" copy /y "browser-extension\service-worker.js" "browser-extension\service-worker.js.bak-v0661" >nul
if exist "browser-extension\manifest.json" copy /y "browser-extension\manifest.json" "browser-extension\manifest.json.bak-v0661" >nul

copy /y "%~dp0files\content.js" "browser-extension\content.js" >nul
copy /y "%~dp0files\service-worker.js" "browser-extension\service-worker.js" >nul
copy /y "%~dp0files\manifest.json" "browser-extension\manifest.json" >nul

echo.
echo [BSC DLP] Browser Guard restore aplicado.
echo Versao da extensao: 0.6.6.1
echo O codigo de upload generico foi restaurado.
echo.
echo Agora recarregue a extensao em chrome://extensions.
pause
