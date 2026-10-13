# P1 budget sweep. After A5. Fixed A0 and fixed A4.
# Default is A0, budget 10 s, seed 20260930, entries [:100].
# The A4 slices are amendment 9: every boot estimate is at most 6000 s, so it
# fits the cold window. Any other slice is refused (launch_boot1.ps1 table).
# This script does not open a preregistration.
#
# Boots in order (each after a cold reboot), from the Mac:
#   A0 B=10 [0:100] est 2891 s (done: bdc32a87):
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach'
#   A4 B=10 [0:53] est 4718 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -EntryCount 53'
#   A4 B=10 [53:100] est 4688 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -EntryOffset 53 -EntryCount 47'
#   A0 B=20 [0:100] est 2941 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -BudgetS 20'
#   A4 B=20 [0:25] est 4678 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 20 -EntryCount 25'
#   A4 B=20 [25:53] est 4758 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 20 -EntryOffset 25 -EntryCount 28'
#   A4 B=20 [53:77] est 4658 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 20 -EntryOffset 53 -EntryCount 24'
#   A4 B=20 [77:100] est 4718 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 20 -EntryOffset 77 -EntryCount 23'
#   A0 B=30 [0:100] est 2991 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -BudgetS 30'
#   A4 B=30 [0:21] est 5558 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryCount 21'
#   A4 B=30 [21:42] est 5468 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 21 -EntryCount 21'
#   A4 B=30 [42:61] est 5378 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 42 -EntryCount 19'
#   A4 B=30 [61:81] est 5498 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 61 -EntryCount 20'
#   A4 B=30 [81:100] est 5558 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 81 -EntryCount 19'
#   A0 B=10 [100:200] est 2787 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -EntryOffset 100'
#   A4 B=10 [100:147] est 4468 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -EntryOffset 100 -EntryCount 47'
#   A4 B=10 [147:200] est 4498 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -EntryOffset 147 -EntryCount 53'
#   A0 B=20 [100:200] est 2877 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -BudgetS 20 -EntryOffset 100'
#   A4 B=20 [100:131] est 5758 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 20 -EntryOffset 100 -EntryCount 31'
#   A4 B=20 [131:164] est 5758 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 20 -EntryOffset 131 -EntryCount 33'
#   A4 B=20 [164:200] est 5658 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 20 -EntryOffset 164 -EntryCount 36'
#   A0 B=30 [100:200] est 2967 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -BudgetS 30 -EntryOffset 100'
#   A4 B=30 [100:115] est 5228 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 100 -EntryCount 15'
#   A4 B=30 [115:136] est 5228 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 115 -EntryCount 21'
#   A4 B=30 [136:157] est 5228 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 136 -EntryCount 21'
#   A4 B=30 [157:179] est 5108 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 157 -EntryCount 22'
#   A4 B=30 [179:200] est 5348 s:
#   ssh zjohn@100.101.81.6 'cd <repo>; git pull --ff-only; powershell -NoProfile -File tools\launch_p1_sweep.ps1 -Detach -Arm A4 -BudgetS 30 -EntryOffset 179 -EntryCount 21'

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
