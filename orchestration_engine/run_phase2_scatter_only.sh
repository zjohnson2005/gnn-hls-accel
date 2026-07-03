#!/usr/bin/env bash
# Scatter csynth + cosim (~30-90 min). Run from repo root on Vitis box.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp ]] ||
   ! grep -q 'x4 PASSED' orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp; then
  echo "ERROR: repo is stale. Run: git pull origin main"
  echo "  (expect dedicated oe_hls_scatter_cosim_tb.cpp for Vitis 2025.2)"
  exit 1
fi

source /tools/software/xilinx/setup_env.sh

echo "=== scatter csynth + cosim (fan-out=2 anchor x4 for II) ==="
rm -rf oe_scatter_proj
vitis_hls -f orchestration_engine/run_hls_scatter.tcl

SCATTER_RPT="$(find oe_scatter_proj -name 'oe_hls_scatter_kernel_csynth.rpt' | head -1)"
if [[ -z "$SCATTER_RPT" ]]; then
  SCATTER_RPT="$(find oe_scatter_proj -name '*_csynth.rpt' | head -1)"
fi
echo "csynth report: $SCATTER_RPT"

COSIM_RPT="$(find oe_scatter_proj -name 'oe_hls_scatter_kernel_cosim.rpt' | head -1)"
if [[ -z "$COSIM_RPT" ]]; then
  COSIM_RPT="$(find oe_scatter_proj -name '*_cosim.rpt' | head -1)"
fi
echo "cosim report: $COSIM_RPT"

mkdir -p orchestration_engine/characterization/out/phase2

python3 -m orchestration_engine.phase2_gate.csynth_parser --report "$SCATTER_RPT"
if [[ -n "$COSIM_RPT" ]]; then
  python3 -m orchestration_engine.phase2_gate.cosim_parser --report "$COSIM_RPT" --fan-out 2
fi
python3 -m orchestration_engine.phase2_gate.gate_report

echo "Done. See orchestration_engine/characterization/out/phase2/phase2_gate.md"
