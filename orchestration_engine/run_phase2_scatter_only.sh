#!/usr/bin/env bash
# Fast path: scatter csynth only (~5-15 min). Run from repo root on Vitis box.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source /tools/software/xilinx/setup_env.sh
export PATH="/tools/software/xilinx/ARCHIVE/Vitis_HLS/2024.2/bin:${PATH}"

echo "=== scatter csynth only ==="
rm -rf oe_scatter_proj
vitis_hls -f orchestration_engine/run_hls_scatter.tcl

SCATTER_RPT="$(find oe_scatter_proj -name 'oe_hls_scatter_kernel_csynth.rpt' | head -1)"
if [[ -z "$SCATTER_RPT" ]]; then
  SCATTER_RPT="$(find oe_scatter_proj -name '*_csynth.rpt' | head -1)"
fi
echo "csynth report: $SCATTER_RPT"

mkdir -p orchestration_engine/characterization/out/phase2

python3 -m orchestration_engine.phase2_gate.csynth_parser --report "$SCATTER_RPT"
python3 -m orchestration_engine.phase2_gate.gate_report

echo "Done. See orchestration_engine/characterization/out/phase2/phase2_gate.md"
