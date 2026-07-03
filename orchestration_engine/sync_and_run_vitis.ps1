# Copy orchestration_engine to GT Vitis box and run scatter csynth.
# Usage (from repo root):
#   $env:VITIS_HOST = "gtusername@ece-rschsrv.ece.gatech.edu"
#   $env:VITIS_DIR  = "~/gnn-hls-accel"
#   .\orchestration_engine\sync_and_run_vitis.ps1

param(
    [string]$RemoteHost = $env:VITIS_HOST,
    [string]$RemoteDir = $(if ($env:VITIS_DIR) { $env:VITIS_DIR } else { "~/gnn-hls-accel" }),
    [ValidateSet("scatter", "full")]
    [string]$Mode = "scatter"
)

if (-not $RemoteHost) {
    Write-Host "Set your SSH target first:" -ForegroundColor Yellow
    Write-Host '  $env:VITIS_HOST = "gtusername@ece-rschsrv.ece.gatech.edu"'
    Write-Host '  $env:VITIS_DIR  = "~/gnn-hls-accel"'
    Write-Host "  .\orchestration_engine\sync_and_run_vitis.ps1"
    exit 1
}

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Syncing to ${RemoteHost}:${RemoteDir} ..." -ForegroundColor Cyan
ssh $RemoteHost "mkdir -p $RemoteDir/orchestration_engine/characterization/out/phase2"
scp -r orchestration_engine/hls orchestration_engine/tb orchestration_engine/phase2_gate `
    orchestration_engine/run_hls_scatter.tcl orchestration_engine/run_hls.tcl `
    orchestration_engine/run_phase2_scatter_only.sh orchestration_engine/run_phase2.sh `
    orchestration_engine/__init__.py `
    "${RemoteHost}:${RemoteDir}/orchestration_engine/"

$script = if ($Mode -eq "full") { "run_phase2.sh" } else { "run_phase2_scatter_only.sh" }

Write-Host "Running orchestration_engine/$script on remote (~5-15 min) ..." -ForegroundColor Cyan
ssh -t $RemoteHost "cd $RemoteDir && chmod +x orchestration_engine/$script && bash orchestration_engine/$script"

Write-Host "`nPulling results back ..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path orchestration_engine/characterization/out/phase2 | Out-Null
scp -r "${RemoteHost}:${RemoteDir}/oe_scatter_proj" . 2>$null
scp "${RemoteHost}:${RemoteDir}/orchestration_engine/characterization/out/phase2/"*.json `
    orchestration_engine/characterization/out/phase2/ 2>$null

Write-Host "Done. Refresh local gate:" -ForegroundColor Green
Write-Host "  py -3 -m orchestration_engine.phase2_gate.gate_report"
