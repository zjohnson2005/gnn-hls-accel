# Read-only WSH / Appx / task investigation. No Remove-* / Disable-*.
$ErrorActionPreference = "Continue"
Write-Host "=== Appx (current user) OpenVINO/Workload ==="
Get-AppxPackage -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match "OpenVINO|Workload" } |
  Select-Object Name, PackageFullName, Status, InstallLocation |
  Format-List

Write-Host "=== AppxProvisionedPackage -Online (OpenVINO/Workload) ==="
try {
  Get-AppxProvisionedPackage -Online -ErrorAction Stop |
    Where-Object { $_.DisplayName -match "OpenVINO|Workload" } |
    Select-Object DisplayName, PackageName, Version, InstallLocation |
    Format-List
} catch {
  Write-Host ("Get-AppxProvisionedPackage failed: {0}" -f $_.Exception.Message)
}

Write-Host "=== Scheduled tasks (name/path match) ==="
Get-ScheduledTask -ErrorAction SilentlyContinue |
  Where-Object {
    $_.TaskName -match "Workload|OpenVINO|SessionHost|Copilot|Intel" -or
    $_.TaskPath -match "Workload|OpenVINO|Copilot|Intel"
  } |
  Select-Object TaskName, TaskPath, State |
  Format-Table -AutoSize

Write-Host "=== Services (name/display match) ==="
Get-Service -ErrorAction SilentlyContinue |
  Where-Object {
    $_.Name -match "Workload|OpenVINO|NPU|IntelAI|SessionHost" -or
    $_.DisplayName -match "Workload|OpenVINO|SessionHost|Intel.*AI"
  } |
  Format-Table Name, Status, StartType, DisplayName -AutoSize

Write-Host "=== WSH process ==="
Get-Process -Name WorkloadsSessionHost -ErrorAction SilentlyContinue |
  Select-Object Id, StartTime, @{n="WS_MB";e={[math]::Round($_.WorkingSet64/1MB,1)}}, Path |
  Format-List

Write-Host "=== WSH Win32_Process ==="
Get-CimInstance Win32_Process -Filter "Name='WorkloadsSessionHost.exe'" -ErrorAction SilentlyContinue |
  Select-Object ProcessId, ParentProcessId, CommandLine, CreationDate |
  Format-List

Write-Host "=== Parent of WSH if present ==="
$wsh = Get-CimInstance Win32_Process -Filter "Name='WorkloadsSessionHost.exe'" -ErrorAction SilentlyContinue
foreach ($p in @($wsh)) {
  $parent = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $p.ParentProcessId) -ErrorAction SilentlyContinue
  Write-Host ("WSH pid={0} parent_pid={1} parent_name={2} parent_cmd={3}" -f `
    $p.ProcessId, $p.ParentProcessId, $parent.Name, $parent.CommandLine)
}

Write-Host "=== Startup / Run keys (HKCU+HKLM, filtered) ==="
$runKeys = @(
  "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
  "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
  "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
)
foreach ($k in $runKeys) {
  if (Test-Path $k) {
    Get-ItemProperty $k -ErrorAction SilentlyContinue |
      Select-Object * -ExcludeProperty PS* |
      ForEach-Object {
        $_.PSObject.Properties | Where-Object {
          $_.Name -match "Workload|OpenVINO|SessionHost|Intel" -or
          [string]$_.Value -match "Workload|OpenVINO|SessionHost|WorkloadsSessionHost"
        } | ForEach-Object {
          Write-Host ("{0} :: {1} = {2}" -f $k, $_.Name, $_.Value)
        }
      }
  }
}

Write-Host "=== PackageFamilyName / Appx package status for known names ==="
$names = @(
  "WindowsWorkload.EP.Intel.OpenVINO.1.8",
  "WindowsWorkload.EP.Intel.OpenVINO.Framework.1.8"
)
foreach ($n in $names) {
  $pkgs = @(Get-AppxPackage -Name $n -ErrorAction SilentlyContinue)
  Write-Host ("{0}: count={1}" -f $n, $pkgs.Count)
  $pkgs | ForEach-Object { Write-Host ("  {0}" -f $_.PackageFullName) }
}
