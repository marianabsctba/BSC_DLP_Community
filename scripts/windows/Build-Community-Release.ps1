[CmdletBinding()]
param(
    [string]$Version = "0.6.10",
    [ValidateSet("amd64")]
    [string]$Architecture = "amd64"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BuildDir = Join-Path $Root "build\community"
$ReleaseName = "BSC-DLP-Community-v$Version-Windows-x64"
$ReleaseDir = Join-Path $BuildDir $ReleaseName
$ZipPath = Join-Path $BuildDir "$ReleaseName.zip"

Remove-Item -Recurse -Force $ReleaseDir -ErrorAction SilentlyContinue
Remove-Item -Force $ZipPath -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir "dashboard") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir "scripts\windows") | Out-Null

Push-Location (Join-Path $Root "agent")
try {
    & go mod download
    if ($LASTEXITCODE -ne 0) { throw "go mod download failed" }
    $OldGOOS = $env:GOOS; $OldGOARCH = $env:GOARCH; $OldCGO = $env:CGO_ENABLED
    try {
        $env:GOOS = "windows"; $env:GOARCH = $Architecture; $env:CGO_ENABLED = "0"
        & go test ./...
        if ($LASTEXITCODE -ne 0) { throw "agent tests failed" }
        & go build -trimpath -ldflags "-s -w" -o (Join-Path $ReleaseDir "bsc-dlp-agent.exe") .
        if ($LASTEXITCODE -ne 0) { throw "agent build failed" }
    }
    finally {
        $env:GOOS = $OldGOOS; $env:GOARCH = $OldGOARCH; $env:CGO_ENABLED = $OldCGO
    }
}
finally { Pop-Location }

$BuildVenv = Join-Path $BuildDir "pyinstaller-venv"
if (-not (Test-Path (Join-Path $BuildVenv "Scripts\python.exe"))) {
    python -m venv $BuildVenv
}
$Python = Join-Path $BuildVenv "Scripts\python.exe"
& $Python -m pip install --disable-pip-version-check -q -r (Join-Path $Root "requirements.txt") pyinstaller
if ($LASTEXITCODE -ne 0) { throw "Python build dependencies failed" }

$PyDist = Join-Path $BuildDir "py-dist"
$PyWork = Join-Path $BuildDir "py-work"
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name bsc-dlp-server `
    --distpath $PyDist `
    --workpath $PyWork `
    --specpath $BuildDir `
    --collect-all uvicorn `
    --collect-all fastapi `
    --collect-all sqlalchemy `
    --collect-all reportlab `
    --icon (Join-Path $Root "dashboard\assets\bsc-dlp.ico") `
    (Join-Path $Root "server.py")
if ($LASTEXITCODE -ne 0) { throw "backend build failed" }
Copy-Item -Force (Join-Path $PyDist "bsc-dlp-server.exe") (Join-Path $ReleaseDir "bsc-dlp-server.exe")

Copy-Item -Force (Join-Path $Root "dashboard\index.html") (Join-Path $ReleaseDir "dashboard\index.html")
if (Test-Path (Join-Path $Root "dashboard\assets")) {
    Copy-Item -Recurse -Force (Join-Path $Root "dashboard\assets") (Join-Path $ReleaseDir "dashboard\assets")
}
foreach ($File in @("README.md","LICENSE","CHANGELOG.md","SECURITY.md")) {
    Copy-Item -Force (Join-Path $Root $File) (Join-Path $ReleaseDir $File)
}
foreach ($File in @("START-BSC-DLP.cmd","START-BSC-DLP-LAN.cmd","STOP-BSC-DLP.cmd","RESET-BSC-DLP.cmd","INSTALL-ENDPOINT.cmd","UNINSTALL-ENDPOINT.cmd")) {
    Copy-Item -Force (Join-Path $Root $File) (Join-Path $ReleaseDir $File)
}
foreach ($File in @("Start-Community.ps1","Stop-Community.ps1","Reset-Community.ps1","Install-Endpoint.ps1","Uninstall-Endpoint.ps1")) {
    Copy-Item -Force (Join-Path $Root "scripts\windows\$File") (Join-Path $ReleaseDir "scripts\windows\$File")
}

Compress-Archive -Path (Join-Path $ReleaseDir "*") -DestinationPath $ZipPath -CompressionLevel Optimal
Write-Host "Community release ready: $ZipPath" -ForegroundColor Green
