# C-2 launcher - TTFT-bound context limit (default: KV precision arms on gpu_only).
#
# Production (Zach, bare SSH after cold boot):
#   powershell -NoProfile -File tools/launch_c2.ps1
#
# CAP-1b (cpu-p cold-start TTFT limit; low bracket below X-2 7743-token SLO miss):
#   powershell -NoProfile -File tools/launch_c2.ps1 -Arms A -Low 500 -High 8000
#   (alias: -Arms cpu-p  maps to delta_n arm id A)
#
# CAP-3 (non-default -ModelSpec; pre-registered in derived/cap3/CAP3_PREDICTIONS.*):
#   powershell -NoProfile -File tools/launch_c2.ps1 -Arms gpu_only_f16 -Low 3000 -High 10000 -ModelSpec configs/models/Qwen3-8B-int4-ov.yaml
#   powershell -NoProfile -File tools/launch_c2.ps1 -Arms gpu_only_f16 -Low 7000 -High 12000 -ModelSpec configs/models/Qwen3-4B-int8-ov.yaml
#
# Dry-run (spawn suppressed; gates report-only; extraction smoke still runs):
#   powershell -NoProfile -File tools/launch_c2.ps1 -DryRun
#   powershell -NoProfile -File tools/launch_c2.ps1 -DryRun -Arms A -Low 500 -High 8000
#
# Steps: (1) non-persistent host clean  (2) five gates  (3) spawn_detached
#        (4) print run_id + artifact dir and exit without waiting.
#
# Payload: tools/run_c1_ceiling.py (same worker as C-1)
#   --criterion ttft_slo --slo-s 10
#   --arms <csv>   (launcher -Arms; default gpu_only_f16,gpu_only_u8,gpu_only_u4)
#   --low / --high (launcher -Low / -High; passed through to bisect bracket end-to-end)
#   Search default: low=8000, high=12000; bisect to +/- 250; 3 repeats
#   Pass: median(prefill_s) <= 10 s
#   Drift canary (INF-1): fixed gpu_only_f16 nc=4000 d=400 RESIDENT;
#     N=min(onset, budget) INF-1b; C=3; early_max threshold floor 0.05;
#     trip => FAIL_CANARY_DRIFT abort (CanaryDriftAbort).
#   Pre-registers (ACTIVE, AM-038): turn-1 TTFT limits agree within +/- 250
#   WITHDRAWN (retained in plan.json): f16 > u8 >= u4 (turn-2 delta claim)
#   Falsified if any pair of limits differs by more than 250 tokens.
#
# Parameters:
#   -Arms <csv>     delta_n arm ids (comma-separated). Alias: cpu-p -> A.
#   -Low / -High    bisect bracket (tokens). Honoured: launcher -> --low/--high -> bisect_arm.
#   -Resolution     bisect stop when (high-low) <= Resolution (default 250).
#   -Repeats        probes per n (default 3).
#   -ModelSpec      FetchedModelSpec YAML (default Qwen3-4B-int4-ov).
#   -AllowUnguarded / -PlannedProbeCount / -DryRun  as before.
#
# WSH watchdog interval 60 s (ENV_CHANGELOG).
# Banners are ASCII only (no en-dash / em-dash in Write-Host).

[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$ModelSpec = "",
    [string]$Arms = "gpu_only_f16,gpu_only_u8,gpu_only_u4",
    [int]$Low = 8000,
    [int]$High = 12000,
    [int]$Resolution = 250,
    [int]$Repeats = 3,
    [switch]$AllowUnguarded,
    [Nullable[int]]$PlannedProbeCount = $null
)

$ErrorActionPreference = "Stop"
# Repo root = parent of tools/ (this script's directory).
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
Set-Location $root

$Tag = "c2_ttft"
$WatchdogIntervalS = 60
$Criterion = "ttft_slo"
$SloS = 10
# Normalize -Arms: trim, drop empties, map cpu-p -> A (delta_n id).
$armParts = @()
foreach ($raw in ($Arms -split ",")) {
    $a = $raw.Trim()
    if ([string]::IsNullOrWhiteSpace($a)) { continue }
    if ($a -eq "cpu-p") { $a = "A" }
    $armParts += $a
}
if ($armParts.Count -eq 0) {
    Write-Host "REFUSED -- -Arms empty after parse"
    exit 2
}
$ArmsCsv = ($armParts -join ",")
# Extraction smoke checks metric plumbing (prefill_s), not the experiment arm.
# Keep gpu_only_f16 so CAP-1b dry-runs are not blocked by cpu-p quiescence under tier-1 load.
$SmokeArm = "gpu_only_f16"
if ($Low -ge $High) {
    Write-Host ("REFUSED -- -Low ({0}) must be < -High ({1})" -f $Low, $High)
    exit 2
}
if ([string]::IsNullOrWhiteSpace($ModelSpec)) {
    $ModelSpec = Join-Path $root "configs\models\Qwen3-4B-int4-ov.yaml"
} elseif (-not [System.IO.Path]::IsPathRooted($ModelSpec)) {
    $ModelSpec = Join-Path $root $ModelSpec
}
$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$WorkerPy = Join-Path $root "tools\run_c1_ceiling.py"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
$SessionRoot = Join-Path $root "derived\c2_ttft"
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

