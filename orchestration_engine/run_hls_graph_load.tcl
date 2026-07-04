# Graph load csynth + cosim. From repo root on ece-rschsrv (Vitis 2025.2.1):
#   source orchestration_engine/hls_env.sh
#   vitis_hls -f orchestration_engine/run_hls_graph_load.tcl

open_project -reset oe_graph_load_proj
set_top oe_hls_graph_load

add_files orchestration_engine/hls/graph_load.cpp -cflags "-I./orchestration_engine/hls"
add_files orchestration_engine/hls/orchestration_engine.cpp -cflags "-I./orchestration_engine/hls"
add_files -tb orchestration_engine/tb/oe_graph_load_tb.cpp -cflags "-I./orchestration_engine/hls -I./orchestration_engine/include"

open_solution -reset sol1 -flow_target vivado
set_part {xczu3eg-sbva484-1-e}
create_clock -period 3.33 -name default

csim_design
csynth_design

config_cosim -trace_level none
cosim_design

exit
