#ifndef MP_TEMPLATE_H
#define MP_TEMPLATE_H

#include "gnn_config.h"
#include "hls_rsqrt.h"
#include <hls_stream.h>

// ============================================================================
// Generic message-passing template (A4).
//
// One reusable "gather -> aggregate -> update" skeleton that the GCN baseline,
// GIN, GraphSAGE, and (in A5) the EGNN are all instances of. Everything is
// compile-time parameterized (feature dims, graph bounds, aggregator), so a
// concrete accelerator is produced by instantiating the primitives with the
// right template arguments -- this is the substrate the Phase A generator
// emits, and the aggregate/update split is the explicit Phase B tier seam.
//
// Synthesizable-subset notes: no dynamic memory, no recursion, no virtual
// dispatch. Aggregator choice is a non-type template parameter so the reducer
// folds away to straight-line RTL.
//
//   AGG_SUM   y_i = sum_{j in N(i)} c_ij * x_j
//   AGG_MEAN  y_i = (1/|N(i)|) sum_j x_j
//   AGG_MAX   y_i = max_{j in N(i)} x_j          (elementwise)
// ============================================================================

enum agg_kind { AGG_SUM = 0, AGG_MEAN = 1, AGG_MAX = 2 };

// ----------------------------------------------------------------------------
// Linear transform Xt = X * W + b over all nodes (the "combine"/update MLP).
//   NODES bound is runtime (num_nodes); FI/FO are compile-time feature dims.
// ----------------------------------------------------------------------------
template <int MAXN, int FI, int FO>
void mp_linear(
    const data_t   X[MAXN][FI],
    const weight_t W[FI][FO],
    const weight_t bias[FO],
    idx_t          num_nodes,
    data_t         Xt[MAXN][FO])
{
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=W    complete dim=1
#pragma HLS ARRAY_PARTITION variable=X    complete dim=2
#pragma HLS ARRAY_PARTITION variable=Xt   complete dim=2
#pragma HLS ARRAY_PARTITION variable=bias complete dim=1
mp_lin_nodes:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MAXN
    mp_lin_out:
        for (int o = 0; o < FO; o++) {
#pragma HLS PIPELINE II=1
            acc_t acc = (acc_t)bias[o];
        mp_lin_in:
            for (int k = 0; k < FI; k++) {
#pragma HLS UNROLL
                acc += (acc_t)(X[i][k] * W[k][o]);
            }
            Xt[i][o] = (data_t)acc;
        }
    }
}

// ----------------------------------------------------------------------------
// Neighbor aggregation over a CSR graph with a compile-time aggregator.
//   NORMALIZE=true applies symmetric GCN coefficients c_ij = d_i^-.5 d_j^-.5;
//   NORMALIZE=false is the plain sum/mean/max used by GIN/SAGE.
// ----------------------------------------------------------------------------
template <int MAXN, int MAXE, int FO, int AGG, bool NORMALIZE>
void mp_aggregate(
    const data_t Xt[MAXN][FO],
    const idx_t  row_ptr[MAXN + 1],
    const idx_t  col_idx[MAXE],
    idx_t        num_nodes,
    data_t       Y[MAXN][FO])
{
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=Xt complete dim=2
#pragma HLS ARRAY_PARTITION variable=Y  complete dim=2

    static data_t inv_sqrt_deg[MAXN];
    if (NORMALIZE) {
    mp_deg:
        for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MAXN
#pragma HLS PIPELINE II=1
            idx_t deg = row_ptr[i + 1] - row_ptr[i];
            inv_sqrt_deg[i] = (deg == 0) ? (data_t)0
                                         : (data_t)nr_rsqrt<3>((float)deg);
        }
    }

mp_agg_nodes:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MAXN
        acc_t acc[FO];
#pragma HLS ARRAY_PARTITION variable=acc complete dim=1
    mp_agg_init:
        for (int o = 0; o < FO; o++) {
#pragma HLS UNROLL
            acc[o] = (AGG == AGG_MAX) ? (acc_t)-1e30 : (acc_t)0;
        }

        idx_t  start = row_ptr[i];
        idx_t  end   = row_ptr[i + 1];
        idx_t  deg   = end - start;
        norm_t inv_i = NORMALIZE ? (norm_t)inv_sqrt_deg[i] : (norm_t)1;

    mp_agg_neighbors:
        for (idx_t p = start; p < end; p++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=64
#pragma HLS PIPELINE II=1
            idx_t  j = col_idx[p];
            norm_t c = NORMALIZE ? (norm_t)(inv_i * (norm_t)inv_sqrt_deg[j])
                                 : (norm_t)1;
        mp_agg_feat:
            for (int o = 0; o < FO; o++) {
#pragma HLS UNROLL
                data_t m = (data_t)(c * Xt[j][o]);
                if (AGG == AGG_MAX) {
                    if ((acc_t)m > acc[o]) acc[o] = (acc_t)m;
                } else {
                    acc[o] += (acc_t)m;   // SUM and MEAN both accumulate
                }
            }
        }

    mp_agg_store:
        for (int o = 0; o < FO; o++) {
#pragma HLS UNROLL
            acc_t out = acc[o];
            if (AGG == AGG_MEAN && deg != 0) {
                out = (acc_t)(out / (acc_t)deg);
            }
            Y[i][o] = (data_t)out;
        }
    }
}

#endif // MP_TEMPLATE_H
