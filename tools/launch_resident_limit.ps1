# RESIDENT-LIMIT. One cell per KV arm. The search bounds are hardcoded in
# tools/run_resident_limit.py. This script does not open a preregistration.
#
# Rehearsal runs in the same context as the real launch: ssh from the Mac, then
# WMI detach (tools/spawn_detached.ps1). The Cursor terminal is refused.
#   ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_resident_limit.ps1 -Detach -Rehearsal"
# Poll the detached log:
#   ssh xps "powershell -NoProfile -Command Get-Content -Tail 50 C:/Users/zjohn/Projects/gnn-hls-accel/derived/c2_ttft/_launches/_rehearsal/resident-limit/resident-limit.log"
# REHEARSAL_COMPLETE is the success line.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @("-NoProfile", "-File", $launcher, "-Profile", "resident-limit")
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
if ($Rehearsal) { $launchArgs += "-Rehearsal" }
& powershell @launchArgs
exit $LASTEXITCODE
