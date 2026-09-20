# H-1 hybrid launcher — live routing arms (D-2).
#
# Order (least budget risk first):
#   R2a slo_escalate, R2b emission_escalate, R0 cloud_only.
#   R1 agnostic_default is DERIVED from sealed cb781dbf — never live.
#
# Cost guard: --MaxUsd is REQUIRED for live arms. Defaults below are 1.5x the
# H1_PREDICTIONS point estimate (read here in the launcher ONLY — the Python
# runner never opens prediction files).
#
#   R2a slo_escalate:      predicted $0.0000  → MaxUsd 0.0000
#   R2b emission_escalate: predicted $13.0812 → MaxUsd 19.6218
#   R0  cloud_only:        predicted $54.0704 → MaxUsd 81.1056
#
# Production (five gates + INF-1b canary preflight):
#   powershell -NoProfile -File tools/launch_h1.ps1 -Policy slo_escalate
#   powershell -NoProfile -File tools/launch_h1.ps1 -Policy emission_escalate
#   powershell -NoProfile -File tools/launch_h1.ps1 -Policy cloud_only
#   powershell -NoProfile -File tools/launch_h1.ps1 -DeriveR1
#
# Hybrid arms load OpenVinoLocalBackend (greedy, max_new_tokens=512, W-3 path)
# via configs/models/Qwen3-4B-int4-ov.yaml. -LocalScript is DEBUG --no-seal only.
#
# Dry-run (gates report-only; spawn suppressed):
#   powershell -NoProfile -File tools/launch_h1.ps1 -Policy cloud_only -DryRun
#
# Steps: (1) non-persistent host clean  (2) five gates  (3) INF-1b canary guard
#        (4) spawn_detached  (5) print run_id + artifact dir; exit without waiting.

[CmdletBinding()]
param(
    [ValidateSet("slo_escalate", "emission_escalate", "cloud_only", "agnostic_default")]
    [string]$Policy = "",
    [switch]$DeriveR1,
    [Nullable[double]]$MaxUsd = $null,
    [switch]$DryRun,
    [string]$LocalScript = "",
    [switch]$AllowUnguarded
)

$ErrorActionPreference = "Stop"
# Repo root = parent of tools/ (this script's directory).
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
Set-Location $root

# 1.5x H1_PREDICTIONS point estimates (launcher-side only; runner is blinded).
$DefaultMaxUsd = @{
    "slo_escalate"      = 0.0
    "emission_escalate" = 19.6218
    "cloud_only"        = 81.1056
}

$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$WorkerPy = Join-Path $root "tools\run_h1_hybrid.py"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
$SessionRoot = Join-Path $root "derived\h1_hybrid"
$LaunchDir = Join-Path $SessionRoot "_launches"
$W3Entries = Join-Path $root "derived\bfcl_feasibility\w3_weight_quality\sealed_6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a\artifacts\multi_turn_probe_entries.json"

$WorkloadAppxNames = @(
    "WindowsWorkload.EP.Intel.OpenVINO.1.8",
    "WindowsWorkload.EP.Intel.OpenVINO.Framework.1.8"
)

function Get-AvailableMBytes {
    try {
        $sample = (Get-Counter '\Memory\Available MBytes' -ErrorAction Stop).CounterSamples[0]
        return [double]$sample.CookedValue
    } catch {
        Write-Host "REFUSED -- Available MBytes unreadable: $($_.Exception.Message)"
        exit 2
    }
}

function Refuse {
    param([Parameter(Mandatory = $true)][string]$Reason)
    Write-Host ""
    Write-Host "REFUSED -- $Reason"
    if ($DryRun) { return }
    exit 1
}

Write-Host "=== launch_h1.ps1 ==="
Write-Host ("mode           : {0}" -f $(if ($DryRun) { "DRY-RUN" } else { "LIVE" }))
Write-Host ("cwd            : {0}" -f (Get-Location).Path)
Write-Host ("started_utc    : {0}" -f (Get-Date).ToUniversalTime().ToString("o"))
Write-Host ""

