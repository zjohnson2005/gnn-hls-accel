# Boot 4. WARM-KV (f16, u8, u4) then DECODE-MATCH.
# Estimates are base_s + measured canary overhead. See launch_boot1.ps1 boot4.
#
# Rehearsal runs in the same context as the real launch: ssh from the Mac, then
# WMI detach (tools/spawn_detached.ps1). The Cursor terminal is refused.
#   ssh xps "cd <repo>; powershell -NoProfile -File tools\launch_boot4.ps1 -Detach -Rehearsal"
# Poll the detached log:
#   ssh xps "powershell -NoProfile -Command Get-Content -Tail 50 <repo>/derived/c2_ttft/_launches/_rehearsal/boot4/boot4.log"
# REHEARSAL_COMPLETE is the success line.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [switch]$Rehearsal
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @("-NoProfile", "-File", $launcher, "-Profile", "boot4")
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
if ($Rehearsal) { $launchArgs += "-Rehearsal" }
& powershell @launchArgs
exit $LASTEXITCODE
