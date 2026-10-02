# Boot 1 sequencer for PARITY-REMEASURE. File work only until this script is started.
#
# From the Mac, one line, detached (returns as soon as WMI has spawned the sequencer).
# <repo-root> is the checkout on the XPS:
#   ssh xps "cd <repo-root>; powershell -NoProfile -File tools\launch_boot1.ps1 -Detach"
#
# Boot 4 rehearsal uses the same ssh + WMI path. Do not start it from the Cursor terminal.
#   ssh xps "cd <repo>; powershell -NoProfile -File tools\launch_boot4.ps1 -Detach -Rehearsal"
# Poll:
#   ssh xps "powershell -NoProfile -Command Get-Content -Tail 50 <repo>/derived/c2_ttft/_launches/_rehearsal/boot4/boot4.log"
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
    [switch]$NoRebootDeviation,
    [switch]$Rehearsal,
    [string]$WatchdogLog = "",
    [ValidateSet("boot1", "boot2", "boot3", "boot4", "resident-limit", "resident-limit-2", "p0-v2", "p1-a0", "p1-a4", "p1-a5", "p1-a1", "t2s-boot1")]
    [string]$Profile = "boot1",
    [int]$P1Seed = 20260930,
    [int]$P1EntryOffset = 0,
    [int]$P1EntryCount = 100
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
if (-not $root) { $root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
Set-Location $root

. (Join-Path $PSScriptRoot "_assert_machine_lock.ps1")
. (Join-Path $PSScriptRoot "boot_cell_result.ps1")
. (Join-Path $PSScriptRoot "_utf8_nobom.ps1")
. (Join-Path $PSScriptRoot "wsh_policy.ps1")

# Every script variable the summary and WSH code reads. Strict mode throws
# on a read before the first assignment. Profile blocks below may overwrite
# UncoldReason, ControlBand, and EstimateDerivation.
$script:LastWshClear = $null
$script:UncoldReason = ""
$script:ControlBand = $null
$script:EstimateDerivation = $null
$script:Rows = @()
$script:LastRunId = ""
$script:FinalState = "crashed"
$script:FinalReason = "sequencer stopped before the summary was finalized"
$script:ForeignQueueEvidence = $null
$script:WatchdogLogMissing = $false
$script:RunStartedUtc = ""
$script:CellStartedUtc = ""
$script:BootId = [guid]::NewGuid().ToString()

$WindowS = 7200
$LaunchDir = Join-Path $root "derived\c2_ttft\_launches"
if ($Rehearsal) {
    $LaunchDir = Join-Path $LaunchDir ("_rehearsal\" + $Profile)
    $env:SEAM_REHEARSAL = "1"
    Write-Host ("rehearsal=true writes={0}" -f $LaunchDir)
}
$SummaryName = switch ($Profile) {
    "boot2" { "BOOT2_SUMMARY.json" }
    "boot3" { "BOOT3_SUMMARY.json" }
    "boot4" { "BOOT4_SUMMARY.json" }
    "resident-limit" { "RESIDENT_LIMIT_SUMMARY.json" }
    "resident-limit-2" { "RESIDENT_LIMIT_2_SUMMARY.json" }
    "p0-v2" { "P0_V2_SUMMARY.json" }
    "p1-a0" { "P1_A0_SUMMARY.json" }
    "p1-a4" { "P1_A4_SUMMARY.json" }
    "p1-a5" { "P1_A5_SUMMARY.json" }
    "p1-a1" { "P1_A1_SUMMARY.json" }
    "t2s-boot1" { "T2S_BOOT1_SUMMARY.json" }
    default { "BOOT1_SUMMARY.json" }
}
$DeferredName = switch ($Profile) {
    "boot2" { "DEFERRED_TO_BOOT3.json" }
    "boot3" { "DEFERRED_TO_BOOT4.json" }
    "boot4" { "DEFERRED_TO_BOOT5.json" }
    "resident-limit" { "DEFERRED_TO_RESIDENT_LIMIT_2.json" }
    "resident-limit-2" { "DEFERRED_TO_RESIDENT_LIMIT_3.json" }
    "p0-v2" { "DEFERRED_TO_P0_V3.json" }
    "p1-a0" { "DEFERRED_TO_P1_A4.json" }
    "p1-a4" { "DEFERRED_TO_P1_A5.json" }
    "p1-a5" { "DEFERRED_TO_P1_A2.json" }
    "p1-a1" { "DEFERRED_TO_P1_A1_NEXT.json" }
    "t2s-boot1" { "DEFERRED_TO_T2S_BOOT2.json" }
    default { "DEFERRED_TO_BOOT2.json" }
}
$script:DeferredStatus = switch ($Profile) {
    "t2s-boot1" { "DEFERRED_TO_T2S_BOOT2" }
    "resident-limit" { "DEFERRED_TO_RESIDENT_LIMIT_2" }
    "resident-limit-2" { "DEFERRED_TO_RESIDENT_LIMIT_3" }
    "p0-v2" { "DEFERRED_TO_P0_V3" }
    "p1-a0" { "DEFERRED_TO_P1_A4" }
    "p1-a4" { "DEFERRED_TO_P1_A5" }
    "p1-a5" { "DEFERRED_TO_P1_A2" }
    "p1-a1" { "DEFERRED_TO_P1_A1_NEXT" }
    default { "DEFERRED_TO_BOOT2" }
}
$SummaryPath = Join-Path $LaunchDir $SummaryName
$DeferredPath = Join-Path $LaunchDir $DeferredName
$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$WorkerPy = Join-Path $root "tools\run_c1_ceiling.py"
$DetPy = Join-Path $root "tools\run_det_probe.py"
$WarmPy = Join-Path $root "tools\run_warm_kv.py"
$DecodePy = Join-Path $root "tools\run_decode_match.py"
$ResidentPy = Join-Path $root "tools\run_resident_limit.py"
$ExchangePy = Join-Path $root "tools\run_exchange_rate.py"
$P1Py = Join-Path $root "tools\run_p1_quality.py"
$SmokePy = Join-Path $root "tools\c2_extraction_smoke.py"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null

$script:RehearsalMac = switch ($Profile) {
    "resident-limit" { 'ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_resident_limit.ps1 -Detach -Rehearsal"' }
    "resident-limit-2" { 'ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_resident_limit_2.ps1 -Detach -Rehearsal"' }
    "p0-v2" { 'ssh zjohn@100.101.81.6 "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_p0_v2.ps1 -Detach -Rehearsal"' }
    "p1-a0" { 'ssh zjohn@100.101.81.6 "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_p1_a0.ps1 -Detach -Rehearsal"' }
    "p1-a4" { 'ssh zjohn@100.101.81.6 "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_p1_a4.ps1 -Detach -Rehearsal"' }
    "p1-a5" { 'ssh zjohn@100.101.81.6 "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_p1_a5.ps1 -Detach -Rehearsal"' }
    "p1-a1" { 'ssh zjohn@100.101.81.6 "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_p1_a1.ps1 -Detach -Rehearsal"' }
    default { 'ssh xps "cd C:/Users/zjohn/Projects/gnn-hls-accel; powershell -NoProfile -File tools\launch_boot4.ps1 -Detach -Rehearsal"' }
}

if ($Detach) {
    if ($Rehearsal -and -not $DryRun) {
        $sshParent = Test-SeamProcessAncestor -Names @("sshd.exe") -Depth 4
        if (-not $sshParent) {
            Write-Host "REFUSED -- rehearsal -Detach must be started from ssh, not this terminal."
            Write-Host ("From the Mac: {0}" -f $script:RehearsalMac)
            exit 1
        }
    }
    $self = "`"$PSCommandPath`""
    $cmd = "powershell -NoProfile -File $self -Profile $Profile"
    if ($NoRebootDeviation) { $cmd += " -NoRebootDeviation" }
    if ($Rehearsal) { $cmd += " -Rehearsal" }
    if ($Profile -eq "p1-a1" -or $Profile -eq "p1-a4" -or $Profile -eq "p1-a5") {
        $cmd += " -P1Seed $P1Seed -P1EntryOffset $P1EntryOffset -P1EntryCount $P1EntryCount"
    }
    if ($WatchdogLog) { $cmd += " -WatchdogLog `"$WatchdogLog`"" }
    $log = Join-Path $LaunchDir "$Profile.log"
    $json = & $SpawnPs1 -CommandLine $cmd -LogPath $log -WorkingDirectory $root
    Write-Host $json
    Write-Host "launched boot1 detached"
    Write-Host ("  log     : {0}" -f $log)
    Write-Host ("  summary : {0}" -f $SummaryPath)
    exit 0
}

if ($Rehearsal -and -not $DryRun) {
    if ($env:SEAM_BOOT_SMOKE_STUB -eq "1") {
        Write-Host "rehearsal_context=strict_harness smoke_stub=1"
    } else {
        $wmiChild = Test-SeamProcessAncestor -Names @("WmiPrvSE.exe") -Depth 4
        if (-not $wmiChild) {
            Write-Host "REFUSED -- rehearsal must run as the WMI-detached child of an ssh launch."
            Write-Host ("From the Mac: {0}" -f $script:RehearsalMac)
            exit 1
        }
    }
}

# Boot 2: estimate = base_s + canary_overhead_s.
# canary_overhead_s = c2246b1f wall 944.242457 - sum of probes.ndjson wall_s 192.106556 = 752.135901.
# Ceiling base_s is the amendment-1 estimate. DET-PROBE-KV base is the cb9773be
# plan.json to SUMMARY.json mtime span 840.522 s, and it adds no canary overhead.
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
    # Boot 4: estimate_s = base_s + canary_overhead_s, next whole second.
    # canary_overhead_s is the boot-2 measured load overhead, 752.1359013.
    # Source medians are sealed 2b3316b6-7f6e-474f-9177-bd5a89aeb58c.
    # Warm base_s is the 12000 median, plus the 26000 median as the bound for
    # the 24000 point (24000 is not a rung), plus the 46000 median, plus
    # 9 x the arm's 12000 median (3 points x 3 turn-2 repeats, each bounded
    # by the 12000 prefill; delta is 183 tokens), plus 2 x the f16 12000
    # median 13.504825195. The last term bounds the discarded two-turn
    # canary warm-up. The canary cell is f16.
    # f16 12k 13.504825195, 26k 51.842308593, 46k 252.707921875,
    # base 466.608132808, estimate 1219.
    # u8 12k 13.277133789, 26k 52.298699218, 46k 230.360359375,
    # base 442.440046873, estimate 1195.
    # u4 12k 13.550313476, 26k 52.206597656, 46k 239.800796875,
    # base 454.520179681, estimate 1207.
    # Decode base_s is 18 x the sealed int4 f16 12000 prefill 13.504825195
    # (2 models x 3 n x 3 repeats) plus the same 2 x 13.504825195 warm-up
    # bound. Each listed n is below 12000. The int8 weight model is not in
    # that sealed run; the same prefill bounds it.
    # Decode base 270.096503900, estimate 1023.
    # Sum of ceilings 4644 s. Window is 7200 s, so boot 4 stays one window.
    $script:EstimateDerivation = [ordered]@{
        formula = "estimate_s = base_s + canary_overhead_s"
        note = "Boot 4 stays one window: estimate sum 4644 s is below 7200 s."
        source_run_id = "2b3316b6-7f6e-474f-9177-bd5a89aeb58c"
        cells = @(
            [ordered]@{ name = "WARM-KV f16"; base_s = 466.608132808; canary_overhead_s = 752.1359013; estimate_s = 1219 }
            [ordered]@{ name = "WARM-KV u8"; base_s = 442.440046873; canary_overhead_s = 752.1359013; estimate_s = 1195 }
            [ordered]@{ name = "WARM-KV u4"; base_s = 454.520179681; canary_overhead_s = 752.1359013; estimate_s = 1207 }
            [ordered]@{ name = "DECODE-MATCH"; base_s = 270.096503900; canary_overhead_s = 752.1359013; estimate_s = 1023 }
        )
    }
    $Cells = @(
        @{
            Name = "WARM-KV f16"; Kind = "warm"; EstimateS = 1219
            Arm = "gpu_only_f16"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        },
        @{
            Name = "WARM-KV u8"; Kind = "warm"; EstimateS = 1195
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        },
        @{
            Name = "WARM-KV u4"; Kind = "warm"; EstimateS = 1207
            Arm = "gpu_only_u4"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        },
        @{
            Name = "DECODE-MATCH"; Kind = "decode"; EstimateS = 1023
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
            Model2 = "configs\models\Qwen3-4B-int8-ov.yaml"
        }
    )
} elseif ($Profile -eq "resident-limit") {
    # Resident-limit: one cell per KV arm. Search is low 12000, high 30000,
    # resolution 500, one attempt per rung. Probe upper bound per arm is
    # 2 + ceil(log2((30000-12000)/500)) = 8.
    # Probe bound is the largest sealed RESIDENT pass in dd2b0779:
    # u4 n=24000 turn1 44.904558593 + turn2 2.535339599 = 47.439898192.
    # base_s = 8 * 47.439898192 = 379.519185536.
    # canary_overhead_s is the boot-2 measured load overhead, 752.1359013.
    # estimate_s is the next whole second of that sum: 1132.
    # Three arms sum to 3396 s. Window is 7200 s, so this stays one window.
    $script:EstimateDerivation = [ordered]@{
        formula = "estimate_s = base_s + canary_overhead_s"
        note = "Resident-limit stays one window: estimate sum 3396 s is below 7200 s."
        source_run_id = "dd2b0779-48c1-4ad6-9567-ed38e8e1fec9"
        probe_bound_s = 47.439898192
        probes_per_arm = 8
        cells = @(
            [ordered]@{ name = "RESIDENT-LIMIT f16"; base_s = 379.519185536; canary_overhead_s = 752.1359013; estimate_s = 1132 }
            [ordered]@{ name = "RESIDENT-LIMIT u8"; base_s = 379.519185536; canary_overhead_s = 752.1359013; estimate_s = 1132 }
            [ordered]@{ name = "RESIDENT-LIMIT u4"; base_s = 379.519185536; canary_overhead_s = 752.1359013; estimate_s = 1132 }
        )
    }
    $Cells = @(
        @{
            Name = "RESIDENT-LIMIT f16"; Kind = "resident"; EstimateS = 1132
            Arm = "gpu_only_f16"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        },
        @{
            Name = "RESIDENT-LIMIT u8"; Kind = "resident"; EstimateS = 1132
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        },
        @{
            Name = "RESIDENT-LIMIT u4"; Kind = "resident"; EstimateS = 1132
            Arm = "gpu_only_u4"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        }
    )
} elseif ($Profile -eq "resident-limit-2") {
    # u4 first, then P0 exchange-rate. f16 and u8 already ran.
    # u4: 8 probes times the sealed dd2b0779 u4 n=24000 resident pass
    # 47.439898192 s = 379.519185536, plus canary overhead 752.1359013,
    # next whole second 1132.
    # P0: serial upper bound of the cold-context probes is 2334.648721088813 s,
    # plus 12 * 5.211120400010259 s model load, plus canary overhead
    # 752.1359013 s = 3149.3180671889363 s, next whole second 3150.
    # 1132 + 3150 = 4282, which is below the 7200 s window.
    $script:EstimateDerivation = [ordered]@{
        formula = "estimate_s = base_s + canary_overhead_s, then the next whole second"
        note = "u4 is 1132 s and P0 is 3150 s. The sum 4282 s is below 7200 s."
        source_run_id = "dd2b0779-48c1-4ad6-9567-ed38e8e1fec9"
        p0_probe_sum_s = 2334.648721088813
        p0_load_s = 62.53344480012311
        p0_canary_overhead_s = 752.1359013
        cells = @(
            [ordered]@{ name = "RESIDENT-LIMIT u4"; base_s = 379.519185536; canary_overhead_s = 752.1359013; estimate_s = 1132 }
            [ordered]@{ name = "P0 EXCHANGE-RATE"; probe_sum_s = 2334.648721088813; load_s = 62.53344480012311; canary_overhead_s = 752.1359013; estimate_s = 3150 }
        )
    }
    $Cells = @(
        @{
            Name = "RESIDENT-LIMIT u4"; Kind = "resident"; EstimateS = 1132
            Arm = "gpu_only_u4"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        },
        @{
            Name = "P0 EXCHANGE-RATE"; Kind = "exchange"; EstimateS = 3150
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        }
    )
} elseif ($Profile -eq "p0-v2") {
    # P0-v2 only. u4 already ran and is not repeated.
    # Q-TIER-CLEAN has a prereg and no rehearsed launcher, so it is not a cell.
    # Probe sum 2344.074677643949 s from the d4f66bbc walls and the warm
    # serial bound, plus 12 * 5.211120400010259 s model load, plus canary
    # overhead 752.1359013 s = 3158.7440237440724 s. Next whole second 3159.
    # 3159 is below the 7200 s window.
    $script:EstimateDerivation = [ordered]@{
        formula = "estimate_s = probe_sum_s + load_s + canary_overhead_s, then the next whole second"
        note = "P0-v2 is 3159 s, which is below 7200 s. u4 is not in this profile."
        source_run_id = "d4f66bbc-3e50-4957-b5cb-85b7175a47a7"
        probe_sum_s = 2344.074677643949
        load_s = 62.53344480012311
        canary_overhead_s = 752.1359013
        sum_before_rounding_s = 3158.7440237440724
        cells = @(
            [ordered]@{ name = "P0-V2 EXCHANGE-RATE"; probe_sum_s = 2344.074677643949; load_s = 62.53344480012311; canary_overhead_s = 752.1359013; estimate_s = 3159 }
        )
    }
    $Cells = @(
        @{
            Name = "P0-V2 EXCHANGE-RATE"; Kind = "exchange"; EstimateS = 3159
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        }
    )
} elseif ($Profile -eq "p1-a0") {
    # P1 boot 1 is A0 only. Arm smokes are tools/launch_p1_preflight.ps1,
    # before the cold reboot. This boot's first GPU work is idle calibration.
    # Generate 4055.8199962596073 s + one pipeline load 5.211120400010259 s
    # + canary overhead 752.1359013 s = 4813.167017959617 s. Next whole second 4814.
    # 4814 is below the 7200 s window. Later arms are separate boots.
    $script:EstimateDerivation = [ordered]@{
        formula = "estimate_s = generate_s + load_s + canary_overhead_s, then the next whole second"
        note = "P1 A0 is 4814 s, which is below 7200 s. Arm smokes run in the preflight, before reboot."
        source_run_id = "ac4e5472-76a9-4999-bf0b-8274d27ce0ca"
        ledger_run_id = "d482c621-4292-4281-b6a1-8635e5eeb6da"
        generate_s = 4055.8199962596073
        load_s = 5.211120400010259
        canary_overhead_s = 752.1359013
        sum_before_rounding_s = 4813.167017959617
        cells = @(
            [ordered]@{ name = "P1 A0"; generate_s = 4055.8199962596073; load_s = 5.211120400010259; canary_overhead_s = 752.1359013; estimate_s = 4814 }
        )
    }
    $Cells = @(
        @{
            Name = "P1 A0"; Kind = "p1"; EstimateS = 4814
            Arm = "A0"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        }
    )
} elseif ($Profile -eq "p1-a4") {
    # Next P1 boot after A0. One registered half of one A4 seed.
    # Default is seed 20260930, entries [:100].
    # Estimates are the amendment-3 next whole second: first half 4500 s,
    # second half 3898 s. Both are below the 7200 s window. This script
    # does not open the amendment file.
    if ($P1Seed -ne 20260930 -and $P1Seed -ne 20261001) {
        throw "REFUSED -- P1 A4 seed $P1Seed is not registered"
    }
    if ($P1EntryOffset -eq 0 -and $P1EntryCount -eq 100) {
        $p1Estimate = 4500
    } elseif ($P1EntryOffset -eq 100 -and $P1EntryCount -eq 100) {
        $p1Estimate = 3898
    } else {
        throw "REFUSED -- P1 A4 entry window offset=$P1EntryOffset count=$P1EntryCount is not a registered half"
    }
    $script:EstimateDerivation = [ordered]@{
        formula = "amendment 3 next whole second of the capped thinking half plus load plus canary overhead"
        note = "Schedule is A4, then A5, then A2, then A3, then bounded A1. A4 thinking uses the greedy stream, the remaining-time token cap, and the think-block strip."
        seed = $P1Seed
        entry_offset = $P1EntryOffset
        entry_count = $P1EntryCount
        estimate_s = $p1Estimate
    }
    $Cells = @(
        @{
            Name = "P1 A4"; Kind = "p1"; EstimateS = $p1Estimate
            Arm = "A4"; Seed = $P1Seed
            EntryOffset = $P1EntryOffset; EntryCount = $P1EntryCount
            Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        }
    )
} elseif ($Profile -eq "p1-a5") {
    # Next P1 boot after A4. One registered half of one A5 seed.
    # Default is seed 20260930, entries [:100].
    # First-half entry walls from A0 run 8a529053 sum to 2133.4399603999987 s.
    # Second half sums to 2029.0370704000024 s. Eligible pre-execution failures
    # in those halves are 25 and 19. Each adds the A2-minus-A0 generate gap
    # per closeout empty trajectory, 3.9987001860672735 s. Load is
    # 5.211120400010259 s and canary overhead is 752.1359013 s. Next whole
    # second is 2991 s and 2863 s. Both are below the 7200 s window.
    # This script does not open the amendment file.
    if ($P1Seed -ne 20260930 -and $P1Seed -ne 20261001) {
        throw "REFUSED -- P1 A5 seed $P1Seed is not registered"
    }
    if ($P1EntryOffset -eq 0 -and $P1EntryCount -eq 100) {
        $p1Estimate = 2991
    } elseif ($P1EntryOffset -eq 100 -and $P1EntryCount -eq 100) {
        $p1Estimate = 2863
    } else {
        throw "REFUSED -- P1 A5 entry window offset=$P1EntryOffset count=$P1EntryCount is not a registered half"
    }
    $script:EstimateDerivation = [ordered]@{
        formula = "A0 half wall plus one A2-sized extra sample per eligible entry, plus load, plus canary overhead, then the next whole second"
        note = "Schedule is A4, then A5, then A2, then A3, then bounded A1. A5 checks the greedy call before execution and decodes again only inside the remaining time."
        seed = $P1Seed
        entry_offset = $P1EntryOffset
        entry_count = $P1EntryCount
        estimate_s = $p1Estimate
    }
    $Cells = @(
        @{
            Name = "P1 A5"; Kind = "p1"; EstimateS = $p1Estimate
            Arm = "A5"; Seed = $P1Seed
            EntryOffset = $P1EntryOffset; EntryCount = $P1EntryCount
            Model = "configs\models\Qwen3-4B-int4-ov.yaml"
        }
    )
} elseif ($Profile -eq "p1-a1") {
    # One registered half of one A1 seed. Default is seed 20260930, entries [:100].
    # Estimates are amendment 3: first half 4377 s, second half 4109 s.
    if ($P1Seed -ne 20260930 -and $P1Seed -ne 20261001) {
        throw "REFUSED -- P1 A1 seed $P1Seed is not registered"
    }
    if ($P1EntryOffset -eq 0 -and $P1EntryCount -eq 100) {
        $p1Estimate = 4377
    } elseif ($P1EntryOffset -eq 100 -and $P1EntryCount -eq 100) {
        $p1Estimate = 4109
    } else {
        throw "REFUSED -- P1 A1 entry window offset=$P1EntryOffset count=$P1EntryCount is not a registered half"
    }
    $script:EstimateDerivation = [ordered]@{
        formula = "amendment 3 next whole second of the half generate wall plus load plus canary overhead"
        note = "A1 is two halves because one seed over 200 entries does not fit in 7200 s."
        source = "derived/h1_hybrid/LOCAL_QUALITY_AMENDMENT_3.json"
        seed = $P1Seed
        entry_offset = $P1EntryOffset
        entry_count = $P1EntryCount
        estimate_s = $p1Estimate
    }
    $Cells = @(
        @{
            Name = "P1 A1"; Kind = "p1"; EstimateS = $p1Estimate
            Arm = "A1"; Seed = $P1Seed
            EntryOffset = $P1EntryOffset; EntryCount = $P1EntryCount
            Model = "configs\models\Qwen3-4B-int4-ov.yaml"
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
    $bandPy = Join-Path $root "tools\t2s_control_band.py"
    $bandJson = & $PythonExe $bandPy --print-band
    if ($LASTEXITCODE -ne 0) { throw "REFUSED -- control band derivation failed" }
    $script:ControlBand = $bandJson | ConvertFrom-Json
    $controlEstimate = [int]$script:ControlBand.estimate_s
    $script:UncoldReason = [string]$script:ControlBand.noreboot_reason
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
            [ordered]@{ name = "T2S 4B-int4 GPU f16 control"; reference_run_id = [string]$script:ControlBand.reference_run_id; n = 18687; repeats = 3; base_s = $script:ControlBand.base_s; canary_overhead_s = $script:ControlBand.canary_overhead_s; estimate_s = $controlEstimate; formula = [string]$script:ControlBand.estimate_formula }
            [ordered]@{ name = "T2S 4B-int4 GPU u8"; base_run_id = "5c714535-9f36-4614-a594-698b6cd09296"; base_s = 520; canary_overhead_s = 752.1359013; estimate_s = 1273 }
            [ordered]@{ name = "T2S 8B-int4 GPU u8"; base_run_id = "051d2681-4bb8-4f50-b9fc-b14441359ba6"; base_s = 570; canary_overhead_s = 752.1359013; estimate_s = 1323 }
        )
    }
    $Cells = @(
        @{
            Name = "T2S 4B-int4 GPU f16 control"; Kind = "control"; EstimateS = $controlEstimate
            Arm = "gpu_only_f16"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
            FixedN = 18687
        },
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
        $prior = @(Select-BootPriorCells -Existing $existing -BootId $script:BootId)
    }
    $doc = [ordered]@{
        boot_id = $script:BootId
        state = $State
        reason = $Reason
        last_run_id = $script:LastRunId
        window_s = $WindowS
        uptime_s = Get-ColdUptimeSeconds
        estimate_derivation = $script:EstimateDerivation
        cells = @(Merge-BootCells -Prior $prior -Added $script:Rows)
    }
    if ($null -ne $script:ForeignQueueEvidence) {
        $doc.foreign_queue_evidence = @($script:ForeignQueueEvidence)
        $doc.watchdog_log_missing = [bool]$script:WatchdogLogMissing
    }
    if ($Profile -eq "t2s-boot1" -and $WatchdogLog) {
        $doc.watchdog_log = [string]$WatchdogLog
    }
    if ($Rehearsal) { $doc.rehearsal = $true }
    if ($NoRebootDeviation) {
        $doc.deviation = [ordered]@{
            kind = "UNCOLD_UPTIME"
            uptime_s = Get-ColdUptimeSeconds
            reason = [string]$script:UncoldReason
        }
    }
    if ($null -ne $script:LastWshClear) {
        $doc.workloads_session_host = $script:LastWshClear
    }
    Write-Utf8NoBom -Path $SummaryPath -Text ($doc | ConvertTo-Json -Depth 8)
    Assert-PythonReadsJson -Path $SummaryPath
}

function Add-Row {
    param($Cell, [string]$Status, [string]$RunId, [string]$Detail)
    $row = [ordered]@{
        name = $Cell.Name
        status = $Status
        run_id = $RunId
        estimate_s = $Cell.EstimateS
        detail = $Detail
    }
    if ($script:CellStartedUtc) {
        $row.started_utc = $script:CellStartedUtc
        $row.ended_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    }
    if ($null -ne $script:LastWshClear) {
        $row.workloads_session_host = $script:LastWshClear
    }
    # An ordered dictionary has no PSObject .name, so Merge-BootCells would drop it.
    $script:Rows += [pscustomobject]$row
    Save-BootSummary -State "running"
}

function Assert-T2sOwnedWorkers {
    if ($Profile -ne "t2s-boot1") { return }
    $checker = Join-Path $root "tools\t2s_queue_watchdog.py"
    $out = & $PythonExe $checker cell-check --root-pid $PID
    if ($LASTEXITCODE -ne 0) {
        $text = ($out | ForEach-Object { "$_" }) -join " "
        if (-not $text) { $text = "REFUSED -- foreign python or llama-server" }
        throw $text
    }
}

function Update-T2sForeignEvidence {
    if ($Profile -ne "t2s-boot1" -or $DryRun) { return }
    if (-not $script:RunStartedUtc) { return }
    $ended = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    $payload = [ordered]@{
        log_path = [string]$WatchdogLog
        started_utc = $script:RunStartedUtc
        ended_utc = $ended
        repo_root = $root
        cells = @($script:Rows)
    }
    $checker = Join-Path $root "tools\t2s_queue_watchdog.py"
    $tmp = Join-Path $env:TEMP "t2s_watchdog_payload.json"
    Write-Utf8NoBom -Path $tmp -Text ($payload | ConvertTo-Json -Depth 6)
    $raw = & $PythonExe $checker apply-summary --payload $tmp
    if ($LASTEXITCODE -ne 0) {
        throw "REFUSED -- watchdog evidence apply failed"
    }
    $doc = ($raw | Out-String) | ConvertFrom-Json
    $script:Rows = @($doc.cells)
    $lines = @()
    if ($null -ne $doc.foreign_queue_evidence) {
        $lines = @($doc.foreign_queue_evidence)
    }
    $script:ForeignQueueEvidence = $lines
    $missing = $doc.PSObject.Properties["watchdog_log_missing"]
    if ($null -ne $missing) { $script:WatchdogLogMissing = [bool]$missing.Value }
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

function Assert-PythonReadsJson {
    param([string]$Path)
    if ($Path -match "sealed_") { throw "REFUSED -- Python handoff targets a sealed path: $Path" }
    if ($Rehearsal) {
        $full = [System.IO.Path]::GetFullPath($Path)
        $launchRoot = [System.IO.Path]::GetFullPath($LaunchDir)
        $temp = [System.IO.Path]::GetFullPath($env:TEMP)
        $underLaunch = $full.StartsWith($launchRoot, [System.StringComparison]::OrdinalIgnoreCase)
        $underTemp = $full.StartsWith($temp, [System.StringComparison]::OrdinalIgnoreCase)
        if (-not $underLaunch -and -not $underTemp) {
            throw "REFUSED -- rehearsal JSON is outside _rehearsal: $full"
        }
    }
    & $PythonExe (Join-Path $root "tools\read_json_utf8.py") $Path
    if ($LASTEXITCODE -ne 0) { throw "REFUSED -- Python could not read $Path" }
}

function Invoke-BootGates {
    param([string]$Label, [switch]$ReportOnly, [switch]$UptimeReportOnly)
    if ($Rehearsal) {
        $probeDir = Join-Path $LaunchDir "gate_probes"
    } else {
        $probeDir = Join-Path $root "derived\_gate_probes"
    }
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
        $gateArgs = @("-m", "seam.measurement_gates", "--repo-root", $root, "--json")
        if ($NoRebootDeviation) { $gateArgs += "--skip-uptime" }
        $output = & $PythonExe @gateArgs 2>&1
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
    $jsonText = $text
    $start = $text.IndexOf("{")
    $end = $text.LastIndexOf("}")
    if ($start -ge 0 -and $end -gt $start) {
        $jsonText = $text.Substring($start, $end - $start + 1)
    }
    Write-Utf8NoBom -Path $outJson -Text $jsonText
    Assert-PythonReadsJson -Path $outJson
    if ($UptimeReportOnly) {
        $parsed = Get-Content -LiteralPath $outJson -Raw -Encoding utf8 | ConvertFrom-Json
        $failed = @($parsed.gates | Where-Object { -not $_.passed })
        $other = @($failed | Where-Object { $_.name -ne "uptime" })
        $up = @($parsed.gates | Where-Object { $_.name -eq "uptime" })
        if ($up.Count -gt 0) {
            Write-Host ("uptime_gate=report_only passed={0} reason={1}" -f $up[0].passed, $up[0].reason)
        }
        if ($other.Count -gt 0) {
            throw "REFUSED -- measurement gates failed (exit $code)"
        }
        return
    }
    if ($code -ne 0) { throw "REFUSED -- measurement gates failed (exit $code)" }
}

function Invoke-CellPreamble {
    param([string]$Label, [switch]$SkipGateFile)
    Write-Host ""
    Write-Host ("=== preamble {0} ===" -f $Label)
    Clear-WorkloadsSessionHost | Out-Null
    # DET-PROBE checks a clean tree before it takes .locks/machine.lock.
    # A gate JSON written here would make that check fail.
    # Rehearsal still runs the gates: uptime is report-only, the others refuse.
    if ($Rehearsal) {
        Invoke-BootGates -Label $Label -UptimeReportOnly
    } elseif (-not $SkipGateFile) {
        Invoke-BootGates -Label $Label
    }
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
    if ($NoRebootDeviation) {
        $env:SEAM_NOREBOOT_DEVIATION = "1"
        $env:SEAM_NOREBOOT_UPTIME_S = [string](Get-ColdUptimeSeconds)
    }
    $fixed = Get-BootCellField -Cell $Cell -Name "FixedN"
    $workerArgs = @(
        "-u", $WorkerPy,
        "--session-id", $sid,
        "--out", $out,
        "--model-spec", $model,
        "--arms", $Cell.Arm,
        "--criterion", "ttft_slo",
        "--slo-s", "10",
        "--repeats", "3",
        "--watchdog-interval-s", "60"
    )
    if ($fixed) {
        $workerArgs += @("--fixed-n", [string]$fixed)
    } else {
        $workerArgs += @(
            "--low", [string]$Cell.Low,
            "--high", [string]$Cell.High,
            "--resolution", "250"
        )
    }
    $workerLines = New-Object System.Collections.Generic.List[string]
    & $PythonExe @workerArgs 2>&1 | ForEach-Object {
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
    $fixed = Get-BootCellField -Cell $Cell -Name "FixedN"
    $kv = Get-BootCellField -Cell $Cell -Name "ExpectKvReadback"
    if ($kind -eq "det") {
        $args = @($PythonExe, "-u", $DetPy)
        if ($arm) { $args += @("--arm", $arm) }
        return [ordered]@{
            kind = $kind; arm = $arm; model = $model; low = $low; high = $high
            expect_kv = $kv; command = ($args -join " ")
        }
    }
    if ($kind -eq "p1") {
        $args = @($PythonExe, "-u", $P1Py, "--arm", $arm)
        $seed = Get-BootCellField -Cell $Cell -Name "Seed"
        $offset = Get-BootCellField -Cell $Cell -Name "EntryOffset"
        $count = Get-BootCellField -Cell $Cell -Name "EntryCount"
        if ($null -ne $seed) { $args += @("--seed", [string]$seed) }
        if ($null -ne $offset) { $args += @("--entry-offset", [string]$offset) }
        if ($null -ne $count) { $args += @("--entry-count", [string]$count) }
        $smokeArgs = @($PythonExe, "-u", $P1Py, "--canary-calibrate")
        return [ordered]@{
            kind = $kind; arm = $arm; model = $model; low = $low; high = $high
            expect_kv = $kv; command = ($args -join " "); smoke = ($smokeArgs -join " ")
        }
    }
    if ($kind -eq "exchange") {
        $modelPath = Join-Path $root $model
        $args = @($PythonExe, "-u", $ExchangePy, "--model-spec", $modelPath)
        $smokeArgs = @($PythonExe, "-u", $ExchangePy, "--smoke", "--model-spec", $modelPath)
        return [ordered]@{
            kind = $kind; arm = $arm; model = $model; low = $low; high = $high
            expect_kv = $kv; command = ($args -join " "); smoke = ($smokeArgs -join " ")
        }
    }
    if ($kind -eq "warm" -or $kind -eq "decode" -or $kind -eq "resident") {
        $script = $WarmPy
        if ($kind -eq "decode") { $script = $DecodePy }
        if ($kind -eq "resident") { $script = $ResidentPy }
        $modelPath = Join-Path $root $model
        $args = @($PythonExe, "-u", $script, "--arm", $arm, "--model-spec", $modelPath)
        if ($kind -eq "decode") {
            $args += @("--n", "2000,4000,8000")
            $model2 = Get-BootCellField -Cell $Cell -Name "Model2"
            if ($model2) { $args += @("--model-spec", (Join-Path $root $model2)) }
        }
        $smokeArgs = @($PythonExe, "-u", $script, "--smoke", "--arm", $arm, "--model-spec", $modelPath)
        return [ordered]@{
            kind = $kind; arm = $arm; model = $model; low = $low; high = $high
            expect_kv = $kv; command = ($args -join " "); smoke = ($smokeArgs -join " ")
        }
    }
    $modelPath = Join-Path $root $model
    $smoke = @(
        $PythonExe, "-u", $SmokePy, "--out", "<cell>\extraction_smoke",
        "--model-spec", $modelPath, "--n-tokens", "64", "--arm", "gpu_only_f16"
    ) -join " "
    $workerParts = @(
        $PythonExe, "-u", $WorkerPy,
        "--session-id", "<new>", "--out", "<cell>",
        "--model-spec", $modelPath, "--arms", $arm,
        "--criterion", "ttft_slo", "--slo-s", "10"
    )
    if ($fixed) {
        $workerParts += @("--fixed-n", [string]$fixed, "--repeats", "3", "--watchdog-interval-s", "60")
    } else {
        $workerParts += @(
            "--low", $low, "--high", $high,
            "--resolution", "250", "--repeats", "3", "--watchdog-interval-s", "60"
        )
    }
    $worker = $workerParts -join " "
    return [ordered]@{
        kind = $kind; arm = $arm; model = $model; low = $low; high = $high
        expect_kv = $kv; command = $worker; smoke = $smoke
    }
}

function Assert-Boot4Bodies {
    $mark = "measurement body is not started"
    $paths = @($WarmPy, $DecodePy)
    if ($env:SEAM_BOOT4_STUB_FIXTURE) { $paths += $env:SEAM_BOOT4_STUB_FIXTURE }
    foreach ($p in $paths) {
        if (-not (Test-Path -LiteralPath $p)) { throw "REFUSED -- runner missing: $p" }
        $text = Get-Content -LiteralPath $p -Raw
        if ($text.Contains($mark)) { throw "REFUSED -- stub measurement body: $p" }
    }
}

function Invoke-BootCommandLine {
    param([string]$CommandLine)
    if ($env:SEAM_BOOT_SMOKE_STUB -eq "1") {
        Write-Host ("smoke_stub {0}" -f $CommandLine)
        $global:LASTEXITCODE = 0
        return
    }
    $parts = @($CommandLine -split " ")
    & $parts[0] @($parts | Select-Object -Skip 1)
}

function Invoke-HangFaultProbe {
    if ($Profile -ne "resident-limit-2" -or -not $Rehearsal) { return }
    $cmd = "$PythonExe -u -m seam.tools.hang_fault_injection"
    if ($DryRun) {
        Write-Host ("hang_probe_planned {0}" -f $cmd)
        return
    }
    if ($env:SEAM_BOOT_SMOKE_STUB -eq "1") {
        Write-Host "hang_probe_stub"
        return
    }
    Write-Host ("hang_probe_run {0}" -f $cmd)
    & $PythonExe -u -m seam.tools.hang_fault_injection
    if ($LASTEXITCODE -ne 0) {
        throw "REFUSED -- hang fault injection failed"
    }
}

function Invoke-P1Budget {
    if ($Profile -ne "p1-a0" -and $Profile -ne "p1-a1" -and $Profile -ne "p1-a4" -and $Profile -ne "p1-a5") { return }
    $mark = "measurement body is not started"
    if (-not (Test-Path -LiteralPath $P1Py)) { throw "REFUSED -- runner missing: $P1Py" }
    $text = Get-Content -LiteralPath $P1Py -Raw
    if ($text.Contains($mark)) { throw "REFUSED -- stub measurement body: $P1Py" }
    $sum = 0
    foreach ($cell in $Cells) { $sum += [int]$cell.EstimateS }
    $fits = "false"
    if ($sum -le $WindowS) { $fits = "true" }
    $label = "p1_a0_estimate_sum_s"
    if ($Profile -eq "p1-a1") { $label = "p1_a1_estimate_s" }
    if ($Profile -eq "p1-a4") { $label = "p1_a4_estimate_s" }
    if ($Profile -eq "p1-a5") { $label = "p1_a5_estimate_s" }
    Write-Host ("{0}={1} window_s={2} fits_one_window={3}" -f $label, $sum, $WindowS, $fits)
    if ($fits -eq "false") {
        throw "REFUSED -- $Profile estimate sum $sum s exceeds window $WindowS s; split the profile before starting"
    }
}

function Invoke-ResidentLimitSmokes {
    if ($Profile -ne "resident-limit" -and $Profile -ne "resident-limit-2" -and $Profile -ne "p0-v2") { return }
    $mark = "measurement body is not started"
    if ($Profile -eq "resident-limit" -or $Profile -eq "resident-limit-2") {
        if (-not (Test-Path -LiteralPath $ResidentPy)) { throw "REFUSED -- runner missing: $ResidentPy" }
        $text = Get-Content -LiteralPath $ResidentPy -Raw
        if ($text.Contains($mark)) { throw "REFUSED -- stub measurement body: $ResidentPy" }
    }
    if ($Profile -eq "resident-limit-2" -or $Profile -eq "p0-v2") {
        if (-not (Test-Path -LiteralPath $ExchangePy)) { throw "REFUSED -- runner missing: $ExchangePy" }
        $exchangeText = Get-Content -LiteralPath $ExchangePy -Raw
        if ($exchangeText.Contains($mark)) { throw "REFUSED -- stub measurement body: $ExchangePy" }
    }
    $sum = 0
    foreach ($cell in $Cells) { $sum += [int]$cell.EstimateS }
    $fits = "false"
    if ($sum -le $WindowS) { $fits = "true" }
    if ($Profile -eq "p0-v2") {
        Write-Host ("p0_v2_estimate_sum_s={0} window_s={1} fits_one_window={2}" -f $sum, $WindowS, $fits)
    } else {
        Write-Host ("resident_limit_estimate_sum_s={0} window_s={1} fits_one_window={2}" -f $sum, $WindowS, $fits)
    }
    if ($fits -eq "false") {
        throw "REFUSED -- $Profile estimate sum $sum s exceeds window $WindowS s; split the profile before starting"
    }
    Invoke-HangFaultProbe
    foreach ($cell in $Cells) {
        $built = Get-BootCellCommand -Cell $cell
        if ($DryRun) {
            Write-Host ("smoke_planned {0} {1}" -f $cell.Name, $built.smoke)
            continue
        }
        Write-Host ("smoke_run {0}" -f $built.smoke)
        Invoke-BootCommandLine -CommandLine $built.smoke
        if ($LASTEXITCODE -ne 0) {
            $script:FinalState = "refused"
            $script:FinalReason = "REFUSED -- smoke failed: $($cell.Name) exit=$LASTEXITCODE"
            Save-BootSummary -State "refused" -Reason $script:FinalReason
            Write-Host $script:FinalReason
            exit $LASTEXITCODE
        }
    }
}

function Invoke-Boot4Smokes {
    if ($Profile -ne "boot4") { return }
    Assert-Boot4Bodies
    $sum = 0
    foreach ($cell in $Cells) { $sum += [int]$cell.EstimateS }
    $fits = "false"
    if ($sum -le $WindowS) { $fits = "true" }
    Write-Host ("boot4_estimate_sum_s={0} window_s={1} fits_one_window={2}" -f $sum, $WindowS, $fits)
    if ($fits -eq "false") {
        throw "REFUSED -- boot4 estimate sum $sum s exceeds window $WindowS s; split the profile before starting"
    }
    foreach ($cell in $Cells) {
        $kind = Get-BootCellField -Cell $cell -Name "Kind"
        if ($kind -ne "warm" -and $kind -ne "decode") { continue }
        $built = Get-BootCellCommand -Cell $cell
        if ($DryRun) {
            Write-Host ("smoke_planned {0} {1}" -f $cell.Name, $built.smoke)
            continue
        }
        Write-Host ("smoke_run {0}" -f $built.smoke)
        Invoke-BootCommandLine -CommandLine $built.smoke
        if ($LASTEXITCODE -ne 0) {
            $script:FinalState = "refused"
            $script:FinalReason = "REFUSED -- smoke failed: $($cell.Name) exit=$LASTEXITCODE"
            Save-BootSummary -State "refused" -Reason $script:FinalReason
            Write-Host $script:FinalReason
            exit $LASTEXITCODE
        }
    }
}

function Invoke-BootDryCell {
    param($Cell)
    $name = Get-BootCellField -Cell $Cell -Name "Name"
    $built = Get-BootCellCommand -Cell $Cell
    Write-Host ("dry_run {0} kind={1} arm={2} model={3} low={4} high={5} expect_kv={6}" -f `
        $name, $built.kind, $built.arm, $built.model, $built.low, $built.high, $built.expect_kv)
    if ($built.kind -eq "det" -or $built.kind -eq "warm" -or $built.kind -eq "decode" -or $built.kind -eq "resident" -or $built.kind -eq "exchange" -or $built.kind -eq "p1") {
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
    if ([string]::IsNullOrWhiteSpace($WatchdogLog)) {
        $WatchdogLog = "C:\apu\ovn\watchdog.log"
    }
    $env:SEAM_WATCHDOG_LOG = [string]$WatchdogLog
    Write-Host "platform_id=evo-t2 config=configs/platforms/evo-t2.yaml"
    Write-Host ("watchdog_log={0}" -f $WatchdogLog)
    Write-Host "free_memory_floor_mb=24000 provenance=derived_unmeasured CAP-4-class peak on 64 GB; floor keeps Available at or above 24000 MB"
    Write-Host "onset_s=null onset_status=unknown provenance=not measured on evo-t2"
    Write-Host "canary_onset_s=657 provenance=borrowed from aipc-c1 session 7f569929; recorded on 5c714535 and 051d2681; not an evo-t2 measurement"
    Write-Host "harness affinity_cpus=0,1,2,3 wslock=request:4294967296:12884901888 max_new_tokens=8 source=5c714535/051d2681"
    Write-Host ("control_band {0}" -f $bandJson)
    if ($NoRebootDeviation) {
        $upNow = Get-ColdUptimeSeconds
        Write-Host ("deviation kind=UNCOLD_UPTIME uptime_s={0} reason={1}" -f $upNow, $script:UncoldReason)
        Write-Host "uptime_gate=skipped other_gates=enforced watchdog=enforced machine_lock=enforced canary=must_arm"
    }
    Assert-BootAc
}

Save-BootSummary -State "started"

# Boot 4 has no reboot step. Smokes run before any measurement cell and a
# smoke failure refuses the boot. Dry-run checks the stub mark and prints
# the smoke commands without loading a model.
Invoke-Boot4Smokes
Invoke-ResidentLimitSmokes
Invoke-P1Budget

if ($Profile -eq "t2s-boot1") {
    $script:RunStartedUtc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
}

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
    if ($NoRebootDeviation) {
        $env:SEAM_NOREBOOT_DEVIATION = "1"
        $env:SEAM_NOREBOOT_UPTIME_S = [string]$uptime
        Write-Host ("uptime_gate=skipped deviation=UNCOLD_UPTIME uptime_s={0}" -f $uptime)
    } elseif ($Rehearsal) {
        Write-Host ("uptime_window=report_only remaining_s={0} estimate_s={1}" -f $remaining, $cell.EstimateS)
    } elseif ($remaining -lt [int]$cell.EstimateS) {
        $script:CellStartedUtc = ""
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
        Write-Utf8NoBom -Path $DeferredPath -Text ($defer | ConvertTo-Json -Depth 5)
        Assert-PythonReadsJson -Path $DeferredPath
        $script:FinalState = "deferred"
        $script:FinalReason = "remaining cold-window time is below the next cell estimate"
        Save-BootSummary -State "deferred" -Reason $script:FinalReason
        Write-Host "DEFERRED"
        exit 0
    }

    $script:CellStartedUtc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    try {
        Assert-T2sOwnedWorkers
        Assert-BootAc
        Assert-BootTree | Out-Null
        if ($cell.Kind -eq "det" -or $cell.Kind -eq "warm" -or $cell.Kind -eq "decode" -or $cell.Kind -eq "resident" -or $cell.Kind -eq "exchange" -or $cell.Kind -eq "p1") {
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

    if ($Rehearsal) {
        $built = Get-BootCellCommand -Cell $cell
        if (-not $built.smoke) { throw "REFUSED -- no rehearsal smoke for $($cell.Name)" }
        Write-Host ("rehearsal_cell {0}" -f $built.smoke)
        Invoke-BootCommandLine -CommandLine $built.smoke
        $exit = $LASTEXITCODE
        if ($exit -ne 0) {
            $script:FinalState = "refused"
            $script:FinalReason = "exit=$exit"
            Add-Row -Cell $cell -Status "REFUSED" -RunId "" -Detail $script:FinalReason
            Save-BootSummary -State "refused" -Reason $script:FinalReason
            exit $exit
        }
        Add-Row -Cell $cell -Status "rehearsal_smoke" -RunId "" -Detail "smoke"
        continue
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

    if ($cell.Kind -eq "warm" -or $cell.Kind -eq "decode" -or $cell.Kind -eq "resident" -or $cell.Kind -eq "exchange" -or $cell.Kind -eq "p1") {
        $built = Get-BootCellCommand -Cell $cell
        $statusFile = Join-Path $LaunchDir ("cell-status-{0}.txt" -f $i)
        $env:SEAM_CELL_STATUS_PATH = $statusFile
        if (Test-Path -LiteralPath $statusFile) { Remove-Item -LiteralPath $statusFile -Force }
        Write-Host $built.command
        $parts = @($built.command -split " ")
        & $parts[0] @($parts | Select-Object -Skip 1)
        $exit = $LASTEXITCODE
        Remove-Item Env:SEAM_CELL_STATUS_PATH -ErrorAction SilentlyContinue
        $recorded = Read-CellStatusFile -Path $statusFile
        if ($exit -ne 0) {
            $script:FinalState = "refused"
            $script:FinalReason = "exit=$exit"
            if ($recorded.RunId) { $script:LastRunId = $recorded.RunId }
            Add-Row -Cell $cell -Status "REFUSED" -RunId $recorded.RunId -Detail $script:FinalReason
            Save-BootSummary -State "refused" -Reason $script:FinalReason
            exit $exit
        }
        if ($recorded.RunId) { $script:LastRunId = $recorded.RunId }
        Add-Row -Cell $cell -Status $recorded.Status -RunId $recorded.RunId -Detail ""
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
    if ($cell.Kind -eq "control") {
        $bandPy = Join-Path $root "tools\t2s_control_band.py"
        $verdictRaw = & $PythonExe $bandPy --check-work (Join-Path $ran.Out "work")
        $verdictCode = $LASTEXITCODE
        Write-Host $verdictRaw
        if ($verdictCode -ne 0) {
            $script:LastRunId = $ran.RunId
            $script:FinalState = "CONTROL_FAILED"
            $script:FinalReason = "control median outside 5c714535 median x (1 +/- tol)"
            Add-Row -Cell $cell -Status "CONTROL_FAILED" -RunId $ran.RunId -Detail $verdictRaw
            Save-BootSummary -State "CONTROL_FAILED" -Reason $script:FinalReason
            Write-Host "CONTROL_FAILED"
            exit 1
        }
    }
    $script:LastRunId = $ran.RunId
    Add-Row -Cell $cell -Status "complete" -RunId $ran.RunId -Detail $detail
}
$script:FinalState = "complete"
$script:FinalReason = ""
if ($Rehearsal) { Write-Host "REHEARSAL_COMPLETE" }
} catch {
    $script:FinalState = "crashed"
    $script:FinalReason = $_.Exception.Message
    Write-Host $script:FinalReason
    exit 1
} finally {
    try {
        Update-T2sForeignEvidence
    } catch {
        $script:FinalReason = $_.Exception.Message
        Write-Host $script:FinalReason
    }
    Save-BootSummary -State $script:FinalState -Reason $script:FinalReason
}

Write-Host "BOOT_COMPLETE"
exit 0
