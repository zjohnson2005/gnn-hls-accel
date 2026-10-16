# KV cache precision readback from compiled cache ports (read-only).
# Prints JSON to the console; writes nothing in the repo. Uses the GPU for a
# few minutes; run only when no measurement is active on the host.
# Usage, from the repo root:
#   powershell -NoProfile -File tools\kv_compiled_readback.ps1
#   powershell -NoProfile -File tools\kv_compiled_readback.ps1 -Kv default
param(
    [ValidateSet("all", "default", "u8", "u4", "f16")]
    [string]$Kv = "all"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Host "REFUSED -- python missing: $PythonExe"
    exit 1
}
Push-Location $root
try {
    & $PythonExe (Join-Path $root "tools\kv_compiled_readback.py") --kv $Kv
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
