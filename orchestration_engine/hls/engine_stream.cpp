#include "orchestration_engine.h"

// LS C2 top: two DATAFLOW tasks + two internal FIFOs (GCN combine/aggregate shape).
// OE_LS_LITE uses plain uint16/uint32 top ports (GNN_LS_LITE pattern) so LS objcopy
// links the instrumented kernel without SIGSEGV on ap_uint* scalars.

static void oe_ls_feed_inputs(
    const oe_graph_op_word_t ops_in[OE_LS_ENGINE_MAX_OPS],
    const ap_uint<16> num_ops,
    const oe_hls_node_id_t completions_in[OE_HLS_MAX_OUTSTANDING],
    const ap_uint<16> num_completions,
    hls::stream<oe_graph_op_word_t> &ops_s,
    hls::stream<oe_hls_node_id_t> &comp_s) {
#pragma HLS INLINE off
feed_ops:
    for (ap_uint<16> i = 0; i < num_ops; ++i) {
#pragma HLS PIPELINE II = 1
#pragma HLS LOOP_TRIPCOUNT min = 1 max = OE_LS_ENGINE_MAX_OPS
        ops_s.write(ops_in[i]);
    }
    oe_graph_op_word_t end_word = 0;
    end_word.range(7, 0) = OE_HLS_OP_WORD_END;
    ops_s.write(end_word);

feed_comp:
    for (ap_uint<16> i = 0; i < num_completions; ++i) {
#pragma HLS PIPELINE II = 1
#pragma HLS LOOP_TRIPCOUNT min = 1 max = OE_HLS_MAX_OUTSTANDING
        comp_s.write(completions_in[i]);
    }
    comp_s.write(oe_hls_node_id_t(OE_HLS_STREAM_END));
}

static void oe_ls_engine_body(
    hls::stream<oe_graph_op_word_t> &ops_s,
    hls::stream<oe_hls_node_id_t> &comp_s,
    oe_hls_node_id_t ready_out[OE_HLS_MAX_NODES],
    oe_hls_node_id_t &num_ready,
    oe_hls_cycle_t &load_cycles,
    oe_hls_cycle_t &scatter_processed,
    ap_uint<32> &ops_processed) {
#pragma HLS INLINE off
    static oe_hls_node_id_t num_nodes;
    static ap_uint<8> succ_count[OE_HLS_MAX_NODES];
    static oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS];
    static oe_hls_node_state_t node_state[OE_HLS_MAX_NODES];
#pragma HLS BIND_STORAGE variable = succ_count type = RAM_2P impl = BRAM
#pragma HLS BIND_STORAGE variable = node_state type = RAM_2P impl = BRAM
#pragma HLS BIND_STORAGE variable = succ_slots type = RAM_2P impl = BRAM

    hls::stream<oe_hls_node_id_t> ready_s("ready_s");
#pragma HLS STREAM variable = ready_s depth = 8

    load_cycles = 0;
    scatter_processed = 0;
    ops_processed = 0;

    oe_hls_graph_load(
        num_nodes,
        succ_count,
        succ_slots,
        node_state,
        ops_s,
        load_cycles,
        ops_processed);

    oe_hls_scatter_stream(
        num_nodes,
        succ_count,
        succ_slots,
        node_state,
        comp_s,
        ready_s,
        scatter_processed);

    oe_hls_node_id_t n = 0;
sink_ready:
    while (true) {
#pragma HLS PIPELINE II = 1
#pragma HLS LOOP_TRIPCOUNT min = 1 max = OE_HLS_MAX_NODES
        const oe_hls_node_id_t id = ready_s.read();
        if (id == oe_hls_node_id_t(OE_HLS_STREAM_END)) {
            break;
        }
        if (n < oe_hls_node_id_t(OE_HLS_MAX_NODES)) {
            ready_out[n] = id;
            n = n + 1;
        }
    }
    num_ready = n;
}

static void oe_hls_engine_stream_impl(
    const oe_graph_op_word_t ops_in[OE_LS_ENGINE_MAX_OPS],
    const ap_uint<16> num_ops,
    const oe_hls_node_id_t completions_in[OE_HLS_MAX_OUTSTANDING],
    const ap_uint<16> num_completions,
    oe_hls_node_id_t ready_out[OE_HLS_MAX_NODES],
    oe_hls_node_id_t &num_ready,
    oe_hls_cycle_t &load_cycles,
    oe_hls_cycle_t &scatter_processed,
    ap_uint<32> &ops_processed) {
    hls::stream<oe_graph_op_word_t> ops_s("ops_s");
    hls::stream<oe_hls_node_id_t> comp_s("comp_s");
#pragma HLS STREAM variable = ops_s depth = 8
#pragma HLS STREAM variable = comp_s depth = 8

#pragma HLS DATAFLOW
    oe_ls_feed_inputs(ops_in, num_ops, completions_in, num_completions, ops_s, comp_s);
    oe_ls_engine_body(
        ops_s,
        comp_s,
        ready_out,
        num_ready,
        load_cycles,
        scatter_processed,
        ops_processed);
}

