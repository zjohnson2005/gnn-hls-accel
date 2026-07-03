# Re-run scatter cosim only (skip csynth). From repo root:
#   vitis_hls -f orchestration_engine/run_hls_scatter_cosim_only.tcl
#
# Resets the project file list (drops stale duplicate TB entries) but keeps sol1 RTL.

open_project -reset oe_scatter_proj
set_top oe_hls_scatter_kernel

add_files orchestration_engine/hls/orchestration_engine.cpp -cflags "-I./orchestration_engine/hls"
add_files -tb orchestration_engine/tb/oe_hls_scatter_tb.cpp \
  -cflags "-I./orchestration_engine/hls" \
  -csimflags "-DOE_COSIM_FANOUT2_ONLY"

open_solution sol1
config_cosim -trace_level none
cosim_design

exit
