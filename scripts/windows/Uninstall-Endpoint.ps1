$ErrorActionPreference = "SilentlyContinue"
$HomeDir = Join-Path $env:LOCALAPPDATA "BSC-DLP-Endpoint"
$AgentTarget = Join-Path $HomeDir "bin\bsc-dlp-agent.exe"
Get-CimInstance Win32_Process -Filter "Name='bsc-dlp-agent.exe'" | ForEach-Object {
    if ($_.ExecutablePath -eq $AgentTarget) { Stop-Process -Id $_.ProcessId -Force }
}
$StartupCmd = Join-Path ([Environment]::GetFolderPath('Startup')) "BSC-DLP-Endpoint.cmd"
Remove-Item $StartupCmd -Force
Remove-Item $HomeDir -Recurse -Force
Write-Host "BSC DLP Endpoint removed." -ForegroundColor Magenta
