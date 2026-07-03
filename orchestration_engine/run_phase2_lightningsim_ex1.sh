#!/usr/bin/env bash
# LightningSim DSE on the official tutorial matrix-multiply example (known LS-compatible).
# Use this when gcn_stream_proj trace capture fails ("kernel did not run") — that design
# has top-level array ports that LS trace hooks do not record on Vitis 2023.x.
#
#   conda activate fifo-advisor
#   bash orchestration_engine/run_phase2_lightningsim_ex1.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LS_DOC="${LS_DOC:-$HOME/lightningsim-doc}"
EX_DIR="$LS_DOC/examples"
SOLUTION_DIR="$EX_DIR/example-1/solution1"
OUT="$ROOT/orchestration_engine/characterization/out/phase2/dse_report.json"

if [[ -n "${CONDA_PREFIX:-}" ]] && [[ -x "$CONDA_PREFIX/bin/python" ]]; then
  OE_PYTHON="$CONDA_PREFIX/bin/python"
else
  OE_PYTHON="$(command -v python || true)"
fi
[[ -n "$OE_PYTHON" ]] || { echo "No python"; exit 1; }
"$OE_PYTHON" -c "import fifo_advisor" 2>/dev/null || {
  echo "Activate fifo-advisor conda env first"; exit 1;
}

source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"
export PATH="$(dirname "$OE_PYTHON"):$PATH"

if [[ ! -d "$EX_DIR/example-1" ]]; then
  echo "Cloning lightningsim-doc examples..."
  git clone --depth=1 https://github.com/sharc-lab/lightningsim-doc.git "$LS_DOC"
fi

CSYNTH="$SOLUTION_DIR/syn/report/matrixmul_csynth.rpt"
if [[ ! -f "$CSYNTH" ]]; then
  echo "=== Building example-1 (matrixmul) with ARCHIVE Vitis ==="
  cd "$EX_DIR"
  vitis_hls -f "$ROOT/orchestration_engine/run_hls_lightningsim_ex1.tcl"
fi

cd "$ROOT"
mkdir -p orchestration_engine/characterization/out/phase2

echo "=== Capturing trace + FIFO DSE on $SOLUTION_DIR ==="
"$OE_PYTHON" -m orchestration_engine.eval.capture_ls_trace --solution-dir "$SOLUTION_DIR" --repo-root "$EX_DIR"
"$OE_PYTHON" -m orchestration_engine.eval.dse_sweep \
  --solution-dir "$SOLUTION_DIR" \
  --n-samples 500 \
  --batch-size 64 \
  --output "$OUT"

"$OE_PYTHON" -m orchestration_engine.phase2_gate.gate_report
echo "Done. DSE on LS reference design (matrixmul). See $OUT"
