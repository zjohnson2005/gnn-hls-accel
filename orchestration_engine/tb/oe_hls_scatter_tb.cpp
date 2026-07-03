#include "orchestration_engine.h"

#include <cstdio>

int main() {
    oe_hls_graph_desc desc;
    desc.num_nodes = 10;
    desc.num_edges = 8;
    desc.num_roots = 1;

    ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1] = {};
    oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES] = {};
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES] = {};
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES] = {};
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES] = {};
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES] = {};

    row_ptr[0] = 0;
    row_ptr[1] = 8;
    for (int i = 0; i < 8; ++i) {
        col_idx[i] = i + 1;
        preds_remaining[i + 1] = 1;
        fire_mode[i + 1] = 0;
        fire_threshold[i + 1] = 0;
    }
    for (int i = 0; i <= 10; ++i) {
        row_ptr[i] = (i == 0) ? 0 : 8;
    }
    preds_remaining[0] = 0;

    oe_hls_cycle_t flat_cycles = 0;
    oe_hls_scatter_kernel(
        desc,
        row_ptr,
        col_idx,
        preds_remaining,
        fire_mode,
        fire_threshold,
        0,
        0,
        ready_flags,
        flat_cycles);

    for (int i = 1; i <= 8; ++i) {
        if (ready_flags[i] != 1) {
            std::printf("FAIL: flat scatter did not ready node %d\n", i);
            return 1;
        }
    }
    if (flat_cycles != 9) {
        std::printf("FAIL: expected flat_cycles=9 got %u\n", (unsigned)flat_cycles);
        return 1;
    }

    for (int i = 0; i < 10; ++i) {
        preds_remaining[i] = (i == 0) ? 0 : 1;
        ready_flags[i] = 0;
    }

    oe_hls_cycle_t batch_cycles = 0;
    oe_hls_scatter_kernel(
        desc,
        row_ptr,
        col_idx,
        preds_remaining,
        fire_mode,
        fire_threshold,
        0,
        1,
        ready_flags,
        batch_cycles);

    if (batch_cycles != 2) {
        std::printf("FAIL: expected batch_cycles=2 got %u\n", (unsigned)batch_cycles);
        return 1;
    }

    std::printf(
        "SCATTER TB PASSED flat_cycles=%u batch_cycles=%u (fan-out=8)\n",
        (unsigned)flat_cycles,
        (unsigned)batch_cycles);
    return 0;
}
