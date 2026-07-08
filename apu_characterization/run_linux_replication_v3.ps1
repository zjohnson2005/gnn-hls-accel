# Phase D: v3 thread-identity replication (~1 hour, 50 OpenAI sessions).
#
#   $env:OPENAI_API_KEY = "sk-..."
#   .\apu_characterization\run_linux_replication_v3.ps1 -AllowDirty

param(
    [switch]$AllowDirty
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

$bootstrap = "$wslRepo/apu_characterization/run_wsl_bootstrap.sh"
$script = "$wslRepo/apu_characterization/run_linux_replication_v3.sh"
$allowArg = ""
if ($AllowDirty) { $allowArg = "--allow-dirty" }

$key = $env:OPENAI_API_KEY -replace "'", "''"

Write-Host "Ensuring WSL venv (.venv-wsl via uv)..."
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; cd '$wslRepo' && bash '$bootstrap'"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Launching v3 replication in WSL (thread-identity, ~1 hour)..."
# Invoke the .sh by path (not stdin) so `$0` resolves the repo; cd is a belt-and-suspenders guard.
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export OPENBLAS_NUM_THREADS=1; export MKL_NUM_THREADS=1; export OMP_NUM_THREADS=1; export OPENAI_API_KEY='$key'; cd '$wslRepo' && bash '$script' $allowArg"
exit $LASTEXITCODE
