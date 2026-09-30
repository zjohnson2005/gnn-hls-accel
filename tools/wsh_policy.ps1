# WorkloadsSessionHost policy.
# Kill and refuse. Every sealed run was measured with the host cleared.
# It respawns about 4 minutes after a kill, so every cell preamble kills again.
# A failed kill keeps the exception text (access denied and the like) in the refusal.

function Get-WshSnapshot {
    $procs = @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)
    $pids = @()
    $ws = @()
    $cpu = @()
    $errors = @()
    foreach ($proc in $procs) {
        $pids += [int]$proc.Id
        try {
            $mb = [double]$proc.WorkingSet64 / 1MB
            $ws += [math]::Round($mb, 6)
        } catch {
            $ws += $null
            $errors += ("pid {0} WS_MB: {1}" -f $proc.Id, $_.Exception.Message)
        }
        try {
            if ($null -eq $proc.CPU) {
                $cpu += $null
            } else {
                $cpu += [math]::Round([double]$proc.CPU, 6)
            }
        } catch {
            $cpu += $null
            $errors += ("pid {0} CPU_s: {1}" -f $proc.Id, $_.Exception.Message)
        }
    }
    return [ordered]@{
        instance_count = $procs.Count
        pids           = @($pids)
        WS_MB          = @($ws)
        CPU_s          = @($cpu)
        read_errors    = @($errors)
    }
}

function Format-WshKillRefusal {
    param($After, [string[]]$KillErrors)
    $errText = "no exception text"
    $msgs = @($KillErrors | Where-Object { $_ })
    if ($msgs.Count -gt 0) { $errText = ($msgs -join "; ") }
    $pids = (@($After.pids) -join ",")
    return (
        "REFUSED -- WorkloadsSessionHost still resident after kill " +
        "(instance_count=$($After.instance_count) pids=$pids exception=$errText)"
    )
}

function Clear-WorkloadsSessionHost {
    $before = Get-WshSnapshot
    $killErrors = @()
    foreach ($proc in @(Get-Process -Name "WorkloadsSessionHost" -ErrorAction SilentlyContinue)) {
        try {
            Stop-Process -Id $proc.Id -Force -ErrorAction Stop
        } catch {
            $killErrors += $_.Exception.Message
        }
    }
    if ($before.instance_count -gt 0) {
        Start-Sleep -Seconds 2
    }
    $after = Get-WshSnapshot
    $record = [ordered]@{
        before      = $before
        kill_errors = @($killErrors)
        after       = $after
    }
    $script:LastWshClear = $record
    if ($after.instance_count -gt 0) {
        throw (Format-WshKillRefusal -After $after -KillErrors @($killErrors))
    }
    if ($before.instance_count -gt 0) {
        Write-Host ("WorkloadsSessionHost: cleared instances={0}" -f $before.instance_count)
    } else {
        Write-Host "WorkloadsSessionHost: none resident"
    }
    return $record
}

function Test-SeamProcessAncestor {
    param([string[]]$Names, [int]$Depth = 4)
    $current = $PID
    for ($i = 0; $i -lt $Depth; $i++) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $current" -ErrorAction SilentlyContinue
        if (-not $proc) { return $false }
        $parentId = 0
        if ($proc.ParentProcessId) { $parentId = [int]$proc.ParentProcessId }
        if ($parentId -le 0) { return $false }
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId = $parentId" -ErrorAction SilentlyContinue
        if (-not $parent) { return $false }
        if ($Names -contains [string]$parent.Name) { return $true }
        $current = $parentId
    }
    return $false
}
