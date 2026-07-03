# Re-run scatter cosim only (reuse existing csynth RTL). From repo root:
#   vitis_hls -f orchestration_engine/run_hls_scatter_cosim_only.tcl
#
# Do NOT use open_project -reset here — that invalidates the synthesized solution.

open_project oe_scatter_proj
open_solution sol1

# Drop stale second-TB entries from older scripts (file deleted from repo).
catch { remove_files orchestration_engine/tb/oe_hls_scatter_cosim_tb.cpp }

add_files -tb orchestration_engine/tb/oe_hls_scatter_tb.cpp \
  -cflags "-I./orchestration_engine/hls" \
  -csimflags "-DOE_COSIM_FANOUT2_ONLY"

config_cosim -trace_level none
cosim_design

exit
