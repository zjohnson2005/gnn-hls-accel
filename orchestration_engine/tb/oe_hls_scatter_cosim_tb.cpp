// Cosim-only TB: fan-out=2 anchor x4 for RTL II measurement.
// Lives in its own HLS project (oe_scatter_cosim_proj) — never linked with
// the full regression TB, so no duplicate main.

#include "orchestration_engine.h"

#include <cstdio>

static ap_uint<8> succ_count[OE_HLS_MAX_NODES];
static oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS];
static oe_hls_node_state_t node_state[OE_HLS_MAX_NODES];
static ap_uint<1> ready_flags[OE_HLS_MAX_NODES];

static int run_fanout2_once() {
    for (int n = 0; n < OE_HLS_MAX_NODES; ++n) {
        succ_count[n] = 0;
        node_state[n] = 0;
        ready_flags[n] = 0;
    }

    if (oe_hls_append_edge(0, 1, succ_count, succ_slots) != 0 ||
        oe_hls_append_edge(0, 2, succ_count, succ_slots) != 0) {
        std::printf("FAIL: append_edge rejected\n");
        return 1;
    }
    node_state[0] = oe_hls_make_node(0, 0, 0);
    node_state[1] = oe_hls_make_node(1, 0, 0);
    node_state[2] = oe_hls_make_node(1, 0, 0);

    oe_hls_cycle_t cycles = 0;
    oe_hls_scatter_kernel(
        4, succ_count, succ_slots, node_state, 0, ready_flags, cycles);

    if (ready_flags[1] != 1 || ready_flags[2] != 1) {
        std::printf("FAIL: fan-out=2 scatter did not ready successors\n");
        return 1;
    }
    if (cycles != 3) {
        std::printf("FAIL: expected scatter_cycles=3 got %u\n", (unsigned)cycles);
        return 1;
    }
    if (!oe_hls_node_fired(node_state[1]) || !oe_hls_node_fired(node_state[2])) {
        std::printf("FAIL: fired bits not set after scatter\n");
        return 1;
    }
    return 0;
}

int main() {
    for (int t = 0; t < 4; ++t) {
        if (run_fanout2_once() != 0) {
            return 1;
        }
    }
    std::printf("COSIM TB fan-out=2 x4 PASSED (multi-transaction for II)\n");
    return 0;
}
