#include "orchestration_engine.h"

// ---------------------------------------------------------------------------
// Session graph load from a packed op stream (II=1 goal per op word).
// Writes succ_count, succ_slots, and node_state in the layout scatter reads.
// ---------------------------------------------------------------------------

static void oe_hls_clear_graph(
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES]) {
#pragma HLS INLINE off
clear_nodes:
    for (oe_hls_node_id_t n = 0; n < OE_HLS_MAX_NODES; ++n) {
#pragma HLS PIPELINE II = 1
        succ_count[n] = 0;
        node_state[n] = 0;
    }
clear_slots:
    for (ap_uint<32> i = 0; i < OE_HLS_SUCC_SLOTS; ++i) {
#pragma HLS PIPELINE II = 1
        succ_slots[i] = 0;
    }
}

static void oe_hls_init_free_list(
    oe_hls_node_id_t free_stack[OE_HLS_MAX_NODES],
    ap_uint<16> &free_top) {
#pragma HLS INLINE off
init_free:
    for (oe_hls_node_id_t i = 0; i < OE_HLS_MAX_NODES; ++i) {
#pragma HLS PIPELINE II = 1
        free_stack[i] = OE_HLS_MAX_NODES - 1 - i;
    }
    free_top = OE_HLS_MAX_NODES;
}

static ap_uint<1> oe_hls_free_pop(
    oe_hls_node_id_t free_stack[OE_HLS_MAX_NODES],
    ap_uint<16> &free_top,
    oe_hls_node_id_t &id_out) {
#pragma HLS INLINE
    if (free_top == 0) {
        return 1;
    }
    free_top = free_top - 1;
    id_out = free_stack[free_top];
    return 0;
}

static void oe_hls_apply_append_node(
    const oe_graph_op_word_t word,
    oe_hls_node_id_t &num_nodes,
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    oe_hls_node_id_t free_stack[OE_HLS_MAX_NODES],
    ap_uint<16> &free_top) {
#pragma HLS INLINE off
    oe_hls_node_id_t popped = 0;
    (void)oe_hls_free_pop(free_stack, free_top, popped);

    const oe_hls_node_id_t id = word.range(23, 8);
    const oe_hls_fire_t mode = word.range(49, 48);
    const ap_uint<8> thr = word.range(65, 50);

    if (id >= OE_HLS_MAX_NODES) {
        return;
    }
    node_state[id] = oe_hls_make_node(0, mode, thr, 0);
    if (id + 1 > num_nodes) {
        num_nodes = id + 1;
    }
}

static void oe_hls_apply_append_edge(
    const oe_graph_op_word_t word,
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    oe_hls_node_id_t &fwd_src,
    ap_uint<8> &fwd_cnt,
    ap_uint<1> &has_fwd) {
#pragma HLS INLINE off
    const oe_hls_node_id_t src = word.range(23, 8);
    const oe_hls_node_id_t dst = word.range(39, 24);

    ap_uint<8> cnt = succ_count[src];
    if (has_fwd && fwd_src == src) {
        cnt = fwd_cnt;
    }

    if (cnt < OE_HLS_SUCC_CAP && dst < OE_HLS_MAX_NODES) {
        succ_slots[src * OE_HLS_SUCC_CAP + cnt] = dst;
        succ_count[src] = cnt + 1;
        fwd_src = src;
        fwd_cnt = cnt + 1;
        has_fwd = 1;

        oe_hls_node_state_t st = node_state[dst];
        ap_uint<8> preds = oe_hls_node_preds(st) + 1;
        st.range(7, 0) = preds;
        node_state[dst] = st;
    }
}

static void oe_hls_apply_set_fire_mode(
    const oe_graph_op_word_t word,
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES]) {
#pragma HLS INLINE off
    const oe_hls_node_id_t id = word.range(23, 8);
    if (id >= OE_HLS_MAX_NODES) {
        return;
    }
    oe_hls_node_state_t st = node_state[id];
    st.range(17, 16) = word.range(49, 48);
    st.range(15, 8) = word.range(65, 50);
    node_state[id] = st;
}

