# ============================================================================
# Vitis HLS build script for the baseline GCN layer.
#   Usage:  vitis_hls -f run_hls.tcl
#   Runs:   C-sim  ->  C-synth  ->  cosim   (the order of trust)
# ============================================================================

open_project -reset gcn_proj
set_top gcn_layer

add_files src/gcn_layer.cpp -cflags "-I./src"
add_files -tb tb/gcn_tb.cpp  -cflags "-I./src"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

# 1) Functional correctness first.
csim_design

# 2) Synthesis estimates (II, est. Fmax, resources).
csynth_design

# 3) Real cycle count -- the reportable currency for any speedup.
cosim_design

exit
