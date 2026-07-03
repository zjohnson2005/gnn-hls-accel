#!/usr/bin/env bash
# LightningSim FIFO DSE on the streaming GCN kernel (DATAFLOW + hls::stream FIFOs).
#
# Toolchain split (important):
#   - Orchestration scatter csynth/cosim (thesis numbers): Vitis 2025.2.1 (hls_env.sh)
#   - LightningSim trace + FIFO DSE: Vitis ARCHIVE 2023.1/2024.x (hls_env_lightningsim.sh)
#   LightningSim/fifo-advisor targets 2021.1–2024.x; 2025.x may break trace.pkl or skew latency.
#
# Run from repo root on the Vitis box, inside the fifo-advisor conda env:
#   conda activate fifo-advisor
#   cd ~/gnn-hls-accel && bash orchestration_engine/run_phase2_lightningsim.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Keep conda python — Xilinx settings64 prepends its own python to PATH.
if [[ -n "${CONDA_PREFIX:-}" ]] && [[ -x "$CONDA_PREFIX/bin/python" ]]; then
  OE_PYTHON="$CONDA_PREFIX/bin/python"
else
  OE_PYTHON="$(command -v python || true)"
fi

if [[ -z "$OE_PYTHON" ]] || ! "$OE_PYTHON" -c "import fifo_advisor" 2>/dev/null; then
  echo "ERROR: fifo-advisor not importable."
  echo "  eval \"\$(\$HOME/miniconda3/bin/conda shell.bash hook)\""
  echo "  conda activate fifo-advisor"
  exit 1
fi

source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"

if [[ -n "${CONDA_PREFIX:-}" ]] && [[ -x "$CONDA_PREFIX/bin/python" ]]; then
  export PATH="$CONDA_PREFIX/bin:$PATH"
  OE_PYTHON="$CONDA_PREFIX/bin/python"
fi

echo "Using python: $OE_PYTHON ($("$OE_PYTHON" -c 'import fifo_advisor; print("fifo-advisor ok")'))"

SOLUTION_DIR="$ROOT/gcn_stream_proj/sol1"
CSYNTH_RPT="$SOLUTION_DIR/syn/report/gcn_layer_stream_csynth.rpt"
LS_TOOLCHAIN_STAMP="$SOLUTION_DIR/.oe_lightningsim_vitis"

# Rebuild if missing or if a previous build used the wrong (2025.x) toolchain.
if [[ -f "$CSYNTH_RPT" ]] && [[ -f "$LS_TOOLCHAIN_STAMP" ]]; then
  echo "Reusing $SOLUTION_DIR (built for LightningSim: $(cat "$LS_TOOLCHAIN_STAMP"))"
elif [[ -f "$CSYNTH_RPT" ]]; then
  echo "WARNING: $CSYNTH_RPT exists but was not built via hls_env_lightningsim.sh."
  echo "Removing gcn_stream_proj and rebuilding with ARCHIVE Vitis for trace capture."
  rm -rf gcn_stream_proj
fi

if [[ ! -f "$CSYNTH_RPT" ]]; then
  echo "=== Building streaming GCN kernel with LightningSim-compatible Vitis ==="
  rm -rf gcn_stream_proj
  vitis_hls -f run_hls_stream.tcl
  echo "$(command -v vitis_hls) via ${OE_LS_VITIS_SETTINGS64:-PATH}" > "$LS_TOOLCHAIN_STAMP"
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
