<#
.SYNOPSIS
  Delta-prefill under session residency: RESIDENT vs NON_RESIDENT.

.DESCRIPTION
  Diagnostic only. No seal, no amendment, no commit.
  Artifacts under derived/delta_prefill/.

  Matrix (one process per cell; turn 2 always in the same warm process as turn 1):
    arms        -Arms comma list (default A,gpu_only; also gpu_only_f16 / gpu_only_u8 / gpu_only_u4)
    n_cached    -NCached comma list (default 12000; e.g. 4000,12000)
    deltas      -Deltas comma list (default 500,2000)
    modes       RESIDENT and NON_RESIDENT at EVERY provided delta.
                NON_RESIDENT: finish_chat then full re-prefill of n_cached+delta.
                DEFECT (fixed): earlier revisions ran NON_RESIDENT only at max(-Deltas),
                so residency ratios at small deltas had no matched cold cell — see
                derived/delta_prefill/DEFECT_non_resident_max_delta_only.md.
    repeats     3, interleaved, randomized order of (arm, n_cached, mode, delta) per round
    max_new     64
    cell wall   -CellTimeoutS (default 1500). Parent kills hung children after the
                cell writes its record; records classification=TIMEOUT and continues.
                Derivation (session d5c98342): OK max elapsed_s=616.8; 2× → 1234;
                rounded up to 1500. Hung cell was 2856.5s (operator kill). generation.timeout_s
                (1800) bounds only generate() inside the child.

  Prefer -Orchestrate (WMI-detached via tools/spawn_detached.ps1). Declares
  launch_context=ssh_detached. Refuses if Cursor/Chrome/etc are resident.
  Pre-run: Available MBytes >= isolation.pre_run_available_mb_min (7000).

  From the Mac, with Cursor and browsers closed on the XPS:

    ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Orchestrate"
    ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Orchestrate -Arms gpu_only_u8 -NCached 4000,12000 -Deltas 100,400,1000,2000"
    ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Orchestrate -Arms gpu_only_u4 -NCached 2000,4000,8000,12000 -Deltas 50,150,400,1000 -Tag dispatch_o_u4"
    ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_dispatch_p_precision_matrix.ps1 -Orchestrate"
    ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Status"

  Drift canary (optional; required for DISPATCH P interleaved precision):
    -CanaryEveryN N>0 inserts a fixed canary cell (default gpu_only / nc=4000 /
    d=400 / RESIDENT) at the start and after every N matrix cells. Threshold is
    derived in-run from the canary's own early-run relative variance (see plan
    canary_gate); abort status=FAIL_CANARY_DRIFT rather than silently degrade.

  Three numbers (after complete):
    1. turn2_prefill_s RESIDENT vs NON_RESIDENT per (arm, n_cached, delta)
    2. gpu_only:A on turn2_prefill_s RESIDENT (max delta) when both arms present
    3. Whether turn2 RESIDENT scales across provided deltas (when >=2)

  Falsification: RESIDENT turn-2 not materially cheaper than NON_RESIDENT → KV not retained.
#>
[CmdletBinding(DefaultParameterSetName = "Run")]
param(
    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [ValidateSet("local_console", "ssh_foreground", "ssh_detached")]
    [string]$LaunchContext = "ssh_foreground",

    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "VerifyDetach")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [string]$Tag = "delta_prefill",

    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "Status")]
    [Parameter(ParameterSetName = "VerifyDetach")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [string]$PythonExe = "C:\Users\zjohn\Projects\gnn-hls-accel\.venv-seam\Scripts\python.exe",

    # Comma-separated n_cached values. Default preserves single 12000.
    # Typed as [object] (not [int]/[string]): unquoted 4000,12000 binds as Object[] and
    # must not throw ConvertToFinalInvalidCastException at parameter binding.
    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [object]$NCached = "12000",

    # Comma-separated turn-2 deltas. Default preserves {500,2000}.
    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [object]$Deltas = "500,2000",

    # Comma-separated arm ids from configs/delta_n.yaml. Default preserves {A,gpu_only}.
    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [object]$Arms = "A,gpu_only",

    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [int]$Repeats = 3,

    # Per-cell wall-clock timeout (parent kills child tree). See synopsis derivation.
    # Citing session d5c98342-a0b2-41a9-b6e2-93ac7a39c3ba: OK max=616.8s; 2×→1234; use 1500.
    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [int]$CellTimeoutS = 1500,

    # Drift canary: 0 disables. N>0 → canary at start and after every N matrix cells.
    # N derivation for DISPATCH P is recorded in derived/kv_precision/DISPATCH_P_TIME_ESTIMATE.md
    # (last-good→first-bad onset in session 7f569929 / mean cell wall).
    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [int]$CanaryEveryN = 0,

    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [string]$CanaryArm = "gpu_only",

    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [int]$CanaryNCached = 4000,

    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [int]$CanaryDelta = 400,

    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [ValidateSet("RESIDENT", "NON_RESIDENT")]
    [string]$CanaryMode = "RESIDENT",

    # First K successful canaries establish ref + early relative variance; gate arms after.
    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [int]$CanaryCalibrationCount = 3,

    # Absolute relative-drift floor when early_max≈0 (same 0.05 spirit as C2f margin).
    [Parameter(ParameterSetName = "Run")]
    [Parameter(ParameterSetName = "Orchestrate")]
    [Parameter(ParameterSetName = "DryRunGate")]
    [double]$CanaryRelDriftFloor = 0.05,

    [Parameter(ParameterSetName = "Run")][switch]$SkipSettle,

    [Parameter(ParameterSetName = "Orchestrate")][switch]$Orchestrate,
    [Parameter(ParameterSetName = "Status")][switch]$Status,
    [Parameter(ParameterSetName = "VerifyDetach")][switch]$VerifyDetach,
    [Parameter(ParameterSetName = "DryRunGate")][switch]$DryRunGate,

    [Parameter(ParameterSetName = "Run")][switch]$DetachedWorker,
    [Parameter(ParameterSetName = "Run")][string]$SessionId,
    [Parameter(ParameterSetName = "Run")][switch]$HeartbeatOnly,
    [Parameter(ParameterSetName = "Run")][int]$HeartbeatSeconds = 30
)

$ErrorActionPreference = "Stop"
$root = "C:\Users\zjohn\Projects\gnn-hls-accel"
. (Join-Path $root "tools\SeamPsCommon.ps1")
$cfgPath = Join-Path $root "configs\delta_n.yaml"
$smokePy = Join-Path $root "tools\smoke_delta_prefill.py"
$sessionRoot = Join-Path $root "derived\delta_prefill"
$launchDir = Join-Path $sessionRoot "_launches"
$statePath = Join-Path $launchDir "launches.json"
try {
    $arms = [string[]](ConvertTo-StringList -Value $Arms -Name "Arms")
    $NCachedList = [int[]](ConvertTo-IntList -Value $NCached -Name "NCached")
    $DeltaList = [int[]](ConvertTo-IntList -Value $Deltas -Name "Deltas")
} catch {
    Write-Output $_.Exception.Message
    exit 2
}
if ($arms.Count -lt 1 -or $NCachedList.Count -lt 1 -or $DeltaList.Count -lt 1) {
    Write-Output "REFUSED -- Arms/NCached/Deltas normalized to empty"
    exit 2
}
foreach ($nc in $NCachedList) {
    if ($nc -lt 1) {
        Write-Output "REFUSED -- each -NCached entry must be >= 1 (got $nc)"
        exit 2
    }
}
foreach ($d in $DeltaList) {
    if ($d -lt 1) {
        Write-Output "REFUSED -- each -Deltas entry must be >= 1 (got $d)"
        exit 2
    }
}
# Max delta retained for three-number summary item 2 (gpu_only:A at largest delta).
# NON_RESIDENT cells are scheduled for every delta (DEFECT_non_resident_max_delta_only fix).
$MaxDelta = [int](($DeltaList | Measure-Object -Maximum).Maximum)
# Canonical CSV strings for Orchestrate inner cmdline (never pass Object[] through).
$ArmsCsv = ($arms -join ",")
$NCachedCsv = ($NCachedList -join ",")
$DeltasCsv = ($DeltaList -join ",")
if ($CellTimeoutS -lt 1) {
    Write-Output "REFUSED -- -CellTimeoutS must be >= 1 (got $CellTimeoutS)"
    exit 2
}
if ($CanaryEveryN -lt 0) {
    Write-Output "REFUSED -- -CanaryEveryN must be >= 0 (0=off; got $CanaryEveryN)"
    exit 2
}
if ($CanaryEveryN -gt 0) {
    if ($CanaryNCached -lt 1 -or $CanaryDelta -lt 1) {
        Write-Output "REFUSED -- canary n_cached/delta must be >= 1"
        exit 2
    }
    if ($CanaryCalibrationCount -lt 2) {
        Write-Output "REFUSED -- -CanaryCalibrationCount must be >= 2 to derive early variance (got $CanaryCalibrationCount)"
        exit 2
    }
    if ($CanaryRelDriftFloor -lt 0) {
        Write-Output "REFUSED -- -CanaryRelDriftFloor must be >= 0 (got $CanaryRelDriftFloor)"
        exit 2
    }
}

