# Re-run scatter cosim only (reuse existing csynth RTL). From repo root:
#   vitis_hls -f orchestration_engine/run_hls_scatter_cosim_only.tcl
#
# Do NOT use open_project -reset here — that invalidates the synthesized solution.

source orchestration_engine/hls_utils.tcl

open_project oe_scatter_proj
open_solution sol1

set csynth_rpt "oe_scatter_proj/sol1/syn/report/oe_hls_scatter_kernel_csynth.rpt"
if {![file exists $csynth_rpt]} {
    puts "ERROR: missing $csynth_rpt — run run_phase2_scatter_only.sh first"
    exit 1
}

oe_remove_scatter_tb
add_files -tb orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp \
  -cflags "-I./orchestration_engine/hls"

config_cosim -trace_level none
cosim_design

exit
