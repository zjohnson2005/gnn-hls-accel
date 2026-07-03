# Vitis HLS environment setup — source this from run_*.sh (requires bash).
# Safe under `set -euo pipefail` in the caller.
#
# Order matters:
#   1. Site setup_env.sh — always sourced when present, even if vitis_hls is
#      already on PATH is not (it exports license/site vars that the Xilinx
#      settings scripts do not).
#   2. Xilinx settings64.sh — the proven non-interactive entry point (see
#      build_all.sh); does the export XILINX_VITIS/XILINX_HLS/PATH/
#      LD_LIBRARY_PATH calls itself. Used when vitis_hls is still missing
#      (site setup_env.sh relies on interactive-shell features like modules).

_oe_source_relaxed() {
  # Xilinx scripts reference unset vars (PYTHONPATH) and may return nonzero
  # benignly; relax -u/-e only while sourcing.
  set +u +e
  # shellcheck disable=SC1090
  source "$1"
  set -u -e
}

if ! command -v vitis_hls >/dev/null 2>&1; then
  if [[ -f /tools/software/xilinx/setup_env.sh ]]; then
    _oe_source_relaxed /tools/software/xilinx/setup_env.sh
  fi
fi

if ! command -v vitis_hls >/dev/null 2>&1; then
  for _oe_env in \
    /tools/software/amd/xilinx/2025.2.1/Vitis/settings64.sh \
    /tools/software/xilinx/latest/Vitis/settings64.sh; do
    if [[ -f "$_oe_env" ]]; then
      _oe_source_relaxed "$_oe_env"
    fi
    if command -v vitis_hls >/dev/null 2>&1; then
      break
    fi
  done
  unset _oe_env
fi

if ! command -v vitis_hls >/dev/null 2>&1; then
  echo "ERROR: vitis_hls not on PATH after sourcing site setup_env.sh and"
  echo "Xilinx settings64.sh. In your shell, run:"
  echo "  source /tools/software/xilinx/setup_env.sh"
  echo "then re-run this script."
  exit 1
fi

echo "Using vitis_hls: $(command -v vitis_hls)  (XILINX_VITIS=${XILINX_VITIS:-unset})"
