# ---------------------------------------------------------------- common.ps1 (Task BS)
# Shared core for the Rithwik runbooks (RTX 4070 E3, evo-x2 E5a/E5b). Built into each run.ps1 by
# tools/build_rithwik_runbooks.py; do not edit the built copies. Windows PowerShell 5.1 compatible,
# no admin, standard library only. Mirrors tools/xrt_llamacpp.py (Task BR): same server flags, same
# prompt rule (n - 64 tokens tiled from one /tokenize call), same hold rule, same bisection
# (bisect_plan: low first, then high, then grid midpoints; each rung once).

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version 2.0

$SEAM_ROOT = 'C:\seam_xrt'
$PROMPT_MARGIN = 64
$PARAGRAPH = 'The survey team walked the river valley at dawn, counting stones along the old wall and ' +
    'writing each number in a small notebook. By noon they had mapped the mill, the bridge and ' +
    'the two farms on the north bank, and they rested under the oak trees while the cart was ' +
    'loaded. In the afternoon the wind turned cold, so they measured the last field quickly, ' +
    'checked every page twice, and carried the instruments back to the station before dark. '
$UTF8 = New-Object System.Text.UTF8Encoding $false

# Pinned downloads (configs/xrt/llamacpp_pin.yaml at the Task BS commit; a test checks they match).
$PIN_GGUF = @{
    name = 'Qwen3-4B-Q4_K_M.gguf'
    url = 'https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/Qwen3-4B-Q4_K_M.gguf'
    size = [int64]2497280256
    sha256 = '7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5'
}

function Write-Note([string]$msg) {
    $line = '[' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + '] ' + $msg
    Write-Host $line
    if ($script:TRANSCRIPT) { [System.IO.File]::AppendAllText($script:TRANSCRIPT, $line + "`r`n", $UTF8) }
}

function Stop-Run([string]$msg) {
    Write-Note ('ABORT: ' + $msg)
    throw ('SEAM_ABORT ' + $msg)
}

# Native command output (stdout + stderr) as strings. Windows PowerShell 5.1 turns redirected stderr
# lines into terminating errors under ErrorActionPreference Stop, so it is relaxed here only.
function Invoke-Native([string]$exe, [string[]]$argv) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $o = @(& $exe @argv 2>&1 | ForEach-Object { [string]$_ }) }
    finally { $ErrorActionPreference = $old }
    return ,$o
}

function Save-Native([string]$exe, [string[]]$argv, [string]$path, [switch]$Append) {
    $text = ((Invoke-Native $exe $argv) -join "`r`n") + "`r`n"
    if ($Append) { [System.IO.File]::AppendAllText($path, $text, $UTF8) }
    else { [System.IO.File]::WriteAllText($path, $text, $UTF8) }
}

function New-SeamLayout {
    foreach ($d in @('bin', 'models', 'logs', 'out', 'zips')) {
        $p = Join-Path $SEAM_ROOT $d
        if (-not (Test-Path $p)) { [void](New-Item -ItemType Directory -Path $p) }
    }
}

function Get-Sha256([string]$path) {
    return (Get-FileHash -Algorithm SHA256 -Path $path).Hash.ToLower()
}

# Download to dest unless an identical file is already there. Size and sha256 are checked BEFORE
# use; on any mismatch the file is deleted and the run aborts. No retries.
function Get-PinnedFile([hashtable]$pin, [string]$dest) {
    Write-Note ('pinned: ' + $pin.url + ' (' + $pin.size + ' B, sha256 ' + $pin.sha256 + ')')
    if (-not (Test-Path $dest)) {
        $part = $dest + '.part'
        if (Test-Path $part) { Remove-Item -Force $part }
        $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
        if ($curl) {
            $co = Invoke-Native $curl.Source @('-L', '--fail', '--silent', '--show-error', '-o', $part, $pin.url)
            if ($LASTEXITCODE -ne 0) {
                Write-Note ('curl: ' + ($co -join ' '))
                if (Test-Path $part) { Remove-Item -Force $part }
                Stop-Run ('download failed (curl exit ' + $LASTEXITCODE + '): ' + $pin.url)
            }
        } else {
            Invoke-WebRequest -UseBasicParsing -Uri $pin.url -OutFile $part
        }
        Move-Item -Path $part -Destination $dest
    }
    $len = (Get-Item $dest).Length
    $sha = Get-Sha256 $dest
    if ($len -ne $pin.size -or $sha -ne $pin.sha256) {
        Remove-Item -Force $dest
        Stop-Run ('size/sha256 mismatch for ' + $dest + ': got ' + $len + ' B ' + $sha + '; file deleted')
    }
    Write-Note ('verified ' + $dest)
}

