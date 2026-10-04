# P1 budget sweep. After A5. Fixed A0 and fixed A4.
# Default is A0, budget 10 s, seed 20260930, entries [:100].
# A4 over the same 100 entries is several boots. The ceiling is the
# step count times the budget, so the entry window has to be a registered slice.
# This script does not open a preregistration.
#
# A0, budget 10, from the Mac:
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach"
# A0, budget 20:
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -BudgetS 20"
# A0, budget 30:
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -BudgetS 30"
# A4, budget 10, entries [:83] then [83:100]:
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -EntryCount 83"
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -EntryOffset 83 -EntryCount 17"
# A4, budget 20, entries [:43], [43:83], [83:100]:
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 20 -EntryCount 43"
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 20 -EntryOffset 43 -EntryCount 40"
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 20 -EntryOffset 83 -EntryCount 17"
# A4, budget 30, entries [:27], [27:57], [57:82], [82:100]:
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryCount 27"
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 27 -EntryCount 30"
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 57 -EntryCount 25"
#   ssh zjohn@100.101.81.6 "cd <repo>; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 82 -EntryCount 18"

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal,
    [ValidateSet("A0", "A4")]
    [string]$Arm = "A0",
    [ValidateSet(10, 20, 30)]
    [int]$BudgetS = 10,
    [int]$Seed = 20260930,
    [int]$EntryOffset = 0,
    [int]$EntryCount = 100
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @(
    "-NoProfile", "-File", $launcher, "-Profile", "p1-sweep",
    "-P1Arm", $Arm, "-P1BudgetS", "$BudgetS",
    "-P1Seed", "$Seed", "-P1EntryOffset", "$EntryOffset", "-P1EntryCount", "$EntryCount"
)
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
if ($Rehearsal) { $launchArgs += "-Rehearsal" }
& powershell @launchArgs
exit $LASTEXITCODE
