# Re-run scatter cosim only (skip csynth). From repo root:
#   vitis_hls -f orchestration_engine/run_hls_scatter_cosim_only.tcl

open_project oe_scatter_proj
open_solution sol1

remove_files orchestration_engine/tb/oe_hls_scatter_tb.cpp -tb
remove_files orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp -tb
add_files -tb orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp -cflags "-I./orchestration_engine/hls"

config_cosim -trace_level none
cosim_design

exit
