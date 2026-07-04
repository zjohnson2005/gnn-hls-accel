# C1 cosim on the SAME gcn_stream_proj/sol1 as trace.pkl / DSE (2023.1 ARCHIVE).
# Does not reset the project — RTL must match the traced solution.
#
#   source orchestration_engine/hls_env_lightningsim.sh
#   vitis_hls -f run_hls_stream_ls_cosim_trace.tcl

open_project gcn_stream_proj
open_solution sol1

config_cosim -trace_level none
cosim_design

exit
