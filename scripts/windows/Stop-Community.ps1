[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$HomeDir = Join-Path $env:LOCALAPPDATA "BSC-DLP-Community"
$RuntimeDir = Join-Path $HomeDir "runtime"

foreach ($Name in @("agent", "server")) {
    $PidFile = Join-Path $RuntimeDir "$Name.pid"
    if (-not (Test-Path $PidFile)) { continue }
    $Value = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
    if ($Value -match '^\d+$') {
        Stop-Process -Id ([int]$Value) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

Write-Host "BSC DLP Community stopped." -ForegroundColor Green
