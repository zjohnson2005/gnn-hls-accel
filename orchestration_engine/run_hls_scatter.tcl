# Scatter csynth + cosim (Phase 2). From repo root:
#   vitis_hls -f orchestration_engine/run_hls_scatter.tcl
#
# csim: full regression TB (oe_hls_scatter_tb.cpp).
# cosim: dedicated x4 TB (oe_hls_scatter_cosim_tb.cpp) for RTL II measurement.
# Vitis 2025.2 has no -cosimflags — swap TB files before cosim_design.

source orchestration_engine/hls_utils.tcl

open_project -reset oe_scatter_proj
set_top oe_hls_scatter_kernel

add_files orchestration_engine/hls/orchestration_engine.cpp -cflags "-I./orchestration_engine/hls"
add_files -tb orchestration_engine/tb/oe_hls_scatter_tb.cpp -cflags "-I./orchestration_engine/hls"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

oe_remove_scatter_tb
add_files -tb orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp \
  -cflags "-I./orchestration_engine/hls"

config_cosim -trace_level none
cosim_design

exit
