[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$ListenAddress = "127.0.0.1",
    [string]$PublicUrl = "",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PublicUrlWasExplicit = -not [string]::IsNullOrWhiteSpace($PublicUrl)


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
    # START must never block on a package-manager installation.
    # The binary release/installer may provision OCR separately.
    return (Find-BscTesseract)
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BrandIcon = Join-Path $ProjectRoot "dashboard\assets\bsc-dlp.ico"

function Ensure-BscShortcut {
    if ($env:BSC_DLP_SKIP_SHORTCUT -eq '1' -or -not (Test-Path $BrandIcon)) { return }
    try {
        $Desktop = [Environment]::GetFolderPath('Desktop')
        if ([string]::IsNullOrWhiteSpace($Desktop)) { return }
        $ShortcutPath = Join-Path $Desktop "BSC DLP Community.lnk"
        $Shell = New-Object -ComObject WScript.Shell
        $Shortcut = $Shell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = Join-Path $ProjectRoot "START-BSC-DLP.cmd"
        $Shortcut.WorkingDirectory = $ProjectRoot
        $Shortcut.IconLocation = "$BrandIcon,0"
        $Shortcut.Description = "BSC DLP Community - Data Loss Prevention"
        $Shortcut.Save()
    }
    catch {
        Write-Warning "Could not create the BSC DLP desktop shortcut: $($_.Exception.Message)"
    }
}
$HomeDir = Join-Path $env:LOCALAPPDATA "BSC-DLP-Community"
$ConfigDir = Join-Path $HomeDir "config"
$DataDir = Join-Path $HomeDir "data"
$SecretsDir = Join-Path $HomeDir "secrets"
$LogsDir = Join-Path $HomeDir "logs"
$RuntimeDir = Join-Path $HomeDir "runtime"
$BinDir = Join-Path $HomeDir "bin"
$QuarantineDir = Join-Path $HomeDir "quarantine"

foreach ($Dir in @($HomeDir,$ConfigDir,$DataDir,$SecretsDir,$LogsDir,$RuntimeDir,$BinDir,$QuarantineDir)) {
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
}

Write-Host ""
Write-Host "BSC DLP Community v0.6.9" -ForegroundColor Magenta
Write-Host "[1/6] Preparing local runtime..." -ForegroundColor Cyan

$ExistingDatabase = Join-Path $DataDir "dlp.db"
if (Test-Path $ExistingDatabase) {
    Write-Host "BSC DLP: existing Community runtime detected. Administrative account and telemetry will be preserved." -ForegroundColor DarkGray
    Write-Host "For a clean first-access setup, run RESET-BSC-DLP.cmd before starting." -ForegroundColor DarkGray
}

$EnrollmentKeyFile = Join-Path $ConfigDir "enrollment.key"
if (-not (Test-Path $EnrollmentKeyFile)) {
    $Bytes = New-Object byte[] 32
    $Rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $Rng.GetBytes($Bytes) } finally { $Rng.Dispose() }
    [System.IO.File]::WriteAllText(
        $EnrollmentKeyFile,
        [Convert]::ToBase64String($Bytes),
        [System.Text.Encoding]::ASCII
    )
}

$env:BSC_DLP_HOME = $HomeDir
$env:BSC_DLP_ENROLLMENT_KEY_FILE = $EnrollmentKeyFile
$env:BSC_DLP_HOST = $ListenAddress
$env:BSC_DLP_PORT = [string]$Port

$BaseUrl = "http://127.0.0.1:$Port"
if ([string]::IsNullOrWhiteSpace($PublicUrl)) {
    if ($ListenAddress -eq "127.0.0.1" -or $ListenAddress -eq "localhost") {
        $PublicUrl = $BaseUrl
    } else {
        $Candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
            Sort-Object -Property InterfaceMetric | Select-Object -First 1
        if ($Candidate) { $PublicUrl = "http://$($Candidate.IPAddress):$Port" } else { $PublicUrl = $BaseUrl }
    }
}
$PublicUrl = $PublicUrl.TrimEnd('/')
$env:BSC_DLP_PUBLIC_URL = $PublicUrl
$ApiUrl = "$BaseUrl/api/v1"

function Test-BscPortFree {
    param([int]$CandidatePort)
    $Listener = $null
    try {
        $Listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $CandidatePort)
        $Listener.Start()
        return $true
    }
    catch { return $false }
    finally { if ($Listener) { try { $Listener.Stop() } catch {} } }
}

function Test-BscHealth {
    try {
        $h = Invoke-RestMethod -Method Get -Uri "$ApiUrl/health" -TimeoutSec 1
        return ($h.status -eq "ok" -and $h.engine -eq "BSC DLP" -and $h.version -eq "0.6.9")
    }
    catch { return $false }
}

