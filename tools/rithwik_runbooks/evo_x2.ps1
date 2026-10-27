<#
.SYNOPSIS
  SEAM XRT queue job, Strix Halo evo-x2: E5a (default GPU share) and, only when allowed, E5b
  (one share point per job). llama.cpp b11559 Vulkan, Qwen3-4B Q4_K_M.
  Registered: docs/registrations/BS_XRT_RUNBOOKS_2026-10-26.md (E5a/E5b split; P-XRT-8 for E5b).
.DESCRIPTION
  No prompts. Parameters come from environment variables. Exit code 0 = all cells finished
  (a cell that fails at its low rung is a result, not an error); 1 = refused or aborted.
  Writes only under C:\seam_xrt\ (everything of a run under C:\seam_xrt\out\<run_id>\).
  No admin, no installs, no system change, no Python.
  Environment:
    E5_PART            a (default) | b
    E5B_SHARE_OK       must be 1 for E5_PART=b (Rithwik's OK that share changes are fine)
    E5B_SHARE_GB       for E5_PART=b: the GPU share set for this point, typed by the operator (GB)
    E5_ROCM            1 = also run the cells with the b11559 HIP build (only if ROCm/HIP already
                       works on this machine); default 0
    SEAM_RUN_ID        resume this run id (default: the last unfinished run of the same part/share)
    SEAM_NEW_RUN       1 = start a new run even if an unfinished one exists
    SEAM_TRIAL_TIMEOUT_S  per-trial timeout, default 3600
    SEAM_OPERATOR      default 'Rithwik Sharma'
  Run:   powershell -NoProfile -ExecutionPolicy Bypass -File C:\path\to\run.ps1
#>
param(
    [switch]$SelfTest,
    [long]$SelfTestLow = 4096,
    [long]$SelfTestHigh = 65536,
    [long]$SelfTestRes = 1024,
    [long]$SelfTestThreshold = 37000,
    [string]$SelfTestPrior = ''
)

#@@COMMON@@

$MACHINE = 'evo-x2'
$PIN_VULKAN = @{
    name = 'llama-b11559-bin-win-vulkan-x64.zip'
    url = 'https://github.com/ggml-org/llama.cpp/releases/download/b11559/llama-b11559-bin-win-vulkan-x64.zip'
    size = [int64]32084119
    sha256 = 'bf2fb2a7fc5d7669ccabbb6de3f6dd6b54058f213b32e731abc62b590f8566dc'
}
$PIN_ROCM = @{
    name = 'llama-b11559-bin-win-rocm-10.0-x64.zip'
    url = 'https://github.com/ggml-org/llama.cpp/releases/download/b11559/llama-b11559-bin-win-rocm-10.0-x64.zip'
    size = [int64]257958782
    sha256 = '5511af01bbcaa17ebdb21dd7ab8fc8841903f25a3a08c8441ee5a43ec5afb9ab'
}

# E5 cells (BS_XRT_RUNBOOKS_2026-10-26.md section 3). KV f16 and q4_0, FA on, ubatch 512, step 1,024,
# one repeat at the largest hold and the first fail.
#   L cells: largest -c that LOADS (KV and compute buffers are allocated at load). Wide range, so the
#            memory boundary is found even when it lies far above the model window. Fast: no prefill.
#   P cells: largest -c that loads AND prefills n - 64 tokens (the E3 / XRT-1 E2 rule), up to 131,072
#            (Qwen3-4B with YaRN); above that the window and the prefill time bind, not memory.
function Get-E5Cells([string]$suffix) {
    return @(
        @{ id = 'E5_L_f16' + $suffix; mode = 'load'; kv = 'f16'; fa = 'on'; ub = 512; low = 4096; high = 4194304; res = 1024; repeats = 1 },
        @{ id = 'E5_L_q4_0' + $suffix; mode = 'load'; kv = 'q4_0'; fa = 'on'; ub = 512; low = 8192; high = 4194304; res = 1024; repeats = 1 },
        @{ id = 'E5_P_f16' + $suffix; mode = 'prefill'; kv = 'f16'; fa = 'on'; ub = 512; low = 4096; high = 131072; res = 1024; repeats = 1 },
        @{ id = 'E5_P_q4_0' + $suffix; mode = 'prefill'; kv = 'q4_0'; fa = 'on'; ub = 512; low = 8192; high = 131072; res = 1024; repeats = 1 }
    )
}

function Get-EnvOr([string]$name, [string]$default) {
    $v = [Environment]::GetEnvironmentVariable($name)
    if ([string]::IsNullOrEmpty($v)) { return $default }
    return $v
}

function Write-SystemSnapshot([string]$runDir, [string]$exe) {
    $f = Join-Path $runDir 'system_at_start.txt'
    $os = Get-CimInstance Win32_OperatingSystem
    $lines = @('os: ' + $os.Caption + ' ' + $os.Version + ' build ' + $os.BuildNumber,
        'ram_total_bytes: ' + (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory,
        'ram_free_kib: ' + $os.FreePhysicalMemory)
    foreach ($g in @(Get-CimInstance Win32_VideoController)) {
        $lines += ('gpu: ' + $g.Name + ' driver ' + $g.DriverVersion + ' date ' + $g.DriverDate + ' AdapterRAM ' + $g.AdapterRAM)
    }
    [System.IO.File]::WriteAllText($f, ($lines -join "`r`n") + "`r`n", $UTF8)
    Save-Native $exe @('--version') (Join-Path $runDir 'llama_version.txt')
    Save-Native $exe @('--list-devices') (Join-Path $runDir 'list_devices.txt')
}

function Invoke-Main {
    New-SeamLayout
    $script:TRANSCRIPT = Join-Path $SEAM_ROOT ('logs\job_' + (Get-Date).ToString('yyyyMMdd_HHmmss') + '.txt')
    $part = (Get-EnvOr 'E5_PART' 'a').ToLower()
    $timeoutS = [double](Get-EnvOr 'SEAM_TRIAL_TIMEOUT_S' '3600')
    $operator = Get-EnvOr 'SEAM_OPERATOR' 'Rithwik Sharma'
    $rocm = (Get-EnvOr 'E5_ROCM' '0') -eq '1'
    $shareLabel = 'default'
    if ($part -eq 'b') {
        if ((Get-EnvOr 'E5B_SHARE_OK' '0') -ne '1') { Stop-Run 'E5_PART=b needs E5B_SHARE_OK=1 (share changes approved by Rithwik)' }
        $gb = Get-EnvOr 'E5B_SHARE_GB' ''
        if ($gb -notmatch '^[0-9]+(\.[0-9]+)?$') { Stop-Run 'E5_PART=b needs E5B_SHARE_GB=<GPU share in GB as set for this point>' }
        $shareLabel = $gb + 'GB'
    } elseif ($part -ne 'a') { Stop-Run ('E5_PART must be a or b, got ' + $part) }
    Write-Note ('SEAM XRT E5' + $part + ' job (evo-x2), share ' + $shareLabel + '. Folder C:\seam_xrt only.')

    $vk = Install-Build @($PIN_VULKAN) (Join-Path $SEAM_ROOT 'bin\b11559-vulkan')
    $builds = @(@{ name = 'vulkan'; exe = $vk; suffix = '' })
    if ($rocm) { $builds += @{ name = 'rocm'; exe = (Install-Build @($PIN_ROCM) (Join-Path $SEAM_ROOT 'bin\b11559-rocm')); suffix = '_rocm' } }
    $model = Join-Path $SEAM_ROOT ('models\' + $PIN_GGUF.name)
    Get-PinnedFile $PIN_GGUF $model

    $partKey = 'E5' + $part + '_' + $shareLabel
    $rid = Resolve-RunId $MACHINE $partKey (Get-EnvOr 'SEAM_RUN_ID' '') ((Get-EnvOr 'SEAM_NEW_RUN' '0') -eq '1')
    $runDir = Get-RunDir $rid
    if (-not (Test-Path $runDir)) { [void](New-Item -ItemType Directory -Path $runDir) }
    $script:TRANSCRIPT = Join-Path $runDir 'transcript.txt'
    Write-Note ('RUN ' + $rid + ' -> ' + $runDir)
    Write-RunMeta $runDir ([ordered]@{ run_id = $rid; machine = $MACHINE; part = $partKey; share_label = $shareLabel
        operator = $operator; started = (Get-Date).ToString('o'); script = $PSCommandPath
        script_sha256 = (Get-Sha256 $PSCommandPath); llama_build = 'b11559 win vulkan x64' + $(if ($rocm) { ' + rocm-10.0' } else { '' })
        gguf_sha256 = $PIN_GGUF.sha256
        note = 'Run as a queue job by the machine owner from the SEAM pinned runbook; the SEAM authors had no access to this machine.' })
    Write-SystemSnapshot $runDir $vk
    $others = @(Get-Process -Name llama-server -ErrorAction SilentlyContinue)
    if ($others.Count -gt 0) { Stop-Run ('another llama-server is running (pid ' + (($others | ForEach-Object { $_.Id }) -join ',') + '); no other GPU job may run concurrently') }

    $all = @()
    foreach ($b in $builds) { $all += Get-E5Cells $b.suffix }
    Show-Budget $all 120 $timeoutS
    foreach ($b in $builds) {
        $ctx = @{ machine = $MACHINE; runId = $rid; runDir = $runDir; exe = $b.exe; model = $model; port = 8092
            timeoutS = $timeoutS; rowsPath = (Join-Path $runDir 'trials.jsonl'); tokenIds = $null
            shareLabel = $shareLabel; beforeTrial = $null; afterTrial = $null }
        foreach ($c in (Get-E5Cells $b.suffix)) { Invoke-Cell $ctx $c }
    }
    [System.IO.File]::WriteAllText((Join-Path $runDir 'RUN_DONE.txt'), (Get-Date).ToString('o'), $UTF8)
    Write-Note ('RUN_DONE ' + $rid + '. Next: powershell -NoProfile -ExecutionPolicy Bypass -File collect.ps1')
}

if ($SelfTest) { Invoke-SelfTest $SelfTestLow $SelfTestHigh $SelfTestRes $SelfTestThreshold $SelfTestPrior; exit 0 }
try { Invoke-Main | Out-Null; exit 0 }
catch { Write-Note ('FAILED: ' + $_.Exception.Message); exit 1 }
