<#
.SYNOPSIS
  SEAM XRT runbook, RTX 4070 laptop: E3 (llama.cpp b11559 CUDA 12.4, Qwen3-4B Q4_K_M).
  Registered: docs/registrations/BR_XRT_2026-10-26.md (P-XRT-7) and BS_XRT_RUNBOOKS_2026-10-26.md.
.DESCRIPTION
  Creates C:\seam_xrt\{bin,models,logs,out,zips} and touches nothing else. Downloads are pinned
  (URL + size + sha256, checked before use; abort on mismatch). No admin, no installs, no Python.
  Resumable: run it again and it continues the last unfinished run (use -NewRun to start over).
  Run:   powershell -ExecutionPolicy Bypass -File .\run.ps1
#>
param(
    [switch]$NewRun,
    [string]$RunId = '',
    [double]$TrialTimeoutS = 1800,
    [string]$Operator = 'Rithwik Sharma',
    [switch]$SelfTest,
    [long]$SelfTestLow = 4096,
    [long]$SelfTestHigh = 65536,
    [long]$SelfTestRes = 1024,
    [long]$SelfTestThreshold = 37000,
    [string]$SelfTestPrior = ''
)

#@@COMMON@@

$MACHINE = 'rtx4070'
$BUILD_DIR = $SEAM_ROOT + '\bin\b11559-cuda-12.4'
$PIN_CUDA = @{
    name = 'llama-b11559-bin-win-cuda-12.4-x64.zip'
    url = 'https://github.com/ggml-org/llama.cpp/releases/download/b11559/llama-b11559-bin-win-cuda-12.4-x64.zip'
    size = [int64]265207128
    sha256 = '4a885b80b26a213e86b774a580ac14fb210eba6220579051339c71b2bda1ecd7'
}
$PIN_CUDART = @{
    name = 'cudart-llama-bin-win-cuda-12.4-x64.zip'
    url = 'https://github.com/ggml-org/llama.cpp/releases/download/b11559/cudart-llama-bin-win-cuda-12.4-x64.zip'
    size = [int64]391443627
    sha256 = '8c79a9b226de4b3cacfd1f83d24f962d0773be79f1e7b75c6af4ded7e32ae1d6'
}
# CUDA 12.4 minimum Windows driver: 551.61 (CUDA 12.4 GA); 12.x minor-version compatibility floor
# 528.33 (NVIDIA CUDA Toolkit release notes, Table 3; LITERATURE).
$DRIVER_MIN = [version]'551.61'
$DRIVER_FLOOR = [version]'528.33'

# E3 cells exactly as registered (RITHWIK_ASKS_2026-10-26 E3): FA off at ubatch 128 / 512 / 2048 with
# KV f16, then FA on at ubatch 512 with f16 and q4_0. Bisection at 1,024; one repeat at the largest
# hold and the first fail (ADDENDUM 1 robust-ceiling rule: >= 2 attempts at the held point).
$CELLS = @(
    @{ id = 'E3_fa0_ub128_f16'; mode = 'prefill'; kv = 'f16'; fa = 'off'; ub = 128; low = 4096; high = 65536; res = 1024; repeats = 1 },
    @{ id = 'E3_fa0_ub512_f16'; mode = 'prefill'; kv = 'f16'; fa = 'off'; ub = 512; low = 4096; high = 65536; res = 1024; repeats = 1 },
    @{ id = 'E3_fa0_ub2048_f16'; mode = 'prefill'; kv = 'f16'; fa = 'off'; ub = 2048; low = 4096; high = 65536; res = 1024; repeats = 1 },
    @{ id = 'E3_fa1_ub512_f16'; mode = 'prefill'; kv = 'f16'; fa = 'on'; ub = 512; low = 4096; high = 65536; res = 1024; repeats = 1 },
    @{ id = 'E3_fa1_ub512_q4_0'; mode = 'prefill'; kv = 'q4_0'; fa = 'on'; ub = 512; low = 8192; high = 196608; res = 1024; repeats = 1 }
)

