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
//          |  hls::stream<feat_row_t>  Xt, one row per token   <-- TIER SEAM
//          v
//     aggregate_tier (memory-bound: gather + normalize over CSR)
//
// The seam stream is exactly the payload that crosses TSVs when the two tiers
// live on different dies, so its width (F_OUT * data_t) and token count
// (num_nodes) are the inter-tier bandwidth knobs Phase B reasons about.
//
// The gather is irregular, so aggregate_tier buffers the streamed rows locally
// before gathering; the stream models ordered transport across the seam, not
// random access through it.
// ============================================================================

// One transformed-feature row, streamed as a single token.
struct feat_row_t {
    data_t v[F_OUT];
};

void gcn_layer_stream(
    const data_t   X[MAX_NODES][F_IN],
    const weight_t W[F_IN][F_OUT],
    const weight_t bias[F_OUT],
    const idx_t    row_ptr[MAX_NODES + 1],
    const idx_t    col_idx[MAX_EDGES],
    idx_t          num_nodes,
    data_t         Y[MAX_NODES][F_OUT]
);

#endif // GCN_LAYER_STREAM_H
