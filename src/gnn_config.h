#ifndef GNN_CONFIG_H
#define GNN_CONFIG_H

#include <ap_fixed.h>
#include <ap_int.h>

// ============================================================================
// Central precision / datatype configuration shared by every GNN kernel.
//
// GNN_LS_LITE: compile-time flag for LightningSim trace capture only (see
// run_hls_stream_ls.tcl). Uses float + plain struct streams so LS SystemC glue
// does not segfault on ap_fixed top ports. Thesis cosim numbers use profile 0.
// ============================================================================

#ifdef GNN_LS_LITE

typedef float   data_t;
typedef float   weight_t;
typedef float   norm_t;
typedef float   acc_t;
typedef ap_uint<16> idx_t;

#else

#ifndef GNN_PRECISION_PROFILE
#define GNN_PRECISION_PROFILE 0
#endif

#if   GNN_PRECISION_PROFILE == 0
#define GNN_DATA_W   16
#define GNN_DATA_I    6
#define GNN_ACC_W    32
#define GNN_ACC_I    12
#elif GNN_PRECISION_PROFILE == 1
#define GNN_DATA_W   12
#define GNN_DATA_I    4
#define GNN_ACC_W    26
#define GNN_ACC_I    10
#elif GNN_PRECISION_PROFILE == 2
#define GNN_DATA_W    8
#define GNN_DATA_I    3
#define GNN_ACC_W    20
#define GNN_ACC_I     8
#else
#error "Unknown GNN_PRECISION_PROFILE"
#endif

typedef ap_fixed<GNN_DATA_W, GNN_DATA_I> data_t;
typedef ap_fixed<GNN_DATA_W, GNN_DATA_I> weight_t;
typedef ap_fixed<18, 2>                  norm_t;
typedef ap_fixed<GNN_ACC_W, GNN_ACC_I>   acc_t;
typedef ap_uint<16>                      idx_t;

#endif // GNN_LS_LITE

#endif // GNN_CONFIG_H
