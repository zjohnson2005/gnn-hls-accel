#ifndef GCN_LAYER_H
#define GCN_LAYER_H

#include "gnn_config.h"

// ============================================================================
// GCN layer accelerator -- baseline (single layer, on-chip BRAM, small graph)
//
//   Computes one GCN propagation step (PyG GCNConv ordering):
//       Xt = X * W + b                       (combine / linear transform)
//       Y[i] = sum_{j in N(i)} c(i,j) * Xt[j]  (normalized neighbor aggregate)
//   with symmetric normalization
//       c(i,j) = 1/sqrt(deg_i) * 1/sqrt(deg_j)
//
//   Self-loops (A + I) are assumed to be already present in the CSR graph, so
//   deg_i = number of CSR neighbors of node i (including itself).
//
//   Datatypes (data_t/weight_t/acc_t/...) come from gnn_config.h, which is the
//   single place to retune precision. Profile 0 is bit-identical to the
//   original baseline.
// ============================================================================

// ---- Compile-time problem sizes (must bound the runtime graph) ----
#define MAX_NODES 256          // upper bound on node count
#define MAX_EDGES 4096         // upper bound on CSR neighbor entries (incl. self-loops)
#define F_IN      16           // input feature dimension
#define F_OUT     16           // output feature dimension

// ---- Top-level kernel ----
void gcn_layer(
    const data_t   X[MAX_NODES][F_IN],   // node input features
    const weight_t W[F_IN][F_OUT],       // combine weight matrix
    const weight_t bias[F_OUT],          // per-output-feature bias
    const idx_t    row_ptr[MAX_NODES + 1], // CSR row pointers (length num_nodes+1)
    const idx_t    col_idx[MAX_EDGES],   // CSR neighbor indices (self-loops included)
    idx_t          num_nodes,            // actual node count (<= MAX_NODES)
    data_t         Y[MAX_NODES][F_OUT]   // output features
);

#endif // GCN_LAYER_H
