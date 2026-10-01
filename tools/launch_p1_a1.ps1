# P1 A1. One registered half of one seed. Default is seed 20260930, entries [:100].
# Arm smokes are tools/launch_p1_preflight.ps1, before the cold reboot.
# This script does not open a preregistration.
#
# First half, seed 20260930, from the Mac, on a cold window:
#   ssh zjohn@100.101.81.6 "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_p1_a1.ps1 -Detach"
# Second half, same seed:
#   ssh zjohn@100.101.81.6 "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_p1_a1.ps1 -Detach -EntryOffset 100"
# First half, seed 20261001:
#   ssh zjohn@100.101.81.6 "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_p1_a1.ps1 -Detach -Seed 20261001"
# Second half, seed 20261001:
#   ssh zjohn@100.101.81.6 "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_p1_a1.ps1 -Detach -Seed 20261001 -EntryOffset 100"

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal,
    [int]$Seed = 20260930,
    [int]$EntryOffset = 0,
    [int]$EntryCount = 100
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @(
    "-NoProfile", "-File", $launcher, "-Profile", "p1-a1",
    "-P1Seed", "$Seed", "-P1EntryOffset", "$EntryOffset", "-P1EntryCount", "$EntryCount"
)
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
if ($Rehearsal) { $launchArgs += "-Rehearsal" }
& powershell @launchArgs
exit $LASTEXITCODE
