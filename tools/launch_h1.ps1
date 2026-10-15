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
#   A dirty tree is refused unless -AllowDirty, which records DIRTY and the
#   sha256 of git diff HEAD in the plan and the seal.
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
# EVO-T2S (-T2S): SEAM_PLATFORM_ID=evo-t2 for the gates, the canary, the
# smoke and the detached worker (passed on its command line); Rithwik's
# watchdog launch-check (C:\apu\ovn\watchdog.log, refuses on a busy queue or
# a foreign python / llama-server); a venv import check (anthropic,
# transformers, bfcl_eval); the uptime gate is skipped and recorded as
# UNCOLD_UPTIME because T2S is not rebooted. Canary onset and floors are the
# aipc-c1 values (borrowed, as in t2s-boot1). Without -T2S this launcher
# refuses on a host that has C:\apu\ovn.
#   powershell -NoProfile -File tools/launch_h1.ps1 -T2S -Interleaved -DryRun
#   powershell -NoProfile -File tools/launch_h1.ps1 -T2S -Interleaved `
#     -ModelSpec configs/models/Qwen3-8B-int4-ov.yaml -DryRun
#
# DEMO-1 / H1-CPU options (defaults unchanged):
#   -Entries <path>     a pinned entries file (run_h1_hybrid.py ENTRY_PINS), e.g.
#                       derived/h1_hybrid/demo1/DEMO1_LONGCTX_30.json. Default W-3.
#   -Placement cpu-p    hybrid local arm on CPU (delta_n arm A). Default gpu_only.
#   -Residency NON_RESIDENT   full prefill every step. Default RESIDENT.
#   -Kv u8|u4|f16|default  KV cache precision of the gpu_only local arm (DEMO-1 V5b);
#                       default = no KV property (DEMO-2 control; readback must be dynamic).
#                       Default u8 (unchanged); the readback refuses a mismatch.
#   -PolicyCapUsd "p=usd,..."   interleaved per-policy caps (default table above).
#   -EntryOffset <i> -EntryCount <n>   one boot's chunk of the pinned entries
#                       (H1-CPU chunking); the plan records the chunk.
#   -ObsMaskK <K>       OBS_MASK arm: keep the first K whitespace tokens of every tool
#                       observation (local and cloud). Default off. Ledger: obs_mask_ledger.json.
#   -ContextWindow <N>  DEMO-2: a local step whose prompt plus max_new_tokens exceeds N is not
#                       generated; the turn escalates (sticky, ctx_overflow). Single-arm only.
#                       Default off.
#   -Policy hybrid_full DEMO-2 policy (mechanical then quality triggers). -MaxUsd is required.
#
# Dry-run (gates report-only; spawn suppressed):
#   powershell -NoProfile -File tools/launch_h1.ps1 -Policy cloud_only -DryRun
#   powershell -NoProfile -File tools/launch_h1.ps1 -Interleaved -DryRun
#
# Launch evidence (live): the gate JSON and the opening canary are written to
# derived/h1_hybrid/_launches/<run_id>/ (gitignored), not to the shared tracked
# derived/h1_hybrid/_canary_opening/ or to derived/_gate_probes/. The worker's
# clean-tree check then passes without --allow-dirty, and the worker records
# every file there with its sha256 in plan.json git.launch_evidence.
#
# Cloud ping (step 5b): when any selected policy can reach the cloud (every
# policy except local_only), tools/cloud_ping.py sends one max_tokens 8 request
# through the runner's own client and model id, in the foreground, before the
# spawn. A failed ping refuses the spawn. The JSON goes to the run's launch
# dir (cloud_ping.json; hashed into plan.json git.launch_evidence on a live
# run). -DryRun pings too (the cheap check, under $0.001) unless -NoCloudPing;
# -NoCloudPing is refused on a live launch.
#
# Steps: (1) non-persistent host clean  (2) five gates  (3) INF-1b canary guard
#        (4) machine-lock / alive-worker check  (5) TURNWISE lifecycle smoke
#        (5b) cloud ping  (6) spawn_detached  (7) print run_id + artifact dir; exit without waiting.

