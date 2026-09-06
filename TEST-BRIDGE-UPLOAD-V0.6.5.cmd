@echo off
setlocal
cd /d "%~dp0"

call "%~dp0scripts\windows\Resolve-PowerShell.cmd"
if errorlevel 1 (
  pause
  exit /b 1
)

"%BSC_DLP_POWERSHELL%" -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$h=@{'X-BSC-DLP-Extension'='1'};" ^
  "$bytes=[Text.Encoding]::UTF8.GetBytes('BSC DLP UPLOAD TEST`nCPF: 123.456.789-09`n');" ^
  "$start=@{destination='upload-test.example';page_url='https://upload-test.example/';event_type='bridge_test';browser='BSC-DLP-Test';filename='clientes_teste.txt';content_type='text/plain';size=$bytes.Length}|ConvertTo-Json -Compress;" ^
  "$s=Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8765/v1/upload/start' -Headers $h -ContentType 'application/json' -Body $start;" ^
  "if(-not $s.upload_id){throw ('No upload_id: '+($s|ConvertTo-Json -Compress))};" ^
  "$chunk=@{upload_id=$s.upload_id;sequence=0;data=[Convert]::ToBase64String($bytes)}|ConvertTo-Json -Compress;" ^
  "Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8765/v1/upload/chunk' -Headers $h -ContentType 'application/json' -Body $chunk|Out-Null;" ^
  "$finish=@{upload_id=$s.upload_id}|ConvertTo-Json -Compress;" ^
  "$r=Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8765/v1/upload/finish' -Headers $h -ContentType 'application/json' -Body $finish;" ^
  "$r|ConvertTo-Json -Depth 5;" ^
  "if($r.block -eq $true){Write-Host '[PASS] Generic browser upload bridge blocked the synthetic sensitive file.' -ForegroundColor Green}else{Write-Host '[CHECK] Bridge responded but did not BLOCK. Check browser_upload policies and agent log.' -ForegroundColor Yellow}"

pause
