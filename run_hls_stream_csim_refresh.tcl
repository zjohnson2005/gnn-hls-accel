# Re-run csim on an existing gcn_stream_proj (refresh autopilot DB before trace capture).
# From repo root, with ARCHIVE Vitis sourced:
#   vitis_hls -f run_hls_stream_csim_refresh.tcl
open_project gcn_stream_proj
open_solution sol1
csim_design
exit
