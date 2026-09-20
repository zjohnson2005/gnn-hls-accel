# Q-8B launcher - interleaved int4-4B vs int4-8B tier quality (KV=f16).
#
# Production (Zach, bare SSH after cold boot):
#   powershell -NoProfile -File tools/launch_q8b.ps1
#
# Dry-run (spawn suppressed; gates report-only; no measurement):
#   powershell -NoProfile -File tools/launch_q8b.ps1 -DryRun
#
# Default pipeline: single-pipe block interleave (load one arm's block, unload,
# load the other). Reload events in reload_events.json; excluded from TTFT/decode.
#
# Dual-resident is KNOWN-BROKEN on this iGPU (citing b1a291f0) — opt in only:
#   powershell -NoProfile -File tools/launch_q8b.ps1 -AllowDualResident
#
# Steps: (1) non-persistent host clean  (2) five gates  (3) spawn_detached
#        (4) print run_id + artifact dir and exit without waiting.
#
# Payload: tools/run_q_8b_quality.py
#   Arms: int4_4B, int4_8B (model-spec axis; placement gpu_only_f16; KV=f16)
#   Entries: same 200 as W-3 / Q-KV; block-interleaved; paired McNemar
#   Predictions: derived/q8b/Q8B_PREDICTIONS.json (must exist before probe)
#   INF-5: RunEnvironmentSession interleaved + arm_order
#   Reload events: derived/.../reload_events.json (excluded from decode metrics)
#   Degenerate guard: N consecutive max_new_tokens+zero-decode → SeamError refuse
#
# Parameters:
#   -AllowDualResident     pass --allow-dual-resident (KNOWN-BROKEN; citing b1a291f0)
#   -ForceBlockInterleave  deprecated no-op (single-pipe is already default)
#   -InterleaveSeed        default 20260916
#   -DryRun                gates + resolve cmd only; no spawn
#
# WSH watchdog: worker does not spawn a WSH watchdog (quality path); host clean
# still kills WorkloadsSessionHost before launch.
# Banners are ASCII only.

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$AllowDualResident,
    [switch]$ForceBlockInterleave,
    [int]$InterleaveSeed = 20260916
)

$ErrorActionPreference = "Stop"
# Repo root = parent of tools/ (this script's directory).
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
Set-Location $root

$Tag = "q8b"
$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$WorkerPy = Join-Path $root "tools\run_q_8b_quality.py"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
$PredJson = Join-Path $root "derived\q8b\Q8B_PREDICTIONS.json"
$SessionRoot = Join-Path $root "derived\q8b"
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

Write-Host "=== launch_q8b.ps1 ==="
Write-Host ("mode           : {0}" -f $(if ($DryRun) { "DRY-RUN (spawn suppressed)" } else { "LIVE" }))
Write-Host ("cwd            : {0}" -f (Get-Location).Path)
Write-Host ("started_utc    : {0}" -f (Get-Date).ToUniversalTime().ToString("o"))
Write-Host ("Worker         : tools/run_q_8b_quality.py")
Write-Host ("Arms           : int4_4B, int4_8B (KV=f16; placement gpu_only_f16)")
Write-Host ("Pipeline       : block_interleave_single_pipe (default)")
Write-Host ("InterleaveSeed : {0}" -f $InterleaveSeed)
Write-Host ("AllowDualResident: {0}  (KNOWN-BROKEN citing b1a291f0)" -f [bool]$AllowDualResident)
if ($ForceBlockInterleave) {
    Write-Host "ForceBlockInterleave: True (deprecated no-op; single-pipe already default)"
}
Write-Host ("Predictions    : {0}" -f $PredJson)
Write-Host ""
Write-Host "TIER NOTE: int4-vs-int4 only. No Qwen3-8B-int8-ov in registry."
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
# 3. Resolved command
# ---------------------------------------------------------------------------
Write-Host "=== 3. resolved Q-8B command ==="

foreach ($p in @($WorkerPy, $SpawnPs1, $PythonExe, $PredJson)) {
    if (-not (Test-Path -LiteralPath $p)) {
        Refuse "missing required path: $p"
        exit 2
    }
}

$sid = [guid]::NewGuid().ToString()
$tagLaunch = "q8b_" + (Get-Date -Format "yyyyMMdd_HHmmss")
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null
$log = Join-Path $LaunchDir "$tagLaunch.log"
$artifactDir = Join-Path $SessionRoot ("q8b_" + $sid)

