# ============================================================================
# A2 precision + rsqrt sweep for the GCN layer.
#   Usage:  rm -rf gcn_sweep && vitis_hls -f run_hls_sweep.tcl
#
# Builds one solution per (precision profile, rsqrt impl) pair so a single run
# produces the accuracy/II/Fmax/resource comparison. Read each solution's
# report under gcn_sweep/<sol>/syn/report/gcn_layer_csynth.rpt and the cosim
# under gcn_sweep/<sol>/sim/report/.
# ============================================================================

open_project -reset gcn_sweep
set_top gcn_layer

# arms: {solution_name  precision_profile  use_nr_rsqrt}
set arms {
    {p0_sqrt 0 0}
    {p0_nr   0 1}
    {p1_nr   1 1}
    {p2_nr   2 1}
}

foreach arm $arms {
    set name    [lindex $arm 0]
    set profile [lindex $arm 1]
    set usenr   [lindex $arm 2]
    # Relax the TB tolerance so narrow-precision arms complete csim/csynth/cosim;
    # accuracy per arm is read from the printed "max abs error", not PASS/FAIL.
    set flags   "-I./src -DGNN_PRECISION_PROFILE=$profile -DUSE_NR_RSQRT=$usenr -DGCN_TB_TOL=0.5"

    add_files src/gcn_layer.cpp -cflags $flags
    add_files -tb tb/gcn_tb.cpp -cflags $flags

    open_solution -reset $name -flow_target vivado
    set_part {xczu3eg-sbva484-1-e}
    create_clock -period 3.33 -name default

    csim_design
    csynth_design
    cosim_design
}

exit
