# Boot 1 sequencer for PARITY-REMEASURE. File work only until this script is started.
#
# From the Mac, one line, detached (returns as soon as WMI has spawned the sequencer).
# <repo-root> is the checkout on the XPS:
#   ssh xps "cd <repo-root>; powershell -NoProfile -File tools\launch_boot1.ps1 -Detach"
#
# Poll the summary (run_ids and statuses; rewritten after every cell):
#   ssh xps "powershell -NoProfile -Command Get-Content -Raw <repo-root>\derived\c2_ttft\_launches\BOOT1_SUMMARY.json"
#
# Order: DET-PROBE, 4B-int4 GPU u8, 8B-int4 GPU u8, 4B-int8 GPU u8, 4B-int4 CPU u8.
# Each cell has its own measurement gates and machine-lock check. Ceiling cells
# run tools/run_c1_ceiling.py without --allow-unguarded, so an unarmed canary
# refuses the cell. Estimates are the boot1_estimates_s in
# derived/c2_ttft/PARITY_REMEASURE_AMEND_1.json. This script does not read that
# file. If remaining cold-window time is below the next cell's estimate, it
# stops and writes DEFERRED_TO_BOOT2.json. It does not skip or shrink a cell.

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$DryRun,
    [ValidateSet("boot1", "boot2", "boot3", "boot4", "t2s-boot1")]
    [string]$Profile = "boot1"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
Set-Location $root

. (Join-Path $PSScriptRoot "_assert_machine_lock.ps1")
. (Join-Path $PSScriptRoot "boot_cell_result.ps1")

$WindowS = 7200
$LaunchDir = Join-Path $root "derived\c2_ttft\_launches"
$SummaryName = switch ($Profile) {
    "boot2" { "BOOT2_SUMMARY.json" }
    "boot3" { "BOOT3_SUMMARY.json" }
    "boot4" { "BOOT4_SUMMARY.json" }
    "t2s-boot1" { "T2S_BOOT1_SUMMARY.json" }
    default { "BOOT1_SUMMARY.json" }
}
$DeferredName = switch ($Profile) {
    "boot2" { "DEFERRED_TO_BOOT3.json" }
    "boot3" { "DEFERRED_TO_BOOT4.json" }
    "boot4" { "DEFERRED_TO_BOOT5.json" }
    "t2s-boot1" { "DEFERRED_TO_T2S_BOOT2.json" }
    default { "DEFERRED_TO_BOOT2.json" }
}
$script:DeferredStatus = switch ($Profile) {
    "t2s-boot1" { "DEFERRED_TO_T2S_BOOT2" }
    default { "DEFERRED_TO_BOOT2" }
}
$SummaryPath = Join-Path $LaunchDir $SummaryName
$DeferredPath = Join-Path $LaunchDir $DeferredName
$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$WorkerPy = Join-Path $root "tools\run_c1_ceiling.py"
$DetPy = Join-Path $root "tools\run_det_probe.py"
$WarmPy = Join-Path $root "tools\run_warm_kv.py"
$DecodePy = Join-Path $root "tools\run_decode_match.py"
$SmokePy = Join-Path $root "tools\c2_extraction_smoke.py"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null

