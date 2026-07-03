# Shared Vitis HLS helpers (source from run_*.tcl).
# Vitis 2025.2: no get_files -filter, no -cosimflags on add_files.

proc oe_remove_scatter_tb {} {
    set removed 0
    foreach f [get_files] {
        if {[string match *oe_hls_scatter_tb.cpp $f] ||
            [string match *oe_hls_scatter_cosim_tb.cpp $f]} {
            puts "Removing TB: $f"
            remove_files $f
            incr removed
        }
    }
    foreach f [get_files] {
        if {[string match *oe_hls_scatter_tb.cpp $f] ||
            [string match *oe_hls_scatter_cosim_tb.cpp $f]} {
            puts "ERROR: scatter TB still registered after remove: $f"
            exit 1
        }
    }
    puts "Removed $removed scatter TB file(s)"
}
