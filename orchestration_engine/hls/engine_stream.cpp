#include "orchestration_engine.h"

// DATAFLOW top for LightningSim (C2): session graph load then streaming scatter.
// load_done synchronizes so scatter never reads graph state before load finishes.

static void oe_hls_engine_load_stage(
    hls::stream<oe_graph_op_word_t> &ops_in,
    hls::stream<ap_uint<1>> &load_done,
    oe_hls_node_id_t &num_nodes,
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &load_cycles,
    ap_uint<32> &ops_processed) {
#pragma HLS INLINE off
    oe_hls_graph_load(
        num_nodes,
        succ_count,
        succ_slots,
        node_state,
        ops_in,
        load_cycles,
        ops_processed);
    load_done.write(1);
}

static void oe_hls_engine_scatter_stage(
    hls::stream<ap_uint<1>> &load_done,
    hls::stream<oe_hls_node_id_t> &completions_in,
    hls::stream<oe_hls_node_id_t> &ready_out,
    oe_hls_node_id_t &num_nodes,
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &scatter_processed) {
#pragma HLS INLINE off
    (void)load_done.read();
    oe_hls_scatter_stream(
        num_nodes,
        succ_count,
        succ_slots,
        node_state,
        completions_in,
        ready_out,
        scatter_processed);
}

void oe_hls_engine_stream(
    hls::stream<oe_graph_op_word_t> &ops_in,
    hls::stream<oe_hls_node_id_t> &completions_in,
    hls::stream<oe_hls_node_id_t> &ready_out,
    oe_hls_cycle_t &load_cycles,
    oe_hls_cycle_t &scatter_processed,
    ap_uint<32> &ops_processed) {
#pragma HLS INTERFACE axis port = ops_in
#pragma HLS INTERFACE axis port = completions_in
#pragma HLS INTERFACE axis port = ready_out
#pragma HLS INTERFACE s_axilite port = load_cycles bundle = control
#pragma HLS INTERFACE s_axilite port = scatter_processed bundle = control
#pragma HLS INTERFACE s_axilite port = ops_processed bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

    static oe_hls_node_id_t num_nodes;
    static ap_uint<8> succ_count[OE_HLS_MAX_NODES];
    static oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS];
    static oe_hls_node_state_t node_state[OE_HLS_MAX_NODES];
#pragma HLS BIND_STORAGE variable = succ_count type = RAM_2P impl = BRAM
#pragma HLS BIND_STORAGE variable = node_state type = RAM_2P impl = BRAM
#pragma HLS BIND_STORAGE variable = succ_slots type = RAM_2P impl = BRAM

    hls::stream<ap_uint<1>> load_done("load_done");
#pragma HLS STREAM variable = load_done depth = 2

#pragma HLS DATAFLOW
    oe_hls_engine_load_stage(
        ops_in,
        load_done,
        num_nodes,
        succ_count,
        succ_slots,
        node_state,
        load_cycles,
        ops_processed);
    oe_hls_engine_scatter_stage(
        load_done,
        completions_in,
        ready_out,
        num_nodes,
        succ_count,
        succ_slots,
        node_state,
        scatter_processed);
}
