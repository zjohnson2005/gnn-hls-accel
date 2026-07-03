# Lean gcn_stream build for LightningSim trace capture: csim + csynth only
# (no cosim — LS replaces it). Run from repo root with ARCHIVE Vitis sourced:
#   rm -rf gcn_stream_proj && vitis_hls -f run_hls_stream_ls.tcl

open_project -reset gcn_stream_proj
set_top gcn_layer_stream

add_files src/gcn_layer_stream.cpp -cflags "-I./src"
add_files -tb tb/gcn_stream_tb.cpp -cflags "-I./src"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

exit