try {
    $py = [System.IO.Path]::GetFullPath($PythonExe)
} catch {
    $py = $PythonExe
}

function Get-LaunchEntriesFromNode {
    param([Parameter(Mandatory = $true)]$Node)
    $out = New-Object System.Collections.Generic.List[object]
    foreach ($n in @($Node)) {
        if ($null -eq $n) { continue }
        $names = @($n.PSObject.Properties.Name)
        if ($names -contains "tag" -and $names -contains "pid" -and $names -contains "log_path") {
            $out.Add($n) | Out-Null
        } elseif ($names -contains "value") {
            foreach ($child in (Get-LaunchEntriesFromNode -Node $n.value)) { $out.Add($child) | Out-Null }
        }
    }
    return $out
}

function Get-Launches {
    if (-not (Test-Path -LiteralPath $statePath)) { return @() }
    try {
        $parsed = Get-Content -LiteralPath $statePath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        Write-Output "REFUSED -- launches.json unreadable: $statePath"
        Write-Output "  $($_.Exception.Message)"
        exit 1
    }
    # ConvertTo-ObjectArray: @($genericList) throws ArgumentException; bare .ToArray()
    # fails when PowerShell unwraps a single-item List to PSCustomObject.
    return ConvertTo-ObjectArray (Get-LaunchEntriesFromNode -Node $parsed)
}

function Save-Launches {
    param([Parameter(Mandatory = $true)][object[]]$Entries)
    New-Item -ItemType Directory -Force -Path $launchDir | Out-Null
    $json = ConvertTo-Json -InputObject @($Entries) -Depth 6
    Set-Content -LiteralPath $statePath -Value $json -Encoding UTF8
}

function Assert-Interpreter {
    if (-not (Test-Path -LiteralPath $py)) {
        Write-Output "REFUSED -- INTERPRETER_MISSING"
        Write-Output "  pinned PythonExe does not exist: $py"
        exit 2
    }
}

# Keep in sync with seam/isolation.py TIER1 / TIER2 (case-insensitive; no .exe).
# Tier 1 REFUSE -- operator-controlled. Tier 2 RECORD only -- auto-respawning shell/vendor
# (CBS + WebExperience msedgewebview2 hosts; 5 s respawn verified 2026-08-09). Available
# floor stays 7000; tier 2 does not refuse.
$script:Tier1ContendingProcessNames = @(
    "Cursor", "Code", "chrome", "msedge",
    "firefox", "brave", "slack", "Discord", "Teams", "ms-teams", "Spotify", "OUTLOOK",
    "obsidian", "docker desktop", "vmmem", "claude"
)
$script:Tier2ContendingProcessNames = @(
    "msedgewebview2", "SearchHost", "Widgets", "WorkloadsSessionHost",
    "DellOptimizer.Systray", "SupportAssistAgent", "ICPS"
)
$script:ContendingProcessNames = $script:Tier1ContendingProcessNames

function Get-ProcessesByNameList {
    param([string[]]$Names)
    $wanted = @{}
    foreach ($n in $Names) { $wanted[$n.ToLowerInvariant()] = $true }
    return @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $wanted.ContainsKey($_.ProcessName.ToLowerInvariant())
    })
}

function Get-ContendingProcesses {
    return @(Get-ProcessesByNameList -Names $script:Tier1ContendingProcessNames)
}

function Get-Tier2RecordedProcesses {
    return @(Get-ProcessesByNameList -Names $script:Tier2ContendingProcessNames)
}

function Write-ProcessGroupReport {
    param(
        [Parameter(Mandatory = $true)][object[]]$Processes,
        [string]$Prefix = "  -"
    )
    $Processes | Group-Object ProcessName | ForEach-Object {
        $privateMb = ($_.Group | Measure-Object -Property PrivateMemorySize64 -Sum).Sum / 1MB
        $pids = ($_.Group | Select-Object -ExpandProperty Id | Select-Object -First 5) -join ", "
        $more = if ($_.Count -gt 5) { ", ..." } else { "" }
        Write-Host ("{0} {1} x{2} private={3:N0} MiB (pids {4}{5})" -f `
            $Prefix, $_.Name, $_.Count, $privateMb, $pids, $more)
    }
}

function Write-ContendingReport {
    param([Parameter(Mandatory = $true)][object[]]$Contending)
    Write-Host "REFUSED -- tier-1 operator-controlled software is resident (private working set):"
    Write-ProcessGroupReport -Processes $Contending
    Write-Host ""
    Write-Host "Close them on the XPS, then relaunch over SSH (script waits pre_run_settle_s)."
    Write-Host "This script does not terminate those processes."
    Write-Host "Tier-2 shell/vendor agents (msedgewebview2, etc.) are recorded only and do not refuse."
}

function Write-Tier2RecordReport {
    param([Parameter(Mandatory = $true)][object[]]$Tier2)
    Write-Host "tier-2 (record only, do not refuse) -- auto-respawning shell/vendor:"
    Write-ProcessGroupReport -Processes $Tier2
}

function Assert-No-Contending {
    $contending = Get-ContendingProcesses
    if ($contending.Count -gt 0) {
        Write-ContendingReport -Contending $contending
        exit 1
    }
    $tier2 = Get-Tier2RecordedProcesses
    if ($tier2.Count -gt 0) {
        Write-Tier2RecordReport -Tier2 $tier2
    }
}

function Get-AvailableMBytes {
    try {
        $sample = (Get-Counter '\Memory\Available MBytes' -ErrorAction Stop).CounterSamples[0]
        return [pscustomobject]@{
            available_mb = [double]$sample.CookedValue
            method       = "Get-Counter:\\Memory\\Available MBytes"
        }
    } catch {
        return [pscustomobject]@{
            available_mb = $null
            method       = "Get-Counter_failed:$($_.Exception.Message)"
        }
    }
}

function Get-MachineDriftSnapshot {
    # Best-effort; null fields mean unreachable (do not invent).
    $avail = Get-AvailableMBytes
    $freq = $null
    $perf = $null
    $pkgC = $null
    try {
        $freq = [double](Get-Counter '\Processor Information(_Total)\Processor Frequency' -ErrorAction Stop).CounterSamples[0].CookedValue
    } catch { $freq = $null }
    try {
        $perf = [double](Get-Counter '\Processor Information(_Total)\% Processor Performance' -ErrorAction Stop).CounterSamples[0].CookedValue
    } catch { $perf = $null }
    try {
        $tz = @(Get-CimInstance -Namespace root\wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop)
        if ($tz.Count -gt 0) {
            $pkgC = [double](($tz[0].CurrentTemperature / 10.0) - 273.15)
        }
    } catch { $pkgC = $null }
    return [ordered]@{
        available_mb              = $avail.available_mb
        available_method          = $avail.method
        processor_frequency_mhz   = $freq
        processor_performance_pct = $perf
        package_temp_c            = $pkgC
        package_temp_source       = $(if ($null -ne $pkgC) { "MSAcpi_ThermalZoneTemperature" } else { "unreachable" })
        snapshot_utc              = (Get-Date).ToUniversalTime().ToString("o")
    }
}

# Get-RelativeDrift / Get-MedianDouble / Get-SinglePipelineRecord /
# Update-CanaryDriftBookkeeping live in tools/SeamPsCommon.ps1.

function Assert-PreRunAvailable {
    param(
        [double]$MinMb,
        [string]$Citation,
        [switch]$ReportOnly
    )
    $avail = Get-AvailableMBytes
    $availText = if ($null -eq $avail.available_mb) { "null" } else { "{0:N1}" -f $avail.available_mb }
    Write-Host ("Available MBytes : {0} (method={1})" -f $availText, $avail.method)
    Write-Host ("pre_run floor    : {0} MB" -f $MinMb)
    if ($Citation) { Write-Host ("citation         : {0}" -f $Citation) }
    if ($null -eq $avail.available_mb) {
        Write-Host "REFUSED -- could not read \Memory\Available MBytes; cannot enforce pre-run gate."
        if (-not $ReportOnly) { exit 2 }
        return $false
    }
    if ([double]$avail.available_mb -lt $MinMb) {
        Write-Host ("REFUSED -- Available MBytes {0:N1} < pre_run_available_mb_min {1}." -f `
            $avail.available_mb, $MinMb)
        $contending = Get-ContendingProcesses
        if ($contending.Count -gt 0) {
            Write-ContendingReport -Contending $contending
        } else {
            Write-Host "No tier-1 operator-controlled process names are resident; other residents still hold memory."
        }
        $tier2 = Get-Tier2RecordedProcesses
        if ($tier2.Count -gt 0) {
            Write-Tier2RecordReport -Tier2 $tier2
        }
        if (-not $ReportOnly) { exit 1 }
        return $false
    }
    return $true
}

