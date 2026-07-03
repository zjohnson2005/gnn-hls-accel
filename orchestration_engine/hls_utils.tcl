# Shared Vitis HLS helpers (source from run_*.tcl).

proc oe_remove_all_tb {} {
    set tb_files [get_files -filter {FILE_TYPE == TB}]
    if {[llength $tb_files] > 0} {
        puts "Removing TB files: $tb_files"
        remove_files $tb_files
    }
    set remaining [get_files -filter {FILE_TYPE == TB}]
    if {[llength $remaining] > 0} {
        puts "ERROR: failed to remove all TB files; still registered: $remaining"
        exit 1
    }
}
