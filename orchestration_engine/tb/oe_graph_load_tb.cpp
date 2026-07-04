// TB for oe_hls_graph_load: (1) 50-node golden compare, (2) load + scatter e2e.

#include "orchestration_engine.h"

#include "oe_graph_op_word.h"

#include <cstdio>
#include <cstring>

static ap_uint<8> succ_count[OE_HLS_MAX_NODES];
static oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS];
static oe_hls_node_state_t node_state[OE_HLS_MAX_NODES];

static ap_uint<8> gold_succ_count[OE_HLS_MAX_NODES];
static oe_hls_node_id_t gold_succ_slots[OE_HLS_SUCC_SLOTS];
static oe_hls_node_state_t gold_node_state[OE_HLS_MAX_NODES];

static void clear_arrays(void) {
    std::memset(succ_count, 0, sizeof(succ_count));
    std::memset(succ_slots, 0, sizeof(succ_slots));
    std::memset(node_state, 0, sizeof(node_state));
    std::memset(gold_succ_count, 0, sizeof(gold_succ_count));
    std::memset(gold_succ_slots, 0, sizeof(gold_succ_slots));
    std::memset(gold_node_state, 0, sizeof(gold_node_state));
}

static void golden_apply_op(const oe_graph_op *op) {
    switch (op->kind) {
    case OE_OP_APPEND_NODE:
        if (op->node_a < OE_HLS_MAX_NODES) {
            gold_node_state[op->node_a] = oe_hls_make_node(
                0, (oe_hls_fire_t)op->fire_mode, (ap_uint<8>)op->fire_threshold, 0);
        }
        break;
    case OE_OP_APPEND_EDGE:
        if (op->node_a < OE_HLS_MAX_NODES && op->node_b < OE_HLS_MAX_NODES) {
            (void)oe_hls_append_edge(
                op->node_a, op->node_b, gold_succ_count, gold_succ_slots);
            oe_hls_node_state_t st = gold_node_state[op->node_b];
            ap_uint<8> preds = oe_hls_node_preds(st) + 1;
            st.range(7, 0) = preds;
            gold_node_state[op->node_b] = st;
        }
        break;
    case OE_OP_SET_FIRE_MODE:
        if (op->node_a < OE_HLS_MAX_NODES) {
            oe_hls_node_state_t st = gold_node_state[op->node_a];
            st.range(17, 16) = (ap_uint<2>)op->fire_mode;
            st.range(15, 8) = (ap_uint<8>)op->fire_threshold;
            gold_node_state[op->node_a] = st;
        }
        break;
    default:
        break;
    }
}

static int build_react_like_ops(
    oe_graph_op *ops,
    int max_ops,
    int *num_nodes_out,
    int *num_ops_out) {
    int nops = 0;
    const int num_nodes = 50;

    for (int i = 0; i < num_nodes; ++i) {
        oe_graph_op op = {};
        op.kind = OE_OP_APPEND_NODE;
        op.node_a = (oe_node_id_t)i;
        op.node_kind = (i % 5 == 0) ? OE_KIND_COORDINATION : OE_KIND_TOOL;
        op.fire_mode = OE_FIRE_ALL_OF;
        op.fire_threshold = 0;
        op.predicted_latency = (oe_cycle_t)(100 + (i * 17));
        if (nops >= max_ops) {
            return -1;
        }
        ops[nops++] = op;
    }

    for (int i = 0; i < num_nodes - 1; ++i) {
        oe_graph_op op = {};
        op.kind = OE_OP_APPEND_EDGE;
        op.node_a = (oe_node_id_t)i;
        op.node_b = (oe_node_id_t)(i + 1);
        if ((i % 7) == 3) {
            op.node_b = (oe_node_id_t)(i + 2);
        }
        if (nops >= max_ops) {
            return -1;
        }
        ops[nops++] = op;
        if ((i % 11) == 5 && i + 1 < num_nodes - 1) {
            oe_graph_op extra = {};
            extra.kind = OE_OP_APPEND_EDGE;
            extra.node_a = (oe_node_id_t)i;
            extra.node_b = (oe_node_id_t)(i + 1);
            if (nops >= max_ops) {
                return -1;
            }
            ops[nops++] = extra;
        }
    }

    if (num_nodes_out) {
        *num_nodes_out = num_nodes;
    }
    if (num_ops_out) {
        *num_ops_out = nops;
    }
    return 0;
}

static int compare_golden(int num_nodes) {
    for (int n = 0; n < num_nodes; ++n) {
        if (succ_count[n] != gold_succ_count[n]) {
            std::printf("FAIL: succ_count[%d] hw=%u gold=%u\n", n, (unsigned)succ_count[n],
                        (unsigned)gold_succ_count[n]);
            return 1;
        }
        if (node_state[n] != gold_node_state[n]) {
            std::printf("FAIL: node_state[%d] hw=%u gold=%u\n", n, (unsigned)node_state[n],
                        (unsigned)gold_node_state[n]);
            return 1;
        }
        for (int s = 0; s < OE_HLS_SUCC_CAP; ++s) {
            const int idx = n * OE_HLS_SUCC_CAP + s;
            if (succ_slots[idx] != gold_succ_slots[idx]) {
                std::printf(
                    "FAIL: succ_slots[%d] hw=%u gold=%u\n",
                    idx,
                    (unsigned)succ_slots[idx],
                    (unsigned)gold_succ_slots[idx]);
                return 1;
            }
        }
    }
    return 0;
}

