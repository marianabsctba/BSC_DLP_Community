@echo off
rem BSC DLP - PowerShell runtime discovery
rem Sets BSC_DLP_POWERSHELL in the caller environment.
rem This file intentionally uses CMD only.

set "BSC_DLP_POWERSHELL="

rem 1) Windows PowerShell in its canonical Windows location.
if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" (
    set "BSC_DLP_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
    goto :found
)

rem 2) PowerShell 7 in the standard 64-bit Program Files location.
if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" (
    set "BSC_DLP_POWERSHELL=%ProgramFiles%\PowerShell\7\pwsh.exe"
    goto :found
)

rem 3) PowerShell 7 x86, when present.
if exist "%ProgramFiles(x86)%\PowerShell\7\pwsh.exe" (
    set "BSC_DLP_POWERSHELL=%ProgramFiles(x86)%\PowerShell\7\pwsh.exe"
    goto :found
)

rem 4) Any PowerShell 7 executable available through PATH.
for /f "delims=" %%P in ('where pwsh.exe 2^>nul') do (
    if not defined BSC_DLP_POWERSHELL set "BSC_DLP_POWERSHELL=%%P"
)
if defined BSC_DLP_POWERSHELL goto :found

rem 5) Any Windows PowerShell executable available through PATH.
for /f "delims=" %%P in ('where powershell.exe 2^>nul') do (
    if not defined BSC_DLP_POWERSHELL set "BSC_DLP_POWERSHELL=%%P"
)
if defined BSC_DLP_POWERSHELL goto :found

echo.
echo [BSC DLP] PowerShell runtime was not found.
echo.
echo Supported runtimes:
echo   - Windows PowerShell 5.1
echo   - PowerShell 7+ ^(pwsh.exe^)
echo.
echo Install PowerShell 7 and run BSC DLP again.
echo Suggested command, when winget is available:
echo   winget install --id Microsoft.PowerShell --source winget
echo.
exit /b 9009

:found
echo [BSC DLP] PowerShell runtime: "%BSC_DLP_POWERSHELL%"
exit /b 0
