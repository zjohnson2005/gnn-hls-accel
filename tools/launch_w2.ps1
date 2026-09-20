# W-2 launcher — weight-precision matrix (int4 vs int8), bare SSH after cold boot.
#
# Production (Zach, one line, no args):
#   powershell -NoProfile -File tools/launch_w2.ps1
#
# Dry-run (spawn suppressed; gates report-only; no measurement):
#   powershell -NoProfile -File tools/launch_w2.ps1 -DryRun
#
# Steps: (1) non-persistent host clean  (2) five gates  (3) spawn_detached
#        (4) print run_id + artifact dir and exit without waiting.

[CmdletBinding()]
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
# Repo root = parent of tools/ (this script's directory).
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
Set-Location $root

# --- fixed W-2 coordinates (do not paraphrase matrix parameter names) ---
$Tag = "w2_weight_precision"
$ArmsCsv = "gpu_only_u8"
$NCachedCsv = "2000,5000,12000"
$DeltasCsv = "150"
$Repeats = 3
$ModelSpecsCsv = @(
    (Join-Path $root "configs\models\Qwen3-4B-int4-ov.yaml"),
    (Join-Path $root "configs\models\Qwen3-4B-int8-ov.yaml")
) -join ","
$CanaryModelSpec = Join-Path $root "configs\models\Qwen3-4B-int4-ov.yaml"
$CanaryEveryN = 12
$CanaryArm = "gpu_only_u8"
$CanaryNCached = 4000
$CanaryDelta = 400
$CanaryMode = "RESIDENT"
$CanaryCalibrationCount = 3
$CanaryRelDriftFloor = 0.05
$PreRunAmendmentFile = Join-Path $root "derived\delta_prefill\AMENDMENT_2026-08-28c.txt"
$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$MatrixPs1 = Join-Path $root "tools\run_delta_prefill_matrix.ps1"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
$SessionRoot = Join-Path $root "derived\delta_prefill"
$LaunchDir = Join-Path $SessionRoot "_launches"
$CellTimeoutS = 1500

# Commissioning: the two Copilot+ OpenVINO Workload packages whose hosts respawn
# WorkloadsSessionHost after reboot (DISPATCH P launch note: Remove-AppxPackage may
# refuse 0x80073D02 package-in-use; kill is the non-persistent step that must re-run).
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
    if ($DryRun) {
        return
    }
    exit 1
}

Write-Host "=== launch_w2.ps1 ==="
Write-Host ("mode           : {0}" -f $(if ($DryRun) { "DRY-RUN (spawn suppressed)" } else { "LIVE" }))
Write-Host ("cwd            : {0}" -f (Get-Location).Path)
Write-Host ("started_utc    : {0}" -f (Get-Date).ToUniversalTime().ToString("o"))
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
            # Commissioning recorded refuse 0x80073D02 (package in use). Loud, not silent.
            $hr = $null
            if ($_.Exception -and $_.Exception.HResult) {
                $hr = ("0x{0:X8}" -f ([uint32]$_.Exception.HResult))
            }
            Write-Host ("REFUSED -- Remove-AppxPackage failed for {0}: {1} (hr={2})" -f `
                $pkg.PackageFullName, $_.Exception.Message, $hr)
            Write-Host "  Continuing: kill is the load-bearing non-persistent step; Appx remove may be package-in-use."
        }
    }
}

$availAfter = Get-AvailableMBytes
Write-Host ("Available MBytes AFTER  clean: {0:N1}  (delta={1:N1})" -f `
    $availAfter, ($availAfter - $availBefore))
Write-Host ""

# ---------------------------------------------------------------------------
# 2. Five gates (print all; refuse with named reason; no partial proceed live)
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
# 3. Build resolved matrix command; print; spawn (or dry-run schedule)
# ---------------------------------------------------------------------------
Write-Host "=== 3. resolved matrix command ==="

