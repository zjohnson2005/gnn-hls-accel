# H-1 hybrid launcher - live routing arms (D-2) + H1 interleaved (2- or 3-policy).
#
# Single-policy order (least budget risk first):
#   R2a slo_escalate, R2b emission_escalate, R0 cloud_only.
#   R1 agnostic_default is DERIVED from sealed cb781dbf - never live.
#
# Interleaved (INF-5 session_design=interleaved):
#   Same 200 entries, entry-by-entry. Default: H1-3POLICY
#     slo_escalate -> emission_escalate -> full_signal_bounceback
#     Caps: R2a $5, R2b $20, R2c $10, session $35.
#   H1-2POLICY (R2c omitted by selection - optional subset):
#     powershell -NoProfile -File tools/launch_h1.ps1 -Interleaved `
#       -InterleavedPolicies slo_escalate,emission_escalate -SessionMaxUsd 25
#     Caps: R2a $5, R2b $20, session $25. Seal records r2c_excluded.
#   KV/model match sealed R2a 86d0f4cf (gpu_only RESIDENT u8 int4-4B).
#   Resume skips completed entries per policy.
#
# Cost guard: --MaxUsd is REQUIRED for single-policy live arms. Defaults below
# are 1.5x the H1_PREDICTIONS point estimate (read here in the launcher ONLY -
# the Python runner never opens prediction files).
#
#   R2a slo_escalate:      predicted $0.0000  -> MaxUsd 0.0000
#   R2b emission_escalate: predicted $13.0812 -> MaxUsd 19.6218
#   R0  cloud_only:        predicted $54.0704 -> MaxUsd 81.1056
#
# Production (five gates + INF-1b canary preflight):
#   powershell -NoProfile -File tools/launch_h1.ps1 -Policy slo_escalate
#   powershell -NoProfile -File tools/launch_h1.ps1 -Policy emission_escalate
#   powershell -NoProfile -File tools/launch_h1.ps1 -Policy cloud_only
#   powershell -NoProfile -File tools/launch_h1.ps1 -DeriveR1
#   powershell -NoProfile -File tools/launch_h1.ps1 -Interleaved
#   powershell -NoProfile -File tools/launch_h1.ps1 -Interleaved `
#     -InterleavedPolicies slo_escalate,emission_escalate -SessionMaxUsd 25
#
# Hybrid arms load OpenVinoLocalBackend (greedy, max_new_tokens=512, W-3 path)
# via -ModelSpec (default configs/models/Qwen3-4B-int4-ov.yaml). -LocalScript is DEBUG --no-seal only.
# R2b-on-8B: -ModelSpec configs/models/Qwen3-8B-int4-ov.yaml (derived/h1_hybrid/R2B_8B_PREDICTIONS.*).
#
# NOTE: R2C-TURNWISE lifecycle is owned by OpenVinoLocalBackend (begin_entry /
# finish_entry per (entry, policy)). Launcher step 5 runs --lifecycle-smoke
# before spawn so a missing begin fails here, not mid detached run.
# Live R2c / H1-3POLICY seal still needs a clean host, RESIDENT u8, and a
# measured re-prefill canary. Stub backends still refuse --seal.
#
# Machine lock: refuse spawn when .locks/machine.lock is held by a live PID, or
# when another measurement worker (run_h1_hybrid.py / known matrix workers) is
# already alive. Two interleaved launches eight minutes apart (2026-09-20) only
# avoided contention because R2c refused - this check makes that a hard refuse.
#
# Dry-run (gates report-only; spawn suppressed):
#   powershell -NoProfile -File tools/launch_h1.ps1 -Policy cloud_only -DryRun
#   powershell -NoProfile -File tools/launch_h1.ps1 -Interleaved -DryRun
#
# Steps: (1) non-persistent host clean  (2) five gates  (3) INF-1b canary guard
#        (4) machine-lock / alive-worker check  (5) TURNWISE lifecycle smoke
#        (6) spawn_detached  (7) print run_id + artifact dir; exit without waiting.

[CmdletBinding()]
param(
    [ValidateSet("slo_escalate", "emission_escalate", "cloud_only", "agnostic_default", "full_signal_bounceback")]
    [string]$Policy = "",
    [switch]$Interleaved,
    # Comma-separated subset of interleaved arms (order preserved). Empty = full 3-policy.
    # Example: -InterleavedPolicies slo_escalate,emission_escalate
    [string]$InterleavedPolicies = "",
    [switch]$DeriveR1,
    [Nullable[double]]$MaxUsd = $null,
    [Nullable[double]]$SessionMaxUsd = $null,
    [switch]$DryRun,
    [string]$LocalScript = "",
    [string]$ModelSpec = "",
    [switch]$AllowUnguarded
)

$ErrorActionPreference = "Stop"
# Repo root = parent of tools/ (this script's directory).
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
Set-Location $root

# Shared machine-lock / alive-worker gate
. (Join-Path $PSScriptRoot "_assert_machine_lock.ps1")

