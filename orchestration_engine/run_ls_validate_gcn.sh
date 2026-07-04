#!/usr/bin/env bash
# C1: compare Vitis cosim vs LightningSim on the SAME GNN_LS_LITE build (2023.1).
# Does NOT touch gcn_stream_proj/sol1/trace.pkl.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

if [[ -n "${CONDA_PREFIX:-}" ]] && [[ -x "$CONDA_PREFIX/bin/python" ]]; then
  export PATH="$CONDA_PREFIX/bin:$PATH"
fi

source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"

echo "=== gcn_stream GNN_LS_LITE cosim (2023.1 ARCHIVE, paired with LS trace) ==="
vitis_hls -f run_hls_stream_ls_cosim.tcl

RPT="$(find gcn_stream_ls_cosim_proj -name '*_cosim.rpt' | head -1)"
if [[ -n "$RPT" ]]; then
  python3 -m orchestration_engine.phase2_gate.cosim_parser \
    --report "$RPT" \
    --out "$OUT/cosim_gcn_stream_ls.json"
fi

python3 -m orchestration_engine.eval.ls_validate --mode ls_lite
python3 -m orchestration_engine.phase2_gate.gate_report

echo "Done. See $OUT/ls_validation.json"
