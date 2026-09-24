# Boot 2. Same sequencer as boot 1, remaining cells plus DET-PROBE-KV.
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
