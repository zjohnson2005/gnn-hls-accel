#ifndef ORCHESTRATION_ENGINE_H
#define ORCHESTRATION_ENGINE_H

#include "ap_int.h"
#include "oe_hls_config.h"

typedef ap_uint<16> oe_hls_node_id_t;
typedef ap_uint<32> oe_hls_cycle_t;
typedef ap_uint<8> oe_hls_kind_t;
typedef ap_uint<8> oe_hls_fire_t;

// Host-visible configuration for one scheduling epoch over a loaded CSR graph.
struct oe_hls_graph_desc {
    oe_hls_node_id_t num_nodes;
    oe_hls_node_id_t num_edges;
    oe_hls_node_id_t num_roots;
};

void oe_hls_scatter_step(
    const oe_hls_node_id_t completed,
    const oe_hls_node_id_t num_nodes,
    const ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    const oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES],
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES],
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES],
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES]);

// 8-wide unrolled scatter for planner fan-out (64 edges -> 8 cycles at II=1).
void oe_hls_scatter_batch(
    const oe_hls_node_id_t completed,
    const oe_hls_node_id_t num_nodes,
    const ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    const oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES],
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES],
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES],
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES]);

// O(1) tail append into the edge pool (append-only graph growth).
ap_uint<8> oe_hls_append_edge(
    const oe_hls_node_id_t src,
    const oe_hls_node_id_t dst,
    ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<32> &num_edges);

// Fast csynth target: one completion scatter (flat or batch).
void oe_hls_scatter_kernel(
    const oe_hls_graph_desc &desc,
    const ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    const oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES],
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES],
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t completed,
    const ap_uint<8> use_batch,
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &scatter_cycles);

void orchestration_engine(
    const oe_hls_graph_desc &desc,
    const ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    const oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES],
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES],
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES],
    ap_uint<8> node_kind[OE_HLS_MAX_NODES],
    oe_hls_cycle_t predicted_latency[OE_HLS_MAX_NODES],
    oe_hls_node_id_t completion_nodes[OE_HLS_MAX_OUTSTANDING],
    oe_hls_cycle_t completion_cycles[OE_HLS_MAX_OUTSTANDING],
    oe_hls_node_id_t num_completions,
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &out_cycles);

#endif // ORCHESTRATION_ENGINE_H
