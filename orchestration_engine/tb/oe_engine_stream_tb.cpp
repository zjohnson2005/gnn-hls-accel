// TB for oe_hls_engine_stream (C2 DATAFLOW): load a fan-out graph, then stream
// completions. Uses 4 independent fan-out=2 roots (same topology as stream TB).

#include "orchestration_engine.h"

#include "oe_graph_op_word.h"
#include "oe_types.h"

#include <cstdio>

#define OE_ENGINE_TB_TRANSACTIONS 4

static oe_graph_op_word_t pack_append_node(int id) {
    oe_graph_op op = {};
    op.kind = OE_OP_APPEND_NODE;
    op.node_a = (oe_node_id_t)id;
    op.fire_mode = OE_FIRE_ALL_OF;
    return oe_op_word_pack(&op);
}

static oe_graph_op_word_t pack_append_edge(int src, int dst) {
    oe_graph_op op = {};
    op.kind = OE_OP_APPEND_EDGE;
    op.node_a = (oe_node_id_t)src;
    op.node_b = (oe_node_id_t)dst;
    return oe_op_word_pack(&op);
}

int main() {
    hls::stream<oe_graph_op_word_t> ops_in("ops_in");
    hls::stream<oe_hls_node_id_t> completions_in("completions_in");
    hls::stream<oe_hls_node_id_t> ready_out("ready_out");

    for (int t = 0; t < OE_ENGINE_TB_TRANSACTIONS; ++t) {
        const int root = 3 * t;
        ops_in.write(pack_append_node(root));
        ops_in.write(pack_append_node(root + 1));
        ops_in.write(pack_append_node(root + 2));
        ops_in.write(pack_append_edge(root, root + 1));
        ops_in.write(pack_append_edge(root, root + 2));
    }
    ops_in.write(oe_op_word_end());

    for (int t = 0; t < OE_ENGINE_TB_TRANSACTIONS; ++t) {
        completions_in.write(3 * t);
    }
    completions_in.write(OE_HLS_STREAM_END);

    oe_hls_cycle_t load_cycles = 0;
    oe_hls_cycle_t scatter_processed = 0;
    ap_uint<32> ops_processed = 0;
    oe_hls_engine_stream(
        ops_in, completions_in, ready_out, load_cycles, scatter_processed, ops_processed);

    if (scatter_processed != OE_ENGINE_TB_TRANSACTIONS) {
        std::printf(
            "FAIL: expected %d scatter completions got %u\n",
            OE_ENGINE_TB_TRANSACTIONS,
            (unsigned)scatter_processed);
        return 1;
    }

    int fired[OE_HLS_MAX_NODES] = {};
    int n_ready = 0;
    while (true) {
        const oe_hls_node_id_t id = ready_out.read();
        if (id == oe_hls_node_id_t(OE_HLS_STREAM_END)) {
            break;
        }
        fired[id]++;
        n_ready++;
    }

    if (n_ready != 2 * OE_ENGINE_TB_TRANSACTIONS) {
        std::printf(
            "FAIL: expected %d ready events got %d\n",
            2 * OE_ENGINE_TB_TRANSACTIONS,
            n_ready);
        return 1;
    }

    std::printf(
        "ENGINE STREAM TB PASSED: load_cycles=%u ops=%u scatter=%u ready=%d\n",
        (unsigned)load_cycles,
        (unsigned)ops_processed,
        (unsigned)scatter_processed,
        n_ready);
    return 0;
}
