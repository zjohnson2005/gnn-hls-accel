#!/usr/bin/env bash
# GCN stream Vitis 2025.2.1 cosim for ls_validate (does NOT touch gcn_stream_proj trace).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source "$ROOT/orchestration_engine/hls_env.sh"

echo "=== gcn_stream cosim (2025.2.1, separate gcn_stream_cosim_proj) ==="
vitis_hls -f run_hls_stream_cosim.tcl

RPT="$(find gcn_stream_cosim_proj -name '*_cosim.rpt' | head -1)"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

if [[ -n "$RPT" ]]; then
  python3 -m orchestration_engine.phase2_gate.cosim_parser \
    --report "$RPT" \
    --out "$OUT/cosim_gcn_stream.json"
fi

python3 -m orchestration_engine.eval.ls_validate
python3 -m orchestration_engine.phase2_gate.gate_report

echo "Done. See $OUT/ls_validation.json"
