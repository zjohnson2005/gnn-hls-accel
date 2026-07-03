# Re-run scatter cosim only (reuse existing csynth RTL). From repo root:
#   vitis_hls -f orchestration_engine/run_hls_scatter_cosim_only.tcl
#
# Do NOT use open_project -reset here — that invalidates the synthesized solution.

open_project oe_scatter_proj
open_solution sol1

CSYNTH_RPT "oe_scatter_proj/sol1/syn/report/oe_hls_scatter_kernel_csynth.rpt"
if {![file exists $CSYNTH_RPT]} {
    puts "ERROR: missing $CSYNTH_RPT — run run_phase2_scatter_only.sh first"
    exit 1
}

catch { remove_files orchestration_engine/tb/oe_hls_scatter_tb.cpp }
catch { remove_files orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp }
add_files -tb orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp \
  -cflags "-I./orchestration_engine/hls"

config_cosim -trace_level none
cosim_design

exit
