// TB for oe_hls_scatter_stream: 8 completions in one invocation.
// Cosim latency / 8 = measured steady-state cycles per completion (II),
// amortizing the ap_ctrl_hs handshake that dominates the one-shot number.

#include "orchestration_engine.h"

#include <cstdio>

#define OE_STREAM_TB_TRANSACTIONS 8

static ap_uint<8> succ_count[OE_HLS_MAX_NODES];
static oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS];
static oe_hls_node_state_t node_state[OE_HLS_MAX_NODES];

int main() {
    for (int n = 0; n < OE_HLS_MAX_NODES; ++n) {
        succ_count[n] = 0;
        node_state[n] = 0;
    }

    // 8 independent fan-out=2 scatters: root r=3t -> {3t+1, 3t+2}.
    // Successors of one root land in distinct banks (3t+1, 3t+2 differ mod 8).
    const int num_nodes = 3 * OE_STREAM_TB_TRANSACTIONS;
    for (int t = 0; t < OE_STREAM_TB_TRANSACTIONS; ++t) {
        const int root = 3 * t;
        if (oe_hls_append_edge(root, root + 1, succ_count, succ_slots) != 0 ||
            oe_hls_append_edge(root, root + 2, succ_count, succ_slots) != 0) {
            std::printf("FAIL: append rejected for root %d\n", root);
            return 1;
        }
        node_state[root] = oe_hls_make_node(0, 0, 0);
        node_state[root + 1] = oe_hls_make_node(1, 0, 0);
        node_state[root + 2] = oe_hls_make_node(1, 0, 0);
    }

    hls::stream<oe_hls_node_id_t> completions_in("completions_in");
    hls::stream<oe_hls_node_id_t> ready_out("ready_out");
    for (int t = 0; t < OE_STREAM_TB_TRANSACTIONS; ++t) {
        completions_in.write(3 * t);
    }
    completions_in.write(OE_HLS_STREAM_END);

    oe_hls_cycle_t processed = 0;
    oe_hls_scatter_stream(
        num_nodes, succ_count, succ_slots, node_state, completions_in, ready_out,
        processed);

    if (processed != OE_STREAM_TB_TRANSACTIONS) {
        std::printf(
            "FAIL: expected %d completions processed got %u\n",
            OE_STREAM_TB_TRANSACTIONS,
            (unsigned)processed);
        return 1;
    }

    // Expect exactly 2 ready events per completion, then the sentinel.
    int fired[OE_HLS_MAX_NODES] = {};
    int n_ready = 0;
    while (true) {
        if (ready_out.empty()) {
            std::printf("FAIL: ready_out ended without sentinel\n");
            return 1;
        }
        const oe_hls_node_id_t id = ready_out.read();
        if (id == oe_hls_node_id_t(OE_HLS_STREAM_END)) {
            break;
        }
        fired[id]++;
        n_ready++;
    }

    if (n_ready != 2 * OE_STREAM_TB_TRANSACTIONS) {
        std::printf(
            "FAIL: expected %d ready events got %d\n",
            2 * OE_STREAM_TB_TRANSACTIONS,
            n_ready);
        return 1;
    }
    for (int t = 0; t < OE_STREAM_TB_TRANSACTIONS; ++t) {
        if (fired[3 * t + 1] != 1 || fired[3 * t + 2] != 1) {
            std::printf("FAIL: successors of root %d not fired exactly once\n", 3 * t);
            return 1;
        }
    }

    std::printf(
        "STREAM TB PASSED: %d completions, %d ready events "
        "(cosim latency / %d = steady-state cycles per completion)\n",
        OE_STREAM_TB_TRANSACTIONS,
        n_ready,
        OE_STREAM_TB_TRANSACTIONS);
    return 0;
}
