# DEMO-2 runtime-default readback (read-only). Prints JSON to the console;
# writes nothing in the repo. Loads the 4B int4 IR on GPU with no properties.
# Run when no measurement is active on the host (it uses the GPU for about a
# minute). Usage, from the repo root:
#   powershell -NoProfile -File tools\demo2_readback.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Host "REFUSED -- python missing: $PythonExe"
    exit 1
}
Push-Location $root
try {
    & $PythonExe (Join-Path $root "tools\demo2_readback.py")
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