if ($DeriveR1) {
    Write-Host "R1 path: DERIVED from sealed cb781dbf (not MEASURED, not live)."
    $sid = [guid]::NewGuid().ToString()
    $artifactDir = Join-Path $SessionRoot ("derived_r1_" + $sid)
    New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
    $cmd = '"' + $PythonExe + '" -u "' + $WorkerPy + '" --derive-r1 --out "' + $artifactDir + '" --run-id ' + $sid
    Write-Host "RESOLVED_CMD:"
    Write-Host $cmd
    if ($DryRun) {
        Write-Host "DRY-RUN: derive-r1 spawn suppressed."
        exit 0
    }
    & $PythonExe -u $WorkerPy --derive-r1 --out $artifactDir --run-id $sid
    exit $LASTEXITCODE
}

if ([string]::IsNullOrWhiteSpace($Policy)) {
    Refuse "Pass -Policy slo_escalate|emission_escalate|cloud_only, or -DeriveR1"
    exit 1
}
if ($Policy -eq "agnostic_default") {
    Refuse "agnostic_default must not run live. Use -DeriveR1."
    exit 1
}

if ($null -eq $MaxUsd) {
    $MaxUsd = [double]$DefaultMaxUsd[$Policy]
}
Write-Host ("Policy         : {0}" -f $Policy)
Write-Host ("MaxUsd         : {0}" -f $MaxUsd)
Write-Host ("NOTE -- MaxUsd default is 1.5x H1_PREDICTIONS (launcher-side). Runner never reads predictions.")
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Non-persistent host cleaning
# ---------------------------------------------------------------------------
Write-Host "=== 1. host cleaning (non-persistent) ==="
$availBefore = Get-AvailableMBytes
Write-Host ("Available MBytes BEFORE clean: {0:N1}" -f $availBefore)

$wsh = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
if ($wsh.Count -eq 0) {
    Write-Host "WorkloadsSessionHost: none resident"
} else {
    Write-Host ("WorkloadsSessionHost: killing {0} process(es)" -f $wsh.Count)
    if (-not $DryRun) {
        $wsh | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    } else {
        Write-Host "DRY-RUN: would Stop-Process WorkloadsSessionHost"
    }
}

foreach ($pkgName in $WorkloadAppxNames) {
    $pkgs = @(Get-AppxPackage -Name $pkgName -ErrorAction SilentlyContinue)
    foreach ($pkg in $pkgs) {
        Write-Host ("Appx present: {0}" -f $pkg.PackageFullName)
        if ($DryRun) {
            Write-Host ("DRY-RUN: would Remove-AppxPackage {0}" -f $pkg.PackageFullName)
            continue
        }
        try {
            Remove-AppxPackage -Package $pkg.PackageFullName -ErrorAction Stop
        } catch {
            Write-Host ("Appx remove failed (continuing): {0}" -f $_.Exception.Message)
        }
    }
}

$availAfter = Get-AvailableMBytes
Write-Host ("Available MBytes AFTER  clean: {0:N1}" -f $availAfter)
Write-Host ""

# ---------------------------------------------------------------------------
# 2. Five gates (PORT-2: platform YAML + processor AC 100/100; GUID recorded only)
# ---------------------------------------------------------------------------
Write-Host "=== 2. five gates ==="
Write-Host "GATE NOTE -- PORT-2: floors/onset from configs/platforms; AC/no-battery; processor AC 100/100."
Write-Host ""
. (Join-Path $PSScriptRoot "_run_measurement_gates.ps1")
$pythonForGates = if ($PythonExe -and (Test-Path -LiteralPath $PythonExe)) { $PythonExe } `
    else { Join-Path $root ".venv-seam\Scripts\python.exe" }
$platformId = if ($env:SEAM_PLATFORM_ID) { $env:SEAM_PLATFORM_ID } else { "" }
Invoke-SeamMeasurementGates -RepoRoot $root -PythonExe $pythonForGates `
    -PlatformId $platformId -DryRun:$DryRun
Write-Host ""