function Assert-LaunchContext-Honest {
    param(
        [string]$Context,
        [switch]$OrchestrateMode,
        [switch]$WorkerMode
    )
    if ($OrchestrateMode) {
        if ($Context -eq "ssh_foreground") {
            Write-Output "REFUSED -- -Orchestrate requires launch_context=ssh_detached; ssh_foreground rejected."
            exit 1
        }
        if ($Context -ne "ssh_detached") {
            Write-Output "REFUSED -- -Orchestrate requires launch_context=ssh_detached, got $Context"
            exit 1
        }
        return
    }
    if ($WorkerMode) {
        if ($Context -ne "ssh_detached") {
            Write-Output "REFUSED -- DetachedWorker must run with launch_context=ssh_detached, got $Context"
            exit 1
        }
        return
    }
    if ($Context -eq "ssh_foreground" -or $Context -eq "ssh_detached") {
        if (-not $env:SSH_CLIENT -and -not $env:SSH_CONNECTION) {
            Write-Output "REFUSED -- LaunchContext=$Context claimed but SSH_CLIENT/SSH_CONNECTION unset."
            Write-Output "Do not mislabel a local Cursor/console session as ssh_foreground/ssh_detached."
            Write-Output "For the real matrix: -Orchestrate (ssh_detached via spawn_detached)."
            exit 1
        }
    }
}

function Get-IsolationScalar {
    param(
        [string]$Path,
        [string]$Key
    )
    $inIsolation = $false
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*isolation:\s*$') { $inIsolation = $true; continue }
        if ($inIsolation -and $line -match '^\S') { $inIsolation = $false }
        if ($inIsolation -and $line -match ("^\s*{0}:\s*(.+)$" -f [regex]::Escape($Key))) {
            $raw = $Matches[1].Trim()
            if ($raw -match '^"(.*)"\s*(#.*)?$') { return $Matches[1] }
            if ($raw -match "^'(.*)'\s*(#.*)?$") { return $Matches[1] }
            $token = ($raw -split '\s+#', 2)[0].Trim()
            if ($token -match '^(\S+)') { return $Matches[1] }
            return $token
        }
    }
    return $null
}

function Get-RecoveryScalar {
    param(
        [string]$Path,
        [string]$Key
    )
    $inRecovery = $false
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*recovery:\s*$') { $inRecovery = $true; continue }
        if ($inRecovery -and $line -match '^\S') { $inRecovery = $false }
        if ($inRecovery -and $line -match ("^\s*{0}:\s*(.+)$" -f [regex]::Escape($Key))) {
            $raw = $Matches[1].Trim()
            $token = ($raw -split '\s+#', 2)[0].Trim()
            if ($token -match '^(\S+)') { return $Matches[1] }
            return $token
        }
    }
    return $null
}

function Get-YamlScalar {
    param(
        [string]$Path,
        [string]$Key
    )
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match ("^\s*{0}:\s*(\S+)" -f [regex]::Escape($Key))) {
            return $Matches[1]
        }
    }
    return $null
}

function Write-MatrixHeartbeat {
    param(
        [Parameter(Mandatory = $true)][string]$SessionDir,
        [Parameter(Mandatory = $true)][string]$Sid,
        [string]$Phase,
        [object]$CellIndex = $null,
        [string]$Arm = $null,
        [string]$Mode = $null,
        [object]$Delta = $null,
        [object]$Repeat = $null,
        [hashtable]$Extra = $null
    )
    New-Item -ItemType Directory -Force -Path $SessionDir | Out-Null
    $hb = [ordered]@{
        session_id    = $Sid
        phase         = $Phase
        cell_index    = $CellIndex
        arm           = $Arm
        mode          = $Mode
        delta         = $Delta
        n_cached      = $null
        repeat        = $Repeat
        heartbeat_utc = (Get-Date).ToUniversalTime().ToString("o")
        pid           = $PID
    }
    if ($Extra) {
        foreach ($k in $Extra.Keys) { $hb[$k] = $Extra[$k] }
    }
    $path = Join-Path $SessionDir "heartbeat.json"
    $tmp = Join-Path $SessionDir "heartbeat.json.partial"
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($tmp, ($hb | ConvertTo-Json -Depth 4), $utf8)
    Move-Item -LiteralPath $tmp -Destination $path -Force
}

function Wait-InterCellAvailable {
    param(
        [double]$MinMb,
        [double]$SettleS,
        [double]$MaxWaitS,
        [double]$PollS = 5
    )
    # Write-Host: callers capture the boolean return; Write-Output would pollute it.
    Write-Host ("   inter-cell settle {0}s then Available >= {1} MB (max_wait={2}s)..." -f `
        $SettleS, $MinMb, $MaxWaitS)
    Start-Sleep -Seconds $SettleS
    $deadline = (Get-Date).AddSeconds($MaxWaitS)
    while ((Get-Date) -lt $deadline) {
        $avail = Get-AvailableMBytes
        if ($null -ne $avail.available_mb -and [double]$avail.available_mb -ge $MinMb) {
            Write-Host ("   Available recovered: {0:N1} MB" -f $avail.available_mb)
            return $true
        }
        Start-Sleep -Seconds $PollS
    }
    $final = Get-AvailableMBytes
    Write-Host ("WARNING: Available still {0} after max_wait; continuing (recorded)." -f $final.available_mb)
    return $false
}

function Get-CellSpecs {
    # RESIDENT and NON_RESIDENT at every -Deltas entry (one cell per arm/n_cached/mode/delta).
    # Prior design ran NON_RESIDENT only at max(-Deltas); that was a defect — see
    # derived/delta_prefill/DEFECT_non_resident_max_delta_only.md. Do not restore that rule.
    $specs = New-Object System.Collections.Generic.List[object]
    foreach ($nc in $NCachedList) {
        foreach ($arm in $arms) {
            foreach ($d in $DeltaList) {
                $specs.Add([pscustomobject]@{
                        arm = $arm; n_cached = [int]$nc; mode = "RESIDENT"; delta = [int]$d
                    }) | Out-Null
                $specs.Add([pscustomobject]@{
                        arm = $arm; n_cached = [int]$nc; mode = "NON_RESIDENT"; delta = [int]$d
                    }) | Out-Null
            }
        }
    }
    # ConvertTo-ObjectArray: @($specs) on List[object] throws ArgumentException before
    # plan write (session 1f519c47-c554-4939-a16a-63e120cfb254).
    return ConvertTo-ObjectArray $specs
}

function Invoke-DetachedSpawn {
    param(
        [Parameter(Mandatory = $true)][string]$InnerCommand,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][string]$TagName,
        [Parameter(Mandatory = $true)][string]$LaunchCtx,
        [string]$Sid = $null,
        [string]$ResultPath = $null,
        [bool]$VerifyOnly = $false
    )
    $json = & (Join-Path $root "tools\spawn_detached.ps1") `
        -CommandLine $InnerCommand -LogPath $LogPath -WorkingDirectory $root
    $info = $json | ConvertFrom-Json
    $entry = [pscustomobject]@{
        tag             = $TagName
        pid             = $info.pid
        parent_name     = $info.parent_name
        ppid            = $info.ppid
        isolation_mode  = "remote"
        launch_context  = $LaunchCtx
        session_id      = $Sid
        matrix_tag      = $Tag
        n_cached        = $NCachedCsv
        deltas          = $DeltasCsv
        arms            = $ArmsCsv
        cell_timeout_s  = $CellTimeoutS
        verify_detach   = $VerifyOnly
        launched_utc    = (Get-Date).ToUniversalTime().ToString("o")
        log_path        = $LogPath
        result_path     = $ResultPath
    }
    Save-Launches -Entries (@(Get-Launches) + $entry)
    return $info
}

function Write-ThreeNumbers {
    param([System.Collections.IEnumerable]$Cells)
    $rows = @($Cells | Where-Object { $_.classification -eq "OK" -and $null -ne $_.turn2_prefill_s })
    Write-Output ""
    Write-Output "=== THREE NUMBERS ==="

    function Median([double[]]$vals) {
        if (-not $vals -or $vals.Count -eq 0) { return $null }
        $s = @($vals | Sort-Object)
        $n = $s.Count
        if ($n % 2 -eq 1) { return $s[[int]($n / 2)] }
        return ($s[$n / 2 - 1] + $s[$n / 2]) / 2.0
    }

    foreach ($nc in $NCachedList) {
    foreach ($arm in $arms) {
        foreach ($cmpDelta in $DeltaList) {
            $dCmp = [int]$cmpDelta
            $res = @($rows | Where-Object {
                    $_.arm -eq $arm -and $_.mode -eq "RESIDENT" -and [int]$_.delta -eq $dCmp -and
                    ([int]$_.n_cached -eq [int]$nc)
                } | ForEach-Object { [double]$_.turn2_prefill_s })
            $non = @($rows | Where-Object {
                    $_.arm -eq $arm -and $_.mode -eq "NON_RESIDENT" -and [int]$_.delta -eq $dCmp -and
                    ([int]$_.n_cached -eq [int]$nc)
                } | ForEach-Object { [double]$_.turn2_prefill_s })
            $medR = Median $res
            $medN = Median $non
            Write-Output ("1. arm={0} n_cached={1} delta={2} turn2_prefill_s RESIDENT median={3} (n={4}) vs NON_RESIDENT median={5} (n={6})" -f `
                $arm, $nc, $dCmp,
                $(if ($null -eq $medR) { "null" } else { "{0:N3}" -f $medR }),
                $res.Count,
                $(if ($null -eq $medN) { "null" } else { "{0:N3}" -f $medN }),
                $non.Count)
            if ($null -ne $medR -and $null -ne $medN -and $medN -ne 0) {
                $ratio = $medR / $medN
                $falsified = $ratio -ge 0.5
                Write-Output ("   ratio RESIDENT/NON_RESIDENT={0:N3} falsified_kv_not_retained={1}" -f $ratio, $falsified)
            }
        }
    }
    }

    $cmpDelta = [int]$MaxDelta
    $aRes = @($rows | Where-Object { $_.arm -eq "A" -and $_.mode -eq "RESIDENT" -and [int]$_.delta -eq $cmpDelta } |
        ForEach-Object { [double]$_.turn2_prefill_s })
    $gRes = @($rows | Where-Object { $_.arm -eq "gpu_only" -and $_.mode -eq "RESIDENT" -and [int]$_.delta -eq $cmpDelta } |
        ForEach-Object { [double]$_.turn2_prefill_s })
    $medA = Median $aRes
    $medG = Median $gRes
    Write-Output ("2. turn2_prefill_s RESIDENT delta={0} gpu_only:A = {1}" -f `
        $cmpDelta,
        $(if ($null -eq $medA -or $null -eq $medG -or $medA -eq 0) { "null" } else { "{0:N3}" -f ($medG / $medA) }))
    Write-Output ("   (gpu_only median={0} A median={1})" -f `
        $(if ($null -eq $medG) { "null" } else { "{0:N3}" -f $medG }),
        $(if ($null -eq $medA) { "null" } else { "{0:N3}" -f $medA }))

    foreach ($nc in $NCachedList) {
    foreach ($arm in $arms) {
        $parts = New-Object System.Collections.Generic.List[string]
        $medByDelta = @{}
        foreach ($d in $DeltaList) {
            $vals = @($rows | Where-Object {
                    $_.arm -eq $arm -and $_.mode -eq "RESIDENT" -and [int]$_.delta -eq [int]$d -and
                    ([int]$_.n_cached -eq [int]$nc)
                } | ForEach-Object { [double]$_.turn2_prefill_s })
            $med = Median $vals
            $medByDelta[[int]$d] = $med
            $parts.Add(("delta{0} median={1}" -f $d, $(if ($null -eq $med) { "null" } else { "{0:N3}" -f $med }))) | Out-Null
        }
        Write-Output ("3. arm={0} n_cached={1} RESIDENT turn2_prefill_s {2}" -f $arm, $nc, ($parts -join " "))
        if ($DeltaList.Count -ge 2) {
            $dLo = [int]($DeltaList | Measure-Object -Minimum).Minimum
            $dHi = [int]($DeltaList | Measure-Object -Maximum).Maximum
            $mLo = $medByDelta[$dLo]
            $mHi = $medByDelta[$dHi]
            if ($null -ne $mLo -and $null -ne $mHi -and $mLo -gt 0) {
                $scale = $mHi / $mLo
                $ideal = $dHi / [double]$dLo
                Write-Output ("   scale {0}/{1}={2:N3} (delta-like~{3:N1}; n_cached-dominated~1)" -f `
                    $dHi, $dLo, $scale, $ideal)
            }
        }
    }
    }
}

