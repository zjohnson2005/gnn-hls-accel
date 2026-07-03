# Scatter cosim in a dedicated project (x4 fan-out=2 TB for RTL II).
# From repo root:
#   vitis_hls -f orchestration_engine/run_hls_scatter_cosim_only.tcl
#
# Own project + own TB = no TB swapping, no duplicate main. Re-synthesizes
# the kernel here (~30 s) so this script is standalone.

open_project -reset oe_scatter_cosim_proj
set_top oe_hls_scatter_kernel

add_files orchestration_engine/hls/orchestration_engine.cpp -cflags "-I./orchestration_engine/hls"
add_files -tb orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp -cflags "-I./orchestration_engine/hls"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

config_cosim -trace_level none
cosim_design

exit
