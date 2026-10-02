# P1 boot 1. Baseline greedy only.
# Arm smokes are tools/launch_p1_preflight.ps1, before the cold reboot.
# This boot's first GPU work is idle canary calibration.
# This script does not open a preregistration.
#
# Preflight, on the XPS, before reboot:
#   powershell -NoProfile -File tools\launch_p1_preflight.ps1
# Measurement, from the Mac, on a cold window:
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_a0.ps1 -Detach"
# Rehearsal log:
#   ssh zjohn@100.101.81.6 "powershell -NoProfile -Command Get-Content -Tail 80 <repo>/derived/c2_ttft/_launches/_rehearsal/p1-a0/p1-a0.log"
# REHEARSAL_COMPLETE is the success line.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @("-NoProfile", "-File", $launcher, "-Profile", "p1-a0")
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
if ($Rehearsal) { $launchArgs += "-Rehearsal" }
& powershell @launchArgs
exit $LASTEXITCODE