# ----------------------------------------------------------------------------------------------
if ($Status) {
    # Fixed pattern: job timeout, heartbeat-dir discovery, bounded FileShare.ReadWrite reads,
    # no Select-String against the live spawn log.
    $statusJob = Start-Job -ScriptBlock {
        param($root, $statePath, $sessionRoot)
        $ErrorActionPreference = "Stop"
        . (Join-Path $root "tools\SeamPsCommon.ps1")

        function Get-LaunchEntriesFromNode {
            param($Node)
            $out = New-Object System.Collections.Generic.List[object]
            foreach ($n in @($Node)) {
                if ($null -eq $n) { continue }
                $names = @($n.PSObject.Properties.Name)
                if ($names -contains "tag" -and $names -contains "pid" -and $names -contains "log_path") {
                    $out.Add($n) | Out-Null
                } elseif ($names -contains "value") {
                    foreach ($child in (Get-LaunchEntriesFromNode -Node $n.value)) { $out.Add($child) | Out-Null }
                }
            }
            return $out
        }

        function Read-SharedTextFile {
            param([string]$Path, [int]$MaxBytes = 65536, [switch]$Tail)
            if (-not (Test-Path -LiteralPath $Path)) { return $null }
            $fs = $null
            try {
                $fs = [System.IO.File]::Open(
                    $Path,
                    [System.IO.FileMode]::Open,
                    [System.IO.FileAccess]::Read,
                    [System.IO.FileShare]::ReadWrite
                )
                if ($Tail -and $fs.Length -gt $MaxBytes) {
                    $fs.Seek(-[int64]$MaxBytes, [System.IO.SeekOrigin]::End) | Out-Null
                }
                $toRead = [int][Math]::Min([int64]$MaxBytes, $fs.Length - $fs.Position)
                if (-not $Tail) {
                    $toRead = [int][Math]::Min([int64]$MaxBytes, $fs.Length)
                    $fs.Seek(0, [System.IO.SeekOrigin]::Begin) | Out-Null
                }
                $buf = New-Object byte[] $toRead
                $read = $fs.Read($buf, 0, $toRead)
                return [System.Text.Encoding]::UTF8.GetString($buf, 0, $read)
            } catch {
                return $null
            } finally {
                if ($fs) { $fs.Dispose() }
            }
        }

        $lines = New-Object System.Collections.Generic.List[string]
        if (-not (Test-Path -LiteralPath $statePath)) {
            $lines.Add("no delta_prefill run has been launched") | Out-Null
            return @{ exit = 1; lines = $lines }
        }
        $parsed = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $launches = ConvertTo-ObjectArray (Get-LaunchEntriesFromNode -Node $parsed)
        if ($launches.Count -eq 0) {
            $lines.Add("no delta_prefill run has been launched") | Out-Null
            return @{ exit = 1; lines = $lines }
        }
        $last = $launches[-1]
        $alive = $null -ne (Get-Process -Id ([int]$last.pid) -ErrorAction SilentlyContinue)
        $lines.Add("tag            : $($last.tag)") | Out-Null
        $lines.Add("launched       : $($last.launched_utc)") | Out-Null
        $lines.Add("declared       : isolation_mode=$($last.isolation_mode) launch_context=$($last.launch_context)") | Out-Null
        if ($last.matrix_tag) { $lines.Add("matrix_tag     : $($last.matrix_tag)") | Out-Null }
        if ($last.n_cached) { $lines.Add("n_cached       : $($last.n_cached)") | Out-Null }
        if ($last.verify_detach) { $lines.Add("verify_detach  : True") | Out-Null }
        $lines.Add("process        : pid $($last.pid), alive=$alive") | Out-Null
        if ($last.parent_name) {
            $lines.Add("parent         : $($last.parent_name) (ppid $($last.ppid))") | Out-Null
        }

        $sid = $last.session_id
        if (-not $sid) {
            $newest = Get-ChildItem $sessionRoot -Directory -ErrorAction SilentlyContinue |
                      Where-Object { $_.Name -match '^[0-9a-f-]{36}$' } |
                      Sort-Object LastWriteTime -Descending |
                      Select-Object -First 1
            if ($newest) { $sid = $newest.Name }
        }
        if (-not $sid -and $last.log_path) {
            $head = Read-SharedTextFile -Path ([string]$last.log_path) -MaxBytes 65536
            if ($head -match '"session_id"\s*:\s*"([0-9a-f-]{36})"') {
                $sid = $Matches[1]
            } elseif ($head -match 'session_id\s*:\s*([0-9a-f-]{36})') {
                $sid = $Matches[1]
            }
        }
        if ($sid) { $lines.Add("session_id     : $sid") | Out-Null }
        else { $lines.Add("session_id     : (not yet known)") | Out-Null }

        if ($sid) {
            $hb = Join-Path $sessionRoot ("{0}\heartbeat.json" -f $sid)
            $plan = Join-Path $sessionRoot ("{0}\plan.json" -f $sid)
            $hbText = Read-SharedTextFile -Path $hb -MaxBytes 16384
            if ($hbText) {
                $lines.Add("") | Out-Null
                $lines.Add("--- heartbeat ---") | Out-Null
                $lines.Add($hbText.TrimEnd()) | Out-Null
            } elseif (Test-Path -LiteralPath $plan) {
                $lines.Add("plan exists; heartbeat not yet readable") | Out-Null
            }
            $planText = Read-SharedTextFile -Path $plan -MaxBytes 65536
            if ($planText -and $planText -match '"status"\s*:\s*"(complete|verify_detach_complete|FAIL|FAIL_CANARY_DRIFT)"') {
                $lines.Add("") | Out-Null
                $lines.Add("state          : COMPLETE ($($Matches[1]))") | Out-Null
                return @{ exit = 0; lines = $lines }
            }
        }

        if ($last.result_path) {
            $launchResult = Read-SharedTextFile -Path ([string]$last.result_path) -MaxBytes 65536
            if ($launchResult) {
                $lines.Add("state          : COMPLETE") | Out-Null
                $lines.Add("") | Out-Null
                $lines.Add($launchResult.TrimEnd()) | Out-Null
                return @{ exit = 0; lines = $lines }
            }
        }
        if ($alive) {
            $lines.Add("state          : RUNNING -- do not open a session on this machine") | Out-Null
        } else {
            $lines.Add("state          : ENDED WITHOUT A RESULT -- the log below is the evidence") | Out-Null
        }
        $lines.Add("") | Out-Null
        $lines.Add("--- last ~8 KiB of $($last.log_path) ---") | Out-Null
        if ($last.log_path) {
            $tail = Read-SharedTextFile -Path ([string]$last.log_path) -MaxBytes 8192 -Tail
            if ($null -eq $tail) {
                $lines.Add("(log unreadable with FileShare.ReadWrite; not waiting on runner lock)") | Out-Null
            } else {
                $tailLines = $tail -split "`r?`n"
                if ($tailLines.Count -gt 1) { $tailLines = $tailLines[1..($tailLines.Count - 1)] }
                foreach ($tl in $tailLines) { $lines.Add($tl) | Out-Null }
            }
        }
        return @{ exit = $(if ($alive) { 0 } else { 1 }); lines = $lines }
    } -ArgumentList $root, $statePath, $sessionRoot

    $finished = Wait-Job -Job $statusJob -Timeout 15
    if (-not $finished) {
        Stop-Job $statusJob -ErrorAction SilentlyContinue
        Remove-Job $statusJob -Force -ErrorAction SilentlyContinue
        Write-Output "REFUSED -- -Status timed out after 15s (non-blocking by design)"
        Write-Output "  Prefer: Get-Content derived/delta_prefill/<session_id>/heartbeat.json"
        Write-Output "  Do not Select-String / Get-Content -Wait the live launch log while the runner holds it."
        exit 2
    }
    $payload = Receive-Job $statusJob
    Remove-Job $statusJob -Force -ErrorAction SilentlyContinue
    foreach ($line in @($payload.lines)) { Write-Output $line }
    exit ([int]$payload.exit)
}

