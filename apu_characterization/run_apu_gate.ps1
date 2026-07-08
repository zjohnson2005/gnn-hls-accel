# Fail-fast gate: WSL bootstrap (if needed) + unit tests + FO-01 OpenAI smoke.
#
#   $env:OPENAI_API_KEY = "sk-..."
#   .\apu_characterization\run_apu_gate.ps1

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

Write-Host "APU gate (bootstrap + unit tests + FO-01 smoke)..."
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export APU_REPO_ROOT='$wslRepo'; export OPENAI_API_KEY='$key'; cd '$wslRepo' && tr -d '\r' < apu_characterization/run_apu_gate.sh | bash -s --"
exit $LASTEXITCODE
