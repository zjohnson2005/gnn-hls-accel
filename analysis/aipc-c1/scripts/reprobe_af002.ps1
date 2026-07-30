<#
.SYNOPSIS
    Re-capture the Platform A (aipc-c1) machine and driver probes for blueprint finding AF-002.

.DESCRIPTION
    AF-002 requires the committed provenance snapshot to be re-runnable and diffable rather than
    transcribed once by hand. The five original artifacts

        analysis/_c1_machine_probe.txt
        analysis/_c1_drivers_probe.txt
        analysis/_c1_probe.txt
        analysis/_c1_mem_probe.txt
        analysis/_c1_tools_probe.txt

    were produced by ad-hoc interactive commands and are READ-ONLY under spec section 9.1. This
    script never touches them. It writes a fresh capture to a NEW dated directory so the two can be
    diffed.

    Two deliberate differences from the originals, both recorded in AUDIT_LOG.md:

    1. Output is UTF-8. The originals are UTF-16LE because they were produced by PowerShell 5.1
       output redirection. UTF-16LE is why a UTF-8 reader saw mojibake in which every substring
       assertion was vacuously satisfiable.

    2. Memory configuration is read via CIM (Win32_PhysicalMemory) instead of `wmic`. `wmic` is
       removed on Windows 11 25H2, which is why _c1_mem_probe.txt captured a header and zero rows,
       leaving the 8 x 2 GiB bank layout and ConfiguredClockSpeed unattested (MACHINE.md provenance
       gap 1).

    Sections marked NEW close attestation gaps that no original artifact covers. Every command that
    fails records the failure inline: a probe that silently omits a section is indistinguishable
    from a machine that lacks the hardware.

.PARAMETER OutDir
    Destination directory. Created if absent. Existing files are NOT overwritten.
#>
[CmdletBinding()]
param(
    [string]$OutDir
)

$ErrorActionPreference = 'Continue'

if (-not $OutDir) {
    $stamp = Get-Date -Format 'yyyy-MM-dd'
    $OutDir = Join-Path $PSScriptRoot "..\reprobe_af002_$stamp"
}
$OutDir = [System.IO.Path]::GetFullPath($OutDir)
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$isElevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

function Write-Probe {
    param([string]$Name, [string[]]$Lines)
    $path = Join-Path $OutDir $Name
    if (Test-Path $path) { Write-Warning "exists, not overwriting: $path"; return }
    # UTF-8 without BOM and LF line endings, written explicitly rather than via WriteAllLines
    # (which would use CRLF). The repository has core.autocrlf=true and no .gitattributes, so a
    # CRLF file is normalised to LF in the index: its committed bytes, and therefore its SHA-256,
    # would differ from the working copy the hash was computed from. For a provenance artifact whose
    # whole purpose is a citable hash, that is silent rot. LF on disk makes the two agree.
    $text = ($Lines -join "`n") + "`n"
    [System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))
    Write-Output "wrote $path ($($Lines.Count) lines)"
}

function Invoke-Section {
    param([string]$Title, [scriptblock]$Body)
    $out = New-Object System.Collections.Generic.List[string]
    $out.Add("=== $Title ===")
    try {
        $result = & $Body 2>&1 | Out-String
        foreach ($line in ($result -split "`r?`n")) { $out.Add($line.TrimEnd()) }
    } catch {
        # Recorded, never swallowed: an empty section must be distinguishable from a failed one.
        $out.Add("PROBE_ERROR: $($_.Exception.GetType().Name): $($_.Exception.Message)")
    }
    return $out
}

# ==================================================================================================
# machine probe  (counterpart of analysis/_c1_machine_probe.txt)
# ==================================================================================================

$machine = New-Object System.Collections.Generic.List[string]
$machine.AddRange([string[]](Invoke-Section 'systeminfo (filtered)' {
    systeminfo | Select-String -Pattern 'OS Name','OS Version','OS Build Type','System Manufacturer','System Model','System Type','Processor\(s\)','BIOS Version','Total Physical Memory'
}))
$machine.AddRange([string[]](Invoke-Section 'powercfg' { powercfg /getactivescheme }))
$machine.AddRange([string[]](Invoke-Section 'cpu brand' {
    (Get-CimInstance Win32_Processor).Name
}))
$machine.AddRange([string[]](Invoke-Section 'winver registry' {
    $k = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    "$($k.ProductName) $($k.DisplayVersion) build $($k.CurrentBuild).$($k.UBR)"
}))
Write-Probe -Name 'machine_probe.txt' -Lines $machine

