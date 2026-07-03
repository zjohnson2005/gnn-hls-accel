#!/usr/bin/env bash
# Re-run scatter cosim on an existing oe_scatter_proj (~20-60 min).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d oe_scatter_proj ]]; then
  echo "oe_scatter_proj not found — run run_phase2_scatter_only.sh first."
  exit 1
fi

source /tools/software/xilinx/setup_env.sh
export PATH="/tools/software/xilinx/ARCHIVE/Vitis_HLS/2024.2/bin:${PATH}"

echo "=== scatter cosim only (fan-out=2 anchor) ==="
vitis_hls -f orchestration_engine/run_hls_scatter_cosim_only.tcl

COSIM_RPT="$(find oe_scatter_proj -name 'oe_hls_scatter_kernel_cosim.rpt' | head -1)"
echo "cosim report: $COSIM_RPT"

mkdir -p orchestration_engine/characterization/out/phase2
python3 -m orchestration_engine.phase2_gate.cosim_parser --report "$COSIM_RPT" --fan-out 2
python3 -m orchestration_engine.phase2_gate.gate_report

echo "Done. See orchestration_engine/characterization/out/phase2/phase2_gate.md"
