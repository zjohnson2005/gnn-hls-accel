#!/usr/bin/env bash
# Streaming scatter csynth + cosim (steady-state II). Run from repo root on Vitis box.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f orchestration_engine/run_hls_scatter_stream.tcl ]] ||
   [[ ! -f orchestration_engine/tb/oe_hls_stream_tb.cpp ]]; then
  echo "ERROR: streaming scatter scripts missing. Run: git pull origin main"
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

echo "=== streaming scatter csynth + cosim (8 completions / invocation) ==="
rm -rf oe_stream_proj
vitis_hls -f orchestration_engine/run_hls_scatter_stream.tcl

STREAM_RPT="$(find oe_stream_proj -name 'oe_hls_scatter_stream_cosim.rpt' | head -1)"
if [[ -z "$STREAM_RPT" ]]; then
  STREAM_RPT="$(find oe_stream_proj -name '*_cosim.rpt' | head -1)"
fi
echo "stream cosim report: $STREAM_RPT"

mkdir -p orchestration_engine/characterization/out/phase2

if [[ -n "$STREAM_RPT" ]]; then
  # 8 transactions per invocation (OE_STREAM_TB_TRANSACTIONS in the TB).
  python3 -m orchestration_engine.phase2_gate.cosim_parser \
    --report "$STREAM_RPT" --fan-out 2 --transactions 8 \
    --out orchestration_engine/characterization/out/phase2/cosim_stream.json
fi
python3 -m orchestration_engine.phase2_gate.gate_report

echo "Done. See orchestration_engine/characterization/out/phase2/phase2_gate.md"
