#include "orchestration_engine.h"

#include <cstdio>

// Shared TB state (static: segment pool arrays are too large for the stack).
static oe_hls_seg_id_t head_seg[OE_HLS_MAX_NODES];
static oe_hls_seg_id_t tail_seg[OE_HLS_MAX_NODES];
static oe_hls_seg_id_t seg_next[OE_HLS_MAX_SEGS];
static ap_uint<8> seg_count[OE_HLS_MAX_SEGS];
static oe_hls_node_id_t seg_slots[OE_HLS_MAX_SEG_SLOTS];
static oe_hls_node_state_t node_state[OE_HLS_MAX_NODES];
static ap_uint<1> ready_flags[OE_HLS_MAX_NODES];
static ap_uint<32> seg_alloc;

static void pool_reset() {
    for (int n = 0; n < OE_HLS_MAX_NODES; ++n) {
        head_seg[n] = OE_HLS_NULL_SEG;
        tail_seg[n] = OE_HLS_NULL_SEG;
        node_state[n] = 0;
        ready_flags[n] = 0;
    }
    for (int s = 0; s < OE_HLS_MAX_SEGS; ++s) {
        seg_next[s] = OE_HLS_NULL_SEG;
        seg_count[s] = 0;
    }
    seg_alloc = 0;
}

static int add_edge(int src, int dst) {
    if (oe_hls_append_edge(
            src, dst, head_seg, tail_seg, seg_next, seg_count, seg_slots,
            seg_alloc) != 0) {
        std::printf("FAIL: append_edge(%d,%d) rejected\n", src, dst);
        return 1;
    }
    return 0;
}

static oe_hls_cycle_t scatter(int num_nodes, int completed, int use_batch) {
    oe_hls_cycle_t cycles = 0;
    oe_hls_scatter_kernel(
        num_nodes, head_seg, seg_next, seg_count, seg_slots, node_state,
        completed, use_batch, ready_flags, cycles);
    return cycles;
}