[CmdletBinding()]
param(
    [ValidateSet("slo_escalate", "emission_escalate", "cloud_only", "agnostic_default", "full_signal_bounceback", "hybrid_full")]
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
    [switch]$AllowUnguarded,
    [switch]$AllowDirty,
    [switch]$T2S,
    [string]$WatchdogLog = "C:\apu\ovn\watchdog.log",
    [string]$Entries = "",
    [ValidateSet("", "gpu_only", "cpu-p")]
    [string]$Placement = "",
    [ValidateSet("", "RESIDENT", "NON_RESIDENT")]
    [string]$Residency = "",
    [ValidateSet("", "u8", "u4", "f16", "default")]
    [string]$Kv = "",
    [Nullable[int]]$ObsMaskK = $null,
    [Nullable[int]]$ContextWindow = $null,
    [Nullable[int]]$EntryOffset = $null,
    [Nullable[int]]$EntryCount = $null,
    # Interleaved per-policy caps, overriding the defaults, e.g.
    # "emission_escalate=3,full_signal_bounceback=2,local_only=0" (H1-CPU amendment 2).
    [string]$PolicyCapUsd = "",
    # Skip the cloud ping on a -DryRun only. A live launch always pings.
    [switch]$NoCloudPing
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
    "local_only"             = 0.0
}

$DefaultInterleave = @("slo_escalate", "emission_escalate", "full_signal_bounceback")
$AllowedInterleave = @("slo_escalate", "emission_escalate", "full_signal_bounceback", "cloud_only", "local_only")

$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$WorkerPy = Join-Path $root "tools\run_h1_hybrid.py"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
$SessionRoot = Join-Path $root "derived\h1_hybrid"
$LaunchDir = Join-Path $SessionRoot "_launches"
$W3Entries = Join-Path $root "derived\bfcl_feasibility\w3_weight_quality\sealed_6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a\artifacts\multi_turn_probe_entries.json"
# The run's entries. The runner refuses any file whose sha256 is not pinned.
$RunEntries = $W3Entries
if (-not [string]::IsNullOrWhiteSpace($Entries)) {
    if ([System.IO.Path]::IsPathRooted($Entries)) { $RunEntries = $Entries } else { $RunEntries = Join-Path $root $Entries }
}
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

$porcelain = & git -C $root status --porcelain
if ($LASTEXITCODE -ne 0) {
    Refuse "git status failed; refuse launch"
    exit 2
}
$dirtyTree = -not [string]::IsNullOrWhiteSpace(($porcelain | Out-String))
if ($dirtyTree -and -not $AllowDirty) {
    Refuse "dirty working tree; commit the changes or pass -AllowDirty (plan and seal record DIRTY and the sha256 of git diff HEAD)"
    exit 2
}
if ($AllowDirty -and $dirtyTree) {
    Write-Host "NOTE -- -AllowDirty: plan and seal record DIRTY and the sha256 of git diff HEAD"
    Write-Host ""
}

