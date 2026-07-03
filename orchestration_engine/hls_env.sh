# Vitis HLS environment setup — source this from run_*.sh (requires bash).
# Safe under `set -euo pipefail` in the caller.
#
# Strategy:
#   1. vitis_hls already on PATH (caller sourced the env) — use as-is.
#   2. Source the site setup_env.sh (license/site vars; interactive-only for
#      PATH on some boxes, so we don't rely on it alone).
#   3. Source any Xilinx Vitis settings64.sh we can find (does the
#      export XILINX_VITIS / PATH / LD_LIBRARY_PATH calls itself).
#   4. Last resort: find the vitis_hls launcher binary directly and prepend
#      its bin dir to PATH (the launcher self-locates its own env).

_oe_source_relaxed() {
  # Xilinx scripts reference unset vars (PYTHONPATH) and may return nonzero
  # benignly; relax -u/-e only while sourcing.
  set +u +e
  # shellcheck disable=SC1090
  source "$1"
  set -u -e
}

_oe_env_tried=""

if ! command -v vitis_hls >/dev/null 2>&1; then
  for _oe_env in \
    /tools/software/amd/xilinx/2025.2.1/Vitis/settings64.sh \
    /tools/software/amd/xilinx/*/Vitis/settings64.sh \
    /tools/software/amd/xilinx/*/Vitis/*/settings64.sh \
    /tools/software/xilinx/latest/Vitis/settings64.sh \
    /tools/software/xilinx/*/Vitis/settings64.sh \
    /tools/software/xilinx/*/Vitis_HLS/*/settings64.sh; do
    if [[ -f "$_oe_env" ]]; then
      _oe_source_relaxed "$_oe_env"
      _oe_env_tried="$_oe_env_tried $_oe_env"
      if command -v vitis_hls >/dev/null 2>&1; then
        break
      fi
    fi
  done
  unset _oe_env
fi

if ! command -v vitis_hls >/dev/null 2>&1; then
  if [[ -f /tools/software/xilinx/setup_env.sh ]]; then
    _oe_source_relaxed /tools/software/xilinx/setup_env.sh
    _oe_env_tried="$_oe_env_tried /tools/software/xilinx/setup_env.sh"
  fi
fi

if ! command -v vitis_hls >/dev/null 2>&1; then
  for _oe_bin in \
    /tools/software/amd/xilinx/*/Vitis/bin/vitis_hls \
    /tools/software/xilinx/latest/Vitis/bin/vitis_hls \
    /tools/software/xilinx/*/Vitis/bin/vitis_hls \
    /tools/software/xilinx/*/Vitis_HLS/*/bin/vitis_hls; do
    if [[ -x "$_oe_bin" ]]; then
      export PATH="$(dirname "$_oe_bin"):$PATH"
      _oe_env_tried="$_oe_env_tried $_oe_bin(direct)"
      break
    fi
  done
  unset _oe_bin
fi

if ! command -v vitis_hls >/dev/null 2>&1; then
  echo "ERROR: vitis_hls not on PATH."
  echo "Tried:${_oe_env_tried:- (no candidate files found)}"
  echo ""
  echo "--- diagnostics ---"
  ls -d /tools/software/xilinx/* 2>/dev/null || echo "(no /tools/software/xilinx)"
  ls -d /tools/software/amd/xilinx/* 2>/dev/null || echo "(no /tools/software/amd/xilinx)"
  echo "-------------------"
  echo "In a shell where vitis_hls works, run 'command -v vitis_hls' and report"
  echo "the path so hls_env.sh can be fixed. Meanwhile, source the env in your"
  echo "shell first:  source /tools/software/xilinx/setup_env.sh"
  exit 1
fi

echo "Using vitis_hls: $(command -v vitis_hls)  (XILINX_VITIS=${XILINX_VITIS:-unset})"
