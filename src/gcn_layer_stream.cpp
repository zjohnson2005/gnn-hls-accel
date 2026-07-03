#include "gcn_layer_stream.h"

#ifndef USE_NR_RSQRT
#define USE_NR_RSQRT 1
#endif
#if USE_NR_RSQRT
#include "hls_rsqrt.h"
#else
#include "hls_math.h"
#endif

// ----------------------------------------------------------------------------
// Compute tier: Xt = X*W + b, emitted row-by-row into the seam stream.
//   Pipelined over output features (II=1). Each completed row is pushed as one
//   feat_row_t token, so downstream can begin transport while later rows are
//   still being computed.
// ----------------------------------------------------------------------------
static void combine_tier(
    const data_t            X[MAX_NODES][F_IN],
    const weight_t          W[F_IN][F_OUT],
    const weight_t          bias[F_OUT],
    idx_t                   num_nodes,
    hls::stream<feat_row_t> &xt_stream)
{
#pragma HLS ARRAY_PARTITION variable=W    complete dim=1
#pragma HLS ARRAY_PARTITION variable=X    complete dim=2
#pragma HLS ARRAY_PARTITION variable=bias complete dim=1

combine_nodes:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NODES
        feat_row_t row;
#pragma HLS ARRAY_PARTITION variable=row.v complete dim=1
    combine_out:
        for (int o = 0; o < F_OUT; o++) {
#pragma HLS PIPELINE II=1
            acc_t acc = (acc_t)bias[o];
        combine_in:
            for (int k = 0; k < F_IN; k++) {
#pragma HLS UNROLL
                acc += (acc_t)(X[i][k] * W[k][o]);
            }
            row.v[o] = (data_t)acc;
        }
        xt_stream.write(row);
    }
}

// ----------------------------------------------------------------------------
// Near-memory tier: drain the seam stream into a local buffer, then perform
// the normalized CSR gather. inv_sqrt_deg is computed here from row_ptr (the
// degree info travels with the graph, not across the feature seam).
// ----------------------------------------------------------------------------
static void aggregate_tier(
    hls::stream<feat_row_t> &xt_stream,
    const idx_t              row_ptr[MAX_NODES + 1],
    const idx_t              col_idx[MAX_EDGES],
    idx_t                    num_nodes,
    data_t                   Y[MAX_NODES][F_OUT])
{
    static data_t Xt[MAX_NODES][F_OUT];
    static data_t inv_sqrt_deg[MAX_NODES];
#pragma HLS ARRAY_PARTITION variable=Xt complete dim=2
#pragma HLS ARRAY_PARTITION variable=Y  complete dim=2

drain_seam:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NODES
#pragma HLS PIPELINE II=1
        feat_row_t row = xt_stream.read();
        idx_t deg = row_ptr[i + 1] - row_ptr[i];
#if USE_NR_RSQRT
        inv_sqrt_deg[i] = (deg == 0) ? (data_t)0 : (data_t)nr_rsqrt<3>((float)deg);
#else
        inv_sqrt_deg[i] = (deg == 0) ? (data_t)0
                                     : (data_t)(1.0f / hls::sqrt((float)deg));
#endif
    store_row:
        for (int o = 0; o < F_OUT; o++) {
#pragma HLS UNROLL
            Xt[i][o] = row.v[o];
        }
    }

agg_nodes:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NODES
        acc_t acc[F_OUT];
#pragma HLS ARRAY_PARTITION variable=acc complete dim=1
    agg_init:
        for (int o = 0; o < F_OUT; o++) {
#pragma HLS UNROLL
            acc[o] = (acc_t)0;
        }

        idx_t start = row_ptr[i];
        idx_t end   = row_ptr[i + 1];
        norm_t inv_i = (norm_t)inv_sqrt_deg[i];

    agg_neighbors:
        for (idx_t p = start; p < end; p++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=64
#pragma HLS PIPELINE II=1
            idx_t  j = col_idx[p];
            norm_t c = (norm_t)(inv_i * (norm_t)inv_sqrt_deg[j]);
        agg_feat:
            for (int o = 0; o < F_OUT; o++) {
#pragma HLS UNROLL
                acc[o] += (acc_t)(c * Xt[j][o]);
            }
        }
    agg_store:
        for (int o = 0; o < F_OUT; o++) {
#pragma HLS UNROLL
            Y[i][o] = (data_t)acc[o];
        }
    }
}

// ----------------------------------------------------------------------------
// Top level: the two tiers run concurrently in a DATAFLOW region, connected by
// the bounded seam FIFO.
// ----------------------------------------------------------------------------
void gcn_layer_stream(
    const data_t   X[MAX_NODES][F_IN],
    const weight_t W[F_IN][F_OUT],
    const weight_t bias[F_OUT],
    const idx_t    row_ptr[MAX_NODES + 1],
    const idx_t    col_idx[MAX_EDGES],
    idx_t          num_nodes,
    data_t         Y[MAX_NODES][F_OUT])
{
#pragma HLS DATAFLOW
    hls::stream<feat_row_t> xt_stream;
#pragma HLS STREAM variable=xt_stream depth=4

    combine_tier(X, W, bias, num_nodes, xt_stream);
    aggregate_tier(xt_stream, row_ptr, col_idx, num_nodes, Y);
}
