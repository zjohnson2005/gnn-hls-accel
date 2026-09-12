$ErrorActionPreference = "Continue"
$pkg = Get-AppxPackage -Name "WindowsWorkload.SessionManager.1" -ErrorAction SilentlyContinue
Write-Host ("SessionManager InstallLocation: {0}" -f $pkg.InstallLocation)
if ($pkg) {
  Get-ChildItem -LiteralPath $pkg.InstallLocation -Recurse -Filter "*SessionHost*" -ErrorAction SilentlyContinue |
    Select-Object FullName, Length | Format-Table -AutoSize
  $man = Join-Path $pkg.InstallLocation "AppxManifest.xml"
  if (Test-Path $man) {
    Write-Host "=== SessionManager AppxManifest (filtered) ==="
    Select-String -LiteralPath $man -Pattern "Executable|DisplayName|EntryPoint|Category|Application Id" |
      ForEach-Object { $_.Line.Trim() }
  }
}

$pkg2 = Get-AppxPackage -Name "WindowsWorkload.Manager.1" -ErrorAction SilentlyContinue
Write-Host ("Manager InstallLocation: {0}" -f $pkg2.InstallLocation)
if ($pkg2) {
  Get-ChildItem -LiteralPath $pkg2.InstallLocation -Recurse -Filter "*SessionHost*" -ErrorAction SilentlyContinue |
    Select-Object FullName, Length | Format-Table -AutoSize
  $man2 = Join-Path $pkg2.InstallLocation "AppxManifest.xml"
  if (Test-Path $man2) {
    Write-Host "=== Manager AppxManifest (filtered) ==="
    Select-String -LiteralPath $man2 -Pattern "Executable|DisplayName|EntryPoint|Category|Application Id" |
      ForEach-Object { $_.Line.Trim() }
  }
}

Write-Host "=== where.exe WorkloadsSessionHost ==="
where.exe WorkloadsSessionHost 2>$null

Write-Host "=== Get-AppxPackagePackage *OpenVINO* all users attempt ==="
Get-AppxPackage -AllUsers -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match "OpenVINO" } |
  Select-Object Name, PackageFullName, PackageUserInformation |
  Format-List
