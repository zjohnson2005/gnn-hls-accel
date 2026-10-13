# DEMO-1 V5-CAL: RESIDENT turn-2 TTFT at delta 8500 on five n_cached, u8 and
# u4, plus one V5-path point. One cold XPS boot, local-only, $0.
# This script does not open a preregistration.
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_v5_cal.ps1 -Detach -Rehearsal'
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_v5_cal.ps1 -Detach'

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @("-NoProfile", "-File", $launcher, "-Profile", "v5-cal")
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
if ($Rehearsal) { $launchArgs += "-Rehearsal" }
& powershell @launchArgs
exit $LASTEXITCODE
