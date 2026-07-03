#include "orchestration_engine.h"

static void oe_hls_apply_pred_update(
    const oe_hls_node_id_t succ,
    const oe_hls_node_id_t num_nodes,
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES],
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES],
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES],
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES]) {
#pragma HLS INLINE
    if (succ >= num_nodes) {
        return;
    }

    const oe_hls_fire_t mode = fire_mode[succ];
    if (mode == 1) {
        preds_remaining[succ] = 0;
        ready_flags[succ] = 1;
    } else if (mode == 2) {
        if (preds_remaining[succ] > 0) {
            preds_remaining[succ] = preds_remaining[succ] - 1;
        }
        if (preds_remaining[succ] <= fire_threshold[succ]) {
            preds_remaining[succ] = 0;
            ready_flags[succ] = 1;
        }
    } else {
        if (preds_remaining[succ] > 0) {
            preds_remaining[succ] = preds_remaining[succ] - 1;
        }
        if (preds_remaining[succ] == 0) {
            ready_flags[succ] = 1;
        }
    }
}

void oe_hls_scatter_step(
    const oe_hls_node_id_t completed,
    const oe_hls_node_id_t num_nodes,
    const ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    const oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES],
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES],
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES],
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES]) {
#pragma HLS INLINE off

#pragma HLS ARRAY_PARTITION variable = preds_remaining cyclic factor = 4
#pragma HLS ARRAY_PARTITION variable = ready_flags cyclic factor = 4

scatter_successors:
    for (ap_uint<32> i = row_ptr[completed]; i < row_ptr[completed + 1]; ++i) {
#pragma HLS PIPELINE II = 1
#pragma HLS LOOP_TRIPCOUNT min = 0 max = OE_HLS_MAX_OUT_DEGREE
        oe_hls_apply_pred_update(
            col_idx[i],
            num_nodes,
            preds_remaining,
            fire_mode,
            fire_threshold,
            ready_flags);
    }
}

void oe_hls_scatter_batch(
    const oe_hls_node_id_t completed,
    const oe_hls_node_id_t num_nodes,
    const ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    const oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES],
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES],
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES],
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES]) {
#pragma HLS INLINE off

#pragma HLS ARRAY_PARTITION variable = preds_remaining cyclic factor = OE_HLS_BATCH_WIDTH
#pragma HLS ARRAY_PARTITION variable = ready_flags cyclic factor = OE_HLS_BATCH_WIDTH

    const ap_uint<32> begin = row_ptr[completed];
    const ap_uint<32> end = row_ptr[completed + 1];

batch_successors:
    for (ap_uint<32> base = begin; base < end; base += OE_HLS_BATCH_WIDTH) {
#pragma HLS PIPELINE II = 1
#pragma HLS LOOP_TRIPCOUNT min = 0 max = OE_HLS_MAX_OUT_DEGREE / OE_HLS_BATCH_WIDTH + 1
        for (int b = 0; b < OE_HLS_BATCH_WIDTH; ++b) {
#pragma HLS UNROLL
            const ap_uint<32> idx = base + b;
            if (idx < end) {
                oe_hls_apply_pred_update(
                    col_idx[idx],
                    num_nodes,
                    preds_remaining,
                    fire_mode,
                    fire_threshold,
                    ready_flags);
            }
        }
    }
}

ap_uint<8> oe_hls_append_edge(
    const oe_hls_node_id_t src,
    const oe_hls_node_id_t dst,
    ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<32> &num_edges) {
#pragma HLS INLINE off
    if (num_edges >= OE_HLS_MAX_EDGES) {
        return 1;
    }
    const ap_uint<32> slot = row_ptr[src + 1];
    col_idx[slot] = dst;
    row_ptr[src + 1] = slot + 1;
    num_edges = num_edges + 1;
    return 0;
}

void oe_hls_scatter_kernel(
    const oe_hls_graph_desc &desc,
    const ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    const oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES],
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES],
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t completed,
    const ap_uint<8> use_batch,
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &scatter_cycles) {
#pragma HLS INTERFACE s_axilite port = desc bundle = control
#pragma HLS INTERFACE s_axilite port = completed bundle = control
#pragma HLS INTERFACE s_axilite port = use_batch bundle = control
#pragma HLS INTERFACE s_axilite port = scatter_cycles bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

    if (use_batch) {
        oe_hls_scatter_batch(
            completed,
            desc.num_nodes,
            row_ptr,
            col_idx,
            preds_remaining,
            fire_mode,
            fire_threshold,
            ready_flags);
    } else {
        oe_hls_scatter_step(
            completed,
            desc.num_nodes,
            row_ptr,
            col_idx,
            preds_remaining,
            fire_mode,
            fire_threshold,
            ready_flags);
    }

    const ap_uint<32> out_degree = row_ptr[completed + 1] - row_ptr[completed];
    if (use_batch) {
        scatter_cycles = 1 + (out_degree + OE_HLS_BATCH_WIDTH - 1) / OE_HLS_BATCH_WIDTH;
    } else {
        scatter_cycles = 1 + out_degree;
    }
}

void orchestration_engine(
    const oe_hls_graph_desc &desc,
    const ap_uint<32> row_ptr[OE_HLS_MAX_NODES + 1],
    const oe_hls_node_id_t col_idx[OE_HLS_MAX_EDGES],
    ap_uint<16> preds_remaining[OE_HLS_MAX_NODES],
    ap_uint<8> fire_mode[OE_HLS_MAX_NODES],
    ap_uint<16> fire_threshold[OE_HLS_MAX_NODES],
    ap_uint<8> node_kind[OE_HLS_MAX_NODES],
    oe_hls_cycle_t predicted_latency[OE_HLS_MAX_NODES],
    oe_hls_node_id_t completion_nodes[OE_HLS_MAX_OUTSTANDING],
    oe_hls_cycle_t completion_cycles[OE_HLS_MAX_OUTSTANDING],
    oe_hls_node_id_t num_completions,
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &out_cycles) {
#pragma HLS INTERFACE s_axilite port = desc bundle = control
#pragma HLS INTERFACE s_axilite port = out_cycles bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

#pragma HLS ARRAY_PARTITION variable = preds_remaining cyclic factor = 4
#pragma HLS ARRAY_PARTITION variable = ready_flags cyclic factor = 4

    oe_hls_cycle_t cycle = 0;

init_ready:
    for (oe_hls_node_id_t n = 0; n < OE_HLS_MAX_NODES; ++n) {
#pragma HLS PIPELINE II = 1
        if (n >= desc.num_nodes) {
            continue;
        }
        ready_flags[n] = (preds_remaining[n] == 0) ? 1 : 0;
    }

process_completions:
    for (oe_hls_node_id_t c = 0; c < OE_HLS_MAX_OUTSTANDING; ++c) {
#pragma HLS PIPELINE II = 1
        if (c >= num_completions) {
            break;
        }
        const oe_hls_node_id_t node = completion_nodes[c];
        const oe_hls_cycle_t done_at = completion_cycles[c];
        if (done_at > cycle) {
            cycle = done_at;
        }
        oe_hls_scatter_step(
            node,
            desc.num_nodes,
            row_ptr,
            col_idx,
            preds_remaining,
            fire_mode,
            fire_threshold,
            ready_flags);
    }

    out_cycles = cycle;
}
