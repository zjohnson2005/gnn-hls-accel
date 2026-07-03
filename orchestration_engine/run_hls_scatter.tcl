# Scatter csynth + cosim (Phase 2). From repo root:
#   vitis_hls -f orchestration_engine/run_hls_scatter.tcl
#
# csim runs full regression (exactly-once, prune, mid-graph append, fan-out=8).
# cosim runs fan-out=2 anchor x4 (OE_COSIM_FANOUT2_ONLY via -cosimflags for II).

open_project -reset oe_scatter_proj
set_top oe_hls_scatter_kernel

add_files orchestration_engine/hls/orchestration_engine.cpp -cflags "-I./orchestration_engine/hls"
add_files -tb orchestration_engine/tb/oe_hls_scatter_tb.cpp -cflags "-I./orchestration_engine/hls"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

add_files -tb orchestration_engine/tb/oe_hls_scatter_tb.cpp \
  -cflags "-I./orchestration_engine/hls" \
  -cosimflags "-DOE_COSIM_FANOUT2_ONLY"

config_cosim -trace_level none
cosim_design

exit
