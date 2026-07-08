# Phase 1 smoke: FO-01 fan-out (OpenAI, ~2-5 min).
#
#   $env:OPENAI_API_KEY = "sk-..."
#   .\apu_characterization\run_v3_fo01_smoke.ps1

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

$script = "$wslRepo/apu_characterization/run_v3_fo01_smoke_wsl.sh"
$key = $env:OPENAI_API_KEY -replace "'", "''"

Write-Host "FO-01 v3 smoke (OpenAI fan-out, ~2-5 min)..."
# Strip CR if editor reintroduced Windows line endings; APU_REPO_ROOT avoids `$0` issues if piped.
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export APU_REPO_ROOT='$wslRepo'; export OPENAI_API_KEY='$key'; cd '$wslRepo' && tr -d '\r' < apu_characterization/run_v3_fo01_smoke_wsl.sh | bash -s --"
exit $LASTEXITCODE