if ($Detach) {
    $self = "`"$PSCommandPath`""
    $cmd = "powershell -NoProfile -File $self -Profile $Profile"
    $log = Join-Path $LaunchDir "$Profile.log"
    $json = & $SpawnPs1 -CommandLine $cmd -LogPath $log -WorkingDirectory $root
    Write-Host $json
    Write-Host "launched boot1 detached"
    Write-Host ("  log     : {0}" -f $log)
    Write-Host ("  summary : {0}" -f $SummaryPath)
    exit 0
}

# Boot 2: estimate = base_s + canary_overhead_s.
# canary_overhead_s = c2246b1f wall 944.242457 - sum of probes.ndjson wall_s 192.106556 = 752.135901.
# Ceiling base_s is the amendment-1 estimate. DET-PROBE-KV base is the cb9773be
# plan.json to SUMMARY.json mtime span 840.522 s, and it adds no canary overhead.
$script:EstimateDerivation = $null
if ($Profile -eq "boot2") {
    $script:EstimateDerivation = [ordered]@{
        formula = "estimate_s = base_s + canary_overhead_s"
        anchor_run_id = "c2246b1f-c588-4998-838a-5507da87e9ee"
        anchor_wall_s = 944.242457
        anchor_bisection_only_s = 192.1065557
        canary_overhead_s = 752.1359013
        det_probe_run_id = "cb9773be-71a7-4cc8-b9ff-f7b18e5231f8"
        det_probe_wall_s = 840.522023
        det_probe_wall_source = "plan.json mtime to SUMMARY.json mtime; those files have no internal timestamps"
        cells = @(
            [ordered]@{ name = "XPS 8B-int4 GPU u8"; base_s = 315; canary_overhead_s = 752.1359013; estimate_s = 1068 }
            [ordered]@{ name = "XPS 4B-int8 GPU u8"; base_s = 338; canary_overhead_s = 752.1359013; estimate_s = 1091 }
            [ordered]@{ name = "DET-PROBE-KV"; base_s = 840.522023; canary_overhead_s = 0; estimate_s = 841 }
            [ordered]@{ name = "XPS 4B-int4 CPU u8"; base_s = 2010; canary_overhead_s = 752.1359013; estimate_s = 2763 }
        )
    }
    $Cells = @(
        @{
            Name = "XPS 8B-int4 GPU u8"; Kind = "ceiling"; EstimateS = 1068
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-8B-int4-ov.yaml"
            Low = 2000; High = 8000
        },
        @{
            Name = "XPS 4B-int8 GPU u8"; Kind = "ceiling"; EstimateS = 1091
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int8-ov.yaml"
            Low = 4000; High = 17000
        },
        @{
            Name = "DET-PROBE-KV"; Kind = "det"; EstimateS = 841
            Arm = "gpu_only_f16"
        },
        @{
            Name = "XPS 4B-int4 CPU u8"; Kind = "ceiling"; EstimateS = 2763
            Arm = "A"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
            Low = 250; High = 2000; ExpectKvReadback = "u8"
        }
    )
} elseif ($Profile -eq "boot3") {
    $script:EstimateDerivation = [ordered]@{
        formula = "estimate_s = base_s + canary_overhead_s"
        note = "Boot 3 keeps the boot-2 estimates for the three cells that did not run."
        cells = @(
            [ordered]@{ name = "XPS 4B-int8 GPU u8"; base_s = 338; canary_overhead_s = 752.1359013; estimate_s = 1091 }
            [ordered]@{ name = "DET-PROBE-KV"; base_s = 840.522023; canary_overhead_s = 0; estimate_s = 841 }
            [ordered]@{ name = "XPS 4B-int4 CPU u8"; base_s = 2010; canary_overhead_s = 752.1359013; estimate_s = 2763 }
        )
    }
    $Cells = @(
        @{
            Name = "XPS 4B-int8 GPU u8"; Kind = "ceiling"; EstimateS = 1091
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int8-ov.yaml"
            Low = 4000; High = 17000
        },
        @{
            Name = "DET-PROBE-KV"; Kind = "det"; EstimateS = 841
            Arm = "gpu_only_f16"
        },
        @{
            Name = "XPS 4B-int4 CPU u8"; Kind = "ceiling"; EstimateS = 2763
            Arm = "A"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
            Low = 250; High = 2000; ExpectKvReadback = "u8"
        }
    )
} elseif ($Profile -eq "boot4") {
    # Boot 4: estimate_s = base_s + canary_overhead_s.
    # canary_overhead_s is the boot-2 measured load overhead, 752.1359013.
    # WARM-KV base_s is the boot-1 4B-int4 GPU generation budget, 368.
    # DECODE-MATCH base_s is the c2246b1f probe-sum, 192.106556.
    $script:EstimateDerivation = [ordered]@{
        formula = "estimate_s = base_s + canary_overhead_s"
        note = "Boot 4: WARM-KV three arms, then DECODE-MATCH. Ceilings are the next whole second."
        cells = @(
            [ordered]@{ name = "WARM-KV f16"; base_s = 368; canary_overhead_s = 752.1359013; estimate_s = 1121 }
            [ordered]@{ name = "WARM-KV u8"; base_s = 368; canary_overhead_s = 752.1359013; estimate_s = 1121 }
            [ordered]@{ name = "WARM-KV u4"; base_s = 368; canary_overhead_s = 752.1359013; estimate_s = 1121 }
            [ordered]@{ name = "DECODE-MATCH"; base_s = 192.106556; canary_overhead_s = 752.1359013; estimate_s = 945 }
        )
    }
    $Cells = @(
        @{
            Name = "WARM-KV f16"; Kind = "warm"; EstimateS = 1121
            Arm = "gpu_only_f16"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        },
        @{
            Name = "WARM-KV u8"; Kind = "warm"; EstimateS = 1121
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        },
        @{
            Name = "WARM-KV u4"; Kind = "warm"; EstimateS = 1121
            Arm = "gpu_only_u4"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        },
        @{
            Name = "DECODE-MATCH"; Kind = "decode"; EstimateS = 945
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        }
    )
} elseif ($Profile -eq "t2s-boot1") {
    # T2S boot 1. PARITY-REMEASURE cells registered in 91d9005. This script
    # does not open that prereg. estimate_s is the next whole second of
    # base_s + measured canary overhead.
    # base_s 520 is the 5c714535 prereg wall 519.541 rounded up.
    # base_s 570 is the 051d2681 prereg wall 570.010 rounded down to the
    # stated base. Overhead is c2246b1f wall 944.242457 minus probe-sum
    # 192.106556 = 752.1359013, stated as 752.136.
    # Platform onset_s is null (unknown, not measured on evo-t2). The
    # ceiling canary still uses 657, borrowed from aipc-c1 session 7f569929,
    # which is the value 5c714535 and 051d2681 recorded.
    $env:SEAM_PLATFORM_ID = "evo-t2"
    $script:EstimateDerivation = [ordered]@{
        formula = "estimate_s = base_s + canary_overhead_s, then the next whole second"
        platform_id = "evo-t2"
        platform_config = "configs/platforms/evo-t2.yaml"
        free_memory_floor_mb = 24000
        free_memory_floor_provenance = "derived_unmeasured: deepest planned CAP-4-class cell on 64 GB unified memory; peak model+KV+runtime estimate about 36-40 GB leaves about 24-28 GB Available; floor 24000 MB. configs/platforms/evo-t2.yaml measurement_gates.pre_run_available_mb_min."
        onset_s = $null
        onset_status = "unknown"
        onset_provenance = "not measured on evo-t2"
        canary_onset_s = 657
        canary_onset_provenance = "borrowed from aipc-c1 session 7f569929 via docs/CANARY_PROTOCOL.md and tools/ttft_slo_canary.py ONSET_S. Same value recorded on 5c714535 and 051d2681. Not an evo-t2 measurement."
        harness = "tools/run_c1_ceiling.py --criterion ttft_slo --slo-s 10 --resolution 250 --repeats 3"
        affinity_cpus = "0,1,2,3"
        wslock = "request minimum_bytes=4294967296 maximum_bytes=12884901888"
        max_new_tokens = 8
        harness_source = "5c714535 and 051d2681 work spec.json; configs/delta_n.yaml; aipc-c1 topology.p_cpus pinned by run_c1_ceiling.py"
        anchor_run_id = "c2246b1f-c588-4998-838a-5507da87e9ee"
        canary_overhead_s = 752.1359013
        canary_overhead_stated_s = 752.136
        cells = @(
            [ordered]@{ name = "T2S 4B-int4 GPU u8"; base_run_id = "5c714535-9f36-4614-a594-698b6cd09296"; base_s = 520; canary_overhead_s = 752.1359013; estimate_s = 1273 }
            [ordered]@{ name = "T2S 8B-int4 GPU u8"; base_run_id = "051d2681-4bb8-4f50-b9fc-b14441359ba6"; base_s = 570; canary_overhead_s = 752.1359013; estimate_s = 1323 }
        )
    }
    $Cells = @(
        @{
            Name = "T2S 4B-int4 GPU u8"; Kind = "ceiling"; EstimateS = 1273
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
            Low = 14000; High = 26000
        },
        @{
            Name = "T2S 8B-int4 GPU u8"; Kind = "ceiling"; EstimateS = 1323
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-8B-int4-ov.yaml"
            Low = 14000; High = 26000
        }
    )
} else {
$Cells = @(
    @{ Name = "DET-PROBE"; Kind = "det"; EstimateS = 1200 },
    @{
        Name = "XPS 4B-int4 GPU u8"; Kind = "ceiling"; EstimateS = 368
        Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        Low = 8000; High = 12000
    },
    @{
        Name = "XPS 8B-int4 GPU u8"; Kind = "ceiling"; EstimateS = 315
        Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-8B-int4-ov.yaml"
        Low = 2000; High = 8000
    },
    @{
        Name = "XPS 4B-int8 GPU u8"; Kind = "ceiling"; EstimateS = 338
        Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int8-ov.yaml"
        Low = 4000; High = 17000
    },
    @{
        Name = "XPS 4B-int4 CPU u8"; Kind = "ceiling"; EstimateS = 2010
        Arm = "A"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        Low = 250; High = 2000; ExpectKvReadback = "u8"
    }
    )
}

$script:Rows = @()
$script:LastRunId = ""
$script:FinalState = "crashed"
$script:FinalReason = "sequencer stopped before the summary was finalized"

function Get-BootCellField {
    param($Cell, [string]$Name)
    if ($Cell -is [System.Collections.IDictionary]) {
        if ($Cell.Contains($Name)) { return $Cell[$Name] }
        return $null
    }
    $prop = $Cell.PSObject.Properties[$Name]
    if ($null -eq $prop) { return $null }
    return $prop.Value
}

function Get-ColdUptimeSeconds {
    $boot = (Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop).LastBootUpTime
    return [int]((Get-Date) - [datetime]$boot).TotalSeconds
}

function Save-BootSummary {
    param([string]$State, [string]$Reason = "")
    if ($DryRun) { return }
    $prior = @()
    if (Test-Path -LiteralPath $SummaryPath) {
        $existing = Get-Content -LiteralPath $SummaryPath -Raw -Encoding utf8 | ConvertFrom-Json
        $cellsProp = $existing.PSObject.Properties["cells"]
        if ($null -ne $cellsProp) { $prior = @($cellsProp.Value) }
    }
    $doc = [ordered]@{
        state = $State
        reason = $Reason
        last_run_id = $script:LastRunId
        window_s = $WindowS
        uptime_s = Get-ColdUptimeSeconds
        estimate_derivation = $script:EstimateDerivation
        cells = @(Merge-BootCells -Prior $prior -Added $script:Rows)
    }
    ($doc | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $SummaryPath -Encoding utf8
}

function Add-Row {
    param($Cell, [string]$Status, [string]$RunId, [string]$Detail)
    $script:Rows += [ordered]@{
        name = $Cell.Name
        status = $Status
        run_id = $RunId
        estimate_s = $Cell.EstimateS
        detail = $Detail
    }
    Save-BootSummary -State "running"
}

function Assert-BootLockClear {
    $lockPath = Join-Path $root ".locks\machine.lock"
    Write-Host "=== machine-lock / alive-worker check ==="
    if (Test-Path -LiteralPath $lockPath) {
        $raw = Get-Content -LiteralPath $lockPath -Raw -ErrorAction Stop
        $ownerPid = $null
        try {
            $rec = $raw | ConvertFrom-Json
            if ($null -ne $rec.pid) { $ownerPid = [int]$rec.pid }
        } catch {
            throw "REFUSED -- machine.lock present but unparseable"
        }
        if ($null -eq $ownerPid) { throw "REFUSED -- machine.lock present with no pid" }
        $alive = $null -ne (Get-Process -Id $ownerPid -ErrorAction SilentlyContinue)
        if ($alive) { throw "REFUSED -- machine.lock held by live PID $ownerPid" }
        Write-Host "machine.lock present but owner is dead (stale); continuing"
    } else {
        Write-Host "machine.lock: absent"
    }
    $workers = @(Get-SeamAliveMeasurementWorkers -ExcludePids @($PID))
    if ($workers.Count -gt 0) {
        throw "REFUSED -- another measurement worker is alive"
    }
}

function Invoke-BootGates {
    param([string]$Label, [switch]$ReportOnly)
    $probeDir = Join-Path $root "derived\_gate_probes"
    New-Item -ItemType Directory -Force -Path $probeDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $outJson = Join-Path $probeDir ("boot1_" + $Label.Replace(" ", "_") + "_" + $stamp + ".json")
    $prev = $env:PYTHONPATH
    try {
        if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
            $env:PYTHONPATH = $root
        } elseif ($env:PYTHONPATH -notlike "*$root*") {
            $env:PYTHONPATH = "$root;$env:PYTHONPATH"
        }
        $output = & $PythonExe -m seam.measurement_gates --repo-root $root --json 2>&1
        $code = $LASTEXITCODE
    } finally {
        $env:PYTHONPATH = $prev
    }
    $text = ($output | ForEach-Object { "$_" }) -join "`n"
    Write-Host $text
    if ($ReportOnly) {
        Write-Host ("gate_report_only exit={0}" -f $code)
        return
    }
    Set-Content -LiteralPath $outJson -Value $text -Encoding utf8
    if ($code -ne 0) { throw "REFUSED -- measurement gates failed (exit $code)" }
}

