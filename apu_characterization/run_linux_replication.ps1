# Run publishable Linux replication via WSL from PowerShell.
#
#   $env:OPENAI_API_KEY = "sk-..."   # set in THIS PowerShell session
#   .\apu_characterization\run_linux_replication.ps1
#   .\apu_characterization\run_linux_replication.ps1 -AllowDirty   # skip git-clean gate

param(
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"

if (-not $env:OPENAI_API_KEY) {
    Write-Error @"
OPENAI_API_KEY is not set in this PowerShell session.
Set it first (do not commit the key):
  `$env:OPENAI_API_KEY = 'sk-...'
"@
    exit 1
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($repo -match '^([A-Z]):\\(.*)$') {
    $wslRepo = "/mnt/$($Matches[1].ToLower())/$($Matches[2] -replace '\\', '/')"
} else {
    Write-Error "Cannot convert path to WSL: $repo"
    exit 1
}

$script = "$wslRepo/apu_characterization/run_linux_replication.sh"

Write-Host "Launching Linux replication in WSL..."
Write-Host "Repo: $wslRepo"
Write-Host "(~1 hour; 50 OpenAI sessions: 10 tasks x 5 seeds, remote search only.)"
Write-Host "You should see 'WSL replication starting' below within a few seconds."
Write-Host ""

$allowArg = ""
if ($AllowDirty) {
    $allowArg = "--allow-dirty"
}

# Pass key explicitly; use clean WSL PATH (Windows PATH breaks bash export).
$allowArg = ""
if ($AllowDirty) {
    $allowArg = "--allow-dirty"
}

$key = $env:OPENAI_API_KEY -replace "'", "''"
wsl.exe bash --noprofile --norc -c "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export OPENAI_API_KEY='$key'; bash '$script' $allowArg"
exit $LASTEXITCODE
