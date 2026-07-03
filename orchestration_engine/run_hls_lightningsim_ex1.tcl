# Build LightningSim tutorial example-1 (matrix multiply DATAFLOW).
# Clone once:  git clone --depth=1 https://github.com/sharc-lab/lightningsim-doc.git ~/lightningsim-doc
# Run from ~/lightningsim-doc/examples with ARCHIVE Vitis sourced:
#   vitis_hls -f /path/to/gnn-hls-accel/orchestration_engine/run_hls_lightningsim_ex1.tcl

open_project -reset example-1
add_files example-1/matrixmultiplication.cpp
add_files -tb example-1/matrixmultiplication-top.cpp
add_files -tb example-1/matrixmultiplication.gold.dat
set_top matrixmul

open_solution -reset solution1
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design
exit
