#include "gcn_layer.h"
#include "hls_math.h"

// USE_NR_RSQRT (default on): replace the hls::sqrt + divide core with the
// Newton-Raphson reciprocal-sqrt from hls_rsqrt.h. Define USE_NR_RSQRT=0 to
// fall back to the original hls::sqrt path for an apples-to-apples reference.
#ifndef USE_NR_RSQRT
#define USE_NR_RSQRT 1
#endif

#if USE_NR_RSQRT
#include "hls_rsqrt.h"
#endif

// ----------------------------------------------------------------------------
// Stage 1: degrees -> inverse-sqrt-degree table.
//   deg_i = row_ptr[i+1] - row_ptr[i]  (self-loops already in CSR).
//   inv_sqrt_deg[i] = 1 / sqrt(deg_i).
//
//   The reciprocal-sqrt is the hot, DSP-heavy op. With USE_NR_RSQRT it becomes
//   a seeded Newton-Raphson iteration (no sqrt core, no divide).
// ----------------------------------------------------------------------------
static void compute_inv_sqrt_deg(
    const idx_t row_ptr[MAX_NODES + 1],
    idx_t       num_nodes,
    data_t      inv_sqrt_deg[MAX_NODES])
{
deg_loop:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NODES
#pragma HLS PIPELINE II=1
        idx_t deg = row_ptr[i + 1] - row_ptr[i];
        if (deg == 0) {
            inv_sqrt_deg[i] = (data_t)0;
        } else {
#if USE_NR_RSQRT
            inv_sqrt_deg[i] = (data_t)nr_rsqrt<3>((float)deg);
#else
            float s = hls::sqrt((float)deg);
            inv_sqrt_deg[i] = (data_t)(1.0f / s);
#endif
        }
    }
}

// ----------------------------------------------------------------------------
// Stage 2: combine / linear transform   Xt = X * W + b
// ----------------------------------------------------------------------------
static void combine(
    const data_t   X[MAX_NODES][F_IN],
    const weight_t W[F_IN][F_OUT],
    const weight_t bias[F_OUT],
    idx_t          num_nodes,
    data_t         Xt[MAX_NODES][F_OUT])
{
#pragma HLS ARRAY_PARTITION variable=W    complete dim=1
#pragma HLS ARRAY_PARTITION variable=X    complete dim=2
#pragma HLS ARRAY_PARTITION variable=Xt   complete dim=2
#pragma HLS ARRAY_PARTITION variable=bias complete dim=1

combine_nodes:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MAX_NODES
    combine_out:
        for (int o = 0; o < F_OUT; o++) {
#pragma HLS PIPELINE II=1
            acc_t acc = (acc_t)bias[o];
        combine_in:
            for (int k = 0; k < F_IN; k++) {
#pragma HLS UNROLL
                acc += (acc_t)(X[i][k] * W[k][o]);
            }
            Xt[i][o] = (data_t)acc;
        }
    }
}

// ----------------------------------------------------------------------------
// Stage 3: normalized neighbor aggregation
//   Y[i] = sum_{p in [row_ptr[i], row_ptr[i+1])}  c(i,j) * Xt[j],
//   j = col_idx[p],  c(i,j) = inv_sqrt_deg[i] * inv_sqrt_deg[j].
// ----------------------------------------------------------------------------
static void aggregate(
    const data_t Xt[MAX_NODES][F_OUT],
    const idx_t  row_ptr[MAX_NODES + 1],
    const idx_t  col_idx[MAX_EDGES],
    const data_t inv_sqrt_deg[MAX_NODES],
    idx_t        num_nodes,
    data_t       Y[MAX_NODES][F_OUT])
{
#pragma HLS ARRAY_PARTITION variable=Xt complete dim=2
#pragma HLS ARRAY_PARTITION variable=Y  complete dim=2

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
// Top level
// ----------------------------------------------------------------------------
void gcn_layer(
    const data_t   X[MAX_NODES][F_IN],
    const weight_t W[F_IN][F_OUT],
    const weight_t bias[F_OUT],
    const idx_t    row_ptr[MAX_NODES + 1],
    const idx_t    col_idx[MAX_EDGES],
    idx_t          num_nodes,
    data_t         Y[MAX_NODES][F_OUT])
{
    static data_t inv_sqrt_deg[MAX_NODES];
    static data_t Xt[MAX_NODES][F_OUT];
#pragma HLS ARRAY_PARTITION variable=Xt complete dim=2

    compute_inv_sqrt_deg(row_ptr, num_nodes, inv_sqrt_deg);
    combine(X, W, bias, num_nodes, Xt);
    aggregate(Xt, row_ptr, col_idx, inv_sqrt_deg, num_nodes, Y);
}
