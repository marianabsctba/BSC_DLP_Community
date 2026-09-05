[CmdletBinding()]
param(
    [ValidateSet("amd64", "arm64")]
    [string]$Architecture = "amd64"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$AgentDir = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$DistDir = Join-Path $AgentDir "dist"
$Output = Join-Path $DistDir "bsc-dlp-agent-windows-$Architecture.exe"

New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

Push-Location $AgentDir
try {
    Write-Host "[BSC DLP] Downloading Go modules..."
    & go mod download
    if ($LASTEXITCODE -ne 0) { throw "go mod download failed" }

    $OldGOOS = $env:GOOS
    $OldGOARCH = $env:GOARCH
    $OldCGO = $env:CGO_ENABLED

    try {
        $env:GOOS = "windows"
        $env:GOARCH = $Architecture
        $env:CGO_ENABLED = "0"

        Write-Host "[BSC DLP] Building Windows/$Architecture..."
        & go build -trimpath -ldflags "-s -w" -o $Output .
        if ($LASTEXITCODE -ne 0) { throw "go build failed" }
    }
    finally {
        $env:GOOS = $OldGOOS
        $env:GOARCH = $OldGOARCH
        $env:CGO_ENABLED = $OldCGO
    }
}
finally {
    Pop-Location
}

Write-Host "[BSC DLP] Build ready: $Output"
