// TB for oe_hls_scatter_banked_stream: fan-in join with simultaneous completions.

#include "orchestration_engine.h"

#include <cstdio>

static ap_uint<8> succ_count[OE_HLS_MAX_NODES];
static oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS];
static oe_hls_node_state_t node_state[OE_HLS_MAX_NODES];

static int setup_fanin_join(void) {
    for (int n = 0; n < OE_HLS_MAX_NODES; ++n) {
        succ_count[n] = 0;
        node_state[n] = 0;
    }

    const int join = 10;
    for (int s = 0; s < 4; ++s) {
        if (oe_hls_append_edge(s, join, succ_count, succ_slots) != 0) {
            return 1;
        }
        node_state[s] = oe_hls_make_node(0, 0, 0);
    }
    node_state[join] = oe_hls_make_node(4, 0, 0);
    return 0;
}

int main() {
    if (setup_fanin_join() != 0) {
        std::printf("FAIL: setup\n");
        return 1;
    }

    hls::stream<oe_hls_node_id_t> completions_in("completions_in");
    hls::stream<oe_hls_node_id_t> ready_out("ready_out");
    for (int s = 0; s < 4; ++s) {
        completions_in.write(s);
    }
    completions_in.write(OE_HLS_STREAM_END);

    oe_hls_cycle_t processed = 0;
    oe_hls_scatter_banked_stream(
        16, succ_count, succ_slots, node_state, completions_in, ready_out, processed);

    int fired = 0;
    int join_fires = 0;
    while (true) {
        const oe_hls_node_id_t id = ready_out.read();
        if (id == oe_hls_node_id_t(OE_HLS_STREAM_END)) {
            break;
        }
        fired++;
        if (id == 10) {
            join_fires++;
        }
    }

    if (processed != 4) {
        std::printf("FAIL: processed %u expected 4\n", (unsigned)processed);
        return 1;
    }
    if (join_fires != 1) {
        std::printf("FAIL: join fired %d times (expected exactly once)\n", join_fires);
        return 1;
    }
    if (fired != 1) {
        std::printf("FAIL: total fired events %d expected 1\n", fired);
        return 1;
    }

    std::printf("banked scatter fan-in: processed=%u join_fires=%d\n",
                (unsigned)processed, join_fires);
    std::printf("TEST PASSED\n");
    return 0;
}
