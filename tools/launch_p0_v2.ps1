# P0-v2. The exchange-rate cell only. u4 already ran.
# This script does not open a preregistration.
#
# Measurement, from the Mac, on a cold window:
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p0_v2.ps1 -Detach"
# Rehearsal log:
#   ssh zjohn@100.101.81.6 "powershell -NoProfile -Command Get-Content -Tail 50 <repo>/derived/c2_ttft/_launches/_rehearsal/p0-v2/p0-v2.log"
# REHEARSAL_COMPLETE is the success line.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @("-NoProfile", "-File", $launcher, "-Profile", "p0-v2")
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
if ($Rehearsal) { $launchArgs += "-Rehearsal" }
& powershell @launchArgs
exit $LASTEXITCODE
