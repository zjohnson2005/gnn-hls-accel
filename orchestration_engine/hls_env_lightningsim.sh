# Vitis HLS environment for LightningSim / fifo-advisor trace capture.
# Use this ONLY for gcn_stream_proj + DSE — NOT for orchestration scatter cosim.
#
# LightningSim (fifo-advisor 0.2.x) is tested against Vitis 2021.1–2024.x.
# Newer toolchains (2025.x) may fail trace.pkl generation or skew FIFO latency
# because LS AXI models match 2021.1-era interface code (see LightningSim docs).
# Thesis scatter numbers stay on 2025.2.1 via hls_env.sh; this file picks an
# ARCHIVE toolchain the box actually has.

_oe_ls_source_relaxed() {
  set +u +e
  # shellcheck disable=SC1090
  source "$1"
  set -u -e
}

if [[ -n "${OE_LS_VITIS_SETTINGS64:-}" ]] && [[ -f "$OE_LS_VITIS_SETTINGS64" ]]; then
  _oe_ls_source_relaxed "$OE_LS_VITIS_SETTINGS64"
fi

if ! command -v vitis_hls >/dev/null 2>&1; then
  # 2021.1 first: LightningSim's gold-standard version (its LLVM tooling and
  # AXI models were built against it). Then newest-supported downward.
  for _oe_ls_env in \
    /tools/software/xilinx/ARCHIVE/Vitis/2021.1/settings64.sh \
    /tools/software/xilinx/ARCHIVE/Vitis_HLS/2021.1/settings64.sh \
    /tools/software/xilinx/ARCHIVE/Vitis/2024.2/settings64.sh \
    /tools/software/xilinx/ARCHIVE/Vitis_HLS/2024.2/settings64.sh \
    /tools/software/xilinx/ARCHIVE/Vitis/2023.1/settings64.sh \
    /tools/software/xilinx/ARCHIVE/Vitis_HLS/2023.1/settings64.sh; do
    if [[ -f "$_oe_ls_env" ]]; then
      _oe_ls_source_relaxed "$_oe_ls_env"
      if command -v vitis_hls >/dev/null 2>&1; then
        export OE_LS_VITIS_SETTINGS64="$_oe_ls_env"
        break
      fi
    fi
  done
  unset _oe_ls_env
fi

if ! command -v vitis_hls >/dev/null 2>&1; then
  for _oe_ls_bin in \
    /tools/software/xilinx/ARCHIVE/Vitis_HLS/2021.1/bin/vitis_hls \
    /tools/software/xilinx/ARCHIVE/Vitis_HLS/2024.2/bin/vitis_hls \
    /tools/software/xilinx/ARCHIVE/Vitis_HLS/2023.1/bin/vitis_hls; do
    if [[ -x "$_oe_ls_bin" ]]; then
      export PATH="$(dirname "$_oe_ls_bin"):$PATH"
      break
    fi
  done
  unset _oe_ls_bin
fi

if ! command -v vitis_hls >/dev/null 2>&1; then
  echo "ERROR: no LightningSim-compatible vitis_hls found (need ARCHIVE 2021–2024)."
  echo "Set OE_LS_VITIS_SETTINGS64=/path/to/settings64.sh and re-run."
  exit 1
fi

echo "LightningSim HLS toolchain: $(command -v vitis_hls)  (XILINX_VITIS=${XILINX_VITIS:-unset})"
