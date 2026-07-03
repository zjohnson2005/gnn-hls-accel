#!/usr/bin/env bash
# One-shot LightningSim compatibility diagnosis.
#
# Splits the "kernel did not run" failure into its two possible causes:
#   H1 toolchain: Vitis bitcode too new for LS's LLVM tooling
#      -> the LS tutorial design (example-1) ALSO fails on this toolchain
#   H2 design shape: LS trace hooks miss our kernel (array top ports /
#      struct-payload hls::stream) -> example-1 passes, gcn_stream fails
#
# Usage (inside fifo-advisor conda env):
#   bash orchestration_engine/run_ls_diagnose.sh
# Then paste ls_diagnose.log (or its tail).
set -uo pipefail   # no -e: keep going and collect all evidence

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="$ROOT/ls_diagnose.log"
: > "$LOG"

say() { echo "$@" | tee -a "$LOG"; }
run() { say ""; say "\$ $*"; "$@" 2>&1 | tee -a "$LOG"; }

PY="${CONDA_PREFIX:-$HOME/miniconda3/envs/fifo-advisor}/bin/python"
LS_BIN="$(dirname "$PY")/lightningsim"

say "================ 1. Versions ================"
run "$PY" -c "import lightningsim; print('lightningsim', getattr(lightningsim, '__version__', 'unknown'))"
run "$PY" -c "import fifo_advisor; print('fifo_advisor', getattr(fifo_advisor, '__version__', 'unknown'))"

say ""
say "================ 2. Available Vitis toolchains ================"
run ls /tools/software/xilinx/ARCHIVE/Vitis_HLS/
run ls /tools/software/xilinx/ARCHIVE/Vitis/
run ls /tools/software/amd/xilinx/

say ""
say "================ 3. Source LS-compatible Vitis ================"
# shellcheck disable=SC1091
source "$ROOT/orchestration_engine/hls_env_lightningsim.sh" 2>&1 | tee -a "$LOG"
export PATH="$(dirname "$PY"):$PATH"
run command -v vitis_hls
run vitis_hls -version

say ""
say "================ 4. CONTROL: LS tutorial example-1 ================"
LS_DOC="${LS_DOC:-$HOME/lightningsim-doc}"
EX_DIR="$LS_DOC/examples"
if [[ ! -d "$EX_DIR/example-1" ]]; then
  run git clone --depth=1 https://github.com/sharc-lab/lightningsim-doc.git "$LS_DOC"
fi
if [[ ! -f "$EX_DIR/example-1/solution1/syn/report/matrixmul_csynth.rpt" ]]; then
  say "--- building example-1 (few minutes) ---"
  ( cd "$EX_DIR" && vitis_hls -f "$ROOT/orchestration_engine/run_hls_lightningsim_ex1.tcl" ) 2>&1 | tail -20 | tee -a "$LOG"
fi
if [[ -x "$LS_BIN" ]]; then
  run "$LS_BIN" --cli --skip-wait-for-synthesis "$EX_DIR/example-1/solution1"
else
  run "$PY" -m orchestration_engine.eval.capture_ls_trace \
    --solution-dir "$EX_DIR/example-1/solution1" --repo-root "$EX_DIR"
fi
EX1_RC=$?
say ""
say ">>> example-1 trace capture exit code: $EX1_RC (0 = H2 design shape, nonzero = H1 toolchain)"

say ""
say "================ 5. gcn_stream trace capture (verbose) ================"
# The project must be built with the SAME toolchain LS runs against,
# otherwise version effects confound the design-shape test.
STAMP="$ROOT/gcn_stream_proj/sol1/.oe_lightningsim_vitis"
CUR_VITIS="$(command -v vitis_hls)"
if [[ ! -f "$STAMP" ]] || ! grep -qF "$CUR_VITIS" "$STAMP" 2>/dev/null; then
  say "--- rebuilding gcn_stream_proj with $CUR_VITIS (10-20 min) ---"
  rm -rf "$ROOT/gcn_stream_proj"
  ( cd "$ROOT" && vitis_hls -f run_hls_stream_ls.tcl ) 2>&1 | tail -20 | tee -a "$LOG"
  echo "$CUR_VITIS" > "$STAMP" 2>/dev/null || true
fi
rm -f "$ROOT/gcn_stream_proj/sol1/trace.pkl"
if [[ -x "$LS_BIN" ]]; then
  run "$LS_BIN" --cli --skip-wait-for-synthesis "$ROOT/gcn_stream_proj/sol1"
else
  run "$PY" -m orchestration_engine.eval.capture_ls_trace \
    --solution-dir "$ROOT/gcn_stream_proj/sol1"
fi
GCN_RC=$?

say ""
say "================ VERDICT ================"
say "example-1 (LS reference design): exit $EX1_RC"
say "gcn_stream (our DATAFLOW kernel): exit $GCN_RC"
if [[ "$EX1_RC" -ne 0 ]]; then
  say "-> H1 TOOLCHAIN: LS cannot trace even its own tutorial on this Vitis."
  say "   Fix: rebuild with a Vitis version LS supports (2021.1 ideal, 2024.x ok)."
elif [[ "$GCN_RC" -ne 0 ]]; then
  say "-> H2 DESIGN SHAPE: toolchain fine; LS hooks miss gcn_layer_stream."
  say "   Next: bisect kernel shape (array top ports / struct stream) + patch LS."
else
  say "-> Both passed. Re-run: bash orchestration_engine/run_phase2_lightningsim.sh"
fi
say ""
say "Log written to $LOG"
