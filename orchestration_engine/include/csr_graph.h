#ifndef OE_CSR_GRAPH_H
#define OE_CSR_GRAPH_H

#include <stdint.h>

#include "oe_config.h"
#include "oe_types.h"

// Compressed-sparse-row dependency graph (successor lists).
// Same representation as GNN neighbor gather / LightningSim V2 sim graphs.

struct oe_csr_graph {
    oe_node_id_t num_nodes;
    oe_node_id_t num_edges;
    uint32_t row_ptr[OE_MAX_NODES + 1];
    oe_node_id_t col_idx[OE_MAX_EDGES];
};

static inline void oe_csr_init(oe_csr_graph *g) {
    g->num_nodes = 0;
    g->num_edges = 0;
    g->row_ptr[0] = 0;
}

static inline int oe_csr_append_edge(oe_csr_graph *g, oe_node_id_t src, oe_node_id_t dst) {
    if (g->num_edges >= OE_MAX_EDGES) {
        return -1;
    }
    while (g->num_nodes <= src) {
        if (g->num_nodes >= OE_MAX_NODES) {
            return -1;
        }
        g->row_ptr[g->num_nodes + 1] = g->row_ptr[g->num_nodes];
        g->num_nodes++;
    }
    while (g->num_nodes <= dst) {
        if (g->num_nodes >= OE_MAX_NODES) {
            return -1;
        }
        g->row_ptr[g->num_nodes + 1] = g->row_ptr[g->num_nodes];
        g->num_nodes++;
    }
    const uint32_t insert_at = g->row_ptr[src + 1];
    for (uint32_t i = g->num_edges; i > insert_at; --i) {
        g->col_idx[i] = g->col_idx[i - 1];
    }
    for (oe_node_id_t r = src + 1; r <= g->num_nodes; ++r) {
        g->row_ptr[r]++;
    }
    g->col_idx[insert_at] = dst;
    g->num_edges++;
    return 0;
}

static inline uint32_t oe_csr_out_degree(const oe_csr_graph *g, oe_node_id_t node) {
    if (node >= g->num_nodes) {
        return 0;
    }
    return g->row_ptr[node + 1] - g->row_ptr[node];
}

static inline oe_node_id_t oe_csr_successor_at(
    const oe_csr_graph *g, oe_node_id_t node, uint32_t idx) {
    return g->col_idx[g->row_ptr[node] + idx];
}

#endif // OE_CSR_GRAPH_H
