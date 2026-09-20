#Requires -Version 5.1
<#
.SYNOPSIS
  Refuse measurement unless AC + AC processor throttle 100/100 (PORT-2).
.NOTES
  Exit 0 = ok.
  Exit 2 = AC offline (battery present and not on AC).
  Exit 3 = processor AC throttle not 100/100.
  Exit 4 = both.
  Scheme GUID is recorded but never matched — XPS Dell Best Performance and
  T2S stock High performance both pass when PROCTHROTTLEMIN/MAX are 100/100 on AC.
#>
param(
  [switch]$Quiet
)

$ErrorActionPreference = "Stop"

function Get-AcOnline {
  $batteries = @(Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue)
  if ($batteries.Count -eq 0) {
    return @{
      Online = $true
      Raw = "NO_BATTERY"
      BatteryPct = $null
      Reason = "no_battery_mains_only_assume_ac"
    }
  }
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class SeamPowerStatus {
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
  $sps = New-Object SeamPowerStatus+SYSTEM_POWER_STATUS
  [void][SeamPowerStatus]::GetSystemPowerStatus([ref]$sps)
  return @{
    Online = ($sps.ACLineStatus -eq 1)
    Raw = $sps.ACLineStatus
    BatteryPct = $sps.BatteryLifePercent
    Reason = "system_power_status"
  }
}

function Get-ActiveScheme {
  $line = (powercfg /getactivescheme | Out-String)
  if ($line -match 'GUID:\s*([0-9a-fA-F-]{36})\s*\((.+?)\)') {
    return @{ Guid = $Matches[1]; Name = $Matches[2].Trim() }
  }
  throw "Could not parse powercfg /getactivescheme: $line"
}

function Get-AcProcessorPercent([string]$Alias) {
  $text = powercfg /query SCHEME_CURRENT SUB_PROCESSOR $Alias | Out-String
  if ($text -match 'Current AC Power Setting Index:\s*(0x[0-9a-fA-F]+|\d+)') {
    $raw = $Matches[1]
    if ($raw -like '0x*') { return [Convert]::ToInt32($raw, 16) }
    return [int]$raw
  }
  return $null
}

$ac = Get-AcOnline
$scheme = Get-ActiveScheme
$minAc = Get-AcProcessorPercent "PROCTHROTTLEMIN"
$maxAc = Get-AcProcessorPercent "PROCTHROTTLEMAX"

$acOk = [bool]$ac.Online
$procOk = ($minAc -eq 100) -and ($maxAc -eq 100)

if (-not $Quiet) {
  Write-Host ("AC: online={0} raw={1} reason={2} battery%={3}" -f `
    $ac.Online, $ac.Raw, $ac.Reason, $ac.BatteryPct)
  Write-Host ("Plan (recorded, not matched): {0} ({1})" -f $scheme.Name, $scheme.Guid)
  Write-Host ("Processor AC: min={0} max={1} require=100/100 ok={2}" -f $minAc, $maxAc, $procOk)
  Write-Host ("acOk={0} procOk={1}" -f $acOk, $procOk)
}

if ($acOk -and $procOk) { exit 0 }
if (-not $acOk -and -not $procOk) { exit 4 }
if (-not $acOk) { exit 2 }
exit 3