if ($DeriveR1) {
    Write-Host "R1 path: DERIVED from sealed cb781dbf (not MEASURED, not live)."
    $sid = [guid]::NewGuid().ToString()
    $artifactDir = Join-Path $SessionRoot ("derived_r1_" + $sid)
    New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null
    $cmd = '"' + $PythonExe + '" -u "' + $WorkerPy + '" --derive-r1 --out "' + $artifactDir + '" --run-id ' + $sid
    if ($AllowDirty) { $cmd = $cmd + ' --allow-dirty' }
    Write-Host "RESOLVED_CMD:"
    Write-Host $cmd
    if ($DryRun) {
        Write-Host "DRY-RUN: derive-r1 spawn suppressed."
        exit 0
    }
    $deriveArgs = @("-u", $WorkerPy, "--derive-r1", "--out", $artifactDir, "--run-id", $sid)
    if ($AllowDirty) { $deriveArgs += "--allow-dirty" }
    & $PythonExe @deriveArgs
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
    if (-not [string]::IsNullOrWhiteSpace($PolicyCapUsd)) {
        foreach ($item in @($PolicyCapUsd -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })) {
            $kv = $item -split "=", 2
            if ($kv.Count -ne 2) { Refuse ("-PolicyCapUsd item must be POLICY=USD: {0}" -f $item); exit 1 }
            $capName = $kv[0].Trim()
            if ($resolvedInterleavePolicies -notcontains $capName) {
                Refuse ("-PolicyCapUsd names a policy not in -InterleavedPolicies: {0}" -f $capName)
                exit 1
            }
            $capValue = 0.0
            if (-not [double]::TryParse($kv[1].Trim(), [ref]$capValue) -or $capValue -lt 0) {
                Refuse ("-PolicyCapUsd value must be a number >= 0: {0}" -f $item)
                exit 1
            }
            $DefaultPolicyCapUsd[$capName] = $capValue
        }
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
} elseif (-not [string]::IsNullOrWhiteSpace($PolicyCapUsd)) {
    Refuse "-PolicyCapUsd requires -Interleaved (single-policy runs use -MaxUsd)"
    exit 1
} elseif ([string]::IsNullOrWhiteSpace($Policy)) {
    Refuse "Pass -Policy slo_escalate|emission_escalate|cloud_only|full_signal_bounceback, or -Interleaved, or -DeriveR1"
    exit 1
}
if (-not $Interleaved -and $Policy -eq "agnostic_default") {
    Refuse "agnostic_default must not run live. Use -DeriveR1."
    exit 1
}

