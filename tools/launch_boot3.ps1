# Boot 3. The three cells boot 2 did not finish, in the same order.
# 4B-int8 GPU u8 (1091 s), DET-PROBE-KV (841 s), 4B-int4 CPU u8 (2763 s).

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @("-NoProfile", "-File", $launcher, "-Profile", "boot3")
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
& powershell @launchArgs
exit $LASTEXITCODE
