# C2 cosim on the SAME oe_engine_ls_proj/sol1 as trace.pkl / DSE (2023.1 ARCHIVE).
# Does not reset the project — RTL must match the traced solution.
#
#   source orchestration_engine/hls_env_lightningsim.sh
#   vitis_hls -f orchestration_engine/run_hls_oe_engine_ls_cosim_trace.tcl

open_project oe_engine_ls_proj
open_solution sol1

config_cosim -trace_level none
cosim_design

exit
