# ============================================================================
# A5 build: EGNN layer (k_mlp1 / k_magg / k_mlp2).
#   Usage:  rm -rf egnn_proj && vitis_hls -f run_hls_egnn.tcl
#
# csynth reports per-kernel latency/resources; these per-kernel numbers feed
# the Phase B per-tier cost model (cost_model_3d/tier_model.py). Quote cosim
# cycles for end-to-end latency.
# ============================================================================

open_project -reset egnn_proj
set_top egnn_layer

add_files src/egnn_layer.cpp -cflags "-I./src"
add_files -tb tb/egnn_tb.cpp -cflags "-I./src"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design
cosim_design

exit