static int test_golden_load(void) {
    clear_arrays();
    oe_graph_op ops[256];
    int num_nodes = 0;
    int num_ops = 0;
    if (build_react_like_ops(ops, 256, &num_nodes, &num_ops) != 0) {
        std::printf("FAIL: op build\n");
        return 1;
    }

    for (int i = 0; i < num_ops; ++i) {
        golden_apply_op(&ops[i]);
    }

    hls::stream<oe_graph_op_word_t> ops_in("ops_in");
    for (int i = 0; i < num_ops; ++i) {
        ops_in.write(oe_op_word_pack(&ops[i]));
    }
    ops_in.write(oe_op_word_end());

    oe_hls_node_id_t hw_nodes = 0;
    oe_hls_cycle_t load_cycles = 0;
    ap_uint<32> ops_processed = 0;
    oe_hls_graph_load(
        hw_nodes, succ_count, succ_slots, node_state, ops_in, load_cycles, ops_processed);

    if ((int)hw_nodes != num_nodes) {
        std::printf("FAIL: num_nodes hw=%u expected=%d\n", (unsigned)hw_nodes, num_nodes);
        return 1;
    }
    if ((int)ops_processed != num_ops) {
        std::printf(
            "FAIL: ops_processed hw=%u expected=%d\n",
            (unsigned)ops_processed,
            num_ops);
        return 1;
    }

    std::printf(
        "graph_load golden: nodes=%d ops=%d cycles=%u\n",
        num_nodes,
        num_ops,
        (unsigned)load_cycles);

    return compare_golden(num_nodes);
}

static int test_load_then_scatter(void) {
    clear_arrays();
    oe_graph_op ops[128];
    int num_nodes = 0;
    int num_ops = 0;

    const int chain_nodes = 16;
    int nops = 0;
    for (int i = 0; i < chain_nodes; ++i) {
        oe_graph_op op = {};
        op.kind = OE_OP_APPEND_NODE;
        op.node_a = (oe_node_id_t)i;
        op.fire_mode = OE_FIRE_ALL_OF;
        ops[nops++] = op;
    }
    for (int i = 0; i < chain_nodes - 1; ++i) {
        oe_graph_op op = {};
        op.kind = OE_OP_APPEND_EDGE;
        op.node_a = (oe_node_id_t)i;
        op.node_b = (oe_node_id_t)(i + 1);
        ops[nops++] = op;
    }
    num_nodes = chain_nodes;
    num_ops = nops;

    for (int i = 0; i < num_ops; ++i) {
        golden_apply_op(&ops[i]);
    }

    hls::stream<oe_graph_op_word_t> ops_in("ops_in");
    for (int i = 0; i < num_ops; ++i) {
        ops_in.write(oe_op_word_pack(&ops[i]));
    }
    ops_in.write(oe_op_word_end());

    oe_hls_node_id_t hw_nodes = 0;
    oe_hls_cycle_t load_cycles = 0;
    ap_uint<32> ops_processed = 0;
    oe_hls_graph_load(
        hw_nodes, succ_count, succ_slots, node_state, ops_in, load_cycles, ops_processed);

    if (compare_golden(num_nodes) != 0) {
        return 1;
    }

    hls::stream<oe_hls_node_id_t> completions_in("completions_in");
    hls::stream<oe_hls_node_id_t> ready_out("ready_out");
    completions_in.write(0);
    completions_in.write(OE_HLS_STREAM_END);

    oe_hls_cycle_t processed = 0;
    oe_hls_scatter_stream(
        num_nodes, succ_count, succ_slots, node_state, completions_in, ready_out, processed);

    int hw_fired[OE_HLS_MAX_NODES] = {};
    int n_hw = 0;
    while (true) {
        const oe_hls_node_id_t id = ready_out.read();
        if (id == oe_hls_node_id_t(OE_HLS_STREAM_END)) {
            break;
        }
        hw_fired[n_hw++] = (int)id;
    }

    if (n_hw != 1 || hw_fired[0] != 1) {
        std::printf("FAIL: e2e expected fired node 1 got %d events\n", n_hw);
        return 1;
    }

    std::printf(
        "graph_load e2e: chain=%d load_cycles=%u scatter_processed=%u\n",
        chain_nodes,
        (unsigned)load_cycles,
        (unsigned)processed);
    return 0;
}

int main() {
    if (test_golden_load() != 0) {
        return 1;
    }
    if (test_load_then_scatter() != 0) {
        return 1;
    }
    std::printf("TEST PASSED\n");
    return 0;
}
