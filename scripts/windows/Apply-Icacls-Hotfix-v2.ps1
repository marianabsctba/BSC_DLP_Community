$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Target = Join-Path $ProjectRoot "scripts\windows\Start-Community.ps1"

if (-not (Test-Path $Target)) {
    throw "Start-Community.ps1 was not found at: $Target"
}

$Content = [System.IO.File]::ReadAllText($Target)

if ($Content -match 'Token ACL hardening:\s*OK' -or
    $Content -match 'icacls\.exe was not found\. Token ACL hardening is unavailable') {
    Write-Host "[BSC DLP] ICACLS resilience hotfix is already applied." -ForegroundColor Green
    exit 0
}

$Replacement = @'
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

# Flexible match: tolerate whitespace, CRLF/LF and small comment differences.
$Pattern = '(?ms)#\s*Best-effort ACL hardening for the local agent credential\..*?\$Identity\s*=.*?icacls\.exe\s+\$TokenFile\s+/inheritance:r\s*\|\s*Out-Null.*?icacls\.exe\s+\$TokenFile\s+/grant:r\s+"\$\{Identity\}:\(F\)"\s*\|\s*Out-Null'

$Regex = [System.Text.RegularExpressions.Regex]::new(
    $Pattern,
    [System.Text.RegularExpressions.RegexOptions]::Multiline -bor
    [System.Text.RegularExpressions.RegexOptions]::Singleline
)

if (-not $Regex.IsMatch($Content)) {
    # Fallback: locate the two operational icacls lines even if the comment changed.
    $Fallback = '(?ms)\$Identity\s*=\s*"\$env:USERDOMAIN\\\$env:USERNAME"\s*.*?&\s*icacls\.exe\s+\$TokenFile\s+/inheritance:r\s*\|\s*Out-Null\s*.*?&\s*icacls\.exe\s+\$TokenFile\s+/grant:r\s+"\$\{Identity\}:\(F\)"\s*\|\s*Out-Null'
    $Regex = [System.Text.RegularExpressions.Regex]::new(
        $Fallback,
        [System.Text.RegularExpressions.RegexOptions]::Multiline -bor
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )
}

if (-not $Regex.IsMatch($Content)) {
    Write-Host "" 
    Write-Host "[BSC DLP] Could not safely locate the old icacls block." -ForegroundColor Red
    Write-Host "No changes were made." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Lines containing icacls in the current file:" -ForegroundColor Cyan
    Select-String -Path $Target -Pattern 'icacls|Identity.*USERNAME' -Context 2,2 |
        ForEach-Object { Write-Host $_.ToString() }
    exit 2
}

$Updated = $Regex.Replace($Content, [System.Text.RegularExpressions.MatchEvaluator]{
    param($m)
    return $Replacement
}, 1)

$Backup = "$Target.bak-before-icacls-hotfix"
if (-not (Test-Path $Backup)) {
    Copy-Item -Path $Target -Destination $Backup -Force
}

[System.IO.File]::WriteAllText(
    $Target,
    $Updated,
    (New-Object System.Text.UTF8Encoding($false))
)

Write-Host ""
Write-Host "[BSC DLP] ICACLS resilience hotfix v2 applied successfully." -ForegroundColor Green
Write-Host "Updated: $Target" -ForegroundColor DarkGray
Write-Host "Backup:  $Backup" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Behavior now:" -ForegroundColor Cyan
Write-Host "  icacls available -> harden token ACL" -ForegroundColor DarkGray
Write-Host "  icacls missing   -> warning + continue startup" -ForegroundColor DarkGray
