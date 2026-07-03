# Phase 1 finish (c=1000) + Phase 2 prep. Run from repo root:
#   cd C:\Users\zjohn\Projects\gnn-hls-accel
#   $env:OPENAI_API_KEY = "sk-..."
#   .\orchestration_engine\run_next_steps.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path -Parent $Root)

Write-Host "Disabling AC sleep until this script finishes..." -ForegroundColor DarkGray
powercfg /change standby-timeout-ac 0 | Out-Null

try {
    Write-Host ""
    Write-Host "=== Step 1: c=1000 OpenAI anchor (5-15 min) ===" -ForegroundColor Cyan
    if (-not $env:OPENAI_API_KEY) {
        Write-Host "OPENAI_API_KEY not set - skipping c=1000." -ForegroundColor Yellow
        Write-Host '  $env:OPENAI_API_KEY = "sk-..."'
        Write-Host "  py -3 -m orchestration_engine.characterization.phase1_gate.openai_scaling_sweep --levels 1000 --fast --force --skip-gate"
    } else {
        py -3 -m orchestration_engine.characterization.phase1_gate.openai_scaling_sweep `
            --levels 1000 --fast --force --skip-gate
    }

    Write-Host ""
    Write-Host "=== Step 2: Regenerate gate reports ===" -ForegroundColor Cyan
    py -3 -m orchestration_engine.characterization.phase1_gate.gate_report --skip-openai
    py -3 -m orchestration_engine.phase2_gate.gate_report

    Write-Host ""
    Write-Host "=== Step 3: Local dispatch stress at N=1000 (no API) ===" -ForegroundColor Cyan
    py -3 -m orchestration_engine.characterization.phase1_gate.dispatch_stress --levels 100,500,1000

    Write-Host ""
    Write-Host "=== Step 4: Phase 2 HLS on Vitis box ===" -ForegroundColor Cyan
    Write-Host "Copy orchestration_engine.zip to the box, then:"
    Write-Host "  source /tools/software/xilinx/setup_env.sh"
    Write-Host "  cd gnn-hls-accel"
    Write-Host "  bash orchestration_engine/run_phase2_scatter_only.sh"
    Write-Host ""
    Write-Host "Outputs:"
    Write-Host "  orchestration_engine/characterization/out/gate/gate_report.md"
    Write-Host "  orchestration_engine/characterization/out/phase2/phase2_gate.md"
} finally {
    powercfg /change standby-timeout-ac 30 | Out-Null
    Write-Host ""
    Write-Host "Restored AC sleep timeout to 30 min." -ForegroundColor DarkGray
}
