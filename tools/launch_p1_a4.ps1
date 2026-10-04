# P1 A4 as implemented is closed (run 3b4d8207, entries [:100]).
# This launcher refuses. The registered A4 boots are tools/launch_p1_sweep.ps1
# after A5. Do not start the second half.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal,
    [int]$Seed = 20260930,
    [int]$EntryOffset = 0,
    [int]$EntryCount = 100
)

Write-Error "A4-as-implemented is closed"
exit 1
