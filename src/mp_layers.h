#ifndef MP_LAYERS_H
#define MP_LAYERS_H

#include "mp_template.h"

// ============================================================================
// Concrete message-passing layers built from the mp_template primitives (A4).
// Demonstrates that GCN / GIN / GraphSAGE are all instantiations of the same
// gather -> aggregate -> update skeleton, differing only in aggregator choice,
// normalization, and the update policy.
//
// Graph convention matches the rest of the repo: CSR with self-loops baked in.
// ============================================================================

#define MP_MAX_NODES 256
#define MP_MAX_EDGES 4096
#define MP_F         16   // square feature transform for the demo layers

// ---- GIN: y_i = W * ( (1+eps) x_i + sum_{j in N(i)\\i} x_j ) + b ----
// With self-loops in CSR, sum_{j in N(i)} x_j already includes x_i once, so
// adding eps*x_i yields the (1+eps) self weighting. Aggregator: plain SUM.
void gin_layer(
    const data_t   X[MP_MAX_NODES][MP_F],
    const weight_t W[MP_F][MP_F],
    const weight_t bias[MP_F],
    data_t         eps,
    const idx_t    row_ptr[MP_MAX_NODES + 1],
    const idx_t    col_idx[MP_MAX_EDGES],
    idx_t          num_nodes,
    data_t         Y[MP_MAX_NODES][MP_F]);

// ---- GraphSAGE (mean): y_i = W_self x_i + W_neigh mean_{j in N(i)} x_j + b ----
void sage_layer(
    const data_t   X[MP_MAX_NODES][MP_F],
    const weight_t W_self[MP_F][MP_F],
    const weight_t W_neigh[MP_F][MP_F],
    const weight_t bias[MP_F],
    const idx_t    row_ptr[MP_MAX_NODES + 1],
    const idx_t    col_idx[MP_MAX_EDGES],
    idx_t          num_nodes,
    data_t         Y[MP_MAX_NODES][MP_F]);

#endif // MP_LAYERS_H
