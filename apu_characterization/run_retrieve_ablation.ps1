# LH-01 retrieve-locality ablation (OpenAI, publishable) via WSL.
#
#   $env:OPENAI_API_KEY = "sk-..."
#   .\apu_characterization\run_retrieve_ablation.ps1

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

Write-Host "Retrieve-locality ablation (LH-01, seeds 0,1, OpenAI)..."
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export OPENBLAS_NUM_THREADS=1; export MKL_NUM_THREADS=1; export OMP_NUM_THREADS=1; export APU_REPO_ROOT='$wslRepo'; export OPENAI_API_KEY='$key'; cd '$wslRepo' && source .venv-wsl/bin/activate && python -m apu_characterization.experiments.retrieve_locality_ablation --backend openai --seeds 0,1 --allow-dirty"
exit $LASTEXITCODE