// Fan-out=2 anchor: 0 -> {1, 2}, all-of. Expect 3 cycles, both fire once.
static int run_fanout2_once() {
    pool_reset();
    if (add_edge(0, 1) || add_edge(0, 2)) {
        return 1;
    }
    node_state[0] = oe_hls_make_node(0, 0, 0);
    node_state[1] = oe_hls_make_node(1, 0, 0);
    node_state[2] = oe_hls_make_node(1, 0, 0);

    const oe_hls_cycle_t cycles = scatter(4, 0, 0);

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

#ifndef OE_COSIM_FANOUT2_ONLY
// Any-of exactly-once: {0, 1} -> 2 (any-of). First completion fires node 2;
// after the host clears the flag, the second completion must NOT re-fire.
static int run_anyof_exactly_once() {
    pool_reset();
    if (add_edge(0, 2) || add_edge(1, 2)) {
        return 1;
    }
    node_state[0] = oe_hls_make_node(0, 0, 0);
    node_state[1] = oe_hls_make_node(0, 0, 0);
    node_state[2] = oe_hls_make_node(2, 1, 0); // any-of, fan-in 2

    (void)scatter(3, 0, 0);
    if (ready_flags[2] != 1) {
        std::printf("FAIL: any-of did not fire on first predecessor\n");
        return 1;
    }

    ready_flags[2] = 0; // host dispatches node 2
    (void)scatter(3, 1, 0);
    if (ready_flags[2] != 0) {
        std::printf("FAIL: any-of re-fired after dispatch (double dispatch)\n");
        return 1;
    }
    std::printf("any-of exactly-once PASSED\n");
    return 0;
}

// Threshold exactly-once: {0,1,2} -> 3 with threshold 1 (fires when
// preds_remaining <= 1, i.e. after the 2nd completion; 3rd must not re-fire).
static int run_threshold_exactly_once() {
    pool_reset();
    if (add_edge(0, 3) || add_edge(1, 3) || add_edge(2, 3)) {
        return 1;
    }
    node_state[0] = oe_hls_make_node(0, 0, 0);
    node_state[1] = oe_hls_make_node(0, 0, 0);
    node_state[2] = oe_hls_make_node(0, 0, 0);
    node_state[3] = oe_hls_make_node(3, 2, 1); // threshold mode, thr=1

    (void)scatter(4, 0, 0);
    if (ready_flags[3] != 0) {
        std::printf("FAIL: threshold fired too early (preds=2 > thr=1)\n");
        return 1;
    }
    (void)scatter(4, 1, 0);
    if (ready_flags[3] != 1) {
        std::printf("FAIL: threshold did not fire at preds<=thr\n");
        return 1;
    }
    ready_flags[3] = 0; // host dispatches
    (void)scatter(4, 2, 0);
    if (ready_flags[3] != 0) {
        std::printf("FAIL: threshold re-fired after dispatch\n");
        return 1;
    }
    std::printf("threshold exactly-once PASSED\n");
    return 0;
}

// Prune: pruned successor must never fire.
static int run_prune_guard() {
    pool_reset();
    if (add_edge(0, 1)) {
        return 1;
    }
    node_state[0] = oe_hls_make_node(0, 0, 0);
    node_state[1] = oe_hls_make_node(1, 0, 0, /*pruned=*/1);

    (void)scatter(2, 0, 0);
    if (ready_flags[1] != 0) {
        std::printf("FAIL: pruned node fired\n");
        return 1;
    }
    std::printf("prune guard PASSED\n");
    return 0;
}

// Fan-out=8 regression: flat = 1+8 = 9 cycles; batch = 1+1 segment = 2.
static int run_fanout8_regression() {
    pool_reset();
    for (int i = 1; i <= 8; ++i) {
        if (add_edge(0, i)) {
            return 1;
        }
    }
    node_state[0] = oe_hls_make_node(0, 0, 0);
    for (int i = 1; i <= 8; ++i) {
        node_state[i] = oe_hls_make_node(1, 0, 0);
    }

    const oe_hls_cycle_t flat_cycles = scatter(10, 0, 0);
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

    // Reset counters/flags and re-run in batch mode (one 8-wide segment).
    for (int i = 1; i <= 8; ++i) {
        node_state[i] = oe_hls_make_node(1, 0, 0);
        ready_flags[i] = 0;
    }
    const oe_hls_cycle_t batch_cycles = scatter(10, 0, 1);
    if (batch_cycles != 2) {
        std::printf("FAIL: expected batch_cycles=2 got %u\n", (unsigned)batch_cycles);
        return 1;
    }

    std::printf(
        "fan-out=8 regression PASSED flat_cycles=%u batch_cycles=%u\n",
        (unsigned)flat_cycles,
        (unsigned)batch_cycles);
    return 0;
}

// Mid-graph append: appending to node 0 AFTER node 2 already has edges.
// The old CSR tail-append corrupted node 2's row here; segments must not.
static int run_midgraph_append() {
    pool_reset();
    if (add_edge(0, 1) || add_edge(2, 3)) {
        return 1;
    }
    // Runtime append to node 0 (not the last row) — the claim-2 path.
    if (add_edge(0, 4)) {
        return 1;
    }

    node_state[0] = oe_hls_make_node(0, 0, 0);
    node_state[1] = oe_hls_make_node(1, 0, 0);
    node_state[2] = oe_hls_make_node(0, 0, 0);
    node_state[3] = oe_hls_make_node(1, 0, 0);
    node_state[4] = oe_hls_make_node(1, 0, 0);

    (void)scatter(5, 2, 0);
    if (ready_flags[3] != 1) {
        std::printf("FAIL: node 2 successor list corrupted by append to node 0\n");
        return 1;
    }
    const oe_hls_cycle_t cycles = scatter(5, 0, 0);
    if (ready_flags[1] != 1 || ready_flags[4] != 1) {
        std::printf("FAIL: appended edge 0->4 not scattered\n");
        return 1;
    }
    if (cycles != 3) {
        std::printf("FAIL: expected 3 cycles after append got %u\n", (unsigned)cycles);
        return 1;
    }
    std::printf("mid-graph append PASSED\n");
    return 0;
}
#endif

int main() {
#ifdef OE_COSIM_FANOUT2_ONLY
    for (int t = 0; t < 4; ++t) {
        if (run_fanout2_once() != 0) {
            return 1;
        }
    }
    std::printf("COSIM TB fan-out=2 x4 PASSED (multi-transaction for II)\n");
#else
    if (run_fanout2_once() != 0) {
        return 1;
    }
    std::printf("fan-out=2 anchor PASSED scatter_cycles=3\n");
    if (run_anyof_exactly_once() != 0) {
        return 1;
    }
    if (run_threshold_exactly_once() != 0) {
        return 1;
    }
    if (run_prune_guard() != 0) {
        return 1;
    }
    if (run_fanout8_regression() != 0) {
        return 1;
    }
    if (run_midgraph_append() != 0) {
        return 1;
    }
    std::printf("SCATTER TB PASSED\n");
#endif
    return 0;
}
