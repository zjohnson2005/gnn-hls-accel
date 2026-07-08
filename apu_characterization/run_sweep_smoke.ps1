# Concurrency sweep smoke: c=5, one seed, live OpenAI backend, WSL.
# Requires a CLEAN git tree (no --allow-dirty): commit before running.
#
#   $env:OPENAI_API_KEY = "sk-..."
#   .\apu_characterization\run_sweep_smoke.ps1

$ErrorActionPreference = "Stop"

if (-not $env:OPENAI_API_KEY) {
    Write-Error "OPENAI_API_KEY is not set in this PowerShell session."
    exit 1
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($repo -match '^([A-Z]):\\(.*)$') {
    $wslRepo = "/mnt/$($Matches[1].ToLower())/$($Matches[2] -replace '\\', '/')"
} else {
    Write-Error "Cannot convert path to WSL: $repo"
    exit 1
}

$key = $env:OPENAI_API_KEY -replace "'", "''"

Write-Host "Sweep smoke (c=5, seed 0, openai backend, clean tree required)..."
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export OPENBLAS_NUM_THREADS=1; export MKL_NUM_THREADS=1; export OMP_NUM_THREADS=1; export APU_REPO_ROOT='$wslRepo'; export OPENAI_API_KEY='$key'; cd '$wslRepo' && tr -d '\r' < apu_characterization/run_sweep_smoke.sh | bash -s --"
exit $LASTEXITCODE
