# Start the full c-ladder concurrency sweep in WSL background.
# Levels 5,10,25,50,100 / seeds 0,1,2. Survives closing this PowerShell
# window (nohup + pid/state/log files in apu_characterization/out/:
# sweep.pid, sweep.log, sweep.state.json).
#
# NOTE: n=5 seeds at the saturation level is a follow-up run once N_max is
# known (rerun with --levels <N_max> --seeds 0,1,2,3,4).
#
#   $env:OPENAI_API_KEY = "sk-..."
#   .\apu_characterization\run_sweep_ladder.ps1 [-AllowDirty]

param(
    [switch]$AllowDirty,
    [switch]$Resume
)

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
$allowArg = ""
if ($AllowDirty) { $allowArg = "--allow-dirty" }
$resumeArg = ""
if ($Resume) { $resumeArg = "--resume" }

Write-Host "Starting c-ladder sweep in WSL background (levels 5,10,25,50,100 / seeds 0,1,2)..."
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export OPENBLAS_NUM_THREADS=1; export MKL_NUM_THREADS=1; export OMP_NUM_THREADS=1; export APU_REPO_ROOT='$wslRepo'; export OPENAI_API_KEY='$key'; cd '$wslRepo' && tr -d '\r' < apu_characterization/run_sweep_ladder.sh | bash -s -- $allowArg $resumeArg"
exit $LASTEXITCODE
