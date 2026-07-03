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
#
# On this box, ARCHIVE/Vitis_HLS/<ver> is often a partial install (binaries
# only). Headers live under sibling trees such as ARCHIVE/Vitis/<ver>/Vitis_HLS.
# Some ARCHIVE entries (notably 2024.1) have headers but a broken vitis_hls
# runtime ("Not supported revsion: iostream error"); we smoke-test before pick.
#
# Override version preference: export OE_LS_VITIS_VERSION=2023.1

_oe_ls_source_relaxed() {
  set +u +e
  # shellcheck disable=SC1090
  source "$1"
  set -u -e
}

_oe_ls_hls_root_ok() {
  [[ -f "$1/include/ap_fixed.h" ]] && [[ -f "$1/include/Makefile.sysc.rules" ]]
}

_oe_ls_smoke_ok() {
  local vh="$1"
  [[ -x "$vh" ]] || return 1
  local out rc
  out="$("$vh" -version 2>&1)" || rc=$?
  if [[ "${rc:-0}" -eq 0 ]] && [[ -n "$out" ]]; then
    return 0
  fi
  out="$("$vh" 2>&1 | head -3)" || true
  [[ "$out" == *"Not supported"* ]] && return 1
  [[ "$out" == *"iostream error"* ]] && return 1
  [[ "$out" == *"Vitis HLS"* || "$out" == *"vivado_hls"* ]] && return 0
  return 1
}

_oe_ls_header_roots_for_ver() {
  local ver="$1"
  local root
  for root in \
    "/tools/software/amd/xilinx/ARCHIVE/Vitis/$ver/Vitis_HLS" \
    "/tools/software/xilinx/ARCHIVE/Vitis/$ver/Vitis_HLS" \
    "/tools/software/amd/xilinx/ARCHIVE/Vitis/$ver" \
    "/tools/software/xilinx/ARCHIVE/Vitis/$ver" \
    "/tools/software/amd/xilinx/ARCHIVE/Vitis_HLS/$ver" \
    "/tools/software/xilinx/ARCHIVE/Vitis_HLS/$ver" \
    "/tools/software/amd/xilinx/ARCHIVE/$ver/Vitis/Vitis_HLS" \
    "/tools/software/xilinx/ARCHIVE/$ver/Vitis/Vitis_HLS" \
    "/tools/software/amd/xilinx/ARCHIVE/$ver/Vitis_HLS" \
    "/tools/software/xilinx/ARCHIVE/$ver/Vitis_HLS" \
    "/tools/software/amd/xilinx/$ver/Vitis_HLS" \
    "/tools/software/xilinx/$ver/Vitis_HLS"; do
    if _oe_ls_hls_root_ok "$root"; then
      echo "$root"
      return 0
    fi
  done
  return 1
}

_oe_ls_bin_for_ver() {
  local ver="$1"
  local bin
  for bin in \
    "/tools/software/amd/xilinx/ARCHIVE/Vitis_HLS/$ver/bin/vitis_hls" \
    "/tools/software/xilinx/ARCHIVE/Vitis_HLS/$ver/bin/vitis_hls" \
    "/tools/software/amd/xilinx/ARCHIVE/Vitis/$ver/bin/vitis_hls" \
    "/tools/software/xilinx/ARCHIVE/Vitis/$ver/bin/vitis_hls" \
    "/tools/software/amd/xilinx/ARCHIVE/Vitis/$ver/Vitis_HLS/bin/vitis_hls" \
    "/tools/software/xilinx/ARCHIVE/Vitis/$ver/Vitis_HLS/bin/vitis_hls"; do
    if [[ -x "$bin" ]]; then
      echo "$bin"
      return 0
    fi
  done
  return 1
}

_oe_ls_try_settings64() {
  local ver="$1"
  local env
  for env in \
    "/tools/software/amd/xilinx/ARCHIVE/Vitis/$ver/settings64.sh" \
    "/tools/software/xilinx/ARCHIVE/Vitis/$ver/settings64.sh" \
    "/tools/software/amd/xilinx/ARCHIVE/Vitis_HLS/$ver/settings64.sh" \
    "/tools/software/xilinx/ARCHIVE/Vitis_HLS/$ver/settings64.sh"; do
    if [[ -f "$env" ]]; then
      _oe_ls_source_relaxed "$env"
      return 0
    fi
  done
  return 1
}

