# Boot 4. WARM-KV (f16, u8, u4) then DECODE-MATCH.
# Estimates are base_s + measured canary overhead. See launch_boot1.ps1 boot4.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
$launchArgs = @("-NoProfile", "-File", $launcher, "-Profile", "boot4")
if ($Detach) { $launchArgs += "-Detach" }
if ($DryRun) { $launchArgs += "-DryRun" }
& powershell @launchArgs
exit $LASTEXITCODE
