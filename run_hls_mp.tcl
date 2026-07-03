# ============================================================================
# A4 build: generic message-passing template instances (GIN, GraphSAGE).
#   Usage:  rm -rf mp_gin_proj mp_sage_proj && vitis_hls -f run_hls_mp.tcl
#
# Two separate projects so each csim links exactly one testbench main(). Both
# tops reuse src/mp_template.h. Reports land under
# mp_<kind>_proj/sol1/{syn,sim}/report.
# ============================================================================

# ---- GIN ----
open_project -reset mp_gin_proj
set_top gin_layer
add_files src/mp_layers.cpp -cflags "-I./src"
add_files -tb tb/gin_tb.cpp -cflags "-I./src"
open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default
csim_design
csynth_design
cosim_design
close_project

# ---- GraphSAGE ----
open_project -reset mp_sage_proj
set_top sage_layer
add_files src/mp_layers.cpp -cflags "-I./src"
add_files -tb tb/sage_tb.cpp -cflags "-I./src"
open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default
csim_design
csynth_design
cosim_design
close_project

exit
