# OE engine DATAFLOW (graph_load -> scatter) for LightningSim trace + DSE (C2).
# Server-only: ARCHIVE Vitis 2023.1 via hls_env_lightningsim.sh
#   vitis_hls -f orchestration_engine/run_hls_oe_engine_ls.tcl

open_project -reset oe_engine_ls_proj
set_top oe_hls_engine_stream

add_files orchestration_engine/hls/engine_stream.cpp -cflags "-I./orchestration_engine/hls"
add_files orchestration_engine/hls/graph_load.cpp -cflags "-I./orchestration_engine/hls"
add_files orchestration_engine/hls/orchestration_engine.cpp -cflags "-I./orchestration_engine/hls"
add_files -tb orchestration_engine/tb/oe_engine_stream_tb.cpp -cflags "-I./orchestration_engine/hls -I./orchestration_engine/include"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

exit