static oe_hls_cycle_t oe_hls_load_one_session(
    hls::stream<oe_graph_op_word_t> &ops_in,
    oe_hls_node_id_t &num_nodes,
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    oe_hls_node_id_t free_stack[OE_HLS_MAX_NODES],
    ap_uint<16> &free_top,
    ap_uint<32> &ops_processed) {
#pragma HLS INLINE off
    oe_hls_clear_graph(succ_count, succ_slots, node_state);
    oe_hls_init_free_list(free_stack, free_top);
    num_nodes = 0;
    ops_processed = 0;

    oe_hls_node_id_t fwd_src = 0;
    ap_uint<8> fwd_cnt = 0;
    ap_uint<1> has_fwd = 0;
    oe_hls_cycle_t cycles = 0;

op_loop:
    while (true) {
#pragma HLS LOOP_TRIPCOUNT min = 1 max = 512
        const oe_graph_op_word_t word = ops_in.read();
        const ap_uint<8> kind = word.range(7, 0);
        if (kind == OE_HLS_OP_WORD_END) {
            cycles = cycles + 1;
            break;
        }

        if (kind == OE_HLS_OP_APPEND_NODE) {
            oe_hls_apply_append_node(
                word, num_nodes, node_state, free_stack, free_top);
        } else if (kind == OE_HLS_OP_APPEND_EDGE) {
            oe_hls_apply_append_edge(
                word, succ_count, succ_slots, node_state, fwd_src, fwd_cnt, has_fwd);
        } else if (kind == OE_HLS_OP_SET_FIRE_MODE) {
            oe_hls_apply_set_fire_mode(word, node_state);
        }
        ops_processed = ops_processed + 1;
        cycles = cycles + 1;
    }

    return cycles;
}

void oe_hls_graph_load(
    oe_hls_node_id_t &num_nodes,
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    hls::stream<oe_graph_op_word_t> &ops_in,
    oe_hls_cycle_t &load_cycles,
    ap_uint<32> &ops_processed) {
#pragma HLS INTERFACE axis port = ops_in
#pragma HLS INTERFACE s_axilite port = num_nodes bundle = control
#pragma HLS INTERFACE s_axilite port = load_cycles bundle = control
#pragma HLS INTERFACE s_axilite port = ops_processed bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

    static oe_hls_node_id_t free_stack[OE_HLS_MAX_NODES];
    ap_uint<16> free_top = 0;

    load_cycles = oe_hls_load_one_session(
        ops_in,
        num_nodes,
        succ_count,
        succ_slots,
        node_state,
        free_stack,
        free_top,
        ops_processed);
}

// Batched sessions: multiple graphs back-to-back in one invocation (handshake
// amortization). Each session ends with OE_OP_WORD_END; total cycles summed.
void oe_hls_graph_load_batch(
    const oe_hls_node_id_t num_sessions,
    oe_hls_node_id_t &num_nodes,
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    hls::stream<oe_graph_op_word_t> &ops_in,
    oe_hls_cycle_t &load_cycles,
    oe_hls_cycle_t &sessions_loaded,
    ap_uint<32> &ops_processed) {
#pragma HLS INTERFACE axis port = ops_in
#pragma HLS INTERFACE s_axilite port = num_sessions bundle = control
#pragma HLS INTERFACE s_axilite port = num_nodes bundle = control
#pragma HLS INTERFACE s_axilite port = load_cycles bundle = control
#pragma HLS INTERFACE s_axilite port = sessions_loaded bundle = control
#pragma HLS INTERFACE s_axilite port = ops_processed bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

    static oe_hls_node_id_t free_stack[OE_HLS_MAX_NODES];
    ap_uint<16> free_top = 0;

    load_cycles = 0;
    sessions_loaded = 0;
    ops_processed = 0;

session_loop:
    for (oe_hls_node_id_t s = 0; s < num_sessions; ++s) {
#pragma HLS LOOP_TRIPCOUNT min = 1 max = 8
        ap_uint<32> sess_ops = 0;
        const oe_hls_cycle_t c = oe_hls_load_one_session(
            ops_in,
            num_nodes,
            succ_count,
            succ_slots,
            node_state,
            free_stack,
            free_top,
            sess_ops);
        load_cycles = load_cycles + c;
        ops_processed = ops_processed + sess_ops;
        sessions_loaded = sessions_loaded + 1;
    }
}
