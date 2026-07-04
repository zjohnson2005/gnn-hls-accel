#include "gcn_layer_stream.h"

#ifdef GNN_LS_LITE
#include <cstdint>
#endif

#ifndef USE_NR_RSQRT
#define USE_NR_RSQRT 1
#endif
#if USE_NR_RSQRT && !defined(GNN_LS_LITE)
#include "hls_rsqrt.h"
#else
#include "hls_math.h"
#endif

#ifdef GNN_LS_LITE
static seam_token_t pack_seam_row(const data_t v[F_OUT]) {
#pragma HLS INLINE
    seam_token_t tok = 0;
pack:
    for (int o = 0; o < F_OUT; o++) {
#pragma HLS UNROLL
        union {
            float f;
            uint32_t u;
        } c;
        c.f = (float)v[o];
        tok.range((o + 1) * 32 - 1, o * 32) = (ap_uint<32>)c.u;
    }
    return tok;
}

static void unpack_seam_row(seam_token_t tok, data_t v[F_OUT]) {
#pragma HLS INLINE
unpack:
    for (int o = 0; o < F_OUT; o++) {
#pragma HLS UNROLL
        union {
            float f;
            uint32_t u;
        } c;
        ap_uint<32> word = tok.range((o + 1) * 32 - 1, o * 32);
        c.u = (uint32_t)word;
        v[o] = (data_t)c.f;
    }
}
#endif

#ifdef GNN_LS_LITE
static void combine_tier(
    const data_t            *X,
    const weight_t          *W,
    const weight_t          *bias,
    idx_t                   num_nodes,
    hls::stream<seam_token_t> &xt_stream)
#else
static void combine_tier(
    const data_t            X[MAX_NODES][F_IN],
    const weight_t          W[F_IN][F_OUT],
    const weight_t          bias[F_OUT],
    idx_t                   num_nodes,
    hls::stream<seam_token_t> &xt_stream)
#endif
{
#ifndef GNN_LS_LITE
#pragma HLS ARRAY_PARTITION variable=W    complete dim=1
#pragma HLS ARRAY_PARTITION variable=X    complete dim=2
#pragma HLS ARRAY_PARTITION variable=bias complete dim=1
#endif

combine_nodes:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NODES
        data_t row[F_OUT];
#pragma HLS ARRAY_PARTITION variable=row complete dim=1
    combine_out:
        for (int o = 0; o < F_OUT; o++) {
#pragma HLS PIPELINE II=1
            acc_t acc = (acc_t)bias[o];
        combine_in:
            for (int k = 0; k < F_IN; k++) {
#pragma HLS UNROLL
#ifdef GNN_LS_LITE
                acc += (acc_t)(X[i * F_IN + k] * W[k * F_OUT + o]);
#else
                acc += (acc_t)(X[i][k] * W[k][o]);
#endif
            }
            row[o] = (data_t)acc;
        }
#ifdef GNN_LS_LITE
        xt_stream.write(pack_seam_row(row));
#else
        feat_row_t packed;
    pack_struct:
        for (int o = 0; o < F_OUT; o++) {
#pragma HLS UNROLL
            packed.v[o] = row[o];
        }
        xt_stream.write(packed);
#endif
    }
}

#ifdef GNN_LS_LITE
static void aggregate_tier(
    hls::stream<seam_token_t> &xt_stream,
    const idx_t              *row_ptr,
    const idx_t              *col_idx,
    idx_t                    num_nodes,
    data_t                   *Y)
#else
static void aggregate_tier(
    hls::stream<seam_token_t> &xt_stream,
    const idx_t              row_ptr[MAX_NODES + 1],
    const idx_t              col_idx[MAX_EDGES],
    idx_t                    num_nodes,
    data_t                   Y[MAX_NODES][F_OUT])
#endif
{
#ifdef GNN_LS_LITE
    data_t Xt[MAX_NODES][F_OUT];
    data_t inv_sqrt_deg[MAX_NODES];
#else
    static data_t Xt[MAX_NODES][F_OUT];
    static data_t inv_sqrt_deg[MAX_NODES];
#endif
#pragma HLS ARRAY_PARTITION variable=Xt complete dim=2
#ifndef GNN_LS_LITE
#pragma HLS ARRAY_PARTITION variable=Y  complete dim=2
#endif

drain_seam:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NODES
#pragma HLS PIPELINE II=1
        data_t row[F_OUT];
#pragma HLS ARRAY_PARTITION variable=row complete dim=1
#ifdef GNN_LS_LITE
        unpack_seam_row(xt_stream.read(), row);
#else
        feat_row_t tok = xt_stream.read();
    unpack_struct:
        for (int o = 0; o < F_OUT; o++) {
#pragma HLS UNROLL
            row[o] = tok.v[o];
        }
#endif
        idx_t deg = row_ptr[i + 1] - row_ptr[i];
#if USE_NR_RSQRT && !defined(GNN_LS_LITE)
        inv_sqrt_deg[i] = (deg == 0) ? (data_t)0 : (data_t)nr_rsqrt<3>((float)deg);
#else
        inv_sqrt_deg[i] = (deg == 0) ? (data_t)0
                                     : (data_t)(1.0f / hls::sqrt((float)deg));
#endif
    store_row:
        for (int o = 0; o < F_OUT; o++) {
#pragma HLS UNROLL
            Xt[i][o] = row[o];
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
#ifdef GNN_LS_LITE
            Y[i * F_OUT + o] = (data_t)acc[o];
#else
            Y[i][o] = (data_t)acc[o];
#endif
        }
    }
}

#ifdef GNN_LS_LITE
void gcn_layer_stream(
    const data_t   *X,
    const weight_t *W,
    const weight_t *bias,
    const idx_t    *row_ptr,
    const idx_t    *col_idx,
    idx_t          num_nodes,
    data_t         *Y)
#else
void gcn_layer_stream(
    const data_t   X[MAX_NODES][F_IN],
    const weight_t W[F_IN][F_OUT],
    const weight_t bias[F_OUT],
    const idx_t    row_ptr[MAX_NODES + 1],
    const idx_t    col_idx[MAX_EDGES],
    idx_t          num_nodes,
    data_t         Y[MAX_NODES][F_OUT])
#endif
{
#ifdef GNN_LS_LITE
#pragma HLS INTERFACE mode = ap_memory port = X depth = 1024
#pragma HLS INTERFACE mode = ap_memory port = W depth = 256
#pragma HLS INTERFACE mode = ap_memory port = bias depth = 16
#pragma HLS INTERFACE mode = ap_memory port = row_ptr depth = 65
#pragma HLS INTERFACE mode = ap_memory port = col_idx depth = 512
#pragma HLS INTERFACE mode = ap_memory port = Y depth = 1024
#pragma HLS INTERFACE s_axilite port = num_nodes bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control
#endif
#pragma HLS DATAFLOW
    hls::stream<seam_token_t> xt_stream;
#pragma HLS STREAM variable=xt_stream depth=4

    combine_tier(X, W, bias, num_nodes, xt_stream);
    aggregate_tier(xt_stream, row_ptr, col_idx, num_nodes, Y);
}
