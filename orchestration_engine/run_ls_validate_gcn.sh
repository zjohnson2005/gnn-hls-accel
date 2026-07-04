#!/usr/bin/env bash
# C1: compare Vitis cosim vs LightningSim on the SAME GNN_LS_LITE build (2023.1).
# Does NOT touch gcn_stream_proj/sol1/trace.pkl.
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
  echo "WARN: fifo_advisor not found; LS side will fall back to dse_report.json" >&2
  for cand in \
    "${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}" \
    "$HOME/miniconda3/envs/fifo-advisor/bin/python" \
    "$(command -v python3 2>/dev/null || true)"; do
    [[ -n "$cand" ]] && [[ -x "$cand" ]] && echo "$cand" && return 0
  done
  echo "python3"
}

OE_PYTHON="$(_oe_resolve_python)"
export PATH="$(dirname "$OE_PYTHON"):$PATH"

source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"

# Xilinx settings64.sh prepends its python; keep conda/miniconda first for fifo_advisor.
if [[ -n "${CONDA_PREFIX:-}" ]] && [[ -x "$CONDA_PREFIX/bin/python" ]]; then
  export PATH="$CONDA_PREFIX/bin:$PATH"
  OE_PYTHON="$CONDA_PREFIX/bin/python"
fi

echo "=== gcn_stream GNN_LS_LITE cosim (2023.1 ARCHIVE, paired with LS trace) ==="
echo "Using python: $OE_PYTHON"
vitis_hls -f run_hls_stream_ls_cosim.tcl

RPT="$(find gcn_stream_ls_cosim_proj -name '*_cosim.rpt' | head -1)"
if [[ -n "$RPT" ]]; then
  "$OE_PYTHON" -m orchestration_engine.phase2_gate.cosim_parser \
    --report "$RPT" \
    --out "$OUT/cosim_gcn_stream_ls.json"
fi

"$OE_PYTHON" -m orchestration_engine.eval.ls_validate --mode ls_lite
"$OE_PYTHON" -m orchestration_engine.phase2_gate.gate_report --refresh

echo "Done. See $OUT/ls_validation.json"
