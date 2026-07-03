#!/usr/bin/env bash
# Run the remaining HLS builds on the GT server, logging each phase.
# Launched detached via nohup; progress goes to build_all.log.
set -u
cd "$(dirname "$0")"

source /tools/software/amd/xilinx/2025.2.1/Vitis/settings64.sh

run() {
    local name="$1"; shift
    echo "==================== START ${name} $(date) ===================="
    "$@"
    echo "==================== END   ${name} rc=$? $(date) ===================="
}

run A1_baseline   bash -c 'rm -rf gcn_proj && vitis_hls -f run_hls.tcl'
run A3_stream     bash -c 'rm -rf gcn_stream_proj && vitis_hls -f run_hls_stream.tcl'
run A4_mp         bash -c 'rm -rf mp_gin_proj mp_sage_proj && vitis_hls -f run_hls_mp.tcl'
run A2_sweep      bash -c 'rm -rf gcn_sweep && vitis_hls -f run_hls_sweep.tcl'

echo "ALL_BUILDS_DONE $(date)"
