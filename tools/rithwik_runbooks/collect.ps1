<#
.SYNOPSIS
  SEAM XRT collect (@@MACHINE@@): one zip of C:\seam_xrt\logs and C:\seam_xrt\out plus a system
  record, named with machine + date, and its sha256. No prompts, no admin, writes only under
  C:\seam_xrt\. Send the zip and the printed sha256 to Zach.
  Run:   powershell -NoProfile -ExecutionPolicy Bypass -File .\collect.ps1
#>
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$MACHINE = '@@MACHINE@@'
$ROOT = 'C:\seam_xrt'
$UTF8 = New-Object System.Text.UTF8Encoding $false
$stamp = (Get-Date).ToString('yyyyMMdd_HHmm')

function Add-Section([System.Collections.ArrayList]$buf, [string]$title, [scriptblock]$body) {
    [void]$buf.Add('== ' + $title)
    # Continue, not Stop, inside a section: Windows PowerShell 5.1 turns native stderr lines (2>&1) into
    # terminating errors under Stop, and llama-server prints its version on stderr.
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { foreach ($l in @(& $body)) { [void]$buf.Add([string]$l) } }
    catch { [void]$buf.Add('ERROR: ' + $_.Exception.Message) }
    finally { $ErrorActionPreference = $old }
    [void]$buf.Add('')
}

try {
    if (-not (Test-Path (Join-Path $ROOT 'out'))) { throw 'C:\seam_xrt\out not found: run run.ps1 first' }
    $sysDir = Join-Path $ROOT ('out\system_' + $MACHINE + '_' + $stamp)
    [void](New-Item -ItemType Directory -Force -Path $sysDir)
    $buf = New-Object System.Collections.ArrayList
    Add-Section $buf 'collected' { (Get-Date).ToString('o') + ' machine ' + $MACHINE + ' host ' + $env:COMPUTERNAME }
    Add-Section $buf 'OS build' {
        $os = Get-CimInstance Win32_OperatingSystem
        $os.Caption + ' ' + $os.Version + ' build ' + $os.BuildNumber + ' ' + $os.OSArchitecture
        (cmd /c ver) | Where-Object { $_ }
    }
    Add-Section $buf 'CPU / RAM' {
        (Get-CimInstance Win32_Processor | ForEach-Object { $_.Name })
        'TotalPhysicalMemory ' + (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
    }
    Add-Section $buf 'GPU driver (Win32_VideoController)' {
        Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + ' | driver ' + $_.DriverVersion + ' | date ' + $_.DriverDate + ' | AdapterRAM ' + $_.AdapterRAM }
    }
    Add-Section $buf 'GPU memory as reported by the driver (registry qwMemorySize, read-only)' {
        $cls = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
        Get-ChildItem $cls -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match '^[0-9]{4}$' } | ForEach-Object {
            $p = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
            if ($p -and $p.PSObject.Properties.Name -contains 'DriverDesc') {
                $q = $null
                if ($p.PSObject.Properties.Name -contains 'HardwareInformation.qwMemorySize') { $q = $p.'HardwareInformation.qwMemorySize' }
                $p.DriverDesc + ' | qwMemorySize ' + $q
            }
        }
    }
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        Add-Section $buf 'nvidia-smi -q (memory, driver)' { & nvidia-smi -q -d MEMORY 2>&1; & nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used --format=csv 2>&1 }
    }
    if (Get-Command vulkaninfo -ErrorAction SilentlyContinue) {
        Add-Section $buf 'vulkaninfo --summary' { & vulkaninfo --summary 2>&1 }
    }
    Add-Section $buf 'llama.cpp builds (version line, devices with total/free MiB)' {
        Get-ChildItem -Path (Join-Path $ROOT 'bin') -Recurse -Filter llama-server.exe -ErrorAction SilentlyContinue | ForEach-Object {
            '-- ' + $_.FullName
            & $_.FullName --version 2>&1
            & $_.FullName --list-devices 2>&1
        }
    }
    # dxdiag: Dedicated / Shared memory per display device (Shared GPU Memory; on AMD the VGM value
    # appears as Dedicated Memory). Non-admin; takes up to a minute.
    $dx = Join-Path $sysDir 'dxdiag.txt'
    try {
        Start-Process -FilePath dxdiag.exe -ArgumentList @('/t', $dx) -Wait -WindowStyle Hidden
        for ($i = 0; $i -lt 120 -and -not (Test-Path $dx); $i++) { Start-Sleep -Seconds 1 }
    } catch { [void]$buf.Add('dxdiag failed: ' + $_.Exception.Message) }
    Add-Section $buf 'dxdiag display memory' {
        if (Test-Path $dx) { Get-Content $dx | Where-Object { $_ -match 'Card name|Dedicated Memory|Shared Memory|Display Memory|Driver Version' } }
        else { 'dxdiag.txt not written' }
    }
    [System.IO.File]::WriteAllText((Join-Path $sysDir 'system_record.txt'), ($buf -join "`r`n"), $UTF8)

    # sha256 manifest of everything that goes into the zip
    $files = @(Get-ChildItem -Path (Join-Path $ROOT 'logs'), (Join-Path $ROOT 'out') -Recurse -File -ErrorAction SilentlyContinue)
    $man = $files | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower() + '  ' + $_.FullName.Substring($ROOT.Length + 1) }
    [System.IO.File]::WriteAllText((Join-Path $sysDir 'MANIFEST.sha256'), (($man -join "`n") + "`n"), $UTF8)

    $zip = Join-Path $ROOT ('seam_xrt_' + $MACHINE + '_' + $stamp + '.zip')
    if (Test-Path $zip) { throw ('zip already exists: ' + $zip) }
    Compress-Archive -Path (Join-Path $ROOT 'logs'), (Join-Path $ROOT 'out') -DestinationPath $zip
    $h = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
    [System.IO.File]::WriteAllText($zip + '.sha256', $h + '  ' + (Split-Path $zip -Leaf) + "`n", $UTF8)
    Write-Host ''
    Write-Host ('ZIP     ' + $zip)
    Write-Host ('BYTES   ' + (Get-Item $zip).Length)
    Write-Host ('SHA256  ' + $h)
    Write-Host 'Send the zip, this sha256 and the Sysmem Fallback / share screenshot(s) to Zach.'
    exit 0
} catch {
    Write-Host ('COLLECT FAILED: ' + $_.Exception.Message)
    exit 1
}