function Install-Build([hashtable[]]$zips, [string]$dir) {
    foreach ($z in $zips) {
        $zp = Join-Path (Join-Path $SEAM_ROOT 'zips') $z.name
        Get-PinnedFile $z $zp
    }
    if (-not (Test-Path (Join-Path $dir 'llama-server.exe'))) {
        foreach ($z in $zips) {
            Expand-Archive -Force -Path (Join-Path (Join-Path $SEAM_ROOT 'zips') $z.name) -DestinationPath $dir
        }
    }
    $exe = Get-ChildItem -Path $dir -Recurse -Filter llama-server.exe | Select-Object -First 1
    if (-not $exe) { Stop-Run ('no llama-server.exe under ' + $dir) }
    return $exe.FullName
}

# ---------------------------------------------------------------- HTTP (no proxy, explicit timeout)

function Invoke-Http([string]$method, [string]$url, [string]$body, [double]$timeoutS) {
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Method = $method
    $req.Proxy = $null
    $ms = [int][math]::Min(2147483647, [math]::Max(1000, $timeoutS * 1000))
    $req.Timeout = $ms
    $req.ReadWriteTimeout = $ms
    $req.KeepAlive = $false
    $resp = $null
    try {
        if ($body) {
            $bytes = $UTF8.GetBytes($body)
            $req.ContentType = 'application/json'
            $req.ContentLength = $bytes.Length
            $s = $req.GetRequestStream()
            $s.Write($bytes, 0, $bytes.Length)
            $s.Close()
        }
        $resp = $req.GetResponse()
    } catch [System.Net.WebException] {
        $ex = $_.Exception
        if ($ex.Status -eq [System.Net.WebExceptionStatus]::Timeout) {
            return @{ status = -1; text = ('timeout: ' + $ex.Message); json = $null }
        }
        if ($null -eq $ex.Response) {
            return @{ status = 0; text = ('connect: ' + $ex.Message); json = $null }
        }
        $resp = $ex.Response
    } catch {
        return @{ status = 0; text = ('error: ' + $_.Exception.Message); json = $null }
    }
    $status = [int]$resp.StatusCode
    $reader = New-Object System.IO.StreamReader($resp.GetResponseStream(), $UTF8)
    $text = $reader.ReadToEnd()
    $reader.Close()
    $resp.Close()
    $json = $null
    try { $json = $text | ConvertFrom-Json } catch { $json = $null }
    return @{ status = $status; text = $text; json = $json }
}

# ---------------------------------------------------------------- pure helpers (mirrored by tests)

function Get-BatchFor([int]$ubatch) { return [math]::Max($ubatch, 2048) }

function Get-GridMid([int64]$lo, [int64]$hi, [int64]$res) {
    if ($hi - $lo -le $res) { return $null }
    $snapped = [int64]([math]::Floor([math]::Floor(($lo + $hi) / 2) / $res) * $res)
    if ($snapped -le $lo) { $snapped = $lo + $res }
    if ($snapped -ge $hi) { return $null }
    return $snapped
}

