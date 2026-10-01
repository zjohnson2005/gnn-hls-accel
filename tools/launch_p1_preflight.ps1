# P1 arm smokes. Run this before the cold reboot, then reboot, then
# tools/launch_p1_a0.ps1 -Detach. The measurement boot does not run these
# smokes. Its first GPU work is canary calibration with no P1 pipeline loaded.
#   powershell -NoProfile -File tools\launch_p1_preflight.ps1

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
Set-Location $root
$python = Join-Path $root ".venv-seam\Scripts\python.exe"
& $python -u (Join-Path $root "tools\run_p1_quality.py") --smoke
exit $LASTEXITCODE