Write-Host "=== launch_c2.ps1 ==="
Write-Host ("mode           : {0}" -f $(if ($DryRun) { "DRY-RUN (spawn suppressed)" } else { "LIVE" }))
Write-Host ("cwd            : {0}" -f (Get-Location).Path)
Write-Host ("started_utc    : {0}" -f (Get-Date).ToUniversalTime().ToString("o"))
Write-Host ("Worker         : tools/run_c1_ceiling.py")
Write-Host ("Arms           : {0}" -f $ArmsCsv)
Write-Host ("Search         : low={0} high={1} resolution={2} repeats={3}" -f $Low, $High, $Resolution, $Repeats)
Write-Host ("Bracket chain  : -Low/-High -> worker --low/--high -> bisect_arm(low, high)")
Write-Host ("ExtractionSmoke: gpu_only_f16 n=64 (metric path; independent of -Arms)")
Write-Host ("Criterion      : {0}  slo_s={1}" -f $Criterion, $SloS)
Write-Host ("ModelSpec      : {0}" -f $ModelSpec)
Write-Host ("WatchdogIntervalS: {0}" -f $WatchdogIntervalS)
Write-Host ""
Write-Host "PRE-REGISTERED PREDICTION (written into plan.json before first probe):"
Write-Host "  ACTIVE: three turn-1 TTFT limits AGREE within +/- 250 tokens."
Write-Host "  FALSIFIED if any pair differs by more than 250 tokens."
Write-Host "  WITHDRAWN (retained): f16 > u8 >= u4 - turn-2 delta claim, not turn-1."
Write-Host "  NOT C-2: turn-2 delta-prefill 10 s limit (wider search; f16 > u8 >= u4)."
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
Write-Host "=== 3. resolved C-2 command ==="

foreach ($p in @($WorkerPy, $SpawnPs1, $PythonExe, $ModelSpec)) {
    if (-not (Test-Path -LiteralPath $p)) {
        Refuse "missing required path: $p"
        exit 2
    }
}

$sid = [guid]::NewGuid().ToString()
$tagLaunch = "c2_" + (Get-Date -Format "yyyyMMdd_HHmmss")
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null
$log = Join-Path $LaunchDir "$tagLaunch.log"
$artifactDir = Join-Path $SessionRoot $sid

$resolvedCmd = 'set SEAM_LAUNCH_CONTEXT=ssh_detached' +
    '&& "' + $PythonExe + '" -u "' + $WorkerPy + '"' +
    ' --session-id ' + $sid +
    ' --out "' + $artifactDir + '"' +
    ' --model-spec "' + $ModelSpec + '"' +
    ' --arms ' + $ArmsCsv +
    ' --criterion ' + $Criterion +
    ' --slo-s ' + $SloS +
    ' --low ' + $Low +
    ' --high ' + $High +
    ' --resolution ' + $Resolution +
    ' --repeats ' + $Repeats +
    ' --watchdog-interval-s ' + $WatchdogIntervalS
if ($null -ne $PlannedProbeCount) {
    $resolvedCmd = $resolvedCmd + ' --planned-probe-count ' + $PlannedProbeCount
}
if ($AllowUnguarded) {
    $resolvedCmd = $resolvedCmd + ' --allow-unguarded'
    Write-Host "NOTE -- -AllowUnguarded: session may finalize with UNGUARDED if canary never arms."
}

Write-Host "RESOLVED_CMD:"
Write-Host $resolvedCmd
Write-Host ""
Write-Host ("session_id (run_id) : {0}" -f $sid)
Write-Host ("artifact_dir        : {0}" -f $artifactDir)
Write-Host ("launch_log          : {0}" -f $log)
Write-Host ""

# ---------------------------------------------------------------------------
# Extraction smoke (n=64): must return non-null numeric prefill_s.
# Would have caught e39aaa86 (pass + null prefill_s) before the run.
# ---------------------------------------------------------------------------
Write-Host "=== extraction smoke (n=64, real cell) ==="
$SmokePy = Join-Path $root "tools\c2_extraction_smoke.py"
$SmokeOut = Join-Path $SessionRoot "_extraction_smoke"
if (-not (Test-Path -LiteralPath $SmokePy)) {
    Refuse "missing extraction smoke: $SmokePy"
    exit 2
}
& $PythonExe -u $SmokePy --out $SmokeOut --model-spec $ModelSpec --n-tokens 64 --arm $SmokeArm
if ($LASTEXITCODE -ne 0) {
    Write-Host "REFUSED -- extraction smoke failed; not launching C-2"
    exit $LASTEXITCODE
}
Write-Host ""