# 1.5x H1_PREDICTIONS point estimates (launcher-side only; runner is blinded).
$DefaultMaxUsd = @{
    "slo_escalate"           = 0.0
    "emission_escalate"      = 19.6218
    "cloud_only"             = 81.1056
    "full_signal_bounceback" = 10.0
}

$DefaultPolicyCapUsd = @{
    "slo_escalate"           = 5.0
    "emission_escalate"      = 20.0
    "full_signal_bounceback" = 10.0
    "cloud_only"             = 81.1056
}

$DefaultInterleave = @("slo_escalate", "emission_escalate", "full_signal_bounceback")
$AllowedInterleave = @("slo_escalate", "emission_escalate", "full_signal_bounceback", "cloud_only")

$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$WorkerPy = Join-Path $root "tools\run_h1_hybrid.py"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
$SessionRoot = Join-Path $root "derived\h1_hybrid"
$LaunchDir = Join-Path $SessionRoot "_launches"
$W3Entries = Join-Path $root "derived\bfcl_feasibility\w3_weight_quality\sealed_6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a\artifacts\multi_turn_probe_entries.json"
$MachineLockPath = Join-Path $root ".locks\machine.lock"

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

function Resolve-InterleavedPolicyList {
    param([string]$Raw)
    if ([string]::IsNullOrWhiteSpace($Raw)) {
        return @($DefaultInterleave)
    }
    $parts = @($Raw -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
    if ($parts.Count -eq 0) {
        Refuse "-InterleavedPolicies resolved to empty list"
        return @()
    }
    $seen = @{}
    $out = @()
    foreach ($p in $parts) {
        if ($AllowedInterleave -notcontains $p) {
            Refuse ("-InterleavedPolicies unknown policy: {0} (allowed: {1})" -f $p, ($AllowedInterleave -join ","))
            return @()
        }
        if ($seen.ContainsKey($p)) {
            Refuse ("-InterleavedPolicies duplicate: {0}" -f $p)
            return @()
        }
        $seen[$p] = $true
        $out += $p
    }
    return $out
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

$resolvedInterleavePolicies = @()
if ($Interleaved) {
    if (-not [string]::IsNullOrWhiteSpace($Policy)) {
        Refuse "Pass -Interleaved alone (do not combine with -Policy)"
        exit 1
    }
    $resolvedInterleavePolicies = @(Resolve-InterleavedPolicyList -Raw $InterleavedPolicies)
    $hasR2c = $resolvedInterleavePolicies -contains "full_signal_bounceback"
    if ($null -eq $SessionMaxUsd) {
        if ($hasR2c) { $SessionMaxUsd = [double]35.0 }
        else { $SessionMaxUsd = [double]25.0 }
    }
    $tag = if ($hasR2c) { "H1-3POLICY" } else { "H1-2POLICY" }
    Write-Host ("Mode           : INTERLEAVED ({0})" -f $tag)
    Write-Host ("ArmOrder       : {0}" -f ($resolvedInterleavePolicies -join " -> "))
    Write-Host ("SessionMaxUsd  : {0}" -f $SessionMaxUsd)
    $capBits = @()
    foreach ($p in $resolvedInterleavePolicies) {
        $capBits += ("{0}={1}" -f $p, $DefaultPolicyCapUsd[$p])
    }
    Write-Host ("Policy caps    : {0}" -f ($capBits -join " "))
    if (-not $hasR2c) {
        Write-Host "R2c           : EXCLUDED (H1-2POLICY subset; recorded in plan/seal)"
    }
    Write-Host "session_design : interleaved (INF-5)"
    Write-Host ""
} elseif (-not [string]::IsNullOrWhiteSpace($InterleavedPolicies)) {
    Refuse "-InterleavedPolicies requires -Interleaved"
    exit 1
} elseif ([string]::IsNullOrWhiteSpace($Policy)) {
    Refuse "Pass -Policy slo_escalate|emission_escalate|cloud_only|full_signal_bounceback, or -Interleaved, or -DeriveR1"
    exit 1
}
if (-not $Interleaved -and $Policy -eq "agnostic_default") {
    Refuse "agnostic_default must not run live. Use -DeriveR1."
    exit 1
}

if (-not $Interleaved) {
    if ($null -eq $MaxUsd) {
        $MaxUsd = [double]$DefaultMaxUsd[$Policy]
    }
    Write-Host ("Policy         : {0}" -f $Policy)
    Write-Host ("MaxUsd         : {0}" -f $MaxUsd)
    Write-Host ("NOTE -- MaxUsd default is 1.5x H1_PREDICTIONS (launcher-side). Runner never reads predictions.")
    Write-Host ""
}
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
# 4. Machine-lock / alive-worker check (hard refuse)
# ---------------------------------------------------------------------------
Assert-SeamMachineLockClear -RepoRoot $root -DryRun:$DryRun
if ($DryRun) {
    # Assert already printed; DryRun returns without exit when workers found.
    $dryWorkers = @(Get-SeamAliveMeasurementWorkers -ExcludePids @($PID))
    if ($dryWorkers.Count -gt 0 -or (Test-Path -LiteralPath $MachineLockPath)) {
        Write-Host "DRY-RUN: machine-lock / worker check would refuse live spawn"
    }
}

# ---------------------------------------------------------------------------
# 5. TURNWISE lifecycle smoke (one W-3 entry x interleaved policies; stubbed generate)
# ---------------------------------------------------------------------------
Write-Host "=== 5. TURNWISE lifecycle smoke ==="
Write-Host "OpenVinoLocalBackend begin/finish per (entry, policy); stubbed generate; no GPU IR."
if (-not (Test-Path -LiteralPath $W3Entries)) { Refuse "W3 entries pin missing: $W3Entries"; exit 2 }
if (-not (Test-Path -LiteralPath $PythonExe)) { Refuse "PythonExe missing: $PythonExe"; exit 2 }
if (-not (Test-Path -LiteralPath $WorkerPy)) { Refuse "WorkerPy missing: $WorkerPy"; exit 2 }
& $PythonExe -u $WorkerPy --lifecycle-smoke --entries $W3Entries
$lifeRc = $LASTEXITCODE
if ($lifeRc -ne 0) {
    Refuse "TURNWISE lifecycle smoke failed (exit $lifeRc); refuse spawn"
    if (-not $DryRun) { exit $lifeRc }
}
Write-Host "Lifecycle smoke PASS."
Write-Host ""

# ---------------------------------------------------------------------------
# 6. Spawn
# ---------------------------------------------------------------------------
if (-not (Test-Path -LiteralPath $SpawnPs1)) { Refuse "spawn_detached missing: $SpawnPs1"; exit 2 }
if (-not (Test-Path -LiteralPath $PythonExe)) { Refuse "PythonExe missing: $PythonExe"; exit 2 }
if (-not (Test-Path -LiteralPath $W3Entries)) { Refuse "W3 entries pin missing: $W3Entries"; exit 2 }

$sid = [guid]::NewGuid().ToString()
if ($Interleaved) {
    $tagLaunch = "h1_interleaved_" + (Get-Date -Format "yyyyMMdd_HHmmss")
    $artifactDir = Join-Path $SessionRoot ("interleaved_" + $sid)
} else {
    $tagLaunch = "h1_" + $Policy + "_" + (Get-Date -Format "yyyyMMdd_HHmmss")
    $artifactDir = Join-Path $SessionRoot ($Policy + "_" + $sid)
}
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null
$log = Join-Path $LaunchDir "$tagLaunch.log"

if ($Interleaved) {
    $resolvedCmd = 'set SEAM_LAUNCH_CONTEXT=ssh_detached' +
        '&& "' + $PythonExe + '" -u "' + $WorkerPy + '"' +
        ' --interleaved' +
        ' --session-max-usd ' + $SessionMaxUsd
    foreach ($p in $resolvedInterleavePolicies) {
        $resolvedCmd = $resolvedCmd + ' --interleaved-policy ' + $p
        $resolvedCmd = $resolvedCmd + ' --policy-cap ' + $p + '=' + $DefaultPolicyCapUsd[$p]
    }
    $resolvedCmd = $resolvedCmd +
        ' --out "' + $artifactDir + '"' +
        ' --run-id ' + $sid +
        ' --entries "' + $W3Entries + '"'
} else {
    $resolvedCmd = 'set SEAM_LAUNCH_CONTEXT=ssh_detached' +
        '&& "' + $PythonExe + '" -u "' + $WorkerPy + '"' +
        ' --policy ' + $Policy +
        ' --max-usd ' + $MaxUsd +
        ' --out "' + $artifactDir + '"' +
        ' --run-id ' + $sid +
        ' --entries "' + $W3Entries + '"'
}

if (-not [string]::IsNullOrWhiteSpace($LocalScript)) {
    $resolvedCmd = $resolvedCmd + ' --local-script "' + $LocalScript + '" --no-seal'
    Write-Host "NOTE -- -LocalScript is DEBUG replay only (forces --no-seal)."
} else {
    if ([string]::IsNullOrWhiteSpace($ModelSpec)) {
        $ModelSpec = Join-Path $root "configs\models\Qwen3-4B-int4-ov.yaml"
    } elseif (-not [System.IO.Path]::IsPathRooted($ModelSpec)) {
        $ModelSpec = Join-Path $root $ModelSpec
    }
    if (-not (Test-Path -LiteralPath $ModelSpec)) {
        Refuse "ModelSpec missing: $ModelSpec"
        if (-not $DryRun) { exit 2 }
    }
    $resolvedCmd = $resolvedCmd + ' --model-spec "' + $ModelSpec + '"'
    Write-Host ("ModelSpec      : {0}" -f $ModelSpec)
}

Write-Host "RESOLVED_CMD:"
Write-Host $resolvedCmd
Write-Host ""
Write-Host ("session_id (run_id) : {0}" -f $sid)
Write-Host ("artifact_dir        : {0}" -f $artifactDir)
Write-Host ("launch_log          : {0}" -f $log)
if ($Interleaved) {
    Write-Host ("session_max_usd     : {0}" -f $SessionMaxUsd)
    Write-Host ("arm_order           : {0}" -f ($resolvedInterleavePolicies -join ","))
} else {
    Write-Host ("max_usd             : {0}" -f $MaxUsd)
}
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
