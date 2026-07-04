# GCN stream cosim on Vitis 2025.2.1 for LS validation (C1 / E2).
# Uses a SEPARATE project dir so gcn_stream_proj/sol1/trace.pkl is preserved.
#
#   source orchestration_engine/hls_env.sh
#   vitis_hls -f run_hls_stream_cosim.tcl

open_project -reset gcn_stream_cosim_proj
set_top gcn_layer_stream

add_files src/gcn_layer_stream.cpp -cflags "-I./src"
add_files -tb tb/gcn_stream_tb.cpp -cflags "-I./src"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design
cosim_design

exit
