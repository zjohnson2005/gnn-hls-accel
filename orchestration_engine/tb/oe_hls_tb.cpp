#include "orchestration_engine.h"

#include <cstdio>

static oe_hls_seg_id_t head_seg[OE_HLS_MAX_NODES];
static oe_hls_seg_id_t tail_seg[OE_HLS_MAX_NODES];
static oe_hls_seg_id_t seg_next[OE_HLS_MAX_SEGS];
static ap_uint<8> seg_count[OE_HLS_MAX_SEGS];
static oe_hls_node_id_t seg_slots[OE_HLS_MAX_SEG_SLOTS];
static oe_hls_node_state_t node_state[OE_HLS_MAX_NODES];
static ap_uint<1> ready_flags[OE_HLS_MAX_NODES];
static ap_uint<32> seg_alloc;

int main() {
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

    // Chain 0 -> 1 -> 2.
    if (oe_hls_append_edge(0, 1, head_seg, tail_seg, seg_next, seg_count,
                           seg_slots, seg_alloc) != 0 ||
        oe_hls_append_edge(1, 2, head_seg, tail_seg, seg_next, seg_count,
                           seg_slots, seg_alloc) != 0) {
        std::printf("FAIL: chain append rejected\n");
        return 1;
    }
    node_state[0] = oe_hls_make_node(0, 0, 0);
    node_state[1] = oe_hls_make_node(1, 0, 0);
    node_state[2] = oe_hls_make_node(1, 0, 0);

    oe_hls_node_id_t completion_nodes[OE_HLS_MAX_OUTSTANDING] = {};
    oe_hls_cycle_t completion_cycles[OE_HLS_MAX_OUTSTANDING] = {};
    completion_nodes[0] = 0;
    completion_cycles[0] = 10;
    completion_nodes[1] = 1;
    completion_cycles[1] = 20;

    oe_hls_cycle_t out_cycles = 0;
    orchestration_engine(
        3, head_seg, seg_next, seg_count, seg_slots, node_state,
        completion_nodes, completion_cycles, 2, ready_flags, out_cycles);

    if (ready_flags[2] != 1) {
        std::printf("FAIL: node 2 not ready after chain completions\n");
        return 1;
    }
    if (out_cycles != 20) {
        std::printf("FAIL: expected out_cycles=20 got %u\n", (unsigned)out_cycles);
        return 1;
    }

    // Runtime mid-graph append to node 1 (node 2's list must stay intact —
    // this exact pattern corrupted the old CSR tail-append).
    if (oe_hls_append_edge(1, 2, head_seg, tail_seg, seg_next, seg_count,
                           seg_slots, seg_alloc) != 0) {
        std::printf("FAIL: append_edge rejected\n");
        return 1;
    }

    // Node 2 already fired via the chain; batch scatter must NOT re-fire it.
    ready_flags[2] = 0;
    oe_hls_cycle_t scatter_cycles = 0;
    oe_hls_scatter_kernel(
        3, head_seg, seg_next, seg_count, seg_slots, node_state,
        1, 1, ready_flags, scatter_cycles);
    if (ready_flags[2] != 0) {
        std::printf("FAIL: fired node re-fired after runtime append\n");
        return 1;
    }

    std::printf(
        "HLS TB PASSED out_cycles=%u scatter_cycles=%u segs_used=%u\n",
        (unsigned)out_cycles,
        (unsigned)scatter_cycles,
        (unsigned)seg_alloc);
    return 0;
}