# attempt: scriptblock param($n) -> $true / $false. Same order and outputs as bisect_plan.
function Invoke-Bisect([int64]$low, [int64]$high, [int64]$res, [scriptblock]$attempt) {
    if ($high -le $low) { throw 'high must be > low' }
    if ($res -le 0 -or (($high - $low) % $res) -ne 0) { throw 'high - low must be a positive multiple of res' }
    $points = New-Object System.Collections.ArrayList
    $once = {
        param([int64]$n)
        foreach ($p in $points) { if ($p.n -eq $n) { throw ('rung ' + $n + ' already attempted') } }
        $h = [bool](& $attempt $n)
        [void]$points.Add([ordered]@{ n = $n; holds = $h })
        return $h
    }
    if (-not (& $once $low)) {
        return [ordered]@{ status = 'below_low_rung'; largest_hold = $null; first_fail = $low; points = $points }
    }
    if (& $once $high) {
        return [ordered]@{ status = 'above_range'; largest_hold = $high; first_fail = $null; points = $points }
    }
    $lo = $low; $hi = $high
    while ($true) {
        $mid = Get-GridMid $lo $hi $res
        if ($null -eq $mid) { break }
        if (& $once $mid) { $lo = $mid } else { $hi = $mid }
    }
    return [ordered]@{ status = 'complete'; largest_hold = $lo; first_fail = $hi; points = $points }
}

function Get-MaxTrials([int64]$low, [int64]$high, [int64]$res, [int]$repeats) {
    $steps = ($high - $low) / $res
    $b = [math]::Ceiling([math]::Log($steps) / [math]::Log(2))
    return [int](2 + $b + 2 * $repeats)
}

function Get-TiledTokens([int[]]$ids, [int]$n) {
    $list = New-Object 'System.Collections.Generic.List[int]' ($n + $ids.Length)
    while ($list.Count -lt $n) { $list.AddRange($ids) }
    return $list.GetRange(0, $n).ToArray()
}

