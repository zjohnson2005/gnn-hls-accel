#include "mp_layers.h"

// ----------------------------------------------------------------------------
// GIN
// ----------------------------------------------------------------------------
void gin_layer(
    const data_t   X[MP_MAX_NODES][MP_F],
    const weight_t W[MP_F][MP_F],
    const weight_t bias[MP_F],
    data_t         eps,
    const idx_t    row_ptr[MP_MAX_NODES + 1],
    const idx_t    col_idx[MP_MAX_EDGES],
    idx_t          num_nodes,
    data_t         Y[MP_MAX_NODES][MP_F])
{
    static data_t agg[MP_MAX_NODES][MP_F];
    static data_t H[MP_MAX_NODES][MP_F];
#pragma HLS ARRAY_PARTITION variable=agg complete dim=2
#pragma HLS ARRAY_PARTITION variable=H   complete dim=2

    // sum over CSR neighbors (no normalization)
    mp_aggregate<MP_MAX_NODES, MP_MAX_EDGES, MP_F, AGG_SUM, false>(
        X, row_ptr, col_idx, num_nodes, agg);

gin_combine:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MP_MAX_NODES
#pragma HLS PIPELINE II=1
    gin_combine_f:
        for (int o = 0; o < MP_F; o++) {
#pragma HLS UNROLL
            H[i][o] = (data_t)(agg[i][o] + (data_t)(eps * X[i][o]));
        }
    }

    mp_linear<MP_MAX_NODES, MP_F, MP_F>(H, W, bias, num_nodes, Y);
}

// ----------------------------------------------------------------------------
// GraphSAGE (mean aggregator, two weight matrices)
// ----------------------------------------------------------------------------
void sage_layer(
    const data_t   X[MP_MAX_NODES][MP_F],
    const weight_t W_self[MP_F][MP_F],
    const weight_t W_neigh[MP_F][MP_F],
    const weight_t bias[MP_F],
    const idx_t    row_ptr[MP_MAX_NODES + 1],
    const idx_t    col_idx[MP_MAX_EDGES],
    idx_t          num_nodes,
    data_t         Y[MP_MAX_NODES][MP_F])
{
    static data_t agg[MP_MAX_NODES][MP_F];
#pragma HLS ARRAY_PARTITION variable=agg complete dim=2
#pragma HLS ARRAY_PARTITION variable=W_self  complete dim=1
#pragma HLS ARRAY_PARTITION variable=W_neigh complete dim=1
#pragma HLS ARRAY_PARTITION variable=X       complete dim=2
#pragma HLS ARRAY_PARTITION variable=Y       complete dim=2
#pragma HLS ARRAY_PARTITION variable=bias    complete dim=1

    mp_aggregate<MP_MAX_NODES, MP_MAX_EDGES, MP_F, AGG_MEAN, false>(
        X, row_ptr, col_idx, num_nodes, agg);

sage_nodes:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=MP_MAX_NODES
    sage_out:
        for (int o = 0; o < MP_F; o++) {
#pragma HLS PIPELINE II=1
            acc_t acc = (acc_t)bias[o];
        sage_in:
            for (int k = 0; k < MP_F; k++) {
#pragma HLS UNROLL
                acc += (acc_t)(X[i][k]   * W_self[k][o]);
                acc += (acc_t)(agg[i][k] * W_neigh[k][o]);
            }
            Y[i][o] = (data_t)acc;
        }
    }
}