if ($Interleaved -and $null -ne $ContextWindow) {
    Refuse "-ContextWindow is single-arm only (DEMO-2)"
    exit 1
}
if (-not $Interleaved -and $Policy -eq "hybrid_full" -and $null -eq $MaxUsd) {
    Refuse "-MaxUsd is required for hybrid_full (per-cell cap from the DEMO-2 prereg)"
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
# 0. Platform (EVO-T2S needs -T2S)
# ---------------------------------------------------------------------------
Write-Host "=== 0. platform ==="
$T2sMarker = "C:\apu\ovn"
if ($T2S) {
    $env:SEAM_PLATFORM_ID = "evo-t2"
    Write-Host "platform_id=evo-t2 config=configs/platforms/evo-t2.yaml"
    Write-Host ("watchdog_log={0}" -f $WatchdogLog)
    Write-Host "uptime_gate=skipped deviation=UNCOLD_UPTIME (T2S is not rebooted); other gates enforced"
    Write-Host "canary onset_s=657 and healthy floors are borrowed from aipc-c1 (not an evo-t2 measurement)"
    $names = @(Get-Process -Name python, llama-server -ErrorAction SilentlyContinue |
        ForEach-Object { $_.ProcessName })
    if ($names.Count -eq 0) {
        $running = "[]"
    } else {
        $running = ConvertTo-Json -InputObject @($names) -Compress
    }
    & $PythonExe (Join-Path $root "tools\t2s_queue_watchdog.py") launch-check --log $WatchdogLog --running-json $running
    if ($LASTEXITCODE -ne 0) {
        Refuse "T2S watchdog launch-check failed (exit $LASTEXITCODE)"
    }
    & $PythonExe -c "import anthropic, transformers, bfcl_eval; print('venv_imports_ok')"
    if ($LASTEXITCODE -ne 0) {
        Refuse "T2S venv lacks anthropic, transformers or bfcl_eval"
    }
} elseif (Test-Path -LiteralPath $T2sMarker) {
    Refuse "this host has $T2sMarker (EVO-T2S); pass -T2S so the gates and the plan use evo-t2"
} else {
    Write-Host "platform_id from SEAM_PLATFORM_ID or configs/platforms/active_platform_id.txt"
}
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

# The run_id is fixed before the gates so every launcher-owned evidence file
# lands in this run's launch dir.
$sid = [guid]::NewGuid().ToString()
$SessionLaunchDir = Join-Path $LaunchDir $sid
if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $SessionLaunchDir | Out-Null
}
Write-Host ("launch_evidence_dir : {0}" -f $SessionLaunchDir)
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
$gateProbeDir = if ($DryRun) { "" } else { $SessionLaunchDir }
$gateJson = Invoke-SeamMeasurementGates -RepoRoot $root -PythonExe $pythonForGates `
    -PlatformId $platformId -SkipUptime:$T2S -DryRun:$DryRun -ProbeDir $gateProbeDir
$gateFails = @(Get-SeamGateRefusals -GateJson $gateJson)
Write-Host ""

# ---------------------------------------------------------------------------
# 3. INF-1b canary guard (fixed cell + dual-bound N; refuse unarmed seal)
# ---------------------------------------------------------------------------
Write-Host "=== 3. INF-1b canary ==="
Write-Host "fixed cell: gpu_only_f16 n_cached=4000 delta=400 RESIDENT"
Write-Host "thresholds: C=3 healthy-session floor (t1 and t2) onset_s=657"
$CanaryOpeningPy = Join-Path $root "tools\run_h1_canary_opening.py"
if (-not (Test-Path -LiteralPath $CanaryOpeningPy)) {
    Refuse "missing INF-1b canary opening: $CanaryOpeningPy"
    if (-not $DryRun) { exit 2 }
}
# Per-run, gitignored. The tracked derived/h1_hybrid/_canary_opening/ (d482c621,
# ff09628) is left as it is. A dry run is --logic-only and writes nothing.
$CanaryOut = Join-Path $SessionLaunchDir "canary_opening"
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
# 5b. Cloud ping (foreground; same client and model id as the worker)
# ---------------------------------------------------------------------------
Write-Host "=== 5b. cloud ping ==="
$cloudPolicies = @()
if ($Interleaved) {
    $cloudPolicies = @($resolvedInterleavePolicies | Where-Object { $_ -ne "local_only" })
} elseif ($Policy -ne "local_only") {
    $cloudPolicies = @($Policy)
}
if ($NoCloudPing -and -not $DryRun) {
    Refuse "-NoCloudPing is only for -DryRun; a live launch always pings the cloud first"
    exit 1
}
if ($cloudPolicies.Count -eq 0) {
    Write-Host "cloud ping: skipped (no selected policy reaches the cloud)"
} elseif ($NoCloudPing) {
    Write-Host "DRY-RUN: cloud ping skipped (-NoCloudPing)"
} else {
    $CloudPingPy = Join-Path $root "tools\cloud_ping.py"
    if (-not (Test-Path -LiteralPath $CloudPingPy)) { Refuse "cloud ping missing: $CloudPingPy"; exit 2 }
    New-Item -ItemType Directory -Force -Path $SessionLaunchDir | Out-Null
    $CloudPingJson = Join-Path $SessionLaunchDir "cloud_ping.json"
    Write-Host ("cloud ping for: {0}" -f ($cloudPolicies -join ","))
    & $PythonExe -u $CloudPingPy --out $CloudPingJson
    $pingRc = $LASTEXITCODE
    Write-Host ("cloud_ping_json: {0}" -f $CloudPingJson)
    if ($pingRc -ne 0) {
        Refuse "cloud ping failed (exit $pingRc; see $CloudPingJson); refuse spawn"
        if (-not $DryRun) { exit $pingRc }
    } else {
        Write-Host "Cloud ping PASS."
    }
}
Write-Host ""

# ---------------------------------------------------------------------------
# 6. Spawn
# ---------------------------------------------------------------------------
if (-not (Test-Path -LiteralPath $SpawnPs1)) { Refuse "spawn_detached missing: $SpawnPs1"; exit 2 }
if (-not (Test-Path -LiteralPath $PythonExe)) { Refuse "PythonExe missing: $PythonExe"; exit 2 }
if (-not (Test-Path -LiteralPath $W3Entries)) { Refuse "W3 entries pin missing: $W3Entries"; exit 2 }

if ($Interleaved) {
    $tagLaunch = "h1_interleaved_" + (Get-Date -Format "yyyyMMdd_HHmmss")
    $artifactDir = Join-Path $SessionRoot ("interleaved_" + $sid)
} else {
    $tagLaunch = "h1_" + $Policy + "_" + (Get-Date -Format "yyyyMMdd_HHmmss")
    $artifactDir = Join-Path $SessionRoot ($Policy + "_" + $sid)
}
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null
$log = Join-Path $LaunchDir "$tagLaunch.log"

# The WMI child does not inherit this shell's environment.
$envPrefix = 'set SEAM_LAUNCH_CONTEXT=ssh_detached'
if ($T2S) { $envPrefix = $envPrefix + '&& set SEAM_PLATFORM_ID=evo-t2' }

if ($Interleaved) {
    $resolvedCmd = $envPrefix +
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
        ' --entries "' + $RunEntries + '"' +
        ' --launch-evidence-dir "' + $SessionLaunchDir + '"'
} else {
    $resolvedCmd = $envPrefix +
        '&& "' + $PythonExe + '" -u "' + $WorkerPy + '"' +
        ' --policy ' + $Policy +
        ' --max-usd ' + $MaxUsd +
        ' --out "' + $artifactDir + '"' +
        ' --run-id ' + $sid +
        ' --entries "' + $RunEntries + '"' +
        ' --launch-evidence-dir "' + $SessionLaunchDir + '"'
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

if (-not (Test-Path -LiteralPath $RunEntries)) { Refuse "entries file missing: $RunEntries"; exit 2 }
if (-not [string]::IsNullOrWhiteSpace($Placement)) {
    $resolvedCmd = $resolvedCmd + ' --placement ' + $Placement
}
if (-not [string]::IsNullOrWhiteSpace($Residency)) {
    $resolvedCmd = $resolvedCmd + ' --residency ' + $Residency
}
if (-not [string]::IsNullOrWhiteSpace($Kv)) {
    if ($Placement -eq "cpu-p") {
        Refuse "-Kv applies to the gpu_only arm; -Placement cpu-p loads delta_n arm A, whose KV is not pinned"
        exit 1
    }
    $resolvedCmd = $resolvedCmd + ' --kv ' + $Kv
}
if ($null -ne $ObsMaskK) {
    $resolvedCmd = $resolvedCmd + ' --obs-mask-k ' + $ObsMaskK
}
if ($null -ne $ContextWindow) {
    $resolvedCmd = $resolvedCmd + ' --context-window ' + $ContextWindow
}
if ($null -ne $EntryOffset) {
    $resolvedCmd = $resolvedCmd + ' --entry-offset ' + $EntryOffset
}
if ($null -ne $EntryCount) {
    $resolvedCmd = $resolvedCmd + ' --entry-count ' + $EntryCount
}

if ($AllowDirty) {
    $resolvedCmd = $resolvedCmd + ' --allow-dirty'
}

Write-Host "RESOLVED_CMD:"
Write-Host $resolvedCmd
Write-Host ""
Write-Host ("session_id (run_id) : {0}" -f $sid)
Write-Host ("artifact_dir        : {0}" -f $artifactDir)
Write-Host ("launch_log          : {0}" -f $log)
Write-Host ("launch_evidence_dir : {0}" -f $SessionLaunchDir)
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
