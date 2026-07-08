# Start v3 replication in WSL background (~1 hr). Poll with make apu-replicate-check.
#
#   $env:OPENAI_API_KEY = "sk-..."
#   .\apu_characterization\run_apu_replicate_unattended.ps1 [-AllowDirty]

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

$key = $env:OPENAI_API_KEY -replace "'", "''"
$allowArg = ""
if ($AllowDirty) { $allowArg = "--allow-dirty" }

Write-Host "Starting unattended v3 replication in WSL..."
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export OPENBLAS_NUM_THREADS=1; export MKL_NUM_THREADS=1; export OMP_NUM_THREADS=1; export APU_REPO_ROOT='$wslRepo'; export OPENAI_API_KEY='$key'; cd '$wslRepo' && tr -d '\r' < apu_characterization/run_apu_replicate_unattended.sh | bash -s -- $allowArg"
exit $LASTEXITCODE