# ----------------------------------------------------------------------------------------------
Assert-Interpreter

if ($VerifyDetach) {
    $launchContext = "ssh_detached"
    New-Item -ItemType Directory -Force -Path $launchDir | Out-Null
    $sid = [guid]::NewGuid().ToString()
    $tagLaunch = "delta_prefill_verify_" + (Get-Date -Format "yyyyMMdd_HHmmss")
    $log = Join-Path $launchDir "$tagLaunch.log"
    $resultPath = Join-Path $launchDir "$tagLaunch.result.json"
    $self = Join-Path $root "tools\run_delta_prefill_matrix.ps1"
    $inner = 'set SEAM_LAUNCH_CONTEXT=ssh_detached' +
             '&& powershell -NoProfile -File "' + $self + '"' +
             ' -DetachedWorker -HeartbeatOnly -HeartbeatSeconds 30' +
             ' -LaunchContext ssh_detached -SessionId ' + $sid +
             ' -Tag "' + $Tag + '"' +
             ' -PythonExe "' + $py + '"'
    $info = Invoke-DetachedSpawn -InnerCommand $inner -LogPath $log -TagName $tagLaunch `
        -LaunchCtx $launchContext -Sid $sid -ResultPath $resultPath -VerifyOnly $true
    Write-Output "launched detached delta_prefill VERIFY (heartbeat-only)"
    Write-Output "  tag            : $tagLaunch"
    Write-Output "  pid            : $($info.pid) (parent $($info.parent_name) -- not this session)"
    Write-Output "  launch_context : $launchContext"
    Write-Output "  session_id     : $sid"
    Write-Output "  log            : $log"
    Write-Output ""
    Write-Output "Poll with:"
    Write-Output "  powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Status"
    exit 0
}

if ($DryRunGate) {
    $preRunMin = Get-IsolationScalar -Path $cfgPath -Key "pre_run_available_mb_min"
    $preRunCite = Get-IsolationScalar -Path $cfgPath -Key "pre_run_available_mb_min_citation"
    if (-not $preRunMin) {
        Write-Output "REFUSED -- isolation.pre_run_available_mb_min missing from $cfgPath"
        exit 2
    }
    Write-Output "dry-run cleanliness gate (no matrix)"
    Write-Output ("  arms             : {0}" -f ($arms -join ","))
    Write-Output ("  n_cached         : {0}" -f ($NCachedList -join ","))
    Write-Output ("  deltas           : {0}" -f ($DeltaList -join ","))
    Write-Output ("  max_delta        : {0} (summary item 2; NON_RESIDENT runs every -Deltas entry)" -f $MaxDelta)
    Write-Output ("  cell_timeout_s   : {0}" -f $CellTimeoutS)
    Write-Output ("  cell_timeout_derivation: session d5c98342 OK max elapsed_s=616.8; 2x=1234; rounded to 1500")
    Write-Output ("  cells/round      : {0}" -f (Get-CellSpecs).Count)
    Write-Output ("  canary_every_n   : {0}" -f $CanaryEveryN)
    if ($CanaryEveryN -gt 0) {
        Write-Output ("  canary_config    : arm={0} nc={1} d={2} mode={3} calib={4} floor={5}" -f `
            $CanaryArm, $CanaryNCached, $CanaryDelta, $CanaryMode, $CanaryCalibrationCount, $CanaryRelDriftFloor)
    }
    Write-Output ("  tier1 refuse names: {0}" -f ($script:Tier1ContendingProcessNames -join ", "))
    Write-Output ("  tier2 record names: {0}" -f ($script:Tier2ContendingProcessNames -join ", "))
    $contending = Get-ContendingProcesses
    if ($contending.Count -gt 0) {
        Write-ContendingReport -Contending $contending
    } else {
        Write-Output "tier1 refuse list: none resident"
    }
    $tier2 = Get-Tier2RecordedProcesses
    if ($tier2.Count -gt 0) {
        Write-Tier2RecordReport -Tier2 $tier2
    } else {
        Write-Output "tier2 record list: none resident"
    }
    $ok = Assert-PreRunAvailable -MinMb ([double]$preRunMin) -Citation $preRunCite -ReportOnly
    if ($contending.Count -gt 0 -or -not $ok) {
        Write-Output "dry-run FAIL -- close tier-1 software / reclaim memory; no matrix started"
        exit 1
    }
    Write-Output "dry-run PASS -- Available above floor and no tier-1 residents (tier-2 recorded only)"
    exit 0
}

