# Banked scatter csynth + cosim. Server-only (Vitis 2025.2.1):
#   vitis_hls -f orchestration_engine/run_hls_scatter_banked.tcl

open_project -reset oe_scatter_banked_proj
set_top oe_hls_scatter_banked_stream

add_files orchestration_engine/hls/orchestration_engine.cpp -cflags "-I./orchestration_engine/hls"
add_files -tb orchestration_engine/tb/oe_scatter_banked_tb.cpp -cflags "-I./orchestration_engine/hls"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

config_cosim -trace_level none
cosim_design

exit
