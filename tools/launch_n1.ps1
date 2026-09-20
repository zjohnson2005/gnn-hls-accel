# N-1 launcher - CB equivalence probe (gates attention-window / axis 5).
#
# Production (Zach, one line, no args, bare SSH after cold boot):
#   powershell -NoProfile -File tools/launch_n1.ps1
#
# Dry-run (spawn suppressed; gates report-only; no measurement):
#   powershell -NoProfile -File tools/launch_n1.ps1 -DryRun
#
# Steps: (1) non-persistent host clean  (2) five gates
#        (3) spawn_detached of run_delta_prefill_matrix.ps1
#        (4) print run_id + artifact dir and exit without waiting.
#
# Payload: ContinuousBatchingPipeline (use_cache_eviction=False) vs plain
# LLMPipeline via -PipelineTypes. int4 / gpu_only_u8 / n_cached+delta matched
# to 41e419bd subset. Canary pinned to -CanaryPipelineType llm. WSH watchdog
# and orchestrator WS ceiling live in the matrix runner (WatchdogIntervalS /
# OrchestratorWsCeilingMb).

[CmdletBinding()]
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
# Repo root = parent of tools/ (this script's directory).
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
Set-Location $root

. (Join-Path $PSScriptRoot "_assert_machine_lock.ps1")

# --- fixed N-1 coordinates (do not paraphrase matrix parameter names) ---
$Tag = "n1_cb_equivalence"
$ArmsCsv = "gpu_only_u8"
$NCachedCsv = "2000,4000,12000"
$DeltasCsv = "400"
$Repeats = 3
$ModelSpecsCsv = (Join-Path $root "configs\models\Qwen3-4B-int4-ov.yaml")
$CanaryModelSpec = $ModelSpecsCsv
$PipelineTypesCsv = "llm,cb_no_eviction"
$CanaryPipelineType = "llm"
$CanaryEveryN = 4
$CanaryArm = "gpu_only_u8"
$CanaryNCached = 4000
$CanaryDelta = 400
$CanaryMode = "RESIDENT"
$CanaryCalibrationCount = 3
$CanaryRelDriftFloor = 0.05
$WatchdogIntervalS = 300
$OrchestratorWsCeilingMb = 512
$PreRunAmendmentFile = Join-Path $root "derived\delta_prefill\N1_CB_EQUIVALENCE_PREDICTION.md"
$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$MatrixPs1 = Join-Path $root "tools\run_delta_prefill_matrix.ps1"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
$SessionRoot = Join-Path $root "derived\delta_prefill"
$LaunchDir = Join-Path $SessionRoot "_launches"
$CellTimeoutS = 1500

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

Write-Host "=== launch_n1.ps1 ==="
Write-Host ("mode           : {0}" -f $(if ($DryRun) { "DRY-RUN (spawn suppressed)" } else { "LIVE" }))
Write-Host ("cwd            : {0}" -f (Get-Location).Path)
Write-Host ("started_utc    : {0}" -f (Get-Date).ToUniversalTime().ToString("o"))
Write-Host ""
Write-Host "NOTE -- N-1 gates axis 5 (attention window). PRE-REGISTERED claim:"
Write-Host "  no significant CB(eviction-off) vs plain LLMPipeline difference"
Write-Host "  (significant = exceeding session canary early_max). Divergence =>"
Write-Host "  within-CB baseline required before any window cell."
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
Write-Host "NOTE -- WorkloadsSessionHost watchdog: matrix worker re-kills every $($WatchdogIntervalS)s"
Write-Host "  for the life of the run (respawn interval measured ~10-15 min)."
Write-Host ""

# ---------------------------------------------------------------------------
# 2. Five gates
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
# 3. Resolved command + spawn / dry-run
# ---------------------------------------------------------------------------
Write-Host "=== 3. resolved N-1 matrix command ==="

if (-not (Test-Path -LiteralPath $MatrixPs1)) {
    Refuse "matrix runner missing: $MatrixPs1"
    exit 2
}
if (-not (Test-Path -LiteralPath $SpawnPs1)) {
    Refuse "spawn_detached missing: $SpawnPs1"
    exit 2
}
if (-not (Test-Path -LiteralPath $PythonExe)) {
    Refuse "PythonExe missing: $PythonExe"
    exit 2
}
if (-not (Test-Path -LiteralPath $ModelSpecsCsv)) {
    Refuse "model spec missing: $ModelSpecsCsv"
    exit 2
}
if (-not (Test-Path -LiteralPath $PreRunAmendmentFile)) {
    Refuse "pre-registration missing: $PreRunAmendmentFile"
    exit 2
}

