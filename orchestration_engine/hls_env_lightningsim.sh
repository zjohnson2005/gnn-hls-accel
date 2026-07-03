# Vitis HLS environment for LightningSim / fifo-advisor trace capture.
# Use this ONLY for LS trace + FIFO DSE — NOT for orchestration scatter cosim.
#
# LightningSim's LLVM tooling and AXI models were built against Vitis 2021.1
# (its gold-standard version); 0.2.x added support through 2024.x. 2025.x
# bitcode breaks trace capture. Thesis scatter numbers stay on 2025.2.1 via
# hls_env.sh; this file picks the most LS-compatible ARCHIVE toolchain.
#
# CRITICAL: LightningSim compiles its testbench support code against
# $XILINX_HLS/include and links via $XILINX_HLS/include/Makefile.sysc.rules.
# If XILINX_HLS points at a different Vitis version than the one that built
# the project bitcode, ap_fixed/hls::stream ABI mismatches cause the
# instrumented testbench to SEGFAULT (surfaces as "kernel did not run").
# So this script always force-aligns XILINX_HLS with the vitis_hls it picks,
# even when the calling shell already has a (possibly mixed) Xilinx env.
#
# Both site trees are probed: /tools/software/amd/xilinx/ARCHIVE/... and
# /tools/software/xilinx/ARCHIVE/... (the box symlinks between them).

_oe_ls_source_relaxed() {
  set +u +e
  # shellcheck disable=SC1090
  source "$1"
  set -u -e
}

# Accept a pre-existing vitis_hls only if it is an LS-compatible version
# (2021.x-2024.x, judging by its installation path).
_oe_ls_path_ok() {
  case "$1" in
    *202[1-4]*) return 0 ;;
    *) return 1 ;;
  esac
}

_oe_ls_cur="$(command -v vitis_hls 2>/dev/null || true)"
if [[ -n "$_oe_ls_cur" ]] && ! _oe_ls_path_ok "$_oe_ls_cur"; then
  echo "NOTE: ignoring vitis_hls on PATH ($_oe_ls_cur) — not LS-compatible (need 2021-2024)."
  _oe_ls_cur=""
fi

if [[ -z "$_oe_ls_cur" ]]; then
  if [[ -n "${OE_LS_VITIS_SETTINGS64:-}" ]] && [[ -f "$OE_LS_VITIS_SETTINGS64" ]]; then
    _oe_ls_source_relaxed "$OE_LS_VITIS_SETTINGS64"
    _oe_ls_cur="$(command -v vitis_hls 2>/dev/null || true)"
  fi
fi

if [[ -z "$_oe_ls_cur" ]]; then
  # 2021.1 first (LS gold standard), then newest-supported downward.
  for _oe_ls_ver in 2021.1 2024.2 2024.1 2023.2 2023.1 2022.2 2022.1; do
    for _oe_ls_env in \
      "/tools/software/amd/xilinx/ARCHIVE/Vitis/$_oe_ls_ver/settings64.sh" \
      "/tools/software/xilinx/ARCHIVE/Vitis/$_oe_ls_ver/settings64.sh" \
      "/tools/software/amd/xilinx/ARCHIVE/Vitis_HLS/$_oe_ls_ver/settings64.sh" \
      "/tools/software/xilinx/ARCHIVE/Vitis_HLS/$_oe_ls_ver/settings64.sh"; do
      if [[ -f "$_oe_ls_env" ]]; then
        _oe_ls_source_relaxed "$_oe_ls_env"
        _oe_ls_cur="$(command -v vitis_hls 2>/dev/null || true)"
        if [[ -n "$_oe_ls_cur" ]] && _oe_ls_path_ok "$_oe_ls_cur"; then
          export OE_LS_VITIS_SETTINGS64="$_oe_ls_env"
          break 2
        fi
        _oe_ls_cur=""
      fi
    done
  done
  unset _oe_ls_ver _oe_ls_env
fi

if [[ -z "$_oe_ls_cur" ]]; then
  for _oe_ls_ver in 2021.1 2024.2 2024.1 2023.2 2023.1; do
    for _oe_ls_bin in \
      "/tools/software/amd/xilinx/ARCHIVE/Vitis_HLS/$_oe_ls_ver/bin/vitis_hls" \
      "/tools/software/xilinx/ARCHIVE/Vitis_HLS/$_oe_ls_ver/bin/vitis_hls" \
      "/tools/software/amd/xilinx/ARCHIVE/Vitis/$_oe_ls_ver/bin/vitis_hls" \
      "/tools/software/xilinx/ARCHIVE/Vitis/$_oe_ls_ver/bin/vitis_hls"; do
      if [[ -x "$_oe_ls_bin" ]]; then
        export PATH="$(dirname "$_oe_ls_bin"):$PATH"
        _oe_ls_cur="$_oe_ls_bin"
        break 2
      fi
    done
  done
  unset _oe_ls_ver _oe_ls_bin
fi

if [[ -z "$_oe_ls_cur" ]]; then
  echo "ERROR: no LightningSim-compatible vitis_hls found (need ARCHIVE 2021-2024)."
  echo "Checked /tools/software/{amd/,}xilinx/ARCHIVE/{Vitis,Vitis_HLS}/<ver>/"
  echo "Set OE_LS_VITIS_SETTINGS64=/path/to/settings64.sh and re-run."
  # return when sourced, exit when executed
  return 1 2>/dev/null || exit 1
fi

# Force-align XILINX_HLS with the resolved binary: <root>/bin/vitis_hls -> <root>.
_oe_ls_root="$(cd "$(dirname "$_oe_ls_cur")/.." && pwd)"
if [[ "${XILINX_HLS:-}" != "$_oe_ls_root" ]]; then
  if [[ -n "${XILINX_HLS:-}" ]]; then
    echo "NOTE: overriding stale XILINX_HLS=$XILINX_HLS"
  fi
  export XILINX_HLS="$_oe_ls_root"
fi
unset _oe_ls_cur _oe_ls_root

echo "LightningSim HLS toolchain: $(command -v vitis_hls)"
echo "  XILINX_HLS=$XILINX_HLS"
if [[ -n "${XILINX_VITIS:-}" ]] && [[ "${XILINX_VITIS}" != "$XILINX_HLS"* ]]; then
  echo "  (XILINX_VITIS=$XILINX_VITIS is a different install; harmless for LS, which only uses XILINX_HLS)"
fi