if ($DryRun) {
    Write-Host "=== DRY-RUN: prompt bracket + arm pin + AM-038 payload ==="
    $dryOut = Join-Path $SessionRoot ("{0}_dryrun" -f $Tag)
    New-Item -ItemType Directory -Force -Path $dryOut | Out-Null
    $dryPy = Join-Path $dryOut "_dryrun_preflight.py"
    $armsPyLiteral = ($armParts | ForEach-Object { "'" + $_ + "'" }) -join ", "
    @"
import json, sys
from pathlib import Path
sys.path.insert(0, r"$root")
from transformers import AutoTokenizer
from seam.config import resolve_config
from seam.tools.delta_n import build_exact_prompt, _PLATFORM_PATH, _MEASUREMENT_PATH, _DELTA_N_PATH
from tools.run_c1_ceiling import (
    _ttft_slo_predictions, CRITERION_TTFT_SLO, SLO_S_DEFAULT
)

root = Path(r"$root")
resolved = resolve_config(
    [root / _PLATFORM_PATH, root / _MEASUREMENT_PATH, root / _DELTA_N_PATH],
    repo_root=root,
)
cfg = resolved.data
arms_by_id = {a["id"]: a for a in cfg["arms"]}
selected = [$armsPyLiteral]
for aid in selected:
    assert aid in arms_by_id, aid
    print("ARM_OK", aid)
if "gpu_only_f16" in selected:
    props = arms_by_id["gpu_only_f16"].get("properties") or {}
    assert str(props.get("KV_CACHE_PRECISION")).lower() == "f16", props
    print("ARM_PIN_OK gpu_only_f16 KV_CACHE_PRECISION=f16")
for aid in selected:
    if aid.startswith("gpu_only_"):
        props = arms_by_id[aid].get("properties") or {}
        print("ARM", aid, "KV_CACHE_PRECISION", props.get("KV_CACHE_PRECISION"))
from seam.model_provenance import load_local_spec
spec = load_local_spec(Path(r"$ModelSpec"))
ir_dir = Path(str(spec["ir_dir"]))
assert ir_dir.is_dir(), ir_dir
print("MODEL_SPEC_OK", r"$ModelSpec")
print("IR_DIR_OK", ir_dir)
tok = AutoTokenizer.from_pretrained(str(ir_dir))
unit = cfg["ladder"]["filler_unit"]
low, high = int($Low), int($High)
for n in sorted({low, (low + high) // 2, high}):
    text, realized = build_exact_prompt(tok, target_tokens=n, unit=unit)
    assert realized == n, (n, realized)
    print("PROMPT_OK", n, "chars", len(text))
print("BRACKET_OK low", low, "high", high)
pred = _ttft_slo_predictions(slo_s=float($SloS), repeats=int($Repeats))
print("CRITERION", CRITERION_TTFT_SLO)
print("ACTIVE_ORDER", pred["primary_prediction"]["order"])
print("ACTIVE_FALSIFIED_IF", pred["primary_prediction"]["falsified_if"])
print("WITHDRAWN_ORDER", pred["withdrawn_prediction"]["order"])
print("SEPARATE_NOT_C2", pred["separate_experiment_not_c2"]["name"])
print("SLO_S", SLO_S_DEFAULT)
print("DRYRUN_OK")
"@ | Set-Content -LiteralPath $dryPy -Encoding utf8

    & $PythonExe -u $dryPy
    if ($LASTEXITCODE -ne 0) {
        Write-Host "REFUSED -- dry-run preflight failed"
        exit $LASTEXITCODE
    }
    Write-Host ""
    Write-Host "=== DRY-RUN gate refusal summary ==="
    if ($gateFails.Count -eq 0) {
        Write-Host "Would refuse: (none -- all five gates PASS on this host right now)"
    } else {
        Write-Host "Would refuse:"
        foreach ($r in $gateFails) { Write-Host ("  - {0}" -f $r) }
    }
    Write-Host ""
    Write-Host "DRY-RUN complete. Extraction smoke ran; spawn NOT executed."
    exit 0
}

Write-Host "=== 4. spawn_detached (live) ==="
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
$json = & $SpawnPs1 -CommandLine $resolvedCmd -LogPath $log -WorkingDirectory $root
Write-Host $json
$info = $json | ConvertFrom-Json
Write-Host ""
Write-Host "launched C-2 detached"
Write-Host ("  run_id           : {0}" -f $sid)
Write-Host ("  artifact_dir     : {0}" -f $artifactDir)
Write-Host ("  pid              : {0} (parent {1})" -f $info.pid, $info.parent_name)
Write-Host ("  log              : {0}" -f $log)
Write-Host ""
Write-Host "Exiting launcher now. Close SSH. Poll:"
Write-Host ("  Get-Content {0}\plan.json" -f $artifactDir)
Write-Host ("  Get-Content {0}\summary.json" -f $artifactDir)
exit 0
