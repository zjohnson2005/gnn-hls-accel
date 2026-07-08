# Poll background c-ladder sweep (WSL).
#
#   .\apu_characterization\run_sweep_check.ps1
#   .\apu_characterization\run_sweep_check.ps1 -Validate

param(
    [switch]$Validate
)

$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($repo -match '^([A-Z]):\\(.*)$') {
    $wslRepo = "/mnt/$($Matches[1].ToLower())/$($Matches[2] -replace '\\', '/')"
} else {
    Write-Error "Cannot convert path to WSL: $repo"
    exit 1
}

$validateArg = ""
if ($Validate) { $validateArg = "--validate" }

wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export APU_REPO_ROOT='$wslRepo'; cd '$wslRepo' && tr -d '\r' < apu_characterization/run_sweep_check.sh | bash -s -- $validateArg"
exit $LASTEXITCODE
