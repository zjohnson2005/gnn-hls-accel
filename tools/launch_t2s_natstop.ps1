# T2S NPU-NATSTOP. Diagnostic, not a measurement. One detached session, 16 child
# processes in sequence (tools/npu_natstop.py), never two NPU pipelines at once.
# Modeled on tools/launch_t2s_npu1.ps1.
# -Detach refuses unless the watchdog log is idle, no python or llama-server
# is running, and free memory is at least 24000 MB. It then respawns this
# script through tools/spawn_detached.ps1 (WMI child) with its own log:
#   derived\c2_ttft\_launches\npu-natstop_<UTC stamp>.log
# -Rehearsal runs the same path with the smoke children (no openvino) and
# writes under derived\c2_ttft\_launches\_rehearsal\npu-natstop\. Its log ends
# REHEARSAL_COMPLETE. A real run's log ends NATSTOP_COMPLETE.
# Run dir: derived\npu\natstop_<run_id>\ (printed as NATSTOP_VERDICT ... <dir>).
# This host is not rebooted; there is no cold-window gate (nothing is cited).
# This script does not open the NPU-NATSTOP rule file.
# This script does not register a logon task or a scheduled task.
#
# From the Mac (rehearsal, then real):
#   ssh zach@100.72.40.24 'cd C:\Users\zach\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_t2s_natstop.ps1 -Detach -Rehearsal'
#   ssh zach@100.72.40.24 'cd C:\Users\zach\Projects\gnn-hls-accel; git pull --ff-only; .\tools\launch_t2s_natstop.ps1 -Detach'

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$Rehearsal,
    [string]$WatchdogLog = "C:\apu\ovn\watchdog.log"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root ".venv-seam\Scripts\python.exe"
$watchdog = Join-Path $PSScriptRoot "t2s_queue_watchdog.py"
$natstopPy = Join-Path $PSScriptRoot "npu_natstop.py"
$spawn = Join-Path $PSScriptRoot "spawn_detached.ps1"
. (Join-Path $PSScriptRoot "_assert_machine_lock.ps1")
. (Join-Path $PSScriptRoot "wsh_policy.ps1")

$launchDir = Join-Path $root "derived\c2_ttft\_launches"
if ($Rehearsal) { $launchDir = Join-Path $launchDir "_rehearsal\npu-natstop" }
$macRehearsal = "ssh zach@100.72.40.24 'cd C:\Users\zach\Projects\gnn-hls-accel; .\tools\launch_t2s_natstop.ps1 -Detach -Rehearsal'"

if ($Detach) {
    if ($Rehearsal) {
        if (-not (Test-SeamProcessAncestor -Names @("sshd.exe") -Depth 4)) {
            Write-Host "REFUSED -- rehearsal -Detach must be started from ssh, not this terminal."
            Write-Host ("From the Mac: {0}" -f $macRehearsal)
            exit 1
        }
    } else {
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
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $log = Join-Path $launchDir ("npu-natstop_" + $stamp + ".log")
    if (Test-Path -LiteralPath $log) {
        Write-Host ("REFUSED -- log exists: {0}" -f $log)
        exit 1
    }
    $cmd = "powershell -NoProfile -File `"$PSCommandPath`" -WatchdogLog `"$WatchdogLog`""
    if ($Rehearsal) { $cmd += " -Rehearsal" }
    $json = & $spawn -CommandLine $cmd -LogPath $log -WorkingDirectory $root
    Write-Host $json
    Write-Host "launched npu-natstop detached"
    Write-Host ("  log : {0}" -f $log)
    exit 0
}

# Not -Detach: this must be the WMI child of an ssh launch.
if (-not (Test-SeamProcessAncestor -Names @("WmiPrvSE.exe") -Depth 4)) {
    Write-Host "REFUSED -- run with -Detach from ssh; this body runs only as the WMI child."
    Write-Host ("From the Mac: {0}" -f $macRehearsal)
    exit 1
}

Write-Host ("npu-natstop rehearsal={0} utc={1}" -f [bool]$Rehearsal, (Get-Date).ToUniversalTime().ToString("o"))
Assert-SeamMachineLockClear -RepoRoot $root

$pyArgs = @("-u", $natstopPy, "--watchdog-log", $WatchdogLog)
if ($Rehearsal) {
    $pyArgs += @("--smoke", "--out", (Join-Path $launchDir "runs"))
}
& $python @pyArgs
$code = $LASTEXITCODE
Write-Host ("npu_natstop exit={0}" -f $code)
if ($code -ne 0) { exit $code }
if ($Rehearsal) { Write-Host "REHEARSAL_COMPLETE" } else { Write-Host "NATSTOP_COMPLETE" }
exit 0