if ($Orchestrate) {
    if ($PSBoundParameters.ContainsKey("LaunchContext") -and $LaunchContext -ne "ssh_detached") {
        Assert-LaunchContext-Honest -Context $LaunchContext -OrchestrateMode
    }
    $launchContext = "ssh_detached"
    Assert-LaunchContext-Honest -Context $launchContext -OrchestrateMode
    Assert-No-Contending
    $preRunMinOrch = Get-IsolationScalar -Path $cfgPath -Key "pre_run_available_mb_min"
    $preRunCiteOrch = Get-IsolationScalar -Path $cfgPath -Key "pre_run_available_mb_min_citation"
    if (-not $preRunMinOrch) {
        Write-Output "REFUSED -- isolation.pre_run_available_mb_min missing from $cfgPath"
        exit 2
    }
    Assert-PreRunAvailable -MinMb ([double]$preRunMinOrch) -Citation $preRunCiteOrch | Out-Null

    New-Item -ItemType Directory -Force -Path $launchDir | Out-Null
    $sid = [guid]::NewGuid().ToString()
    $tagLaunch = "delta_prefill_" + (Get-Date -Format "yyyyMMdd_HHmmss")
    $log = Join-Path $launchDir "$tagLaunch.log"
    $resultPath = Join-Path $launchDir "$tagLaunch.result.json"
    $self = Join-Path $root "tools\run_delta_prefill_matrix.ps1"
    # Always quote CSV scalars — never splice Object[] into the cmd line.
    $inner = 'set SEAM_LAUNCH_CONTEXT=ssh_detached' +
             '&& powershell -NoProfile -File "' + $self + '"' +
             ' -DetachedWorker -LaunchContext ssh_detached' +
             ' -SessionId ' + $sid +
             ' -Tag "' + $Tag + '"' +
             ' -Arms "' + $ArmsCsv + '"' +
             ' -NCached "' + $NCachedCsv + '"' +
             ' -Deltas "' + $DeltasCsv + '"' +
             ' -CellTimeoutS ' + $CellTimeoutS +
             ' -Repeats ' + $Repeats +
             ' -CanaryEveryN ' + $CanaryEveryN +
             ' -CanaryArm "' + $CanaryArm + '"' +
             ' -CanaryNCached ' + $CanaryNCached +
             ' -CanaryDelta ' + $CanaryDelta +
             ' -CanaryMode ' + $CanaryMode +
             ' -CanaryCalibrationCount ' + $CanaryCalibrationCount +
             ' -CanaryRelDriftFloor ' + $CanaryRelDriftFloor +
             ' -PythonExe "' + $py + '"'
    $info = Invoke-DetachedSpawn -InnerCommand $inner -LogPath $log -TagName $tagLaunch `
        -LaunchCtx $launchContext -Sid $sid -ResultPath $resultPath -VerifyOnly $false

    Write-Output "launched detached delta_prefill matrix"
    Write-Output "  tag            : $tagLaunch"
    Write-Output "  pid            : $($info.pid) (parent $($info.parent_name) -- not this session)"
    Write-Output "  isolation_mode : remote"
    Write-Output "  launch_context : $launchContext"
    Write-Output "  session_id     : $sid"
    Write-Output "  matrix_tag     : $Tag"
    Write-Output "  arms           : $($arms -join ',')"
    Write-Output "  n_cached       : $($NCachedList -join ',')"
    Write-Output "  deltas         : $($DeltaList -join ',')"
    Write-Output "  max_delta      : $MaxDelta"
    Write-Output "  cell_timeout_s : $CellTimeoutS"
    Write-Output "  repeats        : $Repeats"
    Write-Output "  canary_every_n : $CanaryEveryN"
    if ($CanaryEveryN -gt 0) {
        Write-Output ("  canary         : {0} nc={1} d={2} {3} calib={4} floor={5}" -f `
            $CanaryArm, $CanaryNCached, $CanaryDelta, $CanaryMode, $CanaryCalibrationCount, $CanaryRelDriftFloor)
    }
    Write-Output "  log            : $log"
    Write-Output ""
    Write-Output "Close this session. Do not touch the XPS. Poll with:"
    Write-Output "  powershell -NoProfile -File tools/run_delta_prefill_matrix.ps1 -Status"
    Write-Output ""
    Write-Output "Heartbeat:"
    Write-Output ("  derived/delta_prefill/{0}/heartbeat.json" -f $sid)
    exit 0
}

# ----------------------------------------------------------------------------------------------
# Worker / foreground run path
if ($DetachedWorker) {
    Assert-LaunchContext-Honest -Context $LaunchContext -WorkerMode
    if (-not $SessionId) {
        Write-Output "REFUSED -- -DetachedWorker requires -SessionId"
        exit 1
    }
} else {
    Assert-No-Contending
    Assert-LaunchContext-Honest -Context $LaunchContext
}

$sessionDir = $null
if ($SessionId) {
    $sessionDir = Join-Path $sessionRoot $SessionId
    New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null
    Write-Output ("session_id     : {0}" -f $SessionId)
}

if ($HeartbeatOnly) {
    if (-not $sessionDir) {
        Write-Output "REFUSED -- -HeartbeatOnly requires -SessionId"
        exit 1
    }
    $deadline = (Get-Date).AddSeconds([Math]::Max(5, $HeartbeatSeconds))
    $tick = 0
    Write-MatrixHeartbeat -SessionDir $sessionDir -Sid $SessionId -Phase "verify_detach_start" `
        -Extra @{ tick = $tick; heartbeat_only = $true }
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        $tick++
        Write-MatrixHeartbeat -SessionDir $sessionDir -Sid $SessionId -Phase "verify_detach" `
            -Extra @{ tick = $tick; heartbeat_only = $true }
    }
    Write-MatrixHeartbeat -SessionDir $sessionDir -Sid $SessionId -Phase "verify_detach_complete" `
        -Extra @{ tick = $tick; heartbeat_only = $true }
    $plan = [ordered]@{
        session_id     = $SessionId
        tag            = $Tag
        launch_context = $LaunchContext
        status         = "verify_detach_complete"
        ticks          = $tick
        ended_utc      = (Get-Date).ToUniversalTime().ToString("o")
    }
    $plan | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $sessionDir "plan.json") -Encoding utf8
    $plan | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $sessionDir "result.json") -Encoding utf8
    Write-Output "verify_detach complete ticks=$tick"
    exit 0
}

$preRunSettle = Get-IsolationScalar -Path $cfgPath -Key "pre_run_settle_s"
if (-not $preRunSettle) { $preRunSettle = "300" }
$preRunAvailableMin = Get-IsolationScalar -Path $cfgPath -Key "pre_run_available_mb_min"
$preRunAvailableCite = Get-IsolationScalar -Path $cfgPath -Key "pre_run_available_mb_min_citation"
if (-not $preRunAvailableMin) {
    Write-Output "REFUSED -- isolation.pre_run_available_mb_min missing from $cfgPath"
    exit 2
}
$recoverySettle = Get-RecoveryScalar -Path $cfgPath -Key "settle_s"
if (-not $recoverySettle) { $recoverySettle = "20" }
$recoveryMaxWait = Get-RecoveryScalar -Path $cfgPath -Key "max_wait_s"
if (-not $recoveryMaxWait) { $recoveryMaxWait = "420" }

$baseSeed = Get-YamlScalar -Path $cfgPath -Key "randomization_seed"
if (-not $baseSeed) { $baseSeed = "20260805" }

New-Item -ItemType Directory -Force -Path $sessionRoot | Out-Null
$planPath = if ($sessionDir) {
    Join-Path $sessionDir "plan.json"
} else {
    Join-Path $sessionRoot "${Tag}_plan.json"
}

$cellSpecs = Get-CellSpecs
$canaryEnabled = ($CanaryEveryN -gt 0)
$canaryNDerivation = $null
if ($canaryEnabled) {
    $canaryNDerivation = (
        "N=CanaryEveryN from measured thermal onset in session 7f569929-4484-4af7-8231-5b535526f653 " +
        "(dispatch_o_u8): last-good nc=8000 RESIDENT turn1_prefill_s=6.993 at 2026-08-12T03:15:35Z " +
        "-> first-bad turn1=33.958 at 03:26:32Z (delta_t=657s). Mean cell wall from DISPATCH_O_TIME_ESTIMATE " +
        "4929s/96cells=51.34s -> cells_in_onset=657/51.34~=12.8. N=floor(cells_in_onset)=12 so >=1 canary " +
        "falls inside the observed onset window. Not a round number chosen for convenience."
    )
}
$plan = [ordered]@{
    tag                               = $Tag
    session_id                        = $SessionId
    launch_context                    = $LaunchContext
    kind                              = "delta_prefill_matrix"
    arms                              = $arms
    n_cached                          = @($NCachedList | ForEach-Object { [int]$_ })
    deltas                            = @($DeltaList | ForEach-Object { [int]$_ })
    max_delta                         = [int]$MaxDelta
    non_resident_delta_rule           = "every -Deltas entry (paired with RESIDENT); see DEFECT_non_resident_max_delta_only.md"
    cell_timeout_s                    = [int]$CellTimeoutS
    cell_timeout_derivation           = (
        "session d5c98342-a0b2-41a9-b6e2-93ac7a39c3ba: OK max elapsed_s=616.8; " +
        "2x=1234; rounded up to 1500. Hung cell gpu_only RESIDENT d500 r1 elapsed_s=2856.5 " +
        "(CL_OUT_OF_RESOURCES / oneDNN errcode -5 / post-record spin / operator kill exit=-1). " +
        "generation.timeout_s=1800 bounds only generate() inside the child."
    )
    repeats                           = $Repeats
    cell_specs_per_round              = @(
        $cellSpecs | ForEach-Object {
            [ordered]@{
                arm = $_.arm; n_cached = [int]$_.n_cached; mode = $_.mode; delta = [int]$_.delta
            }
        }
    )
    cells_per_round                   = $cellSpecs.Count
    canary                            = [ordered]@{
        enabled              = $canaryEnabled
        every_n_matrix_cells = [int]$CanaryEveryN
        arm                  = $CanaryArm
        n_cached             = [int]$CanaryNCached
        delta                = [int]$CanaryDelta
        mode                 = $CanaryMode
        calibration_count    = [int]$CanaryCalibrationCount
        rel_drift_floor      = [double]$CanaryRelDriftFloor
        n_derivation         = $canaryNDerivation
        threshold_derivation = $(if ($canaryEnabled) {
            "After CanaryCalibrationCount successful canaries: ref_t1=median(turn1_prefill_s), " +
            "ref_t2=median(turn2_prefill_s). early_max_t1=max_i |t1_i-ref_t1|/ref_t1 (same for t2). " +
            "threshold_t1=max(2*early_max_t1, CanaryRelDriftFloor); same for t2. " +
            "2x early envelope = allow as much additional deviation as already observed in calibration; " +
            "floor=0.05 matches C2f canary_gate margin_above_idle_p95 spirit when early_max~=0. " +
            "Gate arms only after calibration. Abort status=FAIL_CANARY_DRIFT if either turn exceeds threshold. " +
            "Threshold is NOT a pre-chosen round number (e.g. not 2.0x or 5x)."
        } else { $null })
    }
    pre_run_settle_s                  = [double]$preRunSettle
    inter_cell_settle_s               = [double]$recoverySettle
    inter_cell_settle_source          = "recovery.settle_s + poll Available to pre_run floor"
    inter_cell_max_wait_s             = [double]$recoveryMaxWait
    pre_run_available_mb_min          = [double]$preRunAvailableMin
    pre_run_available_mb_min_citation = $preRunAvailableCite
    randomization_seed                = [int]$baseSeed
    started_utc                       = (Get-Date).ToUniversalTime().ToString("o")
    environment_launch                = Get-MachineDriftSnapshot
    ssh_client                        = $env:SSH_CLIENT
    ssh_connection                    = $env:SSH_CONNECTION
    seam_launch_context_env           = $env:SEAM_LAUNCH_CONTEXT
    detached_worker                   = [bool]$DetachedWorker
    cells                             = @()
    canaries                          = @()
    status                            = "running"
}
$plan | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $planPath -Encoding utf8

if ($sessionDir) {
    Write-MatrixHeartbeat -SessionDir $sessionDir -Sid $SessionId -Phase "starting" `
        -Extra @{ pre_run_settle_s = [double]$preRunSettle }
}

