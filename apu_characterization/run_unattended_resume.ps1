# Post-reboot / logon resume for APU characterization.
#
# Invoked by Task Scheduler (register_unattended_task.ps1) or manually:
#   .\apu_characterization\run_unattended_resume.ps1 [-Mode Auto|Replicate|Probe] [-AllowDirty]
#
# Logs: apu_characterization/out/unattended_run.log

param(
    [ValidateSet("Auto", "Replicate", "Probe")]
    [string]$Mode = "Auto",
    [switch]$AllowDirty
)

$ErrorActionPreference = "Stop"

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$logDir = Join-Path $repo "apu_characterization\out"
$logFile = Join-Path $logDir "unattended_run.log"

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-ResumeLog {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$ts $Message"
    Add-Content -Path $logFile -Value $line -Encoding utf8
    Write-Host $line
}

Write-ResumeLog "=== unattended resume start (Mode=$Mode) ==="

if ($repo -match '^([A-Z]):\\(.*)$') {
    $wslRepo = "/mnt/$($Matches[1].ToLower())/$($Matches[2] -replace '\\', '/')"
} else {
    Write-ResumeLog "ERROR: Cannot convert path to WSL: $repo"
    exit 1
}

# WSL may not be ready immediately after logon.
$wslReady = $false
for ($i = 1; $i -le 12; $i++) {
    wsl.exe --status 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $wslReady = $true
        break
    }
    Write-ResumeLog "waiting for WSL ($i/12)..."
    Start-Sleep -Seconds 10
}
if (-not $wslReady) {
    Write-ResumeLog "ERROR: WSL not available after 120s"
    exit 1
}

$modeLower = $Mode.ToLowerInvariant()
$allowArg = ""
if ($AllowDirty) { $allowArg = "--allow-dirty" }

$keyArg = ""
if ($env:OPENAI_API_KEY) {
    $key = $env:OPENAI_API_KEY -replace "'", "''"
    $keyArg = "export OPENAI_API_KEY='$key';"
} else {
    Write-ResumeLog "WARN: OPENAI_API_KEY not set in Windows user env (replication/gate will fail if needed)"
}

$rerunArg = ""
if ($env:APU_REREPPLICATE -eq "1") {
    $rerunArg = "export APU_REREPPLICATE=1;"
}

$wslCmd = "export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:`$HOME/.local/bin; export OPENBLAS_NUM_THREADS=1; export MKL_NUM_THREADS=1; export OMP_NUM_THREADS=1; export APU_REPO_ROOT='$wslRepo'; export APU_UNATTENDED_MODE='$modeLower'; ${keyArg}${rerunArg} cd '$wslRepo' && tr -d '\r' < apu_characterization/run_unattended_resume.sh | bash -s -- --mode '$modeLower' $allowArg"

Write-ResumeLog "launching WSL resume script..."
$output = wsl.exe bash --noprofile --norc -c $wslCmd 2>&1
foreach ($line in $output) {
    Write-ResumeLog $line
}
$code = $LASTEXITCODE
Write-ResumeLog "=== unattended resume exit $code ==="
exit $code
