// Minimal cosim testbench: single flat scatter with fan-out=2 (Phase 2 crossover anchor).
#include "orchestration_engine.h"

#include <cstdio>

int main() {
    oe_hls_graph_desc desc;
    desc.num_nodes = 4;
    desc.num_edges = 2;
    desc.num_roots = 1;

    ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1] = {};
    oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES] = {};
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES] = {};
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES] = {};
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES] = {};
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES] = {};

    row_ptr[0] = 0;
    row_ptr[1] = 2;
    for (int i = 2; i <= 4; ++i) {
        row_ptr[i] = 2;
    }
    col_idx[0] = 1;
    col_idx[1] = 2;
    preds_remaining[0] = 0;
    preds_remaining[1] = 1;
    preds_remaining[2] = 1;
    fire_mode[1] = 0;
    fire_mode[2] = 0;
    fire_threshold[1] = 0;
    fire_threshold[2] = 0;

    oe_hls_cycle_t scatter_cycles = 0;
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
        scatter_cycles);

    if (ready_flags[1] != 1 || ready_flags[2] != 1) {
        std::printf("FAIL: fan-out=2 scatter did not ready successors\n");
        return 1;
    }
    if (scatter_cycles != 3) {
        std::printf("FAIL: expected scatter_cycles=3 got %u\n", (unsigned)scatter_cycles);
        return 1;
    }

    std::printf("COSIM TB fan-out=2 PASSED scatter_cycles=%u\n", (unsigned)scatter_cycles);
    return 0;
}