# Stop stale processes previously launched by this portable runtime.
foreach ($PidFile in @("agent.pid", "server.pid")) {
    $Path = Join-Path $RuntimeDir $PidFile
    if (Test-Path $Path) {
        $OldPid = (Get-Content $Path -Raw -ErrorAction SilentlyContinue).Trim()
        if ($OldPid -match '^\d+$') {
            Stop-Process -Id ([int]$OldPid) -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $Path -Force -ErrorAction SilentlyContinue
    }
}

# If the requested port is occupied by another process/version, choose the next
# available local port instead of failing with an opaque backend health error.
if (-not (Test-BscHealth) -and -not (Test-BscPortFree -CandidatePort $Port)) {
    if ($PublicUrlWasExplicit) {
        throw "TCP port $Port is already in use. Choose another -Port when using an explicit -PublicUrl."
    }

    $RequestedPort = $Port
    $FoundPort = $null
    foreach ($CandidatePort in (($RequestedPort + 1)..($RequestedPort + 50))) {
        if (Test-BscPortFree -CandidatePort $CandidatePort) { $FoundPort = $CandidatePort; break }
    }
    if (-not $FoundPort) { throw "No free TCP port was found between $($RequestedPort + 1) and $($RequestedPort + 50)." }

    $Port = [int]$FoundPort
    $env:BSC_DLP_PORT = [string]$Port
    $BaseUrl = "http://127.0.0.1:$Port"
    if ($ListenAddress -eq "127.0.0.1" -or $ListenAddress -eq "localhost") {
        $PublicUrl = $BaseUrl
    } else {
        $Candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
            Sort-Object -Property InterfaceMetric | Select-Object -First 1
        if ($Candidate) { $PublicUrl = "http://$($Candidate.IPAddress):$Port" } else { $PublicUrl = $BaseUrl }
    }
    $PublicUrl = $PublicUrl.TrimEnd('/')
    $env:BSC_DLP_PUBLIC_URL = $PublicUrl
    $ApiUrl = "$BaseUrl/api/v1"
    Write-Host "BSC DLP: port $RequestedPort is in use; using $Port instead." -ForegroundColor Yellow
}

Write-Host "[2/6] Starting backend..." -ForegroundColor Cyan

# ----- server -----
$ServerExe = Join-Path $ProjectRoot "bsc-dlp-server.exe"
$ServerProcess = $null

if (-not (Test-BscHealth)) {
    if (Test-Path $ServerExe) {
        $ServerArgs = @{
            FilePath = $ServerExe
            WorkingDirectory = $ProjectRoot
            WindowStyle = "Hidden"
            PassThru = $true
            RedirectStandardOutput = (Join-Path $LogsDir "server.out.log")
            RedirectStandardError = (Join-Path $LogsDir "server.err.log")
        }
        $ServerProcess = Start-Process @ServerArgs
    }
    else {
        # Contributor/source mode: bootstrap a private Python runtime automatically.
        $VenvDir = Join-Path $HomeDir "venv"
        $VenvPython = Join-Path $VenvDir "Scripts\python.exe"

        if (-not (Test-Path $VenvPython)) {
            $Python = Get-Command python.exe -ErrorAction SilentlyContinue
            if (-not $Python) {
                $Python = Get-Command py.exe -ErrorAction SilentlyContinue
            }
            if (-not $Python) {
                throw "This is a source package and Python was not found. Use the prebuilt Community release or install Python 3.10+."
            }

            if ($Python.Name -eq "py.exe") {
                & $Python.Source -3 -m venv $VenvDir
            } else {
                & $Python.Source -m venv $VenvDir
            }
            if ($LASTEXITCODE -ne 0) { throw "Could not create the BSC DLP Python runtime." }
        }

        $RequirementsFile = Join-Path $ProjectRoot "requirements.txt"
        $RequirementsMarker = Join-Path $VenvDir "requirements.sha256"
        $RequirementsHash = (Get-FileHash -Algorithm SHA256 -Path $RequirementsFile).Hash
        $InstalledHash = ""
        if (Test-Path $RequirementsMarker) {
            $InstalledHash = (Get-Content $RequirementsMarker -Raw -ErrorAction SilentlyContinue).Trim()
        }
        if ($InstalledHash -ne $RequirementsHash) {
            Write-Host "      Installing backend dependencies (first run/update only)..." -ForegroundColor DarkGray
            & $VenvPython -m pip --disable-pip-version-check install -q -r $RequirementsFile
            if ($LASTEXITCODE -ne 0) { throw "Could not install backend dependencies." }
            Set-Content -Path $RequirementsMarker -Value $RequirementsHash -Encoding ASCII -NoNewline
        } else {
            Write-Host "      Backend dependencies already ready." -ForegroundColor DarkGray
        }

        $ServerArgs = @{
            FilePath = $VenvPython
            ArgumentList = @("server.py")
            WorkingDirectory = $ProjectRoot
            WindowStyle = "Hidden"
            PassThru = $true
            RedirectStandardOutput = (Join-Path $LogsDir "server.out.log")
            RedirectStandardError = (Join-Path $LogsDir "server.err.log")
        }
        $ServerProcess = Start-Process @ServerArgs
    }

    Set-Content -Path (Join-Path $RuntimeDir "server.pid") -Value $ServerProcess.Id -Encoding ASCII -NoNewline
}

$Healthy = $false
for ($i=0; $i -lt 60; $i++) {
    if (Test-BscHealth) { $Healthy = $true; break }
    Start-Sleep -Milliseconds 250
}
if (-not $Healthy) {
    $ErrorLog = Join-Path $LogsDir "server.err.log"
    Write-Host ""
    Write-Host "BSC DLP backend did not become healthy on $BaseUrl." -ForegroundColor Red
    if (Test-Path $ErrorLog) {
        Write-Host "Last backend log lines:" -ForegroundColor Yellow
        Get-Content $ErrorLog -Tail 20 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  $_" }
    }
    throw "BSC DLP backend startup failed."
}

Write-Host "[3/6] Backend healthy on $BaseUrl" -ForegroundColor Green
Write-Host "[4/6] Enrolling local endpoint..." -ForegroundColor Cyan

# ----- endpoint enrollment -----
$EndpointId = "bsc-dlp-$([System.Net.Dns]::GetHostName())"
$Key = (Get-Content $EnrollmentKeyFile -Raw).Trim()
$EnrollArgs = @{
    Method = "Post"
    Uri = "$ApiUrl/enroll"
    Headers = @{ "X-Enrollment-Key" = $Key }
    ContentType = "application/json"
    Body = (@{ endpoint_id = $EndpointId } | ConvertTo-Json -Compress)
}
$Response = Invoke-RestMethod @EnrollArgs

$TokenFile = Join-Path $SecretsDir "agent.token"
[System.IO.File]::WriteAllText($TokenFile, [string]$Response.token, [System.Text.Encoding]::ASCII)

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

Write-Host "[5/6] Preparing endpoint agent..." -ForegroundColor Cyan

# ----- agent -----
$ReleaseAgent = Join-Path $ProjectRoot "bsc-dlp-agent.exe"
if (Test-Path $ReleaseAgent) {
    $AgentExe = $ReleaseAgent
} else {
    # Source/contributor mode: always rebuild so an older runtime binary cannot
    # silently survive an upgrade.
    $Go = Get-Command go.exe -ErrorAction SilentlyContinue
    if (-not $Go) {
        throw "This is a source package and Go was not found. Use the prebuilt Community release or install Go."
    }
    $AgentExe = Join-Path $BinDir "bsc-dlp-agent.exe"
    Push-Location (Join-Path $ProjectRoot "agent")
    try {
        & $Go.Source build -trimpath -ldflags "-s -w" -o $AgentExe .
        if ($LASTEXITCODE -ne 0) { throw "Could not build the Windows endpoint agent." }
    }
    finally { Pop-Location }
}

$env:BSC_DLP_API = $ApiUrl
$env:BSC_DLP_TOKEN_FILE = $TokenFile
$env:BSC_DLP_ENDPOINT_ID = $EndpointId
$env:BSC_DLP_LOG_FILE = Join-Path $LogsDir "agent.log"
$env:BSC_DLP_QUARANTINE = $QuarantineDir

$Tesseract = Ensure-BscTesseract
if ($Tesseract) {
    $env:BSC_DLP_TESSERACT = $Tesseract
    $env:BSC_DLP_OCR_LANGS = "por+eng,eng"
    Write-Host "      OCR enabled: $Tesseract" -ForegroundColor DarkGray
} else {
    Write-Warning "OCR is not installed. The console will still start; image/scanned-PDF OCR will be unavailable until Tesseract is installed."
}

$AgentArgs = @{
    FilePath = $AgentExe
    WorkingDirectory = $ProjectRoot
    WindowStyle = "Hidden"
    PassThru = $true
}
$AgentProcess = Start-Process @AgentArgs
Set-Content -Path (Join-Path $RuntimeDir "agent.pid") -Value $AgentProcess.Id -Encoding ASCII -NoNewline

Write-Host "[6/6] BSC DLP is ready." -ForegroundColor Green
Write-Host ""
Write-Host "BSC DLP v0.6.7 is running." -ForegroundColor Green
Write-Host "Dashboard: $BaseUrl"
Write-Host "Endpoint URL: $PublicUrl"
Write-Host "Runtime:   $HomeDir"
Write-Host "Endpoint:  $EndpointId"
Write-Host ""

Ensure-BscShortcut

if (-not $NoBrowser) {
    Start-Process $BaseUrl
}
