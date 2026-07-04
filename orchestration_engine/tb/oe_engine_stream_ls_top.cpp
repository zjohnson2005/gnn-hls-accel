// LS trace TB: separate top file (LightningSim tutorial pattern).
// OE_LS_LITE top uses plain uint64/uint16/uint32 only (no ap_uint in kernel signature).

#include "orchestration_engine.h"

#include "oe_graph_op_word.h"
#include "oe_types.h"

#include <cstdio>
#include <cstring>

#define OE_ENGINE_TB_TRANSACTIONS 4

static void pack_op_word(oe_graph_op_word_t word, uint64_t out[2]) {
    std::memset(out, 0, sizeof(uint64_t) * 2);
    out[0] = (uint64_t)word.range(63, 0);
    out[1] = (uint64_t)word.range(127, 64);
}

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
    static uint64_t ops_words[OE_LS_ENGINE_MAX_OPS * 2];
    static uint16_t completions_in[OE_HLS_MAX_OUTSTANDING];
    static uint16_t ready_out[OE_HLS_MAX_NODES];
    static uint32_t metrics_out[4];

    uint16_t num_ops = 0;
    for (int t = 0; t < OE_ENGINE_TB_TRANSACTIONS; ++t) {
        const int root = 3 * t;
        pack_op_word(pack_append_node(root), &ops_words[num_ops * 2]);
        num_ops++;
        pack_op_word(pack_append_node(root + 1), &ops_words[num_ops * 2]);
        num_ops++;
        pack_op_word(pack_append_node(root + 2), &ops_words[num_ops * 2]);
        num_ops++;
        pack_op_word(pack_append_edge(root, root + 1), &ops_words[num_ops * 2]);
        num_ops++;
        pack_op_word(pack_append_edge(root, root + 2), &ops_words[num_ops * 2]);
        num_ops++;
    }

    uint16_t num_completions = 0;
    for (int t = 0; t < OE_ENGINE_TB_TRANSACTIONS; ++t) {
        completions_in[num_completions++] = (uint16_t)(3 * t);
    }

    oe_hls_engine_stream(
        ops_words,
        num_ops,
        completions_in,
        num_completions,
        ready_out,
        metrics_out);

    const uint32_t scatter_processed = metrics_out[2];
    const uint32_t num_ready = metrics_out[0];

    if (scatter_processed != (uint32_t)OE_ENGINE_TB_TRANSACTIONS) {
        std::printf(
            "FAIL: expected %d scatter completions got %u\n",
            OE_ENGINE_TB_TRANSACTIONS,
            (unsigned)scatter_processed);
        return 1;
    }

    if (num_ready != (uint32_t)(2 * OE_ENGINE_TB_TRANSACTIONS)) {
        std::printf(
            "FAIL: expected %d ready events got %u\n",
            2 * OE_ENGINE_TB_TRANSACTIONS,
            (unsigned)num_ready);
        return 1;
    }

    std::printf(
        "ENGINE STREAM TB PASSED: load_cycles=%u ops=%u scatter=%u ready=%u\n",
        (unsigned)metrics_out[1],
        (unsigned)metrics_out[3],
        (unsigned)scatter_processed,
        (unsigned)num_ready);
    return 0;
}