function Invoke-CellPreamble {
    param([string]$Label, [switch]$SkipGateFile)
    Write-Host ""
    Write-Host ("=== preamble {0} ===" -f $Label)
    $wsh = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
    if ($wsh.Count -gt 0) {
        $wsh | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        $left = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
        if ($left.Count -gt 0) {
            throw "REFUSED -- WorkloadsSessionHost still resident"
        }
    }
    # DET-PROBE checks a clean tree before it takes .locks/machine.lock.
    # A gate JSON written here would make that check fail.
    if (-not $SkipGateFile) { Invoke-BootGates -Label $Label }
    Assert-BootLockClear
}

function Invoke-DetProbe {
    param($Cell)
    $detArgs = @("-u", $DetPy)
    $arm = Get-BootCellField -Cell $Cell -Name "Arm"
    if ($arm) { $detArgs += @("--arm", $arm) }
    $lines = & $PythonExe @detArgs 2>&1
    $exit = $LASTEXITCODE
    $lines | ForEach-Object { Write-Host $_ }
    $runId = ""
    foreach ($line in $lines) {
        $text = [string]$line
        if ($text.StartsWith("RUN_ID ")) { $runId = $text.Substring(7).Trim() }
    }
    return @{ Exit = $exit; RunId = $runId }
}

