#Requires -Version 5.1
<#
.SYNOPSIS
  Abort C1 runs unless AC + pinned power plan match MACHINE.md.
.NOTES
  Exit 0 = pinned OK. Exit 2 = AC offline. Exit 3 = wrong plan. Exit 4 = both.
#>
param(
  [string]$MachineMd = (Join-Path $PSScriptRoot "..\MACHINE.md"),
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"

function Get-AcOnline {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class C1PowerStatus {
  [DllImport("kernel32.dll")]
  public static extern bool GetSystemPowerStatus(out SYSTEM_POWER_STATUS sps);
  [StructLayout(LayoutKind.Sequential)]
  public struct SYSTEM_POWER_STATUS {
    public byte ACLineStatus;
    public byte BatteryFlag;
    public byte BatteryLifePercent;
    public byte SystemStatusFlag;
    public int BatteryLifeTime;
    public int BatteryFullLifeTime;
  }
}
"@ -ErrorAction SilentlyContinue
  $sps = New-Object C1PowerStatus+SYSTEM_POWER_STATUS
  [void][C1PowerStatus]::GetSystemPowerStatus([ref]$sps)
  return @{ Online = ($sps.ACLineStatus -eq 1); Raw = $sps.ACLineStatus; BatteryPct = $sps.BatteryLifePercent }
}

function Get-ActiveScheme {
  $line = (powercfg /getactivescheme | Out-String)
  if ($line -match 'GUID:\s*([0-9a-fA-F-]{36})\s*\((.+?)\)') {
    return @{ Guid = $Matches[1]; Name = $Matches[2].Trim() }
  }
  throw "Could not parse powercfg /getactivescheme: $line"
}

function Get-PinnedFromMachineMd([string]$path) {
  if (-not (Test-Path $path)) { throw "MACHINE.md not found: $path" }
  $guid = $null; $name = $null
  foreach ($line in Get-Content $path) {
    # MACHINE.md uses: - **Label:** `value`
    if ($line -match 'Pinned power plan GUID:\*\*\s+`([0-9a-fA-F-]+)`') { $guid = $Matches[1].Trim() }
    if ($line -match 'Pinned power plan name:\*\*\s+`([^`]+)`') { $name = $Matches[1].Trim() }
  }
  if (-not $guid -or -not $name) { throw "MACHINE.md missing pinned power plan GUID/name fields" }
  return @{ Guid = $guid; Name = $name }
}

$pin = Get-PinnedFromMachineMd $MachineMd
$ac = Get-AcOnline
$scheme = Get-ActiveScheme

$acOk = [bool]$ac.Online
$planOk = ($scheme.Guid -ieq $pin.Guid) -or ($scheme.Name -ieq $pin.Name)

if (-not $Quiet) {
  Write-Host ("AC: online={0} raw={1} battery%={2}" -f $ac.Online, $ac.Raw, $ac.BatteryPct)
  Write-Host ("Plan active: {0} ({1})" -f $scheme.Name, $scheme.Guid)
  Write-Host ("Plan pinned: {0} ({1})" -f $pin.Name, $pin.Guid)
  Write-Host ("acOk={0} planOk={1}" -f $acOk, $planOk)
}

if ($acOk -and $planOk) { exit 0 }
if (-not $acOk -and -not $planOk) { exit 4 }
if (-not $acOk) { exit 2 }
exit 3