function Read-Shared([string]$path) {
    if (-not (Test-Path $path)) { return '' }
    $fs = [System.IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
    try {
        $sr = New-Object System.IO.StreamReader($fs, $UTF8)
        return $sr.ReadToEnd()
    } finally { $fs.Close() }
}

# {kind: {device: MiB}}; same regex as xrt_llamacpp.parse_buffers.
function Get-Buffers([string]$text) {
    $out = [ordered]@{}
    $re = '(?<dev>\S+)\s+(?<kind>model|KV|compute|output|RS)\s+buffer size\s*=\s*(?<mib>[0-9]+(?:\.[0-9]+)?)\s*MiB'
    foreach ($m in [regex]::Matches($text, $re)) {
        $kind = $m.Groups['kind'].Value
        if ($kind -eq 'KV') { $kind = 'kv' } elseif ($kind -eq 'RS') { $kind = 'rs' }
        if (-not $out.Contains($kind)) { $out[$kind] = [ordered]@{} }
        $dev = $m.Groups['dev'].Value
        $v = [double]$m.Groups['mib'].Value
        if ($out[$kind].Contains($dev)) { $out[$kind][$dev] = [math]::Round($out[$kind][$dev] + $v, 4) }
        else { $out[$kind][$dev] = $v }
    }
    return $out
}

# "using device X (...) - N MiB free" lines (src/llama.cpp at b11559).
function Get-DeviceFree([string]$text) {
    $out = [ordered]@{}
    foreach ($m in [regex]::Matches($text, 'using device (?<dev>\S+) .* - (?<mib>[0-9]+) MiB free')) {
        $out[$m.Groups['dev'].Value] = [int64]$m.Groups['mib'].Value
    }
    return $out
}

# Failure cause from the server log + request error (recorded only; the bisection treats every
# non-hold as a fail, as xrt_llamacpp does).
function Get-Cause([string]$text) {
    if ($text -match 'quantized V cache requires flash_attn|requires Flash Attention') { return 'refused_fa' }
    if ($text -match 'max_buffer_size|maxMemoryAllocationSize|exceeds device max') { return 'max_buffer' }
    if ($text -match '(?i)out of memory|ErrorOutOfDeviceMemory|failed to allocate|cudaMalloc failed|unable to allocate|OutOfDeviceMemory|hipMalloc') { return 'memory' }
    return 'other'
}

function Get-ErrorLines([string]$text) {
    $l = @($text -split "`r?`n" | Where-Object { $_ -match '(?i)error|failed|exception|out of memory|abort' } | Select-Object -First 20)
    return ,$l
}

function Get-Tail([string]$text, [int]$n) {
    $l = @($text -split "`r?`n")
    if ($l.Count -le $n) { return ($l -join "`n") }
    return ($l[($l.Count - $n)..($l.Count - 1)] -join "`n")
}

# ---------------------------------------------------------------- server lifecycle

function Get-ServerArgs([string]$model, [int64]$ctx, [int]$ub, [string]$kv, [string]$fa, [int]$port) {
    if (@('f16', 'q8_0', 'q4_0') -notcontains $kv) { throw ('bad kv ' + $kv) }
    if (@('on', 'off') -notcontains $fa) { throw ('bad fa ' + $fa) }
    return @('-m', $model, '-c', [string]$ctx, '-b', [string](Get-BatchFor $ub), '-ub', [string]$ub,
        '-ctk', $kv, '-ctv', $kv, '-fa', $fa, '-ngl', '99', '--fit', 'off', '-np', '1',
        '--cache-ram', '0', '--no-warmup', '--host', '127.0.0.1', '--port', [string]$port)
}

function Assert-PortFree([int]$port) {
    $r = Invoke-Http 'GET' ('http://127.0.0.1:' + $port + '/health') $null 2
    if ($r.status -ne 0) {
        Stop-Run ('port ' + $port + ' already answers /health (status ' + $r.status + '); stop the other server first')
    }
}

function Start-Server([string]$exe, [string[]]$argv, [string]$logBase) {
    $env:ZES_ENABLE_SYSMAN = '1'
    $p = Start-Process -FilePath $exe -ArgumentList $argv -NoNewWindow -PassThru `
        -RedirectStandardOutput ($logBase + '.out.log') -RedirectStandardError ($logBase + '.err.log')
    $null = $p.Handle
    return $p
}

function Stop-Server($p) {
    if (-not $p.HasExited) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        if (-not $p.WaitForExit(30000)) { Stop-Run ('llama-server pid ' + $p.Id + ' survived Stop-Process') }
    }
    try { return $p.ExitCode } catch { return $null }
}

function Read-ServerLog([string]$logBase) {
    return (Read-Shared ($logBase + '.err.log')) + "`n" + (Read-Shared ($logBase + '.out.log'))
}

function Wait-Ready($p, [string]$logBase, [int]$port, [double]$timeoutS, [datetime]$t0) {
    while ($true) {
        if ($p.HasExited) { return 'exit' }
        $r = Invoke-Http 'GET' ('http://127.0.0.1:' + $port + '/health') $null 5
        if ($r.status -eq 200) { return 'ready' }
        $t = Read-ServerLog $logBase
        if ($t.Contains('model loaded') -and $t.Contains('listening on')) { return 'ready' }
        if (((Get-Date) - $t0).TotalSeconds -ge $timeoutS) { return 'timeout' }
        Start-Sleep -Milliseconds 500
    }
}

# ---------------------------------------------------------------- run state (resumable)

function Add-Row([string]$path, $row) {
    $line = ($row | ConvertTo-Json -Compress -Depth 8)
    [System.IO.File]::AppendAllText($path, $line + "`n", $UTF8)
}

function Read-Rows([string]$path) {
    $rows = New-Object System.Collections.ArrayList
    if (Test-Path $path) {
        foreach ($l in [System.IO.File]::ReadAllLines($path, $UTF8)) {
            if ($l.Trim().StartsWith('{')) { [void]$rows.Add(($l | ConvertFrom-Json)) }
        }
    }
    return ,$rows
}

function Get-PriorStatus($rows, [string]$cellId, [string]$phase, [int64]$n, [int]$k) {
    # k-th (0-based) prior row for this cell / phase / n, or $null
    $hits = @($rows | Where-Object { $_.mode -eq 'trial' -and $_.cell -eq $cellId -and $_.phase -eq $phase -and [int64]$_.n_ctx -eq $n })
    if ($hits.Count -gt $k) { return $hits[$k].status }
    return $null
}

# One trial: fresh server at -c n; mode 'prefill' posts n - 64 tokens (hold = HTTP 200, no error,
# prompt_n >= n - 64, server alive); mode 'load' stops once ready (hold = ready).
function Invoke-Trial($ctx, $cell, [int64]$n, [string]$phase) {
    $nPrompt = $n - $PROMPT_MARGIN
    $argv = Get-ServerArgs $ctx.model $n $cell.ub $cell.kv $cell.fa $ctx.port
    $logDir = Join-Path $ctx.runDir 'server_logs'
    if (-not (Test-Path $logDir)) { [void](New-Item -ItemType Directory -Path $logDir) }
    $idx = @(Get-ChildItem -Path $logDir -Filter ($cell.id + '_*.err.log')).Count
    $logBase = Join-Path $logDir ('{0}_{1:D3}_{2}_n{3}' -f $cell.id, $idx, $phase, $n)
    if (Test-Path ($logBase + '.err.log')) { Stop-Run ('log exists: ' + $logBase) }
    if ($idx -gt 0) { Start-Sleep -Seconds 2 }
    Assert-PortFree $ctx.port
    if ($ctx.beforeTrial) { & $ctx.beforeTrial $cell $n $logBase }
    $t0 = Get-Date
    $p = Start-Server $ctx.exe $argv $logBase
    $status = 'fail_load'; $http = $null; $promptN = $null; $promptMs = $null; $reqErr = $null
    try {
        $ready = Wait-Ready $p $logBase $ctx.port $ctx.timeoutS $t0
        if ($ready -eq 'timeout') { $status = 'timeout' }
        elseif ($ready -eq 'ready' -and $cell.mode -eq 'load') { $status = 'hold' }
        elseif ($ready -eq 'ready') {
            if (-not $ctx.tokenIds) {
                $tb = '{"content":' + ($PARAGRAPH | ConvertTo-Json) + ',"add_special":false}'
                $tr = Invoke-Http 'POST' ('http://127.0.0.1:' + $ctx.port + '/tokenize') $tb 60
                if ($tr.status -ne 200 -or $null -eq $tr.json -or -not $tr.json.tokens) {
                    Stop-Run ('/tokenize failed: status ' + $tr.status + ' ' + $tr.text)
                }
                $ctx.tokenIds = [int[]]@($tr.json.tokens)
            }
            $ids = Get-TiledTokens $ctx.tokenIds ([int]$nPrompt)
            $body = '{"prompt":[' + ($ids -join ',') + '],"n_predict":1,"cache_prompt":false,"temperature":0}'
            $remaining = [math]::Max(1, $ctx.timeoutS - ((Get-Date) - $t0).TotalSeconds)
            $r = Invoke-Http 'POST' ('http://127.0.0.1:' + $ctx.port + '/completion') $body $remaining
            $http = $r.status
            $j = $r.json
            if ($null -ne $j) {
                $tm = $null
                if ($j.PSObject.Properties.Name -contains 'timings') { $tm = $j.timings }
                if ($null -ne $tm -and $tm.PSObject.Properties.Name -contains 'prompt_n') { $promptN = [int64]$tm.prompt_n }
                elseif ($j.PSObject.Properties.Name -contains 'tokens_evaluated') { $promptN = [int64]$j.tokens_evaluated }
                if ($null -ne $tm -and $tm.PSObject.Properties.Name -contains 'prompt_ms') { $promptMs = [double]$tm.prompt_ms }
            }
            $hasErr = ($null -ne $j -and $j.PSObject.Properties.Name -contains 'error')
            if ($r.status -eq -1) { $status = 'timeout'; $reqErr = $r.text }
            elseif ($r.status -eq 200 -and -not $hasErr -and $null -ne $promptN -and $promptN -ge $nPrompt -and -not $p.HasExited) {
                $status = 'hold'
            } else {
                $status = 'fail_prefill'
                $reqErr = $r.text
                if ($reqErr.Length -gt 2000) { $reqErr = $reqErr.Substring(0, 2000) }
            }
        }
    } finally {
        $rc = Stop-Server $p
    }
    $wall = [math]::Round(((Get-Date) - $t0).TotalSeconds, 3)
    $text = Read-ServerLog $logBase
    $err = $null; $cause = $null
    if ($status -ne 'hold') {
        $err = (@($reqErr, (Get-Tail $text 40)) | Where-Object { $_ }) -join "`n"
        $cause = Get-Cause ($text + "`n" + $reqErr)
    }
    $row = [ordered]@{
        mode = 'trial'; run_id = $ctx.runId; machine = $ctx.machine; cell = $cell.id; cell_mode = $cell.mode
        phase = $phase; n_ctx = $n; n_prompt = $nPrompt; prompt_n = $promptN; kv = $cell.kv; fa = $cell.fa
        ubatch = $cell.ub; batch = (Get-BatchFor $cell.ub); ngl = 99; share_label = $ctx.shareLabel
        status = $status; cause = $cause; http_status = $http; returncode = $rc; prompt_ms = $promptMs
        buffers = (Get-Buffers $text); device_free_mib = (Get-DeviceFree $text)
        error_lines = (Get-ErrorLines $text); error = $err; wall_s = $wall
        t_start = $t0.ToString('o'); log_base = $logBase; argv = $argv
    }
    if ($ctx.afterTrial) { & $ctx.afterTrial $row }
    Add-Row $ctx.rowsPath $row
    Write-Note ('TRIAL ' + $cell.id + ' ' + $phase + ' n=' + $n + ' status=' + $status + ' wall_s=' + $wall)
    return $row
}

# One cell: bisection (replaying prior rows of this run, so a restart resumes), then repeats at
# largest hold and first fail. Writes a cell_done row.
function Invoke-Cell($ctx, $cell) {
    $rows = Read-Rows $ctx.rowsPath
    $done = @($rows | Where-Object { $_.mode -eq 'cell_done' -and $_.cell -eq $cell.id })
    if ($done.Count -gt 0) { Write-Note ('cell ' + $cell.id + ' already done; skipped'); return }
    Write-Note ('CELL ' + $cell.id + ' mode=' + $cell.mode + ' kv=' + $cell.kv + ' fa=' + $cell.fa + ' ub=' + $cell.ub + ' range=[' + $cell.low + ', ' + $cell.high + '] step ' + $cell.res)
    $att = {
        param([int64]$n)
        $prior = Get-PriorStatus $rows $cell.id 'bisect' $n 0
        if ($null -ne $prior) { Write-Note ('  replay n=' + $n + ' ' + $prior); return ($prior -eq 'hold') }
        return ((Invoke-Trial $ctx $cell $n 'bisect').status -eq 'hold')
    }
    $res = Invoke-Bisect $cell.low $cell.high $cell.res $att
    $rep = New-Object System.Collections.ArrayList
    $targets = @()
    if ($null -ne $res.largest_hold) { $targets = @(@($res.largest_hold, $res.first_fail) | Where-Object { $null -ne $_ }) }
    for ($k = 0; $k -lt $cell.repeats; $k++) {
        foreach ($n in $targets) {
            $prior = Get-PriorStatus $rows $cell.id 'repeat' $n $k
            if ($null -eq $prior) { $prior = (Invoke-Trial $ctx $cell $n 'repeat').status }
            [void]$rep.Add([ordered]@{ n = $n; status = $prior })
        }
    }
    $summary = [ordered]@{
        mode = 'cell_done'; run_id = $ctx.runId; machine = $ctx.machine; cell = $cell.id
        cell_mode = $cell.mode; kv = $cell.kv; fa = $cell.fa; ubatch = $cell.ub; share_label = $ctx.shareLabel
        low = $cell.low; high = $cell.high; res = $cell.res
        status = $res.status; largest_hold = $res.largest_hold; first_fail = $res.first_fail
        points = $res.points; repeats = $rep; t_end = (Get-Date).ToString('o')
    }
    Add-Row $ctx.rowsPath $summary
    Write-Note ('CELL_DONE ' + $cell.id + ' status=' + $res.status + ' largest_hold=' + $res.largest_hold + ' first_fail=' + $res.first_fail)
}

function Show-Budget($cells, [double]$estTrialS, [double]$timeoutS) {
    $tot = 0
    foreach ($c in $cells) {
        $m = Get-MaxTrials $c.low $c.high $c.res $c.repeats
        $tot += $m
        Write-Note ('  ' + $c.id + ': at most ' + $m + ' trials')
    }
    $h = [math]::Round($tot * $estTrialS / 3600, 1)
    Write-Note ('TIME BUDGET: at most ' + $tot + ' trials; about ' + $h + ' h at ~' + $estTrialS + ' s per trial (per-trial timeout ' + $timeoutS + ' s)')
}

function Get-RunDir([string]$runId) { return (Join-Path (Join-Path $SEAM_ROOT 'out') $runId) }

# Latest unfinished run for this machine/part, else a new 8-hex run_id.
function Resolve-RunId([string]$machine, [string]$part, [string]$requested, [bool]$newRun) {
    if ($requested) { return $requested }
    if (-not $newRun) {
        $cands = Get-ChildItem -Path (Join-Path $SEAM_ROOT 'out') -Directory -ErrorAction SilentlyContinue |
            Where-Object { (Test-Path (Join-Path $_.FullName 'run_meta.json')) -and -not (Test-Path (Join-Path $_.FullName 'RUN_DONE.txt')) } |
            Sort-Object LastWriteTime -Descending
        foreach ($c in $cands) {
            $m = Get-Content -Raw (Join-Path $c.FullName 'run_meta.json') | ConvertFrom-Json
            if ($m.machine -eq $machine -and $m.part -eq $part) { return $c.Name }
        }
    }
    return ([guid]::NewGuid().ToString('N').Substring(0, 8))
}

function Write-RunMeta([string]$runDir, $meta) {
    $p = Join-Path $runDir 'run_meta.json'
    if (-not (Test-Path $p)) { [System.IO.File]::WriteAllText($p, ($meta | ConvertTo-Json -Depth 6), $UTF8) }
}

# Self-test of the bisection (no server, no download): used by tests/test_rithwik_runbooks.py.
# threshold: largest n that holds; prior: "n:hold,n:fail" rows replayed without an attempt.
function Invoke-SelfTest([int64]$low, [int64]$high, [int64]$res, [int64]$threshold, [string]$prior) {
    $pre = @{}
    if ($prior) { foreach ($kv in $prior.Split(',')) { $a = $kv.Split(':'); $pre[[int64]$a[0]] = $a[1] } }
    $attempted = New-Object System.Collections.ArrayList
    $att = {
        param([int64]$n)
        if ($pre.ContainsKey($n)) { return ($pre[$n] -eq 'hold') }
        [void]$attempted.Add($n)
        return ($n -le $threshold)
    }
    $r = Invoke-Bisect $low $high $res $att
    $o = [ordered]@{ status = $r.status; largest_hold = $r.largest_hold; first_fail = $r.first_fail
        points = $r.points; attempted = $attempted; max_trials = (Get-MaxTrials $low $high $res 0)
        tiled = (Get-TiledTokens @(5, 6, 7) 8) }
    Write-Output ('SELFTEST ' + ($o | ConvertTo-Json -Compress -Depth 6))
}
# ---------------------------------------------------------------- end common.ps1