#ifdef OE_LS_LITE

static oe_graph_op_word_t oe_ls_word_from_u64(const uint64_t lo, const uint64_t hi) {
#pragma HLS INLINE
    oe_graph_op_word_t w = 0;
    w.range(63, 0) = lo;
    w.range(127, 64) = hi;
    return w;
}

void oe_hls_engine_stream(
    const uint64_t *ops_words,
    uint16_t num_ops,
    const uint16_t *completions_in,
    uint16_t num_completions,
    uint16_t *ready_out,
    uint32_t *metrics_out) {
#pragma HLS INTERFACE mode = ap_memory port = ops_words depth = 1024
#pragma HLS INTERFACE mode = ap_memory port = completions_in depth = 64
#pragma HLS INTERFACE mode = ap_memory port = ready_out depth = 256
#pragma HLS INTERFACE mode = ap_memory port = metrics_out depth = 4
#pragma HLS INTERFACE s_axilite port = num_ops bundle = control
#pragma HLS INTERFACE s_axilite port = num_completions bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

    static oe_graph_op_word_t ops_buf[OE_LS_ENGINE_MAX_OPS];
    static oe_hls_node_id_t comp_buf[OE_HLS_MAX_OUTSTANDING];
    static oe_hls_node_id_t ready_buf[OE_HLS_MAX_NODES];

    const ap_uint<16> nops = num_ops;
    const ap_uint<16> ncomp = num_completions;

copy_ops:
    for (ap_uint<16> i = 0; i < nops; ++i) {
#pragma HLS PIPELINE II = 1
        ops_buf[i] = oe_ls_word_from_u64(ops_words[2 * i], ops_words[2 * i + 1]);
    }
copy_comp:
    for (ap_uint<16> i = 0; i < ncomp; ++i) {
#pragma HLS PIPELINE II = 1
        comp_buf[i] = completions_in[i];
    }

    oe_hls_node_id_t num_ready = 0;
    oe_hls_cycle_t load_cycles = 0;
    oe_hls_cycle_t scatter_processed = 0;
    ap_uint<32> ops_processed = 0;

    oe_hls_engine_stream_impl(
        ops_buf,
        nops,
        comp_buf,
        ncomp,
        ready_buf,
        num_ready,
        load_cycles,
        scatter_processed,
        ops_processed);

export_ready:
    for (ap_uint<16> i = 0; i < num_ready; ++i) {
#pragma HLS PIPELINE II = 1
        ready_out[i] = (uint16_t)ready_buf[i];
    }

    metrics_out[0] = (uint32_t)num_ready;
    metrics_out[1] = (uint32_t)load_cycles;
    metrics_out[2] = (uint32_t)scatter_processed;
    metrics_out[3] = (uint32_t)ops_processed;
}

#else

void oe_hls_engine_stream(
    const oe_graph_op_word_t ops_in[OE_LS_ENGINE_MAX_OPS],
    const ap_uint<16> num_ops,
    const oe_hls_node_id_t completions_in[OE_HLS_MAX_OUTSTANDING],
    const ap_uint<16> num_completions,
    oe_hls_node_id_t ready_out[OE_HLS_MAX_NODES],
    oe_hls_node_id_t *num_ready,
    oe_hls_cycle_t *load_cycles,
    oe_hls_cycle_t *scatter_processed,
    ap_uint<32> *ops_processed) {
#pragma HLS INTERFACE mode = ap_memory port = ops_in depth = 512
#pragma HLS INTERFACE mode = ap_memory port = completions_in depth = 64
#pragma HLS INTERFACE mode = ap_memory port = ready_out depth = 256
#pragma HLS INTERFACE mode = ap_memory port = num_ready depth = 1
#pragma HLS INTERFACE mode = ap_memory port = load_cycles depth = 1
#pragma HLS INTERFACE mode = ap_memory port = scatter_processed depth = 1
#pragma HLS INTERFACE mode = ap_memory port = ops_processed depth = 1
#pragma HLS INTERFACE s_axilite port = num_ops bundle = control
#pragma HLS INTERFACE s_axilite port = num_completions bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

    oe_hls_node_id_t nready = 0;
    oe_hls_cycle_t load = 0;
    oe_hls_cycle_t scatter = 0;
    ap_uint<32> ops = 0;

    oe_hls_engine_stream_impl(
        ops_in,
        num_ops,
        completions_in,
        num_completions,
        ready_out,
        nready,
        load,
        scatter,
        ops);

    *num_ready = nready;
    *load_cycles = load;
    *scatter_processed = scatter;
    *ops_processed = ops;
}

#endif
