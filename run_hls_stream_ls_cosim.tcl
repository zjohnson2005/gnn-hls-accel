# GNN_LS_LITE cosim for C1 LS validation (same stamp as trace.pkl / DSE).
# Uses ARCHIVE Vitis 2023.1 via hls_env_lightningsim.sh — NOT thesis 2025.2.1.
# Separate project dir preserves gcn_stream_proj/sol1/trace.pkl.
#
#   source orchestration_engine/hls_env_lightningsim.sh
#   vitis_hls -f run_hls_stream_ls_cosim.tcl

open_project -reset gcn_stream_ls_cosim_proj
set_top gcn_layer_stream

add_files src/gcn_layer_stream.cpp -cflags "-I./src -DGNN_LS_LITE"
add_files -tb tb/gcn_stream_tb.cpp -cflags "-I./src -DGNN_LS_LITE"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

config_cosim -trace_level none
cosim_design

exit
