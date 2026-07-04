#!/usr/bin/env bash
# GCN stream Vitis 2025.2.1 cosim (thesis ap_fixed, E2). NOT used for C1 LS validation.
# C1 uses run_ls_validate_gcn.sh (GNN_LS_LITE on 2023.1 vs trace.pkl).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source "$ROOT/orchestration_engine/hls_env.sh"

echo "=== gcn_stream thesis cosim (2025.2.1 ap_fixed, gcn_stream_cosim_proj) ==="
vitis_hls -f run_hls_stream_cosim.tcl

RPT="$(find gcn_stream_cosim_proj -name '*_cosim.rpt' | head -1)"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

if [[ -n "$RPT" ]]; then
  python3 -m orchestration_engine.phase2_gate.cosim_parser \
    --report "$RPT" \
    --out "$OUT/cosim_gcn_stream.json"
  echo "Wrote $OUT/cosim_gcn_stream.json (thesis E2; not C1 LS pairing)"
fi

