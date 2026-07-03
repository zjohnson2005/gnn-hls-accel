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
# Everything below goes to both terminal and log; sourcing stays in this shell.
exec > >(tee -a "$LOG") 2>&1

say() { echo; echo "$@"; }
run() { echo; echo "\$ $*"; "$@"; }

PY="${CONDA_PREFIX:-$HOME/miniconda3/envs/fifo-advisor}/bin/python"
LS_BIN="$(dirname "$PY")/lightningsim"

say "================ 1. Versions ================"
run "$PY" -c "import lightningsim; print('lightningsim', getattr(lightningsim, '__version__', 'unknown'))"
run "$PY" -c "import fifo_advisor; print('fifo_advisor ok')"

say "================ 2. Available Vitis toolchains ================"
run ls /tools/software/amd/xilinx/ARCHIVE/Vitis/
run ls /tools/software/amd/xilinx/ARCHIVE/Vitis_HLS/
run ls /tools/software/xilinx/ARCHIVE/Vitis/
run ls /tools/software/xilinx/ARCHIVE/Vitis_HLS/

say "================ 3. Source LS-compatible Vitis ================"
# shellcheck disable=SC1091
if ! source "$ROOT/orchestration_engine/hls_env_lightningsim.sh"; then
  say "VERDICT: no usable ARCHIVE toolchain found. Paste this log."
  exit 1
fi
export PATH="$(dirname "$PY"):$PATH"
run command -v vitis_hls

say "================ 4. CONTROL: LS tutorial example-1 ================"
LS_DOC="${LS_DOC:-$HOME/lightningsim-doc}"
EX_DIR="$LS_DOC/examples"
EX_SOL="$EX_DIR/example-1/solution1"
if [[ ! -d "$EX_DIR/example-1" ]]; then
  run git clone --depth=1 https://github.com/sharc-lab/lightningsim-doc.git "$LS_DOC"
fi
if [[ ! -f "$EX_SOL/syn/report/matrixmul_csynth.rpt" ]]; then
  say "--- building example-1 (few minutes) ---"
  ( cd "$EX_DIR" && vitis_hls -f "$ROOT/orchestration_engine/run_hls_lightningsim_ex1.tcl" ) | tail -30
fi
EX1_RC=125
if [[ -f "$EX_SOL/syn/report/matrixmul_csynth.rpt" ]]; then
  rm -f "$EX_SOL/trace.pkl"
  ( cd "$EX_DIR" && timeout 900 "$LS_BIN" --cli "$EX_SOL" )
  EX1_RC=$?
else
  say "example-1 csynth FAILED - cannot run LS control (see build output above)"
fi
say ">>> example-1 exit code: $EX1_RC (0=pass, 124=timeout/hang, 125=build failed)"

say "================ 5. gcn_stream trace capture ================"
STAMP="$ROOT/gcn_stream_proj/sol1/.oe_lightningsim_vitis"
CUR_VITIS="$(command -v vitis_hls)"
if [[ ! -f "$STAMP" ]] || ! grep -qF "$CUR_VITIS" "$STAMP" 2>/dev/null; then
  say "--- rebuilding gcn_stream_proj with $CUR_VITIS (10-20 min) ---"
  rm -rf "$ROOT/gcn_stream_proj"
  ( cd "$ROOT" && vitis_hls -f run_hls_stream_ls.tcl ) | tail -30
  echo "$CUR_VITIS" > "$STAMP" 2>/dev/null || true
fi
GCN_RC=125
if [[ -f "$ROOT/gcn_stream_proj/sol1/syn/report/gcn_layer_stream_csynth.rpt" ]]; then
  rm -f "$ROOT/gcn_stream_proj/sol1/trace.pkl"
  ( cd "$ROOT" && timeout 1800 "$LS_BIN" --cli "$ROOT/gcn_stream_proj/sol1" )
  GCN_RC=$?
else
  say "gcn_stream csynth FAILED - see build output above"
fi
say ">>> gcn_stream exit code: $GCN_RC"

say "================ VERDICT ================"
say "example-1 (LS reference design): exit $EX1_RC"
say "gcn_stream (our DATAFLOW kernel): exit $GCN_RC"
if [[ "$EX1_RC" -ne 0 ]]; then
  say "-> H1 TOOLCHAIN: LS cannot trace even its own tutorial on this Vitis."
  say "   Fix: try another ARCHIVE version (set OE_LS_VITIS_SETTINGS64) or patch LS."
elif [[ "$GCN_RC" -ne 0 ]]; then
  say "-> H2 DESIGN SHAPE: toolchain fine; LS hooks miss gcn_layer_stream."
  say "   Next: bisect kernel interface shape + patch LightningSim."
else
  say "-> Both passed. Re-run: bash orchestration_engine/run_phase2_lightningsim.sh"
fi
say ""
say "Log written to $LOG"