# ==================================================================================================
# memory probe  (counterpart of analysis/_c1_mem_probe.txt — the artifact that captured zero rows)
# ==================================================================================================

$mem = New-Object System.Collections.Generic.List[string]
$mem.AddRange([string[]](Invoke-Section 'memory banks via CIM Win32_PhysicalMemory (NEW: wmic is removed on 25H2)' {
    Get-CimInstance Win32_PhysicalMemory |
        Select-Object BankLabel, DeviceLocator, Capacity, Speed, ConfiguredClockSpeed,
                      ConfiguredVoltage, SMBIOSMemoryType, FormFactor, Manufacturer, PartNumber, SerialNumber |
        Format-List
}))
$mem.AddRange([string[]](Invoke-Section 'memory bank count and total' {
    $banks = @(Get-CimInstance Win32_PhysicalMemory)
    "bank_count=$($banks.Count)"
    "total_bytes=$(($banks | Measure-Object -Property Capacity -Sum).Sum)"
    "per_bank_bytes=$(($banks | ForEach-Object { $_.Capacity }) -join ',')"
}))
$mem.AddRange([string[]](Invoke-Section 'memory array via CIM Win32_PhysicalMemoryArray' {
    Get-CimInstance Win32_PhysicalMemoryArray | Format-List *
}))
$mem.AddRange([string[]](Invoke-Section 'OS-reported total' {
    $cs = Get-CimInstance Win32_ComputerSystem
    "TotalPhysicalMemory=$($cs.TotalPhysicalMemory)"
}))
$mem.AddRange([string[]](Invoke-Section 'AC status' {
    $b = Get-CimInstance Win32_Battery
    "BatteryStatus=$($b.BatteryStatus)"
    "EstimatedChargeRemaining=$($b.EstimatedChargeRemaining)"
    $ps = Get-CimInstance -Namespace root\wmi -ClassName BatteryStatus -ErrorAction SilentlyContinue
    "PowerOnline=$($ps.PowerOnline)"
    "Discharging=$($ps.Discharging)"
}))
Write-Probe -Name 'mem_probe.txt' -Lines $mem

# ==================================================================================================
# topology probe  (NEW — no original artifact records core counts or EfficiencyClass)
# ==================================================================================================

$topo = New-Object System.Collections.Generic.List[string]
$topo.AddRange([string[]](Invoke-Section 'CIM processor core and thread counts' {
    Get-CimInstance Win32_Processor |
        Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed,
                      L2CacheSize, L3CacheSize, Description, Revision |
        Format-List
}))
$topo.AddRange([string[]](Invoke-Section 'logical processor count' {
    "NumberOfLogicalProcessors=$((Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors)"
    "environment_PROCESSOR_COUNT=$($env:NUMBER_OF_PROCESSORS)"
}))
$topo.AddRange([string[]](Invoke-Section 'per-core EfficiencyClass via GetLogicalProcessorInformationEx (RelationProcessorCore)' {
    # Same Win32 call seam/topology.py uses. Reported here so the OS hypothesis is captured as an
    # artifact; spec section 4 forbids trusting this ordering without the microbenchmark.
    Add-Type -ErrorAction Stop -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class SeamLpi {
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetLogicalProcessorInformationEx(int rel, IntPtr buf, ref uint len);
    public static List<string> Cores() {
        var rows = new List<string>();
        uint len = 0;
        GetLogicalProcessorInformationEx(0, IntPtr.Zero, ref len);
        IntPtr buf = Marshal.AllocHGlobal((int)len);
        try {
            if (!GetLogicalProcessorInformationEx(0, buf, ref len))
                throw new Exception("GetLogicalProcessorInformationEx failed: " + Marshal.GetLastWin32Error());
            int off = 0; int idx = 0;
            while (off < (int)len) {
                int size = Marshal.ReadInt32(buf, off + 4);
                byte flags = Marshal.ReadByte(buf, off + 8);
                byte eff   = Marshal.ReadByte(buf, off + 9);
                short groups = Marshal.ReadInt16(buf, off + 30);
                var cpus = new List<int>();
                short group = 0;
                for (int g = 0; g < groups; g++) {
                    int mo = off + 32 + g * 16;
                    long mask = Marshal.ReadInt64(buf, mo);
                    group = Marshal.ReadInt16(buf, mo + 8);
                    for (int b = 0; b < 64; b++) if ((mask & (1L << b)) != 0) cpus.Add(b);
                }
                rows.Add(String.Format("core_index={0} EfficiencyClass={1} logical_cpus=[{2}] group={3} smt={4}",
                    idx, eff, String.Join(",", cpus), group, ((flags & 0x1) != 0)));
                idx++; off += size;
            }
        } finally { Marshal.FreeHGlobal(buf); }
        return rows;
    }
}
'@
    [SeamLpi]::Cores()
}))
$topo.AddRange([string[]](Invoke-Section 'NOTE' {
    'EfficiencyClass above is the OS HYPOTHESIS only. Spec section 4 requires the P/LP-E split to be'
    'established by the pinned microbenchmark in seam/topology.py, not by this field. Recording it'
    'here makes the hypothesis auditable; it does not verify it.'
}))
Write-Probe -Name 'topology_probe.txt' -Lines $topo

