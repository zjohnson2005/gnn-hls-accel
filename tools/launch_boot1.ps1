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
    [ValidateSet("boot1", "boot2")]
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
$SummaryName = if ($Profile -eq "boot2") { "BOOT2_SUMMARY.json" } else { "BOOT1_SUMMARY.json" }
$DeferredName = if ($Profile -eq "boot2") { "DEFERRED_TO_BOOT3.json" } else { "DEFERRED_TO_BOOT2.json" }
$SummaryPath = Join-Path $LaunchDir $SummaryName
$DeferredPath = Join-Path $LaunchDir $DeferredName
$PythonExe = Join-Path $root ".venv-seam\Scripts\python.exe"
$WorkerPy = Join-Path $root "tools\run_c1_ceiling.py"
$DetPy = Join-Path $root "tools\run_det_probe.py"
$SmokePy = Join-Path $root "tools\c2_extraction_smoke.py"
$SpawnPs1 = Join-Path $root "tools\spawn_detached.ps1"
New-Item -ItemType Directory -Force -Path $LaunchDir | Out-Null

if ($Detach) {
    $self = "`"$PSCommandPath`""
    $cmd = "powershell -NoProfile -File $self -Profile $Profile"
    $log = Join-Path $LaunchDir "boot1.log"
    $json = & $SpawnPs1 -CommandLine $cmd -LogPath $log -WorkingDirectory $root
    Write-Host $json
    Write-Host "launched boot1 detached"
    Write-Host ("  log     : {0}" -f $log)
    Write-Host ("  summary : {0}" -f $SummaryPath)
    exit 0
}

# Boot 2 estimates rescale amendment 1 by the anchor wall 944.242457 / 368.
if ($Profile -eq "boot2") {
    $Cells = @(
        @{
            Name = "XPS 8B-int4 GPU u8"; Kind = "ceiling"; EstimateS = 809
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-8B-int4-ov.yaml"
            Low = 2000; High = 8000
        },
        @{
            Name = "XPS 4B-int8 GPU u8"; Kind = "ceiling"; EstimateS = 868
            Arm = "gpu_only_u8"; Model = "configs\models\Qwen3-4B-int8-ov.yaml"
            Low = 4000; High = 17000
        },
        @{
            Name = "XPS 4B-int4 CPU u8"; Kind = "ceiling"; EstimateS = 5158
            Arm = "A"; Model = "configs\models\Qwen3-4B-int4-ov.yaml"
            Low = 250; High = 2000; ExpectKvReadback = "u8"
        },
        @{
            Name = "DET-PROBE-KV"; Kind = "det"; EstimateS = 3080
            Arm = "gpu_only_f16"
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

function Get-ColdUptimeSeconds {
    $boot = (Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop).LastBootUpTime
    return [int]((Get-Date) - [datetime]$boot).TotalSeconds
}

function Save-BootSummary {
    param([string]$State, [string]$Reason = "")
    $doc = [ordered]@{
        state = $State
        reason = $Reason
        last_run_id = $script:LastRunId
        window_s = $WindowS
        uptime_s = Get-ColdUptimeSeconds
        cells = @($script:Rows)
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
    param([string]$Label)
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
    Set-Content -LiteralPath $outJson -Value $text -Encoding utf8
    Write-Host $text
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
    if ($Cell.Arm) { $detArgs += @("--arm", $Cell.Arm) }
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

function Assert-BootAc {
    $b = @(Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue)
    if ($b.Count -eq 0) { return }
    foreach ($one in $b) {
        if ([int]$one.BatteryStatus -ne 2) {
            throw "REFUSED -- ac: on battery (BatteryStatus=$($one.BatteryStatus))"
        }
    }
}

Save-BootSummary -State "started"

try {
for ($i = 0; $i -lt $Cells.Count; $i++) {
    $cell = $Cells[$i]
    $uptime = Get-ColdUptimeSeconds
    $remaining = $WindowS - $uptime
    Write-Host ("time_check {0}: uptime_s={1} remaining_s={2} estimate_s={3}" -f `
        $cell.Name, $uptime, $remaining, $cell.EstimateS)
    if ($remaining -lt [int]$cell.EstimateS) {
        $left = @()
        for ($j = $i; $j -lt $Cells.Count; $j++) {
            $left += $Cells[$j].Name
            Add-Row -Cell $Cells[$j] -Status "DEFERRED_TO_BOOT2" -RunId "" -Detail "remaining_s=$remaining"
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
        if ($cell.Kind -eq "det") {
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
    if ($cell.ExpectKvReadback) {
        $hit = Get-ChildItem -Path (Join-Path $ran.Out "work") -Filter "*.result.json" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        $normalized = ""
        if ($hit) {
            $doc = Get-Content -LiteralPath $hit.FullName -Raw | ConvertFrom-Json
            $rows = @($doc.kv_cache_precision_readback)
            if ($rows.Count -gt 0 -and $rows[0].readback) {
                $normalized = [string]$rows[0].readback.normalized
            }
        }
        $detail = "$detail kv_readback=$normalized"
        if ($normalized -ne $cell.ExpectKvReadback) {
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