function Invoke-CeilingCell {
    param($Cell)
    $model = Join-Path $root $Cell.Model
    if (-not (Test-Path -LiteralPath $model)) { throw "REFUSED -- missing model spec $($Cell.Model)" }
    $sid = [guid]::NewGuid().ToString()
    $out = Join-Path $root ("derived\c2_ttft\" + $sid)
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $smokeOut = Join-Path $out "extraction_smoke"
    & $PythonExe -u $SmokePy --out $smokeOut `
        --model-spec $model --n-tokens 64 --arm gpu_only_f16 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "REFUSED -- extraction smoke failed" }
    $env:SEAM_LAUNCH_CONTEXT = "ssh_detached"
    $workerLines = New-Object System.Collections.Generic.List[string]
    & $PythonExe -u $WorkerPy `
        --session-id $sid `
        --out $out `
        --model-spec $model `
        --arms $Cell.Arm `
        --criterion ttft_slo `
        --slo-s 10 `
        --low $Cell.Low `
        --high $Cell.High `
        --resolution 250 `
        --repeats 3 `
        --watchdog-interval-s 60 2>&1 | ForEach-Object {
            $workerLines.Add([string]$_)
            Write-Host $_
        }
    $exit = $LASTEXITCODE
    $summaryPath = Join-Path $out "summary.json"
    return Get-BootCeilingResult -SummaryPath $summaryPath -Stdout @($workerLines) -ExitCode $exit -RunId $sid -Out $out
}

function Assert-BootTree {
    $raw = & $PythonExe (Join-Path $root "tools\boot_tree_check.py")
    if ($LASTEXITCODE -ne 0) { throw "REFUSED -- clean-tree check: $raw" }
    $verdict = $raw | ConvertFrom-Json
    $paths = @($verdict.untracked_derived)
    $env:SEAM_UNTRACKED_DERIVED = ($paths -join "`n")
    return $paths
}

function Get-BootCellCommand {
    param($Cell)
    $kind = Get-BootCellField -Cell $Cell -Name "Kind"
    $arm = Get-BootCellField -Cell $Cell -Name "Arm"
    $model = Get-BootCellField -Cell $Cell -Name "Model"
    $low = Get-BootCellField -Cell $Cell -Name "Low"
    $high = Get-BootCellField -Cell $Cell -Name "High"
    $kv = Get-BootCellField -Cell $Cell -Name "ExpectKvReadback"
    if ($kind -eq "det") {
        $args = @($PythonExe, "-u", $DetPy)
        if ($arm) { $args += @("--arm", $arm) }
        return [ordered]@{
            kind = $kind; arm = $arm; model = $model; low = $low; high = $high
            expect_kv = $kv; command = ($args -join " ")
        }
    }
    if ($kind -eq "warm" -or $kind -eq "decode") {
        $script = $WarmPy
        if ($kind -eq "decode") { $script = $DecodePy }
        $modelPath = Join-Path $root $model
        $args = @($PythonExe, "-u", $script, "--arm", $arm, "--model-spec", $modelPath)
        if ($kind -eq "decode") { $args += @("--n", "2000,4000,8000") }
        return [ordered]@{
            kind = $kind; arm = $arm; model = $model; low = $low; high = $high
            expect_kv = $kv; command = ($args -join " "); smoke = $null
        }
    }
    $modelPath = Join-Path $root $model
    $smoke = @(
        $PythonExe, "-u", $SmokePy, "--out", "<cell>\extraction_smoke",
        "--model-spec", $modelPath, "--n-tokens", "64", "--arm", "gpu_only_f16"
    ) -join " "
    $worker = @(
        $PythonExe, "-u", $WorkerPy,
        "--session-id", "<new>", "--out", "<cell>",
        "--model-spec", $modelPath, "--arms", $arm,
        "--criterion", "ttft_slo", "--slo-s", "10",
        "--low", $low, "--high", $high,
        "--resolution", "250", "--repeats", "3", "--watchdog-interval-s", "60"
    ) -join " "
    return [ordered]@{
        kind = $kind; arm = $arm; model = $model; low = $low; high = $high
        expect_kv = $kv; command = $worker; smoke = $smoke
    }
}

function Invoke-BootDryCell {
    param($Cell)
    $name = Get-BootCellField -Cell $Cell -Name "Name"
    $built = Get-BootCellCommand -Cell $Cell
    Write-Host ("dry_run {0} kind={1} arm={2} model={3} low={4} high={5} expect_kv={6}" -f `
        $name, $built.kind, $built.arm, $built.model, $built.low, $built.high, $built.expect_kv)
    if ($built.kind -eq "det" -or $built.kind -eq "warm" -or $built.kind -eq "decode") {
        Invoke-BootGates -Label $name -ReportOnly
    } else {
        Invoke-BootGates -Label $name -ReportOnly
        Write-Host ("smoke {0}" -f $built.smoke)
    }
    Write-Host ("command {0}" -f $built.command)
    Write-Host ("DRY_RUN_OK {0}" -f $name)
}

function Assert-BootAc {
    if ($Profile -eq "t2s-boot1") {
        Write-Host "battery_present=false ac=pass reason=platform power.has_battery is false (evo-t2 mains-only)"
        return
    }
    $b = @(Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue)
    if ($b.Count -eq 0) { return }
    foreach ($one in $b) {
        if ([int]$one.BatteryStatus -ne 2) {
            throw "REFUSED -- ac: on battery (BatteryStatus=$($one.BatteryStatus))"
        }
    }
}

if ($Profile -eq "t2s-boot1") {
    Write-Host "platform_id=evo-t2 config=configs/platforms/evo-t2.yaml"
    Write-Host "free_memory_floor_mb=24000 provenance=derived_unmeasured CAP-4-class peak on 64 GB; floor keeps Available at or above 24000 MB"
    Write-Host "onset_s=null onset_status=unknown provenance=not measured on evo-t2"
    Write-Host "canary_onset_s=657 provenance=borrowed from aipc-c1 session 7f569929; recorded on 5c714535 and 051d2681; not an evo-t2 measurement"
    Write-Host "harness affinity_cpus=0,1,2,3 wslock=request:4294967296:12884901888 max_new_tokens=8 source=5c714535/051d2681"
    Assert-BootAc
}

Save-BootSummary -State "started"

try {
for ($i = 0; $i -lt $Cells.Count; $i++) {
    $cell = $Cells[$i]
    $uptime = Get-ColdUptimeSeconds
    $remaining = $WindowS - $uptime
    Write-Host ("time_check {0}: uptime_s={1} remaining_s={2} estimate_s={3}" -f `
        $cell.Name, $uptime, $remaining, $cell.EstimateS)
    if ($DryRun) {
        Invoke-BootDryCell -Cell $cell
        continue
    }
    if ($remaining -lt [int]$cell.EstimateS) {
        $left = @()
        for ($j = $i; $j -lt $Cells.Count; $j++) {
            $left += $Cells[$j].Name
            Add-Row -Cell $Cells[$j] -Status $script:DeferredStatus -RunId "" -Detail "remaining_s=$remaining"
        }
        $defer = [ordered]@{
            reason = "remaining cold-window time is below the next cell estimate"
            uptime_s = $uptime
            remaining_s = $remaining
            window_s = $WindowS
            cells = $left
        }
        ($defer | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $DeferredPath -Encoding utf8
        $script:FinalState = "deferred"
        $script:FinalReason = "remaining cold-window time is below the next cell estimate"
        Save-BootSummary -State "deferred" -Reason $script:FinalReason
        Write-Host "DEFERRED"
        exit 0
    }

    try {
        Assert-BootAc
        Assert-BootTree | Out-Null
        if ($cell.Kind -eq "det" -or $cell.Kind -eq "warm" -or $cell.Kind -eq "decode") {
            Invoke-CellPreamble -Label $cell.Name -SkipGateFile
        } else {
            Invoke-CellPreamble -Label $cell.Name
        }
    } catch {
        $script:FinalState = "refused"
        $script:FinalReason = $_.Exception.Message
        Add-Row -Cell $cell -Status "REFUSED" -RunId "" -Detail $script:FinalReason
        Save-BootSummary -State "refused" -Reason $script:FinalReason
        Write-Host $script:FinalReason
        exit 1
    }

    if ($cell.Kind -eq "det") {
        $ran = Invoke-DetProbe -Cell $cell
        if ($ran.Exit -ne 0) {
            $script:LastRunId = $ran.RunId
            $script:FinalState = "refused"
            $script:FinalReason = "exit=$($ran.Exit)"
            Add-Row -Cell $cell -Status "REFUSED" -RunId $ran.RunId -Detail $script:FinalReason
            Save-BootSummary -State "refused" -Reason $script:FinalReason
            exit $ran.Exit
        }
        $script:LastRunId = $ran.RunId
        Add-Row -Cell $cell -Status "complete" -RunId $ran.RunId -Detail ""
        continue
    }

    if ($cell.Kind -eq "warm" -or $cell.Kind -eq "decode") {
        $built = Get-BootCellCommand -Cell $cell
        Write-Host $built.command
        $parts = @($built.command -split " ")
        & $parts[0] @($parts | Select-Object -Skip 1)
        $exit = $LASTEXITCODE
        if ($exit -ne 0) {
            $script:FinalState = "refused"
            $script:FinalReason = "exit=$exit"
            Add-Row -Cell $cell -Status "REFUSED" -RunId "" -Detail $script:FinalReason
            Save-BootSummary -State "refused" -Reason $script:FinalReason
            exit $exit
        }
        Add-Row -Cell $cell -Status "complete" -RunId "" -Detail ""
        continue
    }

    try {
        $ran = Invoke-CeilingCell -Cell $cell
    } catch {
        $script:FinalState = "refused"
        $script:FinalReason = $_.Exception.Message
        Add-Row -Cell $cell -Status "REFUSED" -RunId "" -Detail $script:FinalReason
        Save-BootSummary -State "refused" -Reason $script:FinalReason
        Write-Host $script:FinalReason
        exit 1
    }
    $detail = "summary_status=$($ran.Status)"
    if ($ran.Exit -ne 0 -or $ran.Status -match "UNARMED|REFUSED") {
        $script:LastRunId = $ran.RunId
        $script:FinalState = "refused"
        $script:FinalReason = "canary did not arm ($detail)"
        Add-Row -Cell $cell -Status "REFUSED_CANARY" -RunId $ran.RunId -Detail $detail
        Save-BootSummary -State "refused" -Reason $script:FinalReason
        Write-Host ("REFUSED -- canary did not arm for {0} ({1})" -f $cell.Name, $detail)
        exit 1
    }
    $expectKv = Get-BootCellField -Cell $cell -Name "ExpectKvReadback"
    if ($expectKv) {
        $hit = Get-ChildItem -Path (Join-Path $ran.Out "work") -Filter "*.result.json" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        $normalized = ""
        if ($hit) {
            $doc = Get-Content -LiteralPath $hit.FullName -Raw | ConvertFrom-Json
            # Script scope is case-insensitive, so a variable named rows would overwrite script:Rows.
            $kvReadback = @($doc.kv_cache_precision_readback)
            if ($kvReadback.Count -gt 0 -and $kvReadback[0].readback) {
                $normalized = [string]$kvReadback[0].readback.normalized
            }
        }
        $detail = "$detail kv_readback=$normalized"
        if ($normalized -ne $expectKv) {
            $script:LastRunId = $ran.RunId
            $script:FinalState = "refused"
            $script:FinalReason = "CPU KV readback is not u8"
            Add-Row -Cell $cell -Status "KV_READBACK_NOT_U8" -RunId $ran.RunId -Detail $detail
            Save-BootSummary -State "refused" -Reason $script:FinalReason
            Write-Host "REFUSED -- CPU KV readback is not u8"
            exit 1
        }
    }
    $script:LastRunId = $ran.RunId
    Add-Row -Cell $cell -Status "complete" -RunId $ran.RunId -Detail $detail
}
$script:FinalState = "complete"
$script:FinalReason = ""
} catch {
    $script:FinalState = "crashed"
    $script:FinalReason = $_.Exception.Message
    Write-Host $script:FinalReason
    exit 1
} finally {
    Save-BootSummary -State $script:FinalState -Reason $script:FinalReason
}

Write-Host "BOOT_COMPLETE"
exit 0