function Get-NvSmiQuery {
    $q = Invoke-Native 'nvidia-smi' @('--query-gpu=name,driver_version,memory.total,memory.used,memory.free,pstate,temperature.gpu,power.draw', '--format=csv,noheader,nounits')
    return ($q -join "`n")
}

function Invoke-Main {
    New-SeamLayout
    $script:TRANSCRIPT = Join-Path $SEAM_ROOT ('logs\install_' + (Get-Date).ToString('yyyyMMdd_HHmmss') + '.txt')
    Write-Note 'SEAM XRT E3 runbook (RTX 4070). Folder C:\seam_xrt only; no admin; no installs.'

    # 1. driver requirement
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $smi) { Stop-Run 'nvidia-smi not found: the NVIDIA driver is required' }
    $first = (Get-NvSmiQuery).Split("`n")[0]
    $drv = [version](($first.Split(',')[1]).Trim())
    Write-Note ('GPU: ' + $first)
    Write-Note ('DRIVER REQUIREMENT: llama.cpp b11559 CUDA 12.4 build needs NVIDIA driver >= ' + $DRIVER_MIN + ' (floor ' + $DRIVER_FLOOR + '). Found ' + $drv + '.')
    if ($drv -lt $DRIVER_FLOOR) { Stop-Run ('driver ' + $drv + ' is below ' + $DRIVER_FLOOR + '; update the NVIDIA driver first') }
    if ($drv -lt $DRIVER_MIN) {
        $a = Read-Host ('Driver ' + $drv + ' is below ' + $DRIVER_MIN + '. Type YES to try anyway, anything else to stop')
        if ($a -ne 'YES') { Stop-Run 'stopped at the driver check' }
    }

    # 2. pinned downloads
    $exe = Install-Build @($PIN_CUDA, $PIN_CUDART) $BUILD_DIR
    $model = Join-Path $SEAM_ROOT ('models\' + $PIN_GGUF.name)
    Get-PinnedFile $PIN_GGUF $model

    # 3. run id, run folder
    $rid = Resolve-RunId $MACHINE 'E3' $RunId ([bool]$NewRun)
    $runDir = Get-RunDir $rid
    if (-not (Test-Path $runDir)) { [void](New-Item -ItemType Directory -Path $runDir) }
    $script:TRANSCRIPT = Join-Path $runDir 'transcript.txt'
    Write-Note ('RUN ' + $rid + ' -> ' + $runDir)
    Write-RunMeta $runDir ([ordered]@{ run_id = $rid; machine = $MACHINE; part = 'E3'; operator = $Operator
        started = (Get-Date).ToString('o'); script = $PSCommandPath; script_sha256 = (Get-Sha256 $PSCommandPath)
        llama_build = 'b11559 win cuda-12.4 x64'; gguf_sha256 = $PIN_GGUF.sha256; server_exe = $exe
        note = 'Operated by the machine owner from the SEAM pinned runbook; the SEAM authors had no access to this machine.' })

    # 4. Sysmem Fallback pre-flight (we cannot read this setting; the operator confirms it)
    $pre = Join-Path $runDir 'preflight_sysmem_fallback.txt'
    if (-not (Test-Path $pre)) {
        Write-Host ''
        Write-Host 'REQUIRED BEFORE THE RUN (NVIDIA Control Panel, no admin needed):' -ForegroundColor Yellow
        Write-Host '  Manage 3D settings > Program settings > Add > Browse to:'
        Write-Host ('    ' + $exe)
        Write-Host '  then set "CUDA - Sysmem Fallback Policy" = "Prefer No Sysmem Fallback" and Apply.'
        Write-Host '  Without it, VRAM overflow spills into system RAM and the limit becomes a slowdown, not an error.'
        Write-Host ('  Save a screenshot of the setting into ' + $runDir + ' (any name ending .png or .jpg).')
        Write-Host ''
        $ans = Read-Host 'Type CONFIRMED when "Prefer No Sysmem Fallback" is set for that llama-server.exe'
        if ($ans -ne 'CONFIRMED') { Stop-Run 'Sysmem Fallback pre-flight not confirmed' }
        $shots = @(Get-ChildItem -Path $runDir -Include *.png, *.jpg, *.jpeg -Recurse -ErrorAction SilentlyContinue)
        $txt = 'CUDA - Sysmem Fallback Policy = Prefer No Sysmem Fallback for ' + $exe + "`r`n" +
            'confirmed by operator: ' + $Operator + ' at ' + (Get-Date).ToString('o') + "`r`n" +
            'screenshots in run folder: ' + $shots.Count + "`r`n"
        [System.IO.File]::WriteAllText($pre, $txt, $UTF8)
        if ($shots.Count -eq 0) { Write-Note 'WARNING: no screenshot found in the run folder yet; please add one before collect.ps1' }
    }
    Write-Note ('pre-flight: ' + ((Get-Content -Raw $pre) -replace "`r?`n", ' | '))

    # 5. snapshots
    Save-Native 'nvidia-smi' @() (Join-Path $runDir ('nvidia_smi_' + (Get-Date).ToString('yyyyMMdd_HHmmss') + '.txt'))
    Save-Native $exe @('--version') (Join-Path $runDir 'llama_version.txt')
    Save-Native $exe @('--list-devices') (Join-Path $runDir 'list_devices.txt')
    $used = [int](($first.Split(',')[3]).Trim())
    if ($used -gt 600) { Write-Note ('WARNING: ' + $used + ' MiB of VRAM already in use; close other GPU apps (games, browsers with video) and rerun if you can') }

    # 6. cells
    $ctx = @{ machine = $MACHINE; runId = $rid; runDir = $runDir; exe = $exe; model = $model; port = 8091
        timeoutS = $TrialTimeoutS; rowsPath = (Join-Path $runDir 'trials.jsonl'); tokenIds = $null; shareLabel = $null
        vramMiB = [double](($first.Split(',')[2]).Trim()); beforeTrial = $null
        afterTrial = {
            param($row)
            $sum = 0.0
            foreach ($k in @('model', 'kv', 'compute')) {
                if ($row.buffers.Contains($k)) { foreach ($d in $row.buffers[$k].Keys) { if ($d -like 'CUDA*') { $sum += $row.buffers[$k][$d] } } }
            }
            $row['cuda_buffers_mib'] = [math]::Round($sum, 2)
            $row['exceeds_vram'] = ($sum -gt $ctx.vramMiB)
            if ($sum -gt $ctx.vramMiB) { Write-Note ('WARNING: CUDA buffers ' + $sum + ' MiB > VRAM ' + $ctx.vramMiB + ' MiB: Sysmem Fallback may be ON') }
        } }
    Show-Budget $CELLS 90 $TrialTimeoutS
    foreach ($c in $CELLS) {
        [System.IO.File]::AppendAllText((Join-Path $runDir ('nvsmi_before_' + $c.id + '.csv')), (Get-NvSmiQuery) + "`r`n", $UTF8)
        Invoke-Cell $ctx $c
    }
    [System.IO.File]::WriteAllText((Join-Path $runDir 'RUN_DONE.txt'), (Get-Date).ToString('o'), $UTF8)
    Write-Note ('RUN_DONE ' + $rid + '. Next: powershell -ExecutionPolicy Bypass -File .\collect.ps1')
}

if ($SelfTest) { Invoke-SelfTest $SelfTestLow $SelfTestHigh $SelfTestRes $SelfTestThreshold $SelfTestPrior; exit 0 }
try { Invoke-Main | Out-Null; exit 0 }
catch { Write-Note ('FAILED: ' + $_.Exception.Message); exit 1 }
