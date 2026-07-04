# Fallback C2 build: scatter stream only (DATAFLOW FIFOs on axis streams).
# Use if oe_hls_engine_stream trace capture fails on LS toolchain.

open_project -reset oe_stream_ls_proj
set_top oe_hls_scatter_stream

add_files orchestration_engine/hls/orchestration_engine.cpp -cflags "-I./orchestration_engine/hls"
add_files -tb orchestration_engine/tb/oe_hls_stream_tb.cpp -cflags "-I./orchestration_engine/hls"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

exit