if (-not (Test-Path -LiteralPath $MatrixPs1)) {
    Refuse "matrix runner missing: $MatrixPs1"
    exit 2
}
if (-not (Test-Path -LiteralPath $SpawnPs1)) {
    Refuse "spawn_detached missing: $SpawnPs1"
    exit 2
}
if (-not (Test-Path -LiteralPath $PreRunAmendmentFile)) {
    Refuse "PreRunAmendmentFile missing: $PreRunAmendmentFile"
    exit 2
}
if (-not (Test-Path -LiteralPath $PythonExe)) {
    Refuse "PythonExe missing: $PythonExe"
    exit 2
}
foreach ($ms in ($ModelSpecsCsv -split ",")) {
    if (-not (Test-Path -LiteralPath $ms)) {
        Refuse "model spec missing: $ms"
        exit 2
    }
}
if (-not (Test-Path -LiteralPath $CanaryModelSpec)) {
    Refuse "CanaryModelSpec missing: $CanaryModelSpec"
    exit 2
}

$sid = [guid]::NewGuid().ToString()
$tagLaunch = "delta_prefill_" + (Get-Date -Format "yyyyMMdd_HHmmss")
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null
$log = Join-Path $LaunchDir "$tagLaunch.log"
$resultPath = Join-Path $LaunchDir "$tagLaunch.result.json"
$artifactDir = Join-Path $SessionRoot $sid

# Exact DetachedWorker command line (same parameter names as Orchestrate path).
$resolvedCmd = 'set SEAM_LAUNCH_CONTEXT=ssh_detached' +
    '&& powershell -NoProfile -File "' + $MatrixPs1 + '"' +
    ' -DetachedWorker -LaunchContext ssh_detached' +
    ' -SessionId ' + $sid +
    ' -Tag "' + $Tag + '"' +
    ' -Arms "' + $ArmsCsv + '"' +
    ' -NCached "' + $NCachedCsv + '"' +
    ' -Deltas "' + $DeltasCsv + '"' +
    ' -ModelSpecs "' + $ModelSpecsCsv + '"' +
    ' -CanaryModelSpec "' + $CanaryModelSpec + '"' +
    ' -CellTimeoutS ' + $CellTimeoutS +
    ' -Repeats ' + $Repeats +
    ' -CanaryEveryN ' + $CanaryEveryN +
    ' -CanaryArm "' + $CanaryArm + '"' +
    ' -CanaryNCached ' + $CanaryNCached +
    ' -CanaryDelta ' + $CanaryDelta +
    ' -CanaryMode ' + $CanaryMode +
    ' -CanaryCalibrationCount ' + $CanaryCalibrationCount +
    ' -CanaryRelDriftFloor ' + $CanaryRelDriftFloor +
    ' -PythonExe "' + $PythonExe + '"' +
    ' -PreRunAmendmentFile "' + $PreRunAmendmentFile + '"'

Write-Host "RESOLVED_CMD:"
Write-Host $resolvedCmd
Write-Host ""
Write-Host ("session_id (run_id) : {0}" -f $sid)
Write-Host ("artifact_dir        : {0}" -f $artifactDir)
Write-Host ("launch_log          : {0}" -f $log)
Write-Host ""