Write-Output "delta_prefill matrix"
Write-Output "  launch_context : $LaunchContext"
Write-Output "  tag            : $Tag"
Write-Output "  arms           : $($arms -join ', ')"
Write-Output "  n_cached       : $($NCachedList -join ',')"
Write-Output "  deltas         : $($DeltaList -join ',')"
Write-Output "  max_delta      : $MaxDelta"
Write-Output "  cell_timeout_s : $CellTimeoutS"
Write-Output "  cells/round    : $($cellSpecs.Count) (RESIDENT + NON_RESIDENT x every delta x arms x n_cached)"
Write-Output "  repeats        : $Repeats"
Write-Output "  canary_every_n : $CanaryEveryN"
if ($canaryEnabled) {
    Write-Output ("  canary         : {0} nc={1} d={2} {3} calib={4} floor={5}" -f `
        $CanaryArm, $CanaryNCached, $CanaryDelta, $CanaryMode, $CanaryCalibrationCount, $CanaryRelDriftFloor)
}
Write-Output "  pre_run_settle : $preRunSettle s"
Write-Output "  inter_cell     : recovery.settle_s=$recoverySettle + Available>=$preRunAvailableMin"
Write-Output "  plan           : $planPath"

Assert-No-Contending

if (-not $SkipSettle) {
    Write-Output ""
    Write-Output "Waiting pre_run_settle_s=$preRunSettle (isolation after interactive software closed)..."
    if ($sessionDir) {
        Write-MatrixHeartbeat -SessionDir $sessionDir -Sid $SessionId -Phase "pre_run_settle" `
            -Extra @{ pre_run_settle_s = [double]$preRunSettle }
    }
    Start-Sleep -Seconds ([double]$preRunSettle)
} else {
    Write-Output "WARNING: -SkipSettle set; pre_run_settle skipped (diagnostic only)."
}

Write-Output ""
Write-Output "Pre-run Available gate (before first cell):"
Assert-PreRunAvailable -MinMb ([double]$preRunAvailableMin) -Citation $preRunAvailableCite | Out-Null
Assert-No-Contending

$cellRecords = New-Object System.Collections.Generic.List[object]
$canaryRecords = New-Object System.Collections.Generic.List[object]
$cellIndex = 0
$matrixCellsSinceCanary = 0
$abortReason = $null
$canaryGate = [ordered]@{
    armed                 = $false
    calibration_complete  = $false
    ref_turn1_prefill_s   = $null
    ref_turn2_prefill_s   = $null
    early_max_rel_t1      = $null
    early_max_rel_t2      = $null
    threshold_t1          = $null
    threshold_t2          = $null
    derivation_applied    = $null
}

