[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "Stop-Community.ps1")
$HomeDir = Join-Path $env:LOCALAPPDATA "BSC-DLP-Community"
if (Test-Path $HomeDir) { Remove-Item -Recurse -Force $HomeDir }
Write-Host "BSC DLP Community local data reset." -ForegroundColor Yellow