if ($DryRun) {
    Write-Host '=== DRY-RUN: EmitSchedule (36 cell plan + amendment preview) ==='
    $schedOut = Join-Path $SessionRoot ("{0}_schedule_emit.json" -f $Tag)
    & powershell -NoProfile -File $MatrixPs1 `
        -EmitSchedule `
        -Tag $Tag `
        -Arms $ArmsCsv `
        -NCached $NCachedCsv `
        -Deltas $DeltasCsv `
        -ModelSpecs $ModelSpecsCsv `
        -CanaryModelSpec $CanaryModelSpec `
        -Repeats $Repeats `
        -CanaryEveryN $CanaryEveryN `
        -CanaryArm $CanaryArm `
        -CanaryNCached $CanaryNCached `
        -CanaryDelta $CanaryDelta `
        -CanaryMode $CanaryMode `
        -CanaryCalibrationCount $CanaryCalibrationCount `
        -CanaryRelDriftFloor $CanaryRelDriftFloor `
        -PreRunAmendmentFile $PreRunAmendmentFile `
        -ScheduleOut $schedOut `
        -PythonExe $PythonExe
    if ($LASTEXITCODE -ne 0) {
        Write-Host "REFUSED -- EmitSchedule failed exit=$LASTEXITCODE"
        exit $LASTEXITCODE
    }

    $sched = Get-Content -LiteralPath $schedOut -Raw -Encoding utf8 | ConvertFrom-Json
    $cellsPerRound = @($sched.cell_specs_per_round).Count
    $totalCells = $cellsPerRound * [int]$sched.repeats
    Write-Host ""
    Write-Host ("DRY-RUN schedule: cells_per_round={0} repeats={1} total_cells={2}" -f `
        $cellsPerRound, $sched.repeats, $totalCells)
    Write-Host ("schedule_json: {0}" -f $schedOut)

    if ($null -eq $sched.pre_run_amendment -or [string]::IsNullOrWhiteSpace([string]$sched.pre_run_amendment.text)) {
        Write-Host "REFUSED -- schedule.pre_run_amendment missing or empty"
        exit 1
    }
    $amendOnDisk = [System.IO.File]::ReadAllText($PreRunAmendmentFile)
    $amendInSched = [string]$sched.pre_run_amendment.text
    $amendMatch = ($amendInSched -eq $amendOnDisk)
    Write-Host ("plan.pre_run_amendment preview: chars={0} matches_on_disk={1} source={2}" -f `
        $amendInSched.Length, $amendMatch, $sched.pre_run_amendment.source_path)
    if (-not $amendMatch) {
        Write-Host "REFUSED -- schedule amendment text != on-disk AMENDMENT_2026-08-28c.txt"
        exit 1
    }
    $has28c = $amendInSched.Contains('Amendment 2026-08-28c')
    $hasP2pp = $amendInSched.Contains('P2' + [char]39 + [char]39)
    $hasP1p = $amendInSched.Contains('P1' + [char]39)
    if (-not ($has28c -and $hasP2pp -and $hasP1p)) {
        Write-Host "REFUSED -- amendment text missing expected 28c markers"
        exit 1
    }
    Write-Host "CONFIRM: plan.pre_run_amendment would contain the full 28c text (byte-identical to file)."

    Write-Host ""
    Write-Host "=== DRY-RUN gate refusal summary ==="
    if ($gateFails.Count -eq 0) {
        Write-Host "Would refuse: (none -- all five gates PASS on this host right now)"
    } else {
        Write-Host "Would refuse:"
        foreach ($r in $gateFails) { Write-Host ("  - {0}" -f $r) }
    }

    Write-Host ""
    Write-Host "DRY-RUN complete. Spawn NOT executed. No measurement."
    exit 0
}

# LIVE: spawn detached via tools/spawn_detached.ps1, then exit without waiting.
Write-Host "=== 4. spawn_detached (live) ==="
$json = & $SpawnPs1 -CommandLine $resolvedCmd -LogPath $log -WorkingDirectory $root
Write-Host $json
$info = $json | ConvertFrom-Json
Write-Host ""
Write-Host "launched W-2 detached"
Write-Host ("  run_id           : {0}" -f $sid)
Write-Host ("  artifact_dir     : {0}" -f $artifactDir)
Write-Host ("  pid              : {0} (parent {1})" -f $info.pid, $info.parent_name)
Write-Host ("  log              : {0}" -f $log)
Write-Host ""
Write-Host "Exiting launcher now. Close SSH. Poll:"
Write-Host ("  powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Status")
Write-Host ("  Get-Content derived/delta_prefill/{0}/heartbeat.json" -f $sid)
exit 0