# ==================================================================================================
# drivers probe  (counterpart of analysis/_c1_drivers_probe.txt)
# ==================================================================================================

$drivers = New-Object System.Collections.Generic.List[string]
$drivers.AddRange([string[]](Invoke-Section 'display adapters (pnputil)' {
    pnputil /enum-devices /class Display /connected
}))
$drivers.AddRange([string[]](Invoke-Section 'compute accelerators (pnputil)' {
    pnputil /enum-devices /class ComputeAccelerator /connected
}))
$drivers.AddRange([string[]](Invoke-Section 'iGPU and NPU driver versions via CIM' {
    Get-CimInstance Win32_PnPSignedDriver |
        Where-Object { $_.DeviceName -match 'Intel\(R\) (Graphics|NPU)' } |
        Select-Object DeviceName, DriverVersion, DriverDate, InfName, DeviceID |
        Format-List
}))
$drivers.AddRange([string[]](Invoke-Section "driver store search (elevated=$isElevated)" {
    if (-not $isElevated) {
        'PROBE_SKIPPED: pnputil /enum-drivers requires elevation; not elevated in this session.'
    } else {
        pnputil /enum-drivers | Select-String -Context 0,6 -Pattern 'iigd_dch.inf','npu.inf'
    }
}))
Write-Probe -Name 'drivers_probe.txt' -Lines $drivers

# ==================================================================================================
# tools probe  (counterpart of analysis/_c1_tools_probe.txt)
# ==================================================================================================

$tools = New-Object System.Collections.Generic.List[string]
$tools.AddRange([string[]](Invoke-Section 'where PresentMon' {
    $c = Get-Command PresentMon*, presentmon* -ErrorAction SilentlyContinue
    if ($c) { $c | Select-Object Name, Source | Format-List } else { 'not found on PATH' }
}))
$tools.AddRange([string[]](Invoke-Section 'python interpreters' {
    py --list
}))
$tools.AddRange([string[]](Invoke-Section 'git version' { git --version }))
Write-Probe -Name 'tools_probe.txt' -Lines $tools

# ==================================================================================================
# capture context
# ==================================================================================================

$meta = New-Object System.Collections.Generic.List[string]
$meta.Add('=== reprobe context ===')
$meta.Add("captured_utc=$((Get-Date).ToUniversalTime().ToString('o'))")
$meta.Add("hostname=$($env:COMPUTERNAME)")
$meta.Add("elevated=$isElevated")
$meta.Add("powershell_version=$($PSVersionTable.PSVersion)")
$meta.Add("script=$($MyInvocation.MyCommand.Path)")
$meta.Add('purpose=blueprint AF-002 provenance re-capture; originals under analysis/ are read-only (spec section 9.1) and untouched')
Write-Probe -Name 'reprobe_context.txt' -Lines $meta

Write-Output ''
Write-Output "=== SHA-256 of fresh capture ==="
Get-ChildItem $OutDir -File | Sort-Object Name | ForEach-Object {
    "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower())  $($_.Name)"
}