function Invoke-OneDeltaCell {
    param(
        [Parameter(Mandatory = $true)][string]$Arm,
        [Parameter(Mandatory = $true)][string]$Mode,
        [Parameter(Mandatory = $true)][int]$NCached,
        [Parameter(Mandatory = $true)][int]$Delta,
        [Parameter(Mandatory = $true)][int]$Repeat,
        [object]$Seed = $null,
        [Parameter(Mandatory = $true)][bool]$IsCanary,
        [object]$CanaryIndex = $null,
        [object]$AfterMatrixCellIndex = $null
    )
    $started = (Get-Date).ToUniversalTime().ToString("o")
    $label = if ($IsCanary) { "CANARY" } else { "cell" }
    # Write-Host: callers capture the OrderedDictionary return. Write-Output here made
    # `$rec = Invoke-OneDeltaCell` an Object[3]; `$rec["rel_drift_t1"]` then threw
    # InvalidCastFromStringToInteger (DISPATCH P CANARY0, 2026-08-12).
    Write-Host ("-- {0} arm={1} n_cached={2} mode={3} delta={4} r={5} @ {6}" -f `
        $label, $Arm, $NCached, $Mode, $Delta, $Repeat, $started)
    if ($sessionDir) {
        $phase = if ($IsCanary) { "canary" } else { "cell" }
        Write-MatrixHeartbeat -SessionDir $sessionDir -Sid $SessionId -Phase $phase `
            -CellIndex $cellIndex -Arm $Arm -Mode $Mode -Delta $Delta -Repeat $Repeat `
            -Extra @{
                seed                   = $Seed
                n_cached               = $NCached
                is_canary              = $IsCanary
                canary_index           = $CanaryIndex
                after_matrix_cell_index = $AfterMatrixCellIndex
            }
    }

    if ($IsCanary) {
        $artifactName = "{0}_{1}_CANARY{2}_arm{3}_{4}_nc{5}_d{6}.json" -f `
            $Tag, $LaunchContext, $CanaryIndex, $Arm, $Mode, $NCached, $Delta
    } else {
        $artifactName = "{0}_{1}_arm{2}_{3}_nc{4}_d{5}_r{6}.json" -f `
            $Tag, $LaunchContext, $Arm, $Mode, $NCached, $Delta, $Repeat
    }
    $artifactPath = Join-Path $sessionRoot $artifactName
    if ($sessionDir) {
        $artifactPath = Join-Path $sessionDir $artifactName
    }

    $childArgs = @(
        "-u", $smokePy,
        "--launch-context", $LaunchContext,
        "--arm", $Arm,
        "--mode", $Mode,
        "--n-cached", "$NCached",
        "--delta", "$Delta",
        "--max-new-tokens", "64",
        "--repeat", "$Repeat",
        "--tag", $Tag,
        "--out", $artifactPath
    )
    $child = Invoke-SeamChildProcess -FilePath $py -ArgumentList $childArgs `
        -TimeoutSeconds $CellTimeoutS -WorkingDirectory $root
    $exit = [int]$child.exit_code
    $timedOut = [bool]$child.timed_out
    $elapsedS = [double]$child.elapsed_s

    $cls = $null
    $t1 = $null
    $t2 = $null
    $d1 = $null
    $d2 = $null
    $peak1 = $null
    $peak2 = $null
    $retained = $null
    $envStart = $null
    $envPeak = $null
    $err = $null
    $obj = $null
    $kvReadback = $null
    if (Test-Path -LiteralPath $artifactPath) {
        try {
            $obj = Get-Content -LiteralPath $artifactPath -Raw | ConvertFrom-Json
            $cls = $obj.classification
            $err = $obj.execute_error
            if (-not $err) { $err = $obj.compile_error }
            if ($obj.turn1) {
                $t1 = $obj.turn1.prefill_s
                $d1 = $obj.turn1.decode_tok_s
                $peak1 = $obj.turn1.peak_ws_bytes
            }
            if ($obj.turn2) {
                $t2 = $obj.turn2.prefill_s
                $d2 = $obj.turn2.decode_tok_s
                $peak2 = $obj.turn2.peak_ws_bytes
            }
            if ($obj.cache_retention) {
                $retained = $obj.cache_retention.cache_retained
            }
            $envStart = $obj.environment_start
            $envPeak = $obj.environment_peak
            if ($obj.kv_cache_precision_readback) {
                $kvReadback = $obj.kv_cache_precision_readback
            }
        } catch {
            $cls = "PARSE_ERROR"
            $err = "$_"
        }
    } else {
        $cls = "MISSING_ARTIFACT"
    }
    if ($timedOut) {
        $cls = "TIMEOUT"
        $timeoutNote = ("parent cell wall timeout after {0}s (CellTimeoutS={1}; child pid={2})" -f `
            $elapsedS, $CellTimeoutS, $child.pid)
        if ($err) { $err = "$timeoutNote | prior: $err" } else { $err = $timeoutNote }
    }

    $rec = [ordered]@{
        cell_index       = $cellIndex
        is_canary        = $IsCanary
        canary_index     = $CanaryIndex
        after_matrix_cell_index = $AfterMatrixCellIndex
        arm              = $Arm
        mode             = $Mode
        n_cached         = $NCached
        delta            = $Delta
        repeat           = $Repeat
        seed             = $Seed
        started_utc      = $started
        ended_utc        = (Get-Date).ToUniversalTime().ToString("o")
        exit_code        = $exit
        elapsed_s        = $elapsedS
        timed_out        = $timedOut
        cell_timeout_s   = [int]$CellTimeoutS
        kv_cache_precision_readback = $kvReadback
        classification   = $cls
        turn1_prefill_s  = $t1
        turn2_prefill_s  = $t2
        turn1_decode_tok_s = $d1
        turn2_decode_tok_s = $d2
        peak_ws_turn1    = $peak1
        peak_ws_turn2    = $peak2
        cache_retained   = $retained
        environment_start = $envStart
        environment_peak  = $envPeak
        error            = $err
        artifact         = $artifactPath
    }
    Write-Host ("   classification={0} t1_prefill={1} t2_prefill={2} retained={3} peak_ws=({4}->{5}) exit={6} elapsed_s={7}{8}" -f `
        $cls, $t1, $t2, $retained, $peak1, $peak2, $exit, $elapsedS, `
        $(if ($timedOut) { " TIMEOUT" } else { "" }))

    if ($sessionDir) {
        Write-MatrixHeartbeat -SessionDir $sessionDir -Sid $SessionId -Phase "inter_cell_settle" `
            -CellIndex $cellIndex -Arm $Arm -Mode $Mode -Delta $Delta -Repeat $Repeat `
            -Extra @{ classification = $cls; is_canary = $IsCanary }
    }
    Wait-InterCellAvailable -MinMb ([double]$preRunAvailableMin) `
        -SettleS ([double]$recoverySettle) -MaxWaitS ([double]$recoveryMaxWait) | Out-Null
    Assert-No-Contending
    # -NoEnumerate: defend against any residual success-stream companions.
    Write-Output -NoEnumerate $rec
}

function Invoke-DriftCanary {
    param([object]$AfterMatrixCellIndex)
    $cIdx = $canaryRecords.Count
    $raw = Invoke-OneDeltaCell -Arm $CanaryArm -Mode $CanaryMode `
        -NCached $CanaryNCached -Delta $CanaryDelta -Repeat 0 -Seed $null `
        -IsCanary $true -CanaryIndex $cIdx -AfterMatrixCellIndex $AfterMatrixCellIndex
    # Unwrap Write-Output pollution / member-enumeration trap before string-key writes.
    $rec = Get-SinglePipelineRecord -InputObject $raw
    $script:cellIndex++

    $bk = Update-CanaryDriftBookkeeping `
        -Rec $rec `
        -CanaryGate $canaryGate `
        -PriorCanaryRecords (ConvertTo-ObjectArray $canaryRecords) `
        -CanaryCalibrationCount $CanaryCalibrationCount `
        -CanaryRelDriftFloor $CanaryRelDriftFloor
    $rec = $bk.rec
    if ($bk.just_armed) {
        Write-Host ("   canary_gate ARMED: {0}" -f $bk.derivation_applied)
    }
    $canaryRecords.Add($rec) | Out-Null

    # Persist canary progress into plan for -Status visibility.
    $plan.canaries = ConvertTo-ObjectArray $canaryRecords
    $plan.canary_gate = $canaryGate
    $plan | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $planPath -Encoding utf8

    if ($bk.tripped) {
        Write-Output ("REFUSED -- FAIL_CANARY_DRIFT: {0}" -f $bk.trip_detail)
        return $false
    }
    return $true
}

# Opening canary (matrix cell index -1 = before first matrix cell).
if ($canaryEnabled) {
    Write-Output ""
    Write-Output "=== canary (start) ==="
    if (-not (Invoke-DriftCanary -AfterMatrixCellIndex -1)) {
        $abortReason = "FAIL_CANARY_DRIFT"
    }
}

for ($r = 0; $r -lt $Repeats -and -not $abortReason; $r++) {
    $seed = [int]$baseSeed + (10007 * $r) + ($NCachedList.Count * 17) + ($DeltaList.Count * 3)
    $rng = [System.Random]::new($seed)
    $order = @($cellSpecs)
    for ($i = $order.Count - 1; $i -gt 0; $i--) {
        $j = $rng.Next(0, $i + 1)
        $tmp = $order[$i]
        $order[$i] = $order[$j]
        $order[$j] = $tmp
    }
    Write-Output ""
    Write-Output ("=== repeat={0} seed={1} order=[{2}] ===" -f $r, $seed, `
        (($order | ForEach-Object { "{0}:nc{1}:{2}:d{3}" -f $_.arm, $_.n_cached, $_.mode, $_.delta }) -join ", "))

    foreach ($spec in $order) {
        if ($abortReason) { break }
        $arm = [string]$spec.arm
        $mode = [string]$spec.mode
        $delta = [int]$spec.delta
        $nc = [int]$spec.n_cached
        $rawCell = Invoke-OneDeltaCell -Arm $arm -Mode $mode -NCached $nc -Delta $delta `
            -Repeat $r -Seed $seed -IsCanary $false
        $rec = Get-SinglePipelineRecord -InputObject $rawCell
        $cellRecords.Add($rec) | Out-Null
        $cellIndex++
        $matrixCellsSinceCanary++

        # Checkpoint plan periodically so Status sees progress.
        if (($cellRecords.Count % 4) -eq 0) {
            $plan.cells = ConvertTo-ObjectArray $cellRecords
            $plan | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $planPath -Encoding utf8
        }

        if ($canaryEnabled -and $matrixCellsSinceCanary -ge $CanaryEveryN) {
            Write-Output ""
            Write-Output ("=== canary (after matrix cell {0}) ===" -f ($cellRecords.Count - 1))
            if (-not (Invoke-DriftCanary -AfterMatrixCellIndex ($cellRecords.Count - 1))) {
                $abortReason = "FAIL_CANARY_DRIFT"
                break
            }
            $matrixCellsSinceCanary = 0
        }
    }
}

$plan.cells = ConvertTo-ObjectArray $cellRecords
$plan.canaries = ConvertTo-ObjectArray $canaryRecords
$plan.canary_gate = $canaryGate
$plan.environment_end = Get-MachineDriftSnapshot
$plan.ended_utc = (Get-Date).ToUniversalTime().ToString("o")
if ($abortReason) {
    $plan.status = $abortReason
    $plan.abort_reason = $abortReason
} else {
    $plan.status = "complete"
}
$summaryPath = if ($sessionDir) {
    Join-Path $sessionDir "summary.json"
} else {
    Join-Path $sessionRoot "${Tag}_summary.json"
}
$plan | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $planPath -Encoding utf8
$plan | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $summaryPath -Encoding utf8

if ($sessionDir) {
    $hbPhase = if ($abortReason) { "aborted" } else { "complete" }
    Write-MatrixHeartbeat -SessionDir $sessionDir -Sid $SessionId -Phase $hbPhase `
        -CellIndex $cellIndex -Extra @{
            cells_completed    = $cellRecords.Count
            canaries_completed = $canaryRecords.Count
            status             = $plan.status
        }
    if ($DetachedWorker) {
        $resultPath = Join-Path $launchDir "last_result.json"
        @{
            status     = $plan.status
            session_id = $SessionId
            tag        = $Tag
            cells      = $cellRecords.Count
            canaries   = $canaryRecords.Count
            plan_path  = $planPath
            ended_utc  = $plan.ended_utc
            abort_reason = $abortReason
        } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $resultPath -Encoding utf8
    }
}

Write-Output ""
if ($abortReason) {
    Write-Output ("=== matrix ABORTED ({0}) ===" -f $abortReason)
} else {
    Write-Output "=== matrix complete ==="
}
Write-Output "plan    : $planPath"
Write-Output "summary : $summaryPath"
Write-Output ("cells   : {0}" -f $cellRecords.Count)
Write-Output ("canaries: {0}" -f $canaryRecords.Count)
if ($canaryGate.calibration_complete) {
    Write-Output ("canary_gate: {0}" -f $canaryGate.derivation_applied)
}
Write-ThreeNumbers -Cells $cellRecords
if ($abortReason) { exit 3 }