$resolvedCmd = 'set SEAM_LAUNCH_CONTEXT=ssh_detached' +
    '&& "' + $PythonExe + '" -u "' + $WorkerPy + '"' +
    ' --out "' + $artifactDir + '"' +
    ' --run-id ' + $sid +
    ' --interleave-seed ' + $InterleaveSeed
if ($AllowDualResident) {
    $resolvedCmd = $resolvedCmd + ' --allow-dual-resident'
}
if ($ForceBlockInterleave) {
    # Deprecated no-op retained for old invocation scripts.
    $resolvedCmd = $resolvedCmd + ' --force-block-interleave'
}

Write-Host "RESOLVED_CMD:"
Write-Host $resolvedCmd
Write-Host ""
Write-Host ("session_id (run_id) : {0}" -f $sid)
Write-Host ("artifact_dir        : {0}" -f $artifactDir)
Write-Host ("launch_log          : {0}" -f $log)
Write-Host ""

if ($DryRun) {
    Write-Host "=== DRY-RUN: predictions + arm model specs ==="
    $dryPy = Join-Path $LaunchDir ("{0}_dryrun.py" -f $tagLaunch)
    @"
import json, sys
from pathlib import Path
sys.path.insert(0, r"$root")
from tools.run_q_8b_quality import (
    ARMS, ARM_MODEL_SPECS, PLACEMENT_ARM, KV_EXPECTED, PRED_PATH,
    DUAL_RESIDENT_KNOWN_BROKEN, DUAL_RESIDENT_CITING,
)
from tools.quality_row_persist import DEGENERATE_CONSECUTIVE_N
pred = json.loads(PRED_PATH.read_text(encoding="utf-8-sig"))
assert pred["status"] == "pre_registered_before_measurement"
assert pred["weight_precision"] == "int4"
assert pred["no_int8_8b_in_registry"] is True
for a in ARMS:
    p = ARM_MODEL_SPECS[a]
    assert p.is_file(), p
    print("ARM_SPEC_OK", a, p)
print("PLACEMENT", PLACEMENT_ARM, "KV", KV_EXPECTED)
print("PRED_UTC", pred.get("registered_utc"))
print("DUAL_RESIDENT_KNOWN_BROKEN", DUAL_RESIDENT_KNOWN_BROKEN, DUAL_RESIDENT_CITING)
print("DEGENERATE_N", DEGENERATE_CONSECUTIVE_N)
print("DRYRUN_OK")
"@ | Set-Content -LiteralPath $dryPy -Encoding utf8
    & $PythonExe -u $dryPy
    if ($LASTEXITCODE -ne 0) {
        Write-Host "REFUSED -- dry-run preflight failed"
        exit $LASTEXITCODE
    }
    Write-Host ""
    Write-Host "DRY-RUN complete. Spawn NOT executed."
    exit 0
}

Write-Host "=== 4. spawn_detached (live) ==="
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
$json = & $SpawnPs1 -CommandLine $resolvedCmd -LogPath $log -WorkingDirectory $root
Write-Host $json
$info = $json | ConvertFrom-Json
$launchMeta = @{
    run_id = $sid
    out = $artifactDir
    log = $log
    predictions = "derived/q8b/Q8B_PREDICTIONS.json"
    launched_utc = (Get-Date).ToUniversalTime().ToString("o")
    allow_dual_resident = [bool]$AllowDualResident
    force_block_interleave_deprecated = [bool]$ForceBlockInterleave
    pipeline_default = "block_interleave_single_pipe"
    interleave_seed = $InterleaveSeed
}
$launchMeta | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $LaunchDir ("launch_{0}.json" -f $sid.Substring(0, 8))) -Encoding utf8
Write-Host ""
Write-Host "launched Q-8B detached"
Write-Host ("  run_id           : {0}" -f $sid)
Write-Host ("  artifact_dir     : {0}" -f $artifactDir)
Write-Host ("  pid              : {0} (parent {1})" -f $info.pid, $info.parent_name)
Write-Host ("  log              : {0}" -f $log)
Write-Host ""
Write-Host "Exiting launcher now. Close SSH. Poll:"
Write-Host ("  Get-Content {0}\plan.json" -f $artifactDir)
Write-Host ("  Get-Content {0}\summary.json" -f $artifactDir)
exit 0