$sid = [guid]::NewGuid().ToString()
$tagLaunch = "n1_cb_" + (Get-Date -Format "yyyyMMdd_HHmmss")
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null
$log = Join-Path $LaunchDir "$tagLaunch.log"
$artifactDir = Join-Path $SessionRoot $sid

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
    ' -PipelineTypes "' + $PipelineTypesCsv + '"' +
    ' -CanaryPipelineType "' + $CanaryPipelineType + '"' +
    ' -CellTimeoutS ' + $CellTimeoutS +
    ' -Repeats ' + $Repeats +
    ' -CanaryEveryN ' + $CanaryEveryN +
    ' -CanaryArm "' + $CanaryArm + '"' +
    ' -CanaryNCached ' + $CanaryNCached +
    ' -CanaryDelta ' + $CanaryDelta +
    ' -CanaryMode ' + $CanaryMode +
    ' -CanaryCalibrationCount ' + $CanaryCalibrationCount +
    ' -CanaryRelDriftFloor ' + $CanaryRelDriftFloor +
    ' -WatchdogIntervalS ' + $WatchdogIntervalS +
    ' -OrchestratorWsCeilingMb ' + $OrchestratorWsCeilingMb +
    ' -PythonExe "' + $PythonExe + '"' +
    ' -PreRunAmendmentFile "' + $PreRunAmendmentFile + '"'

Write-Host "RESOLVED_CMD:"
Write-Host $resolvedCmd
Write-Host ""
Write-Host ("session_id (run_id) : {0}" -f $sid)
Write-Host ("artifact_dir        : {0}" -f $artifactDir)
Write-Host ("launch_log          : {0}" -f $log)
Write-Host ("prediction          : {0}" -f $PreRunAmendmentFile)
Write-Host ""

if ($DryRun) {
    Write-Host "=== DRY-RUN: EmitSchedule (N-1 cell plan; no spawn) ==="
    $schedOut = Join-Path $SessionRoot ("{0}_schedule_emit.json" -f $Tag)
    & powershell -NoProfile -File $MatrixPs1 `
        -EmitSchedule `
        -Tag $Tag `
        -Arms $ArmsCsv `
        -NCached $NCachedCsv `
        -Deltas $DeltasCsv `
        -ModelSpecs $ModelSpecsCsv `
        -CanaryModelSpec $CanaryModelSpec `
        -PipelineTypes $PipelineTypesCsv `
        -CanaryPipelineType $CanaryPipelineType `
        -Repeats $Repeats `
        -CanaryEveryN $CanaryEveryN `
        -CanaryArm $CanaryArm `
        -CanaryNCached $CanaryNCached `
        -CanaryDelta $CanaryDelta `
        -CanaryMode $CanaryMode `
        -CanaryCalibrationCount $CanaryCalibrationCount `
        -CanaryRelDriftFloor $CanaryRelDriftFloor `
        -WatchdogIntervalS $WatchdogIntervalS `
        -OrchestratorWsCeilingMb $OrchestratorWsCeilingMb `
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
    Write-Host ("pipeline_types: {0}" -f (($sched.pipeline_types) -join ","))
    Write-Host ("canary_pipeline_type: {0}" -f $sched.canary_pipeline_type)
    Write-Host ("schedule_json: {0}" -f $schedOut)
    Write-Host "CELL_ORDER (first round):"
    $r0 = @($sched.rounds)[0]
    Write-Host ("  seed={0}" -f $r0.seed)
    $idx = 0
    foreach ($c in @($r0.order)) {
        Write-Host ("  [{0}] pipeline={1} nc={2} d={3} mode={4} arm={5}" -f `
            $idx, $c.pipeline_type, $c.n_cached, $c.delta, $c.mode, $c.arm)
        $idx++
    }

    Write-Host ""
    Write-Host "=== PRE-REGISTRATION (on disk) ==="
    Get-Content -LiteralPath $PreRunAmendmentFile | Select-Object -First 24 | ForEach-Object { Write-Host $_ }
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


# Machine-lock / alive-worker check (hard refuse before spawn)
Assert-SeamMachineLockClear -RepoRoot $root -DryRun:$DryRun
Write-Host "=== 4. spawn_detached (live) ==="
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
$json = & $SpawnPs1 -CommandLine $resolvedCmd -LogPath $log -WorkingDirectory $root
Write-Host $json
$info = $json | ConvertFrom-Json
Write-Host ""
Write-Host "launched N-1 detached"
Write-Host ("  run_id           : {0}" -f $sid)
Write-Host ("  artifact_dir     : {0}" -f $artifactDir)
Write-Host ("  pid              : {0} (parent {1})" -f $info.pid, $info.parent_name)
Write-Host ("  log              : {0}" -f $log)
Write-Host ""
Write-Host "Exiting launcher now. Close SSH. Poll:"
Write-Host ("  Get-Content {0}\plan.json" -f $artifactDir)
Write-Host ("  Get-Content {0}\watchdog_kills.jsonl" -f $artifactDir)
exit 0
