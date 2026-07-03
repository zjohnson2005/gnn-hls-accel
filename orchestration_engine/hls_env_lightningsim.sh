# Vitis HLS environment for LightningSim / fifo-advisor trace capture.
# Use this ONLY for LS trace + FIFO DSE — NOT for orchestration scatter cosim.
#
# LightningSim's LLVM tooling and AXI models were built against Vitis 2021.1
# (its gold-standard version); 0.2.x added support through 2024.x. 2025.x
# bitcode breaks trace capture. Thesis scatter numbers stay on 2025.2.1 via
# hls_env.sh; this file picks the most LS-compatible ARCHIVE toolchain.
#
# Both site trees are probed: /tools/software/amd/xilinx/ARCHIVE/... and
# /tools/software/xilinx/ARCHIVE/... (the box symlinks between them).

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
  # 2021.1 first (LS gold standard), then newest-supported downward.
  for _oe_ls_ver in 2021.1 2024.2 2024.1 2023.2 2023.1 2022.2 2022.1; do
    for _oe_ls_env in \
      "/tools/software/amd/xilinx/ARCHIVE/Vitis/$_oe_ls_ver/settings64.sh" \
      "/tools/software/xilinx/ARCHIVE/Vitis/$_oe_ls_ver/settings64.sh" \
      "/tools/software/amd/xilinx/ARCHIVE/Vitis_HLS/$_oe_ls_ver/settings64.sh" \
      "/tools/software/xilinx/ARCHIVE/Vitis_HLS/$_oe_ls_ver/settings64.sh"; do
      if [[ -f "$_oe_ls_env" ]]; then
        _oe_ls_source_relaxed "$_oe_ls_env"
        if command -v vitis_hls >/dev/null 2>&1; then
          export OE_LS_VITIS_SETTINGS64="$_oe_ls_env"
          break 2
        fi
      fi
    done
  done
  unset _oe_ls_ver _oe_ls_env
fi

if ! command -v vitis_hls >/dev/null 2>&1; then
  for _oe_ls_ver in 2021.1 2024.2 2024.1 2023.2 2023.1; do
    for _oe_ls_bin in \
      "/tools/software/amd/xilinx/ARCHIVE/Vitis_HLS/$_oe_ls_ver/bin/vitis_hls" \
      "/tools/software/xilinx/ARCHIVE/Vitis_HLS/$_oe_ls_ver/bin/vitis_hls" \
      "/tools/software/amd/xilinx/ARCHIVE/Vitis/$_oe_ls_ver/bin/vitis_hls" \
      "/tools/software/xilinx/ARCHIVE/Vitis/$_oe_ls_ver/bin/vitis_hls"; do
      if [[ -x "$_oe_ls_bin" ]]; then
        export PATH="$(dirname "$_oe_ls_bin"):$PATH"
        break 2
      fi
    done
  done
  unset _oe_ls_ver _oe_ls_bin
fi

if ! command -v vitis_hls >/dev/null 2>&1; then
  echo "ERROR: no LightningSim-compatible vitis_hls found (need ARCHIVE 2021-2024)."
  echo "Checked /tools/software/{amd/,}xilinx/ARCHIVE/{Vitis,Vitis_HLS}/<ver>/"
  echo "Set OE_LS_VITIS_SETTINGS64=/path/to/settings64.sh and re-run."
  # return when sourced, exit when executed
  return 1 2>/dev/null || exit 1
fi

echo "LightningSim HLS toolchain: $(command -v vitis_hls)  (XILINX_VITIS=${XILINX_VITIS:-unset})"
