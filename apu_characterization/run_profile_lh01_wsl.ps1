# Run LH-01 py-spy profile workflow in WSL (PEP 668 safe venv).
#
#   $env:OPENAI_API_KEY = "sk-..."
#   .\apu_characterization\run_profile_lh01_wsl.ps1

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

$script = "$wslRepo/apu_characterization/run_profile_lh01_wsl.sh"
Write-Host "Launching LH-01 profile + py-spy in WSL (venv at .venv-wsl)..."
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export OPENAI_API_KEY='$env:OPENAI_API_KEY'; bash '$script'"
exit $LASTEXITCODE
