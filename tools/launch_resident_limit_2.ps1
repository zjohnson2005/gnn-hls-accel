# RESIDENT-LIMIT-2. The deferred u4 arm. Search bounds stay in the runner.
# This script does not open a preregistration.
#
# Rehearsal includes the hang fault-injection child, then the u4 smoke.
#   ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_resident_limit_2.ps1 -Detach -Rehearsal"
# Poll:
#   ssh xps "powershell -NoProfile -Command Get-Content -Tail 50 C:/Users/zjohn/Projects/gnn-hls-accel/derived/c2_ttft/_launches/_rehearsal/resident-limit-2/resident-limit-2.log"
# REHEARSAL_COMPLETE is the success line.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @("-NoProfile", "-File", $launcher, "-Profile", "resident-limit-2")
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
if ($Rehearsal) { $launchArgs += "-Rehearsal" }
& powershell @launchArgs
exit $LASTEXITCODE
