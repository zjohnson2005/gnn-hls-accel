# Phase C: v2 replication via WSL (~1 hour, 50 OpenAI sessions).
#
#   $env:OPENAI_API_KEY = "sk-..."
#   .\apu_characterization\run_linux_replication_v2.ps1
#   .\apu_characterization\run_linux_replication_v2.ps1 -AllowDirty

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
$script = "$wslRepo/apu_characterization/run_linux_replication_v2.sh"

Write-Host "Ensuring WSL venv (.venv-wsl via uv)..."
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; bash '$bootstrap'"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Launching v2 replication in WSL..."
$allowArg = ""
if ($AllowDirty) { $allowArg = "--allow-dirty" }

$key = $env:OPENAI_API_KEY -replace "'", "''"
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export OPENAI_API_KEY='$key'; bash '$script' $allowArg"
exit $LASTEXITCODE
