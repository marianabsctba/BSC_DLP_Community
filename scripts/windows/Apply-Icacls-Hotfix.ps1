$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Target = Join-Path $ProjectRoot "scripts\windows\Start-Community.ps1"

if (-not (Test-Path $Target)) {
    throw "Start-Community.ps1 was not found at: $Target"
}

$Content = [System.IO.File]::ReadAllText($Target)

$Old = @'
# Best-effort ACL hardening for the local agent credential.
$Identity = "$env:USERDOMAIN\$env:USERNAME"
& icacls.exe $TokenFile /inheritance:r | Out-Null
& icacls.exe $TokenFile /grant:r "${Identity}:(F)" | Out-Null
'@

$New = @'
# Best-effort ACL hardening for the local agent credential.
# Missing/broken icacls must never prevent BSC DLP from starting.
$Identity = "$env:USERDOMAIN\$env:USERNAME"
$IcaclsPath = $null

$IcaclsCommand = Get-Command icacls.exe -ErrorAction SilentlyContinue
if ($IcaclsCommand) {
    $IcaclsPath = $IcaclsCommand.Source
}
elseif ($env:SystemRoot) {
    $SystemIcacls = Join-Path $env:SystemRoot "System32\icacls.exe"
    if (Test-Path $SystemIcacls) {
        $IcaclsPath = $SystemIcacls
    }
}

if ($IcaclsPath) {
    try {
        & $IcaclsPath $TokenFile /inheritance:r | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "icacls /inheritance returned exit code $LASTEXITCODE"
        }

        & $IcaclsPath $TokenFile /grant:r "${Identity}:(F)" | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "icacls /grant returned exit code $LASTEXITCODE"
        }

        Write-Host "      Token ACL hardening: OK" -ForegroundColor DarkGray
    }
    catch {
        Write-Warning "Token ACL hardening failed; BSC DLP will continue. $($_.Exception.Message)"
    }
}
else {
    Write-Warning "icacls.exe was not found. Token ACL hardening is unavailable; BSC DLP will continue."
}
'@

if ($Content.Contains($New)) {
    Write-Host "[BSC DLP] ICACLS resilience hotfix is already applied." -ForegroundColor Green
    exit 0
}

if (-not $Content.Contains($Old)) {
    throw "Expected v0.5.4 ACL block was not found. The file may already be different; no changes were made."
}

$Updated = $Content.Replace($Old, $New)
[System.IO.File]::WriteAllText($Target, $Updated, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "[BSC DLP] ICACLS resilience hotfix applied successfully." -ForegroundColor Green
Write-Host "Updated: $Target" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Behavior now:" -ForegroundColor Cyan
Write-Host "  icacls available  -> harden agent token ACL" -ForegroundColor DarkGray
Write-Host "  icacls missing    -> warning + continue startup" -ForegroundColor DarkGray
