# T2S boot 1. f16 control at n=18687, then 4B-int4 GPU u8, then 8B-int4 GPU u8.
# Same cell machinery as launch_boot4.ps1. -Detach is launch_boot1.ps1
# -Detach, which uses tools/spawn_detached.ps1 (Win32_Process.Create).
# -Detach refuses unless the last non-digest entry of -WatchdogLog (default
# C:\apu\ovn\watchdog.log) is idle: {"action":"empty_flag"} or {"action":"paused"},
# no python or llama-server is running, and free memory is at least 24000 MB.
# -NoRebootDeviation skips only the uptime gate and records UNCOLD_UPTIME.
# This script does not register a logon task or a scheduled task.
# This script does not open the PARITY-REMEASURE prereg.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal,
    [switch]$NoRebootDeviation,
    [string]$WatchdogLog = "C:\apu\ovn\watchdog.log"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv-seam\Scripts\python.exe"
$watchdog = Join-Path $PSScriptRoot "t2s_queue_watchdog.py"

if ($Detach -and -not $DryRun) {
    $floorMb = 24000
    $names = @(Get-Process -Name python, llama-server -ErrorAction SilentlyContinue |
        ForEach-Object { $_.ProcessName })
    if ($names.Count -eq 0) {
        $running = "[]"
    } else {
        $running = ConvertTo-Json -InputObject @($names) -Compress
    }
    & $python $watchdog launch-check --log $WatchdogLog --running-json $running
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $freeMb = (Get-Counter '\Memory\Available MBytes').CounterSamples[0].CookedValue
    if ([double]$freeMb -lt $floorMb) {
        Write-Host ("REFUSED -- free memory {0} MB is below floor {1}" -f [int]$freeMb, $floorMb)
        exit 1
    }
}

$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @("-NoProfile", "-File", $launcher, "-Profile", "t2s-boot1")
$launchArgs += @("-WatchdogLog", $WatchdogLog)
if ($Rehearsal) { $launchArgs += "-Rehearsal" }
if ($NoRebootDeviation) { $launchArgs += "-NoRebootDeviation" }
if ($Detach -and -not $DryRun) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
& powershell @launchArgs
exit $LASTEXITCODE
