# ============================================================================
# Vitis HLS build script for the orchestration engine scaffold.
#   Usage (from repo root):  vitis_hls -f orchestration_engine/run_hls.tcl
#   Runs:   C-sim  ->  C-synth  (cosim optional once DATAFLOW closes)
# ============================================================================

open_project -reset oe_proj
set_top orchestration_engine

add_files orchestration_engine/hls/orchestration_engine.cpp -cflags "-I./orchestration_engine/hls"
add_files -tb orchestration_engine/tb/oe_hls_tb.cpp -cflags "-I./orchestration_engine/hls"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

# Scatter-only fast path (Phase 2): vitis_hls -f orchestration_engine/run_hls_scatter.tcl
# Uncomment after full DATAFLOW + MSHR integration:
# cosim_design

exit
