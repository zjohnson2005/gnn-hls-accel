# T2S NPU-1 / NPU-2. One MAX_PROMPT_LEN per detached session.
# -Detach refuses unless the watchdog log is idle, no python or llama-server
# is running, and free memory is at least 24000 MB.
# -NoRebootDeviation is always passed: this host is not rebooted.
# This script does not open the NPU preregistration.
# This script does not register a logon task or a scheduled task.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal,
    [switch]$Npu2,
    [switch]$LoadOnly,
    [int]$MaxPromptLen = 0,
    [string]$WatchdogLog = "C:\apu\ovn\watchdog.log"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv-seam\Scripts\python.exe"
$watchdog = Join-Path $PSScriptRoot "t2s_queue_watchdog.py"

if ($Detach -and -not $DryRun -and -not $Rehearsal) {
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
$launchArgs = @(
    "-NoProfile", "-File", $launcher,
    "-Profile", "npu-1",
    "-NoRebootDeviation",
    "-WatchdogLog", $WatchdogLog
)
if ($Rehearsal) { $launchArgs += "-Rehearsal" }
if ($Detach -and -not $DryRun) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
if ($Npu2) { $launchArgs += "-Npu2" }
if ($LoadOnly) { $launchArgs += "-LoadOnly" }
if ($MaxPromptLen -gt 0) { $launchArgs += @("-MaxPromptLen", [string]$MaxPromptLen) }
& powershell @launchArgs
exit $LASTEXITCODE
