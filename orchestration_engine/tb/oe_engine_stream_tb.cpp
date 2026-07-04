// TB for oe_hls_engine_stream (C2): load a fan-out graph, then stream
// completions. Uses 4 independent fan-out=2 roots (same topology as stream TB).
// Array ports (not stream ports): LightningSim traces the INTERNAL FIFOs.

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
    static oe_graph_op_word_t ops_in[OE_LS_ENGINE_MAX_OPS];
    static oe_hls_node_id_t completions_in[OE_HLS_MAX_OUTSTANDING];
    static oe_hls_node_id_t ready_out[OE_HLS_MAX_NODES];

    ap_uint<16> num_ops = 0;
    for (int t = 0; t < OE_ENGINE_TB_TRANSACTIONS; ++t) {
        const int root = 3 * t;
        ops_in[num_ops++] = pack_append_node(root);
        ops_in[num_ops++] = pack_append_node(root + 1);
        ops_in[num_ops++] = pack_append_node(root + 2);
        ops_in[num_ops++] = pack_append_edge(root, root + 1);
        ops_in[num_ops++] = pack_append_edge(root, root + 2);
    }

    ap_uint<16> num_completions = 0;
    for (int t = 0; t < OE_ENGINE_TB_TRANSACTIONS; ++t) {
        completions_in[num_completions++] = 3 * t;
    }

    oe_hls_node_id_t num_ready = 0;
    oe_hls_cycle_t load_cycles = 0;
    oe_hls_cycle_t scatter_processed = 0;
    ap_uint<32> ops_processed = 0;

    oe_hls_engine_stream(
        ops_in,
        num_ops,
        completions_in,
        num_completions,
        ready_out,
        &num_ready,
        &load_cycles,
        &scatter_processed,
        &ops_processed);

    if (scatter_processed != OE_ENGINE_TB_TRANSACTIONS) {
        std::printf(
            "FAIL: expected %d scatter completions got %u\n",
            OE_ENGINE_TB_TRANSACTIONS,
            (unsigned)scatter_processed);
        return 1;
    }

    if (num_ready != 2 * OE_ENGINE_TB_TRANSACTIONS) {
        std::printf(
            "FAIL: expected %d ready events got %u\n",
            2 * OE_ENGINE_TB_TRANSACTIONS,
            (unsigned)num_ready);
        return 1;
    }

    int fired[OE_HLS_MAX_NODES] = {};
    for (int i = 0; i < (int)num_ready; ++i) {
        fired[ready_out[i]]++;
    }
    for (int t = 0; t < OE_ENGINE_TB_TRANSACTIONS; ++t) {
        const int root = 3 * t;
        if (fired[root + 1] != 1 || fired[root + 2] != 1) {
            std::printf("FAIL: successors of root %d did not fire exactly once\n", root);
            return 1;
        }
    }

    std::printf(
        "ENGINE STREAM TB PASSED: load_cycles=%u ops=%u scatter=%u ready=%u\n",
        (unsigned)load_cycles,
        (unsigned)ops_processed,
        (unsigned)scatter_processed,
        (unsigned)num_ready);
    return 0;
}
