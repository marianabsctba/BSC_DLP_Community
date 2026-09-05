[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Add-Type -AssemblyName System.Drawing

$Downloads = [Environment]::GetFolderPath('UserProfile')
try {
    $Shell = New-Object -ComObject Shell.Application
    $Folder = $Shell.Namespace('shell:Downloads')
    if ($Folder -and $Folder.Self.Path) { $Downloads = $Folder.Self.Path }
} catch {
    $Downloads = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'
}

if (-not (Test-Path $Downloads)) {
    New-Item -ItemType Directory -Force -Path $Downloads | Out-Null
}

$Path = Join-Path $Downloads 'bsc-dlp-ocr-cpf-test.png'
$Bitmap = New-Object System.Drawing.Bitmap 1400,700
$Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
$Graphics.Clear([System.Drawing.Color]::White)
$FontTitle = New-Object System.Drawing.Font('Arial', 36, [System.Drawing.FontStyle]::Bold)
$FontBody = New-Object System.Drawing.Font('Arial', 42, [System.Drawing.FontStyle]::Regular)
$Brush = [System.Drawing.Brushes]::Black
try {
    $Graphics.DrawString('BSC DLP - OCR Test', $FontTitle, $Brush, 80, 90)
    $Graphics.DrawString('CPF: 529.982.247-25', $FontBody, $Brush, 80, 250)
    $Graphics.DrawString('Documento ficticio para teste de DLP', $FontBody, $Brush, 80, 390)
    $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    $FontTitle.Dispose()
    $FontBody.Dispose()
    $Graphics.Dispose()
    $Bitmap.Dispose()
}

Write-Host "" 
Write-Host "BSC DLP OCR test image created." -ForegroundColor Magenta
Write-Host "Path: $Path"
Write-Host "Expected: channel=download, document_type=png, classification=CPF, evidence=image_ocr"
Write-Host "Open the admin console and check Events/Incidents." -ForegroundColor DarkGray
