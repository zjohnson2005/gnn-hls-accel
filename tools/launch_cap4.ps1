# CAP-4 launcher - Prefill curve to failure per KV precision (gpu_only / RESIDENT).
#
# Production (Zach, bare SSH after cold boot):
#   powershell -NoProfile -File tools/launch_cap4.ps1
#
# Dry-run (spawn suppressed; gates report-only; no measurement):
#   powershell -NoProfile -File tools/launch_cap4.ps1 -DryRun
#
# Steps: (1) non-persistent host clean  (2) five gates  (3) spawn_detached
#        (4) print run_id + artifact dir and exit without waiting.
#
# Payload: tools/run_cap4_prefill_curve.py
#   Arms: gpu_only_f16, gpu_only_u8, gpu_only_u4 (INTERLEAVED)
#   Primary n: 12000,16000,20000,26000,32000,40000,46000; continue +6000
#   Repeats: 3; report median
#   Predictions: derived/cap4/CAP4_PREDICTIONS.json (must exist before probe)
#   INF-5: RunEnvironmentSession interleaved + arm_order
#
# WSH watchdog interval 60 s.
# Banners are ASCII only.

[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$ModelSpec = "",
    [int]$Repeats = 3,
    [int]$Seed = 20260915
)

$ErrorActionPreference = "Stop"
# Repo root = parent of tools/ (this script's directory).
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
Set-Location $root

. (Join-Path $PSScriptRoot "_assert_machine_lock.ps1")

$Tag = "cap4"
$WatchdogIntervalS = 60
$ArmsCsv = "gpu_only_f16,gpu_only_u8,gpu_only_u4"
$PrimaryRungs = "12000,16000,20000,26000,32000,40000,46000"
$ContinueStep = 6000
if ([string]::IsNullOrWhiteSpace($ModelSpec)) {
    $ModelSpec = Join-Path $root "configs\models\Qwen3-4B-int4-ov.yaml"
} elseif (-not [System.IO.Path]::IsPathRooted($ModelSpec)) {
    $ModelSpec = Join-Path $root $ModelSpec
}
$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$WorkerPy = Join-Path $root "tools\run_cap4_prefill_curve.py"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
$PredJson = Join-Path $root "derived\cap4\CAP4_PREDICTIONS.json"
$SessionRoot = Join-Path $root "derived\cap4"
$LaunchDir = Join-Path $SessionRoot "_launches"

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

Write-Host "=== launch_cap4.ps1 ==="
Write-Host ("mode           : {0}" -f $(if ($DryRun) { "DRY-RUN (spawn suppressed)" } else { "LIVE" }))
Write-Host ("cwd            : {0}" -f (Get-Location).Path)
Write-Host ("started_utc    : {0}" -f (Get-Date).ToUniversalTime().ToString("o"))
Write-Host ("Worker         : tools/run_cap4_prefill_curve.py")
Write-Host ("Arms           : {0} (INTERLEAVED)" -f $ArmsCsv)
Write-Host ("Primary rungs  : {0}" -f $PrimaryRungs)
Write-Host ("Continue step  : {0}" -f $ContinueStep)
Write-Host ("Repeats        : {0}" -f $Repeats)
Write-Host ("ModelSpec      : {0}" -f $ModelSpec)
Write-Host ("WatchdogIntervalS: {0}" -f $WatchdogIntervalS)
Write-Host ""
Write-Host "PRE-REGISTERED (derived/cap4/CAP4_PREDICTIONS.json) BEFORE FIRST PROBE:"
Write-Host "  P1: prefill ~ n^1.6 => ~115 s at 46000 if reachable"
Write-Host "  P2: ALLOC ceiling order f16 < u8 < u4"
Write-Host "  P3: at least one ALLOC_FAILURE before/at 46k; joint falsifier = all reach 46k w/o ALLOC"
Write-Host ""

if (-not (Test-Path -LiteralPath $PredJson)) {
    Refuse "missing pre-registration: $PredJson"
    exit 2
}
$pred = Get-Content -LiteralPath $PredJson -Raw | ConvertFrom-Json
if ($pred.status -ne "pre_registered_before_measurement") {
    Refuse "predictions status must be pre_registered_before_measurement (got $($pred.status))"
    exit 2
}
Write-Host ("Predictions OK: registered_utc={0}" -f $pred.registered_utc)
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
    Write-Host ("WorkloadsSessionHost: killing {0} process(es) pids={1}" -f `
        $wsh.Count, (($wsh | ForEach-Object { $_.Id }) -join ","))
    if (-not $DryRun) {
        $wsh | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        $left = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
        if ($left.Count -gt 0) {
            $leftPids = (($left | ForEach-Object { $_.Id }) -join ",")
            Refuse "WorkloadsSessionHost still resident after Stop-Process (pids $leftPids)"
            if (-not $DryRun) { exit 1 }
        } else {
            Write-Host "WorkloadsSessionHost: cleared"
        }
    } else {
        Write-Host "DRY-RUN: would Stop-Process WorkloadsSessionHost (kill suppressed)"
    }
}

foreach ($pkgName in $WorkloadAppxNames) {
    $pkgs = @(Get-AppxPackage -Name $pkgName -ErrorAction SilentlyContinue)
    if ($pkgs.Count -eq 0) {
        Write-Host ("Appx {0}: not present" -f $pkgName)
        continue
    }
    foreach ($pkg in $pkgs) {
        Write-Host ("Appx present: {0}" -f $pkg.PackageFullName)
        if ($DryRun) {
            Write-Host ("DRY-RUN: would Remove-AppxPackage {0} (remove suppressed)" -f $pkg.PackageFullName)
            continue
        }
        try {
            Remove-AppxPackage -Package $pkg.PackageFullName -ErrorAction Stop
            Write-Host ("Appx removed: {0}" -f $pkg.PackageFullName)
        } catch {
            Write-Host ("Remove-AppxPackage failed for {0}: {1}" -f `
                $pkg.PackageFullName, $_.Exception.Message)
            Write-Host "  Continuing: kill is the load-bearing non-persistent step."
        }
    }
}

