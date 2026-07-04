# C3 variant csynth: argv = project_name cap max_nodes banks
# Invoked by run_phase2_variants.sh

set proj [lindex $argv 0]
set cap [lindex $argv 1]
set max_nodes [lindex $argv 2]
set banks [lindex $argv 3]

if {$proj eq ""} {
    set proj oe_var_default
    set cap 8
    set max_nodes 256
    set banks 4
}

set cflags "-I./orchestration_engine/hls -DOE_HLS_MAX_OUTSTANDING=${cap} -DOE_HLS_MAX_NODES=${max_nodes} -DOE_HLS_SCATTER_BANKS=${banks}"

open_project -reset $proj
set_top oe_hls_scatter_stream

add_files orchestration_engine/hls/orchestration_engine.cpp -cflags $cflags
add_files -tb orchestration_engine/tb/oe_hls_stream_tb.cpp -cflags $cflags

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

exit