# Version order: 2023.1 first (known-good on this box), then 2024.2 (LS example-1
# passed), then others. 2024.1 is late — headers exist but runtime is broken.
if [[ -n "${OE_LS_VITIS_VERSION:-}" ]]; then
  _oe_ls_versions=("$OE_LS_VITIS_VERSION")
else
  _oe_ls_versions=(2023.1 2024.2 2023.2 2022.2 2024.1 2021.1)
fi

_oe_ls_picked_bin=""
_oe_ls_picked_root=""

for _oe_ls_ver in "${_oe_ls_versions[@]}"; do
  _oe_ls_try_settings64 "$_oe_ls_ver" || true
  _oe_ls_cand_bin="$(_oe_ls_bin_for_ver "$_oe_ls_ver" || true)"
  if [[ -z "$_oe_ls_cand_bin" ]]; then
    continue
  fi
  if ! _oe_ls_smoke_ok "$_oe_ls_cand_bin"; then
    echo "NOTE: skipping $_oe_ls_cand_bin (vitis_hls smoke test failed)"
    continue
  fi
  _oe_ls_cand_root="$(_oe_ls_header_roots_for_ver "$_oe_ls_ver" || true)"
  if [[ -z "$_oe_ls_cand_root" ]]; then
    echo "NOTE: skipping $_oe_ls_ver (vitis_hls ok but no header tree found)"
    continue
  fi
  _oe_ls_picked_bin="$_oe_ls_cand_bin"
  _oe_ls_picked_root="$_oe_ls_cand_root"
  echo "Picked Vitis $_oe_ls_ver: bin=$_oe_ls_picked_bin"
  echo "  headers=$_oe_ls_picked_root"
  break
done
unset _oe_ls_ver _oe_ls_cand_bin _oe_ls_cand_root _oe_ls_versions

if [[ -z "$_oe_ls_picked_bin" ]] || [[ -z "$_oe_ls_picked_root" ]]; then
  echo "ERROR: no complete, working LS-compatible Vitis HLS tree found."
  echo "       Need vitis_hls that passes -version AND include/ap_fixed.h."
  echo "Try: export OE_LS_VITIS_VERSION=2023.1"
  echo "Candidate header trees on the box (60s search cap):"
  timeout 60 find /tools/software -maxdepth 10 -path '*/include/ap_fixed.h' 2>/dev/null | head -25
  return 1 2>/dev/null || exit 1
fi

export PATH="$(dirname "$_oe_ls_picked_bin"):$PATH"
if [[ "${XILINX_HLS:-}" != "$_oe_ls_picked_root" ]]; then
  if [[ -n "${XILINX_HLS:-}" ]]; then
    echo "NOTE: overriding stale XILINX_HLS=$XILINX_HLS"
  fi
  export XILINX_HLS="$_oe_ls_picked_root"
fi
unset _oe_ls_picked_bin _oe_ls_picked_root

echo "LightningSim HLS toolchain: $(command -v vitis_hls)"
echo "  XILINX_HLS=$XILINX_HLS"
if [[ -n "${XILINX_VITIS:-}" ]] && [[ "${XILINX_VITIS}" != "$XILINX_HLS"* ]]; then
  echo "  (XILINX_VITIS=$XILINX_VITIS is a different install; harmless for LS, which only uses XILINX_HLS)"
fi

# liblightningsimrt.a is built against conda libstdc++; linking with /usr/bin/g++
# fails on std::__throw_bad_array_new_length(). Keep CC/CXX/LD_LIBRARY_PATH aligned.
_oe_ls_conda_toolchain() {
  local p="${CONDA_PREFIX:-}"
  if [[ -z "$p" ]] && [[ -d "$HOME/miniconda3/envs/fifo-advisor" ]]; then
    p="$HOME/miniconda3/envs/fifo-advisor"
    export CONDA_PREFIX="$p"
  fi
  [[ -n "$p" ]] || return 0
  local gxx="$p/bin/x86_64-conda-linux-gnu-g++"
  local gcc="$p/bin/x86_64-conda-linux-gnu-cc"
  if [[ -x "$gxx" ]]; then
    export CXX="$gxx"
  fi
  if [[ -x "$gcc" ]]; then
    export CC="$gcc"
  fi
  export LD_LIBRARY_PATH="${p}/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export OE_CONDA_LIB="${p}/lib"
}
_oe_ls_conda_toolchain
if [[ -n "${CXX:-}" ]]; then
  echo "  LightningSim link CXX=$CXX"
fi
