# Boot 2 order: 8B-int4 GPU u8, 4B-int8 GPU u8, DET-PROBE-KV, 4B-int4 CPU u8.
# estimate_s = base_s + canary_overhead_s.
# canary_overhead_s = 944.242457 - 192.106556 = 752.136 (c2246b1f wall minus probe walls).
# Ceiling base_s is the amendment-1 estimate (315, 338, 2010).
# DET-PROBE-KV base_s = 840.522 (cb9773be plan.json mtime to SUMMARY.json mtime), overhead 0.
# Ceilings of those sums are 1068, 1091, 841, 2763. The derivation is written
# into the boot summary as estimate_derivation.
# Launch and poll commands are reported outside this file so it does not
# embed a per-user absolute path.

[CmdletBinding()]
param(
    [switch]$Detach
)

$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $PSScriptRoot "launch_boot1.ps1"
if ($Detach) {
    & powershell -NoProfile -File $launcher -Profile boot2 -Detach
    exit $LASTEXITCODE
}
& powershell -NoProfile -File $launcher -Profile boot2
exit $LASTEXITCODE
