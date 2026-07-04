#include "orchestration_engine.h"

// LS C2 top: graph_load then scatter_stream in one ap_ctrl_hs invocation.
// Sequential (not inter-task DATAFLOW): shared BRAM graph state cannot be read
// from two DATAFLOW processes (HLS 200-968). Axis streams on ops/completions/
// ready are still traced by LightningSim for FIFO DSE.

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

    oe_hls_graph_load(
        num_nodes,
        succ_count,
        succ_slots,
        node_state,
        ops_in,
        load_cycles,
        ops_processed);

    oe_hls_scatter_stream(
        num_nodes,
        succ_count,
        succ_slots,
        node_state,
        completions_in,
        ready_out,
        scatter_processed);
}
