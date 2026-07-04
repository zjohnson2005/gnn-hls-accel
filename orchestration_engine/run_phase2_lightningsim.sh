#!/usr/bin/env bash
# LightningSim FIFO DSE on the streaming GCN kernel (DATAFLOW + hls::stream FIFOs).
#
# Toolchain split (important):
#   - Orchestration scatter csynth/cosim (thesis numbers): Vitis 2025.2.1 (hls_env.sh)
#   - LightningSim trace + FIFO DSE: Vitis ARCHIVE 2023.1/2024.x (hls_env_lightningsim.sh)
#   LightningSim/fifo-advisor targets 2021.1–2024.x; 2025.x may break trace.pkl or skew latency.
#
# Run from repo root on the Vitis box (conda activate optional):
#   cd ~/gnn-hls-accel && bash orchestration_engine/run_phase2_lightningsim.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -z "${CONDA_PREFIX:-}" ]] && [[ -d "$HOME/miniconda3/envs/fifo-advisor" ]]; then
  export CONDA_PREFIX="$HOME/miniconda3/envs/fifo-advisor"
fi

_oe_resolve_python() {
  local py cand
  if [[ -n "${OE_PYTHON:-}" ]] && [[ -x "$OE_PYTHON" ]]; then
    if "$OE_PYTHON" -c "import fifo_advisor" 2>/dev/null; then
      echo "$OE_PYTHON"
      return 0
    fi
  fi
  for cand in \
    "${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}" \
    "$HOME/miniconda3/envs/fifo-advisor/bin/python" \
    "$(command -v python 2>/dev/null || true)" \
    "$(command -v python3 2>/dev/null || true)"; do
    [[ -n "$cand" ]] || continue
    [[ -x "$cand" ]] || continue
    if "$cand" -c "import fifo_advisor" 2>/dev/null; then
      echo "$cand"
      return 0
    fi
  done
  echo "ERROR: fifo-advisor not importable. Tried:" >&2
  for cand in \
    "${OE_PYTHON:-}" \
    "${CONDA_PREFIX:+$CONDA_PREFIX/bin/python}" \
    "$HOME/miniconda3/envs/fifo-advisor/bin/python" \
    "$(command -v python 2>/dev/null || true)" \
    "$(command -v python3 2>/dev/null || true)"; do
    [[ -n "$cand" ]] || continue
    echo "  $cand -> $("$cand" -c "import fifo_advisor" 2>&1 || true)" >&2
  done
  echo "Fix: eval \"\$(\$HOME/miniconda3/bin/conda shell.bash hook)\" && conda activate fifo-advisor" >&2
  echo "Or:  export OE_PYTHON=\$HOME/miniconda3/envs/fifo-advisor/bin/python" >&2
  return 1
}

OE_PYTHON="$(_oe_resolve_python)" || exit 1

source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"

# Xilinx settings64 prepends its own python; keep conda env first.
export PATH="$(dirname "$OE_PYTHON"):$PATH"

echo "Using python: $OE_PYTHON ($("$OE_PYTHON" -c 'import fifo_advisor; print("fifo-advisor ok")'))"

# Vitis 2023.2+ compat: make LS find generated headers (hls_signal_handler.h).
"$OE_PYTHON" -m orchestration_engine.eval.patch_lightningsim "$ROOT/gcn_stream_proj/sol1" || exit 1

SOLUTION_DIR="$ROOT/gcn_stream_proj/sol1"
CSYNTH_RPT="$SOLUTION_DIR/syn/report/gcn_layer_stream_csynth.rpt"
LS_TOOLCHAIN_STAMP="$SOLUTION_DIR/.oe_lightningsim_vitis"
# Bump when GNN_LS_LITE source changes (v2 = ap_memory depth pragmas), so the
# trace/DSE build always matches the C1 cosim build (same RTL stamp).
STAMP_TAG="GNN_LS_LITE=df-u16-apmem-v2"

# Rebuild if missing, wrong toolchain, or pre-LS-lite ap_fixed build.
if [[ -f "$CSYNTH_RPT" ]] && [[ -f "$LS_TOOLCHAIN_STAMP" ]] \
   && grep -q "$STAMP_TAG" "$LS_TOOLCHAIN_STAMP"; then
  echo "Reusing $SOLUTION_DIR (built for LightningSim: $(cat "$LS_TOOLCHAIN_STAMP"))"
elif [[ -f "$CSYNTH_RPT" ]]; then
  echo "WARNING: rebuilding $SOLUTION_DIR for LightningSim ($STAMP_TAG required)."
  rm -rf gcn_stream_proj
fi

if [[ ! -f "$CSYNTH_RPT" ]]; then
  echo "=== Building streaming GCN kernel with LightningSim-compatible Vitis ($STAMP_TAG) ==="
  rm -rf gcn_stream_proj
  vitis_hls -f run_hls_stream_ls.tcl
  echo "$(command -v vitis_hls) $STAMP_TAG via ${OE_LS_VITIS_SETTINGS64:-PATH}" > "$LS_TOOLCHAIN_STAMP"
fi

# LightningSim docs/examples use solution1/; Vitis 2023+ defaults to sol1/.
if [[ ! -e "$ROOT/gcn_stream_proj/solution1" ]]; then
  ln -sfn sol1 "$ROOT/gcn_stream_proj/solution1"
fi

if [[ ! -f "$SOLUTION_DIR/trace.pkl" ]]; then
  echo "=== Refresh csim + capture LightningSim trace.pkl ==="
  vitis_hls -f run_hls_stream_csim_refresh.tcl
  if ! "$OE_PYTHON" -m orchestration_engine.eval.capture_ls_trace --solution-dir "$SOLUTION_DIR"; then
    echo "ERROR: gcn_stream trace capture failed — cannot emit trace-backed dse_report.json." >&2
    echo "Fix patch_lightningsim / csim on $SOLUTION_DIR (see run_ls_diagnose.sh)." >&2
    echo "Offline fifo_pareto demos do NOT satisfy the thesis LightningSim gate." >&2
    exit 1
  fi
fi

if [[ ! -d "$SOLUTION_DIR" ]]; then
  echo "ERROR: expected $SOLUTION_DIR after csynth"
  exit 1
fi

mkdir -p orchestration_engine/characterization/out/phase2

echo "=== LightningSim FIFO DSE (500 samples; first run builds trace.pkl) ==="
"$OE_PYTHON" -m orchestration_engine.eval.dse_sweep \
  --solution-dir "$SOLUTION_DIR" \
  --n-samples 500 \
  --batch-size 64 \
  --output orchestration_engine/characterization/out/phase2/dse_report.json

echo ""
"$OE_PYTHON" -m orchestration_engine.phase2_gate.gate_report
echo "Done. See orchestration_engine/characterization/out/phase2/phase2_gate.md"