# ---------------------------------------------------------------------------
# 3. INF-1b canary guard (fixed cell + dual-bound N; refuse unarmed seal)
# ---------------------------------------------------------------------------
Write-Host "=== 3. INF-1b canary ==="
Write-Host "fixed cell: gpu_only_f16 n_cached=4000 delta=400 RESIDENT"
Write-Host "thresholds: C=3 rel_drift_floor=0.05 onset_s=657 (same as C-2/matrix)"
$CanaryOpeningPy = Join-Path $root "tools\run_h1_canary_opening.py"
if (-not (Test-Path -LiteralPath $CanaryOpeningPy)) {
    Refuse "missing INF-1b canary opening: $CanaryOpeningPy"
    if (-not $DryRun) { exit 2 }
}
$CanaryOut = Join-Path $SessionRoot "_canary_opening"
$canaryArgs = @("-u", $CanaryOpeningPy, "--out", $CanaryOut, "--planned-probe-count", "300")
if ($AllowUnguarded) {
    $canaryArgs += "--allow-unguarded"
    Write-Host "NOTE -- -AllowUnguarded set: unarmed finalize would write UNGUARDED."
}
if ($DryRun) {
    Write-Host "DRY-RUN: logic-only canary preflight (no GPU opening cell)"
    $canaryArgs += "--logic-only"
} else {
    Write-Host "LIVE: opening canary cell before spawn (refuse on FAIL_CANARY_DRIFT)"
}
& $PythonExe @canaryArgs
$canaryRc = $LASTEXITCODE
if ($canaryRc -ne 0) {
    Refuse "INF-1b canary failed (exit $canaryRc); refuse spawn"
    if (-not $DryRun) { exit $canaryRc }
}
Write-Host ""

# ---------------------------------------------------------------------------
# 4. Spawn
# ---------------------------------------------------------------------------
if (-not (Test-Path -LiteralPath $SpawnPs1)) { Refuse "spawn_detached missing: $SpawnPs1"; exit 2 }
if (-not (Test-Path -LiteralPath $PythonExe)) { Refuse "PythonExe missing: $PythonExe"; exit 2 }
if (-not (Test-Path -LiteralPath $W3Entries)) { Refuse "W-3 entries pin missing: $W3Entries"; exit 2 }

$sid = [guid]::NewGuid().ToString()
$tagLaunch = "h1_" + $Policy + "_" + (Get-Date -Format "yyyyMMdd_HHmmss")
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null
$log = Join-Path $LaunchDir "$tagLaunch.log"
$artifactDir = Join-Path $SessionRoot ($Policy + "_" + $sid)

$resolvedCmd = 'set SEAM_LAUNCH_CONTEXT=ssh_detached' +
    '&& "' + $PythonExe + '" -u "' + $WorkerPy + '"' +
    ' --policy ' + $Policy +
    ' --max-usd ' + $MaxUsd +
    ' --out "' + $artifactDir + '"' +
    ' --run-id ' + $sid +
    ' --entries "' + $W3Entries + '"'

if (-not [string]::IsNullOrWhiteSpace($LocalScript)) {
    $resolvedCmd = $resolvedCmd + ' --local-script "' + $LocalScript + '" --no-seal'
    Write-Host "NOTE -- -LocalScript is DEBUG replay only (forces --no-seal)."
} else {
    $ModelSpec = Join-Path $root "configs\models\Qwen3-4B-int4-ov.yaml"
    $resolvedCmd = $resolvedCmd + ' --model-spec "' + $ModelSpec + '"'
}

Write-Host "RESOLVED_CMD:"
Write-Host $resolvedCmd
Write-Host ""
Write-Host ("session_id (run_id) : {0}" -f $sid)
Write-Host ("artifact_dir        : {0}" -f $artifactDir)
Write-Host ("launch_log          : {0}" -f $log)
Write-Host ("max_usd             : {0}" -f $MaxUsd)
Write-Host ""

if ($DryRun) {
    Write-Host "=== DRY-RUN gate refusal summary ==="
    if ($gateFails.Count -eq 0) {
        Write-Host "Would refuse: (none -- all five gates PASS on this host right now)"
    } else {
        Write-Host "Would refuse:"
        foreach ($r in $gateFails) { Write-Host ("  - {0}" -f $r) }
    }
    Write-Host "DRY-RUN complete. Spawn NOT executed. No measurement / no spend."
    exit 0
}

New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
& $SpawnPs1 -CommandLine $resolvedCmd -LogPath $log -WorkingDirectory $root
Write-Host ""
Write-Host "Spawned. Detached worker owns the run; this shell exits."
exit 0
