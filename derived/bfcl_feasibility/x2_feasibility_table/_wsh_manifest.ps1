$ErrorActionPreference = "Continue"
$loc = (Get-AppxPackage -Name "WindowsWorkload.Manager.1").InstallLocation
$man = Join-Path $loc "AppxManifest.xml"
Write-Host ("MANIFEST={0}" -f $man)
Get-Content -LiteralPath $man | Select-String -Pattern "Executable|OutOfProcessServer|WorkloadsSessionHost|Category|Extension|uap10|desktop4|windows.activatable" |
  ForEach-Object { $_.Line.Trim() }

Write-Host "=== full exe path ==="
$exe = Join-Path $loc "WorkloadsSessionHost.exe"
Get-Item -LiteralPath $exe | Format-List FullName, Length, LastWriteTime

Write-Host "=== scheduled tasks broader search ==="
Get-ScheduledTask -ErrorAction SilentlyContinue |
  Where-Object {
    $_.Actions.Execute -match "Workload|SessionHost|OpenVINO" -or
    $_.TaskName -match "Workload|SessionHost|OpenVINO|AI|Copilot" -or
    $_.TaskPath -match "Workload|OpenVINO|Copilot|WindowsAI"
  } |
  Select-Object TaskName, TaskPath, State |
  Format-Table -AutoSize

Write-Host "=== Get-CimInstance Win32_Service filtered ==="
Get-CimInstance Win32_Service -ErrorAction SilentlyContinue |
  Where-Object {
    $_.Name -match "Workload|OpenVINO|SessionHost|WindowsAI" -or
    $_.PathName -match "Workload|SessionHost|OpenVINO" -or
    $_.DisplayName -match "Workload|SessionHost|OpenVINO"
  } |
  Select-Object Name, State, StartMode, PathName |
  Format-List
