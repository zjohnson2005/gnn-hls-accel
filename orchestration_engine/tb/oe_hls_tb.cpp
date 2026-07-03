#include "orchestration_engine.h"

#include <cstdio>

static void init_chain_graph(
    oe_hls_graph_desc &desc,
    ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES],
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES],
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES],
    ap_uint<8> node_kind[OE_HLS_MAX_NODES],
    oe_hls_cycle_t predicted_latency[OE_HLS_MAX_NODES],
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES]) {
    desc.num_nodes = 3;
    desc.num_edges = 2;
    desc.num_roots = 1;

    row_ptr[0] = 0;
    row_ptr[1] = 1;
    row_ptr[2] = 2;
    row_ptr[3] = 2;
    col_idx[0] = 1;
    col_idx[1] = 2;

    preds_remaining[0] = 0;
    preds_remaining[1] = 1;
    preds_remaining[2] = 1;

    for (int i = 0; i < 3; ++i) {
        fire_mode[i] = 0;
        fire_threshold[i] = 0;
        node_kind[i] = 1;
        predicted_latency[i] = 10;
        ready_flags[i] = 0;
    }
}

int main() {
    oe_hls_graph_desc desc;
    ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1] = {};
    oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES] = {};
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES] = {};
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES] = {};
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES] = {};
    ap_uint<8> node_kind[OE_HLS_MAX_NODES] = {};
    oe_hls_cycle_t predicted_latency[OE_HLS_MAX_NODES] = {};
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES] = {};

    init_chain_graph(
        desc,
        row_ptr,
        col_idx,
        preds_remaining,
        fire_mode,
        fire_threshold,
        node_kind,
        predicted_latency,
        ready_flags);

    oe_hls_node_id_t completion_nodes[OE_HLS_MAX_OUTSTANDING] = {};
    oe_hls_cycle_t completion_cycles[OE_HLS_MAX_OUTSTANDING] = {};
    completion_nodes[0] = 0;
    completion_cycles[0] = 10;
    completion_nodes[1] = 1;
    completion_cycles[1] = 20;

    oe_hls_cycle_t out_cycles = 0;
    orchestration_engine(
        desc,
        row_ptr,
        col_idx,
        preds_remaining,
        fire_mode,
        fire_threshold,
        node_kind,
        predicted_latency,
        completion_nodes,
        completion_cycles,
        2,
        ready_flags,
        out_cycles);

    if (ready_flags[2] != 1) {
        std::printf("FAIL: node 2 not ready after chain completions\n");
        return 1;
    }
    if (out_cycles != 20) {
        std::printf("FAIL: expected out_cycles=20 got %u\n", (unsigned)out_cycles);
        return 1;
    }

    ap_uint<32> num_edges = desc.num_edges;
    if (oe_hls_append_edge(1, 2, row_ptr, col_idx, num_edges) != 0) {
        std::printf("FAIL: append_edge rejected\n");
        return 1;
    }

    oe_hls_cycle_t scatter_cycles = 0;
    oe_hls_scatter_kernel(
        desc,
        row_ptr,
        col_idx,
        preds_remaining,
        fire_mode,
        fire_threshold,
        1,
        1,
        ready_flags,
        scatter_cycles);

    std::printf("HLS TB PASSED out_cycles=%u scatter_cycles=%u edges=%u\n",
        (unsigned)out_cycles,
        (unsigned)scatter_cycles,
        (unsigned)num_edges);
    return 0;
}