$availAfter = Get-AvailableMBytes
Write-Host ("Available MBytes AFTER  clean: {0:N1}  (delta={1:N1})" -f `
    $availAfter, ($availAfter - $availBefore))
Write-Host ""

# ---------------------------------------------------------------------------
# 2. Five gates (same as C-1/C-2 - MEM-CEIL / allocation claims need a clean host)
# ---------------------------------------------------------------------------
Write-Host "=== 2. five gates ==="
Write-Host "GATE NOTE -- PORT-2: platform YAML floors; AC/no-battery; processor AC 100/100 (GUID recorded only)."
Write-Host ""
. (Join-Path $PSScriptRoot "_run_measurement_gates.ps1")
$pythonForGates = if (Test-Path -LiteralPath $PythonExe) { $PythonExe } `
    elseif (Test-Path -LiteralPath (Join-Path $root ".venv-seam\Scripts\python.exe")) {
        Join-Path $root ".venv-seam\Scripts\python.exe"
    } else { Join-Path $root ".venv-seam\Scripts\python.exe" }
$platformId = if ($env:SEAM_PLATFORM_ID) { $env:SEAM_PLATFORM_ID } else { "" }
Invoke-SeamMeasurementGates -RepoRoot $root -PythonExe $pythonForGates `
    -PlatformId $platformId -DryRun:$DryRun
Write-Host ""

# ---------------------------------------------------------------------------
# 3. Resolved command
# ---------------------------------------------------------------------------
Write-Host "=== 3. resolved CAP-4 command ==="

foreach ($p in @($WorkerPy, $SpawnPs1, $PythonExe, $ModelSpec, $PredJson)) {
    if (-not (Test-Path -LiteralPath $p)) {
        Refuse "missing required path: $p"
        exit 2
    }
}

$sid = [guid]::NewGuid().ToString()
$tagLaunch = "cap4_" + (Get-Date -Format "yyyyMMdd_HHmmss")
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null
$log = Join-Path $LaunchDir "$tagLaunch.log"
$artifactDir = Join-Path $SessionRoot $sid

$resolvedCmd = 'set SEAM_LAUNCH_CONTEXT=ssh_detached' +
    '&& "' + $PythonExe + '" -u "' + $WorkerPy + '"' +
    ' --session-id ' + $sid +
    ' --out "' + $artifactDir + '"' +
    ' --model-spec "' + $ModelSpec + '"' +
    ' --arms ' + $ArmsCsv +
    ' --primary-rungs ' + $PrimaryRungs +
    ' --continue-step ' + $ContinueStep +
    ' --repeats ' + $Repeats +
    ' --seed ' + $Seed +
    ' --watchdog-interval-s ' + $WatchdogIntervalS

Write-Host "RESOLVED_CMD:"
Write-Host $resolvedCmd
Write-Host ""
Write-Host ("session_id (run_id) : {0}" -f $sid)
Write-Host ("artifact_dir        : {0}" -f $artifactDir)
Write-Host ("launch_log          : {0}" -f $log)
Write-Host ""

# Extraction smoke (reuse C-2 n=64 smoke - same child metrics path)
Write-Host "=== extraction smoke (n=64, real cell) ==="
$SmokePy = Join-Path $root "tools\c2_extraction_smoke.py"
$SmokeOut = Join-Path $SessionRoot "_extraction_smoke"
if (-not (Test-Path -LiteralPath $SmokePy)) {
    Refuse "missing extraction smoke: $SmokePy"
    exit 2
}
if ($DryRun) {
    Write-Host "DRY-RUN: would run extraction smoke (suppressed)"
} else {
    & $PythonExe -u $SmokePy --out $SmokeOut --model-spec $ModelSpec --n-tokens 64
    if ($LASTEXITCODE -ne 0) {
        Write-Host "REFUSED -- extraction smoke failed; not launching CAP-4"
        exit $LASTEXITCODE
    }
}
Write-Host ""

if ($DryRun) {
    Write-Host "=== DRY-RUN complete: no spawn ==="
    Write-Host ("would session_id={0}" -f $sid)
    Write-Host ("would out={0}" -f $artifactDir)
    exit 0
}


# Machine-lock / alive-worker check (hard refuse before spawn)
Assert-SeamMachineLockClear -RepoRoot $root -DryRun:$DryRun
Write-Host "=== 4. spawn_detached (live) ==="
& $SpawnPs1 -CommandLine $resolvedCmd -LogPath $log -WorkingDirectory $root
if ($LASTEXITCODE -ne 0) {
    Write-Host "REFUSED -- spawn_detached failed"
    exit $LASTEXITCODE
}
Write-Host "launched CAP-4 detached"
Write-Host ("tail: Get-Content -Wait '{0}'" -f $log)
exit 0
