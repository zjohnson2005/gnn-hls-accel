# TLP-01 S2 live collection (WSL). Loads OPENAI_API_KEY from User env if the
# process env is missing/invalid. Never prints the key.
param()

$ErrorActionPreference = "Stop"

$proc = $env:OPENAI_API_KEY
$user = [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User")
if (-not $proc -or $proc.Trim().Length -lt 20) {
    if ($user -and $user.Trim().Length -ge 20) {
        $env:OPENAI_API_KEY = $user.Trim()
        Write-Host "Loaded OPENAI_API_KEY from User environment (len=$($env:OPENAI_API_KEY.Length))"
    } else {
        Write-Error "OPENAI_API_KEY missing or invalid in process/User environment."
        exit 2
    }
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($repo -notmatch '^([A-Z]):\\(.*)$') {
    Write-Error "Cannot convert repository path to WSL: $repo"
    exit 1
}
$wslRepo = "/mnt/$($Matches[1].ToLower())/$($Matches[2] -replace '\\', '/')"
$key = $env:OPENAI_API_KEY -replace "'", "''"

Write-Host "TLP-01 S2 collection starting in WSL..."
wsl.exe bash --noprofile --norc -c "export OPENAI_API_KEY='$key'; export APU_REPO_ROOT='$wslRepo'; cd '$wslRepo' && tr -d '\r' < apu_characterization/tools/run_t0_s2_collect.sh | bash -s"
exit $LASTEXITCODE
