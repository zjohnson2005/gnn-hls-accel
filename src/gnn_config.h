#ifndef GNN_CONFIG_H
#define GNN_CONFIG_H

#include <ap_fixed.h>
#include <ap_int.h>

// ============================================================================
// Central precision / datatype configuration shared by every GNN kernel.
//
// Bitwidth is the primary Fmax/area lever in this project, so it is hoisted
// out of the kernels into a single profile selector that can be overridden at
// compile time without editing kernel source:
//
//     vitis_hls -f run_hls.tcl                      # profile 0 (baseline)
//     add_files ... -cflags "-DGNN_PRECISION_PROFILE=1"   # narrow
//
// Profiles trade accuracy for timing/area. Profile 0 must stay bit-identical
// to the original baseline so the reference cosim number remains valid.
// ============================================================================

#ifndef GNN_PRECISION_PROFILE
#define GNN_PRECISION_PROFILE 0
#endif

#if   GNN_PRECISION_PROFILE == 0
// Baseline: functional reference. Do not change -- the reference numbers
// captured in A1 are defined against exactly these widths.
#define GNN_DATA_W   16
#define GNN_DATA_I    6
#define GNN_ACC_W    32
#define GNN_ACC_I    12
#elif GNN_PRECISION_PROFILE == 1
// Narrow: shorter carry chains -> higher achievable Fmax, fewer DSPs.
#define GNN_DATA_W   12
#define GNN_DATA_I    4
#define GNN_ACC_W    26
#define GNN_ACC_I    10
#elif GNN_PRECISION_PROFILE == 2
// Aggressive: area/Fmax oriented; accuracy must be re-checked against the TB.
#define GNN_DATA_W    8
#define GNN_DATA_I    3
#define GNN_ACC_W    20
#define GNN_ACC_I     8
#else
#error "Unknown GNN_PRECISION_PROFILE"
#endif

// ---- Datapath types ----
typedef ap_fixed<GNN_DATA_W, GNN_DATA_I> data_t;    // node / edge features, outputs
typedef ap_fixed<GNN_DATA_W, GNN_DATA_I> weight_t;  // linear-transform weights / bias
typedef ap_fixed<18, 2>                  norm_t;    // normalization coeff, range (0, 1]
typedef ap_fixed<GNN_ACC_W, GNN_ACC_I>   acc_t;     // wide accumulator (combine + aggregate)
typedef ap_uint<16>                      idx_t;     // node / edge index (<= 65535)

#endif // GNN_CONFIG_H
