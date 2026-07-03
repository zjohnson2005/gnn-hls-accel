#ifndef GCN_LAYER_STREAM_H
#define GCN_LAYER_STREAM_H

#include "gcn_layer.h"   // sizes (MAX_NODES, F_IN, F_OUT, ...) + datatypes
#include <hls_stream.h>

// ============================================================================
// Streaming / DATAFLOW GCN layer (A3).
//
// Same math as gcn_layer, restructured into two tier-cleavable tasks joined by
// an explicit hls::stream that carries the transformed-feature payload across
// the combine -> aggregate seam:
//
//     combine_tier  (compute-bound: Xt = X*W + b)
//          |  hls::stream<seam_token_t>  Xt, one row per token   <-- TIER SEAM
//          v
//     aggregate_tier (memory-bound: gather + normalize over CSR)
//
// GNN_LS_LITE (LightningSim trace build): seam is ap_uint<F_OUT*32> so LS FIFO
// hooks match _autotb_FifoRead_i512 (struct payloads often crash LS SystemC).
// Thesis cosim uses feat_row_t (ap_fixed) via run_hls_stream.tcl without -DGNN_LS_LITE.
// ============================================================================

#ifdef GNN_LS_LITE
static const int SEAM_TOKEN_W = F_OUT * 32;
typedef ap_uint<SEAM_TOKEN_W> seam_token_t;
#else
struct feat_row_t {
    data_t v[F_OUT];
};
typedef feat_row_t seam_token_t;
#endif

#ifdef GNN_LS_LITE
void gcn_layer_stream(
    const data_t   *X,
    const weight_t *W,
    const weight_t *bias,
    const idx_t    *row_ptr,
    const idx_t    *col_idx,
    idx_t          num_nodes,
    data_t         *Y);
#else
void gcn_layer_stream(
    const data_t   X[MAX_NODES][F_IN],
    const weight_t W[F_IN][F_OUT],
    const weight_t bias[F_OUT],
    const idx_t    row_ptr[MAX_NODES + 1],
    const idx_t    col_idx[MAX_EDGES],
    idx_t          num_nodes,
    data_t         Y[MAX_NODES][F_OUT]);
#endif

#endif // GCN_LAYER_STREAM_H
