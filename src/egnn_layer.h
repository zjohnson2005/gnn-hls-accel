#ifndef EGNN_LAYER_H
#define EGNN_LAYER_H

#include "gnn_config.h"
#include "hls_rsqrt.h"

// ============================================================================
// E(n)-equivariant GNN layer (A5) -- the Phase B core workload.
//
// One EGNN message-passing step (Satorras et al. 2021) on a small point cloud,
// decomposed into the three tier-cleavable kernels named in the plan:
//
//   k_mlp1 (edge MLP phi_e):  per-edge  m_ij = phi_e(h_i, h_j, ||x_i-x_j||^2)
//                             and scalar coordinate weight w_ij = phi_x(m_ij)
//                             -- compute-bound (dense MLPs per edge).
//   k_magg (aggregate):       scatter-add  m_i  = sum_j m_ij
//                             and          dx_i = sum_j (x_i - x_j) * w_ij
//                             -- memory-bound gather/scatter over the edge list.
//   k_mlp2 (node MLP phi_h):  h_i' = h_i + phi_h(h_i, m_i),  x_i' = x_i + dx_i
//                             -- compute-bound.
//
// k_mlp1/k_mlp2 are the compute tier, k_magg the near-memory tier: the
// aggregate/combine seam Phase B partitions across stacked dies.
//
// Equivariance: messages depend on coordinates only through the invariant
// squared distance, and coordinates move along relative vectors (x_i - x_j),
// so rotating/translating the input rotates/translates x' identically and
// leaves h' unchanged.
// ============================================================================

// ---- Compile-time sizes (small point cloud) ----
#define EG_MAX_NODES 64
#define EG_MAX_EDGES 512
#define EG_COORD     3          // spatial dimension
#define EG_H         8          // node feature dim
#define EG_M         8          // message dim
#define EG_HID       16         // MLP hidden dim
#define EG_E_IN      (2 * EG_H + 1)   // phi_e input: [h_i, h_j, dist2]
#define EG_H_IN      (EG_H + EG_M)    // phi_h input: [h_i, m_i]

// All trainable weights for one EGNN layer, passed by const reference.
struct egnn_weights_t {
    // phi_e : EG_E_IN -> EG_HID -> EG_M   (ReLU hidden)
    weight_t e_w1[EG_E_IN][EG_HID];
    weight_t e_b1[EG_HID];
    weight_t e_w2[EG_HID][EG_M];
    weight_t e_b2[EG_M];
    // phi_x : EG_M -> 1   (scalar coordinate gate, linear)
    weight_t x_w[EG_M];
    weight_t x_b;
    // phi_h : EG_H_IN -> EG_HID -> EG_H   (ReLU hidden, residual add outside)
    weight_t h_w1[EG_H_IN][EG_HID];
    weight_t h_b1[EG_HID];
    weight_t h_w2[EG_HID][EG_H];
    weight_t h_b2[EG_H];
};

void egnn_layer(
    const egnn_weights_t &Wt,
    const data_t          h_in[EG_MAX_NODES][EG_H],
    const data_t          x_in[EG_MAX_NODES][EG_COORD],
    const idx_t           edge_src[EG_MAX_EDGES],
    const idx_t           edge_dst[EG_MAX_EDGES],
    idx_t                 num_nodes,
    idx_t                 num_edges,
    data_t                h_out[EG_MAX_NODES][EG_H],
    data_t                x_out[EG_MAX_NODES][EG_COORD]);

#endif // EGNN_LAYER_H
