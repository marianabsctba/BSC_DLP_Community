[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [string]$Server,
    [Parameter(Position=1)]
    [string]$EnrollmentToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest


function Find-BscTesseract {
    $Candidates = @()
    $FromPath = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    if ($FromPath) { $Candidates += $FromPath.Source }
    if ($env:ProgramFiles) { $Candidates += (Join-Path $env:ProgramFiles "Tesseract-OCR\tesseract.exe") }
    $ProgramFilesX86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    if ($ProgramFilesX86) { $Candidates += (Join-Path $ProgramFilesX86 "Tesseract-OCR\tesseract.exe") }
    if ($env:LOCALAPPDATA) {
        $Candidates += (Join-Path $env:LOCALAPPDATA "Programs\Tesseract-OCR\tesseract.exe")
        $Candidates += (Join-Path $env:LOCALAPPDATA "Tesseract-OCR\tesseract.exe")
    }
    foreach ($Candidate in $Candidates | Select-Object -Unique) {
        if ($Candidate -and (Test-Path $Candidate)) { return (Resolve-Path $Candidate).Path }
    }
    return $null
}

function Ensure-BscTesseract {
    $Found = Find-BscTesseract
    if ($Found) { return $Found }
    if ($env:BSC_DLP_SKIP_OCR_BOOTSTRAP -eq '1') { return $null }

    $Winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $Winget) { return $null }

    Write-Host "BSC DLP: OCR engine not found. Installing Tesseract OCR..." -ForegroundColor Magenta
    try {
        & $Winget.Source install -e --id UB-Mannheim.TesseractOCR --silent --accept-source-agreements --accept-package-agreements --disable-interactivity | Out-Host
    }
    catch {
        Write-Warning "Automatic OCR installation failed: $($_.Exception.Message)"
    }
    return (Find-BscTesseract)
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($Server)) {
    $Server = Read-Host "BSC DLP server URL (example: http://10.0.0.10:8000)"
}
if ([string]::IsNullOrWhiteSpace($EnrollmentToken)) {
    $EnrollmentToken = Read-Host "Enrollment code"
}

$Server = $Server.Trim().TrimEnd('/')
if ($Server.EndsWith('/api/v1')) {
    $ApiUrl = $Server
    $Server = $Server.Substring(0, $Server.Length - 7)
} else {
    $ApiUrl = "$Server/api/v1"
}

$HomeDir = Join-Path $env:LOCALAPPDATA "BSC-DLP-Endpoint"
$BinDir = Join-Path $HomeDir "bin"
$SecretsDir = Join-Path $HomeDir "secrets"
$LogsDir = Join-Path $HomeDir "logs"
$QuarantineDir = Join-Path $HomeDir "quarantine"
foreach ($Dir in @($HomeDir,$BinDir,$SecretsDir,$LogsDir,$QuarantineDir)) {
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
}

$AgentTarget = Join-Path $BinDir "bsc-dlp-agent.exe"
$AgentSource = Join-Path $ProjectRoot "bsc-dlp-agent.exe"

if (Test-Path $AgentSource) {
    Copy-Item -Force $AgentSource $AgentTarget
} else {
    $Go = Get-Command go.exe -ErrorAction SilentlyContinue
    if (-not $Go) {
        throw "Agent binary not found. Use the prebuilt Community release, or install Go for source mode."
    }
    Push-Location (Join-Path $ProjectRoot "agent")
    try {
        & $Go.Source build -trimpath -ldflags "-s -w" -o $AgentTarget .
        if ($LASTEXITCODE -ne 0) { throw "Could not build endpoint agent." }
    }
    finally { Pop-Location }
}

try {
    $Health = Invoke-RestMethod -Method Get -Uri "$ApiUrl/health" -TimeoutSec 5
    if ($Health.engine -ne "BSC DLP") { throw "Unexpected server response." }
} catch {
    throw "Cannot reach BSC DLP at $ApiUrl. $($_.Exception.Message)"
}

$EndpointId = "bsc-dlp-$([System.Net.Dns]::GetHostName())"
$Enroll = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiUrl/enroll" `
    -Headers @{ "X-Enrollment-Key" = $EnrollmentToken.Trim() } `
    -ContentType "application/json" `
    -Body (@{ endpoint_id = $EndpointId } | ConvertTo-Json -Compress)

$TokenFile = Join-Path $SecretsDir "agent.token"
[System.IO.File]::WriteAllText($TokenFile, [string]$Enroll.token, [System.Text.Encoding]::ASCII)
$Identity = "$env:USERDOMAIN\$env:USERNAME"
& icacls.exe $TokenFile /inheritance:r | Out-Null
& icacls.exe $TokenFile /grant:r "${Identity}:(F)" | Out-Null

$Tesseract = Ensure-BscTesseract
if ($Tesseract) {
    Write-Host "OCR:        enabled" -ForegroundColor Green
} else {
    Write-Warning "OCR engine unavailable. Image OCR will remain disabled on this endpoint."
}

$Runner = Join-Path $HomeDir "Run-BSC-DLP-Endpoint.ps1"
$runnerText = @"
`$env:BSC_DLP_API = "$ApiUrl"
`$env:BSC_DLP_TOKEN_FILE = "$TokenFile"
`$env:BSC_DLP_ENDPOINT_ID = "$EndpointId"
`$env:BSC_DLP_LOG_FILE = "$(Join-Path $LogsDir 'agent.log')"
`$env:BSC_DLP_QUARANTINE = "$QuarantineDir"
if ("$Tesseract") { `$env:BSC_DLP_TESSERACT = "$Tesseract" }
`$env:BSC_DLP_OCR_LANGS = "por+eng,eng"
& "$AgentTarget"
"@
[System.IO.File]::WriteAllText($Runner, $runnerText, [System.Text.UTF8Encoding]::new($false))

$Startup = [Environment]::GetFolderPath('Startup')
$StartupCmd = Join-Path $Startup "BSC-DLP-Endpoint.cmd"
$cmdText = "@echo off`r`nstart `"`" /min powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Runner`"`r`n"
[System.IO.File]::WriteAllText($StartupCmd, $cmdText, [System.Text.Encoding]::ASCII)

# Stop an older copy from this endpoint runtime and start the freshly configured one.
Get-CimInstance Win32_Process -Filter "Name='bsc-dlp-agent.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.ExecutablePath -eq $AgentTarget) {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList @(
    '-NoProfile','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-File',"`"$Runner`""
) | Out-Null

Write-Host ""
Write-Host "BSC DLP Endpoint installed." -ForegroundColor Magenta
Write-Host "Endpoint:   $EndpointId"
Write-Host "Server:     $Server"
Write-Host "Quarantine: $QuarantineDir"
Write-Host "The endpoint user has no console credentials." -ForegroundColor DarkGray
