#!/usr/bin/env bash
# C1 (thesis pillar): Vitis cosim vs LightningSim on the SAME GNN_LS_LITE RTL stamp.
# Does NOT overwrite gcn_stream_proj/sol1/trace.pkl (uses gcn_stream_ls_cosim_proj).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/orchestration_engine/characterization/out/phase2"
mkdir -p "$OUT"

if [[ -z "${CONDA_PREFIX:-}" ]] && [[ -d "$HOME/miniconda3/envs/fifo-advisor" ]]; then
  export CONDA_PREFIX="$HOME/miniconda3/envs/fifo-advisor"
fi

_oe_resolve_python() {
  local cand
  for cand in \
    "${OE_PYTHON:-}" \
    "${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}" \
    "$HOME/miniconda3/envs/fifo-advisor/bin/python" \
    "$(command -v python3 2>/dev/null || true)"; do
    [[ -n "$cand" ]] || continue
    [[ -x "$cand" ]] || continue
    if "$cand" -c "import fifo_advisor" 2>/dev/null; then
      echo "$cand"
      return 0
    fi
  done
  echo "ERROR: fifo-advisor required for C1 / LightningSim validation." >&2
  return 1
}

OE_PYTHON="$(_oe_resolve_python)" || exit 1
export PATH="$(dirname "$OE_PYTHON"):$PATH"

source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"

if [[ -n "${CONDA_PREFIX:-}" ]] && [[ -x "$CONDA_PREFIX/bin/python" ]]; then
  export PATH="$CONDA_PREFIX/bin:$PATH"
  OE_PYTHON="$CONDA_PREFIX/bin/python"
fi

if [[ ! -f "$ROOT/gcn_stream_proj/sol1/trace.pkl" ]]; then
  echo "ERROR: missing gcn_stream_proj/sol1/trace.pkl — run run_phase2_lightningsim.sh first." >&2
  exit 1
fi

echo "=== C1: GNN_LS_LITE Vitis cosim (2023.1) paired with LS trace build ==="
echo "Using python: $OE_PYTHON"

# Drop stale Vitis side if csynth-only or missing cosim.rpt (pairs ~37 cyc vs LS ~315).
if [[ -f "$OUT/cosim_gcn_stream_ls.json" ]]; then
  if ! "$OE_PYTHON" -c "
from pathlib import Path
import json
from orchestration_engine.phase2_gate.ls_gate import gcn_ls_cosim_json_valid
p = Path('$OUT/cosim_gcn_stream_ls.json')
ok, _ = gcn_ls_cosim_json_valid(json.loads(p.read_text(encoding='utf-8')))
raise SystemExit(0 if ok else 1)
"; then
    echo "Removing stale invalid cosim_gcn_stream_ls.json (not real cosim)"
    rm -f "$OUT/cosim_gcn_stream_ls.json" "$OUT/ls_gcn_eval.json"
  fi
fi

if ! vitis_hls -f run_hls_stream_ls_cosim.tcl; then
  echo ""
  echo "ERROR: GNN_LS_LITE cosim failed. C1 cannot pass without real cosim cycles." >&2
  echo "Check ap_memory depth pragmas in src/gcn_layer_stream.cpp (GNN_LS_LITE top)." >&2
  echo "Do NOT use csynth-only numbers for LightningSim validation." >&2
  exit 1
fi

RPT="$(find gcn_stream_ls_cosim_proj -name '*_cosim.rpt' | head -1)"
if [[ -z "$RPT" ]]; then
  echo "ERROR: cosim finished but no *_cosim.rpt found" >&2
  exit 1
fi

"$OE_PYTHON" -m orchestration_engine.phase2_gate.cosim_parser \
  --report "$RPT" \
  --out "$OUT/cosim_gcn_stream_ls.json"

echo "=== C1: fresh LightningSim eval on gcn_stream_proj/sol1 ==="
"$OE_PYTHON" -m orchestration_engine.eval.ls_capture_gcn_eval

"$OE_PYTHON" -m orchestration_engine.eval.ls_validate --mode ls_lite
"$OE_PYTHON" -m orchestration_engine.phase2_gate.gate_report --refresh

echo "Done. See $OUT/ls_validation.json"
