$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($repo -notmatch '^([A-Z]):\\(.*)$') {
    Write-Error "Cannot convert repository path to WSL: $repo"
    exit 1
}
$wslRepo = "/mnt/$($Matches[1].ToLower())/$($Matches[2] -replace '\\', '/')"

Write-Host "CAP-01 build and contract gate (WSL2 debug environment)..."
wsl.exe bash --noprofile --norc -c "export APU_REPO_ROOT='$wslRepo'; cd '$wslRepo' && tr -d '\r' < apu_characterization/run_cap01_gate.sh | bash -s --"
exit $LASTEXITCODE
