#!/usr/bin/env bash
# Scatter csynth (regression project) + cosim (dedicated x4 project).
# Run from repo root on Vitis box.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp ]] ||
   ! grep -q 'x4 PASSED' orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp; then
  echo "ERROR: repo is stale. Run: git pull origin main"
  exit 1
fi

# Xilinx env: prefer the caller's shell (setup_env.sh may rely on interactive
# features like environment modules). Only try sourcing as a fallback.
if ! command -v vitis_hls >/dev/null 2>&1; then
  set +u +e
  source /tools/software/xilinx/setup_env.sh
  set -u -e
fi
if ! command -v vitis_hls >/dev/null 2>&1; then
  echo "ERROR: vitis_hls not on PATH. In your shell, first run:"
  echo "  source /tools/software/xilinx/setup_env.sh"
  exit 1
fi

echo "=== scatter csynth + csim regression (oe_scatter_proj) ==="
rm -rf oe_scatter_proj
vitis_hls -f orchestration_engine/run_hls_scatter.tcl

echo ""
echo "=== scatter cosim x4 for II (oe_scatter_cosim_proj) ==="
rm -rf oe_scatter_cosim_proj
vitis_hls -f orchestration_engine/run_hls_scatter_cosim_only.tcl

SCATTER_RPT="$(find oe_scatter_proj -name 'oe_hls_scatter_kernel_csynth.rpt' | head -1)"
echo "csynth report: $SCATTER_RPT"

COSIM_RPT="$(find oe_scatter_cosim_proj -name 'oe_hls_scatter_kernel_cosim.rpt' | head -1)"
echo "cosim report: $COSIM_RPT"

mkdir -p orchestration_engine/characterization/out/phase2

python3 -m orchestration_engine.phase2_gate.csynth_parser --report "$SCATTER_RPT"
if [[ -n "$COSIM_RPT" ]]; then
  python3 -m orchestration_engine.phase2_gate.cosim_parser --report "$COSIM_RPT" --fan-out 2
fi
python3 -m orchestration_engine.phase2_gate.gate_report

echo "Done. See orchestration_engine/characterization/out/phase2/phase2_gate.md"
