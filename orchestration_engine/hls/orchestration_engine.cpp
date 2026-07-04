#include "orchestration_engine.h"

// ---------------------------------------------------------------------------
// Fixed-row append (host/graph-load path; O(1), append-safe mid-graph).
// ---------------------------------------------------------------------------
ap_uint<8> oe_hls_append_edge(
    const oe_hls_node_id_t src,
    const oe_hls_node_id_t dst,
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS]) {
#pragma HLS INLINE off
    const ap_uint<8> cnt = succ_count[src];
    if (cnt >= OE_HLS_SUCC_CAP) {
        return 1; // row full
    }
    succ_slots[src * OE_HLS_SUCC_CAP + cnt] = dst;
    succ_count[src] = cnt + 1;
    return 0;
}

// ---------------------------------------------------------------------------
// Flat scatter walk: II=1 per successor slot.
// INVARIANT: successors within one row are unique (edges are unique
// (src, dst) pairs; oe_hls_append_edge is the only writer). Consecutive
// iterations therefore never touch the same node_state word, so the
// loop-carried RMW dependence is declared false — without it the scheduler
// forces read+decode+decrement+writeback into one cycle and Fmax collapses
// (measured 415 -> 210 MHz).
// ---------------------------------------------------------------------------
static void oe_hls_walk_flat(
    const oe_hls_node_id_t completed,
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES]) {
#pragma HLS INLINE off
    const ap_uint<8> cnt = succ_count[completed];
    const ap_uint<32> base = completed * OE_HLS_SUCC_CAP;

walk_slots:
    for (ap_uint<8> i = 0; i < cnt; ++i) {
#pragma HLS PIPELINE II = 1
#pragma HLS DEPENDENCE variable = node_state inter false
#pragma HLS LOOP_TRIPCOUNT min = 0 max = OE_HLS_SUCC_CAP
        const oe_hls_node_id_t succ = succ_slots[base + i];
        if (succ < num_nodes) {
            oe_hls_node_state_t st = node_state[succ];
            if (oe_hls_node_update(st)) {
                ready_flags[succ] = 1;
            }
            node_state[succ] = st;
        }
    }
}

// ---------------------------------------------------------------------------
// Batch scatter walk: whole row (OE_HLS_SUCC_CAP successors) in one cycle.
// Contiguous row indices hit cyclic banks 0..CAP-1 exactly once for
// succ_slots; node_state banking needs bank-distinct successors within a
// row for full parallelism (host load ordering).
// ---------------------------------------------------------------------------
static void oe_hls_walk_batch(
    const oe_hls_node_id_t completed,
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES]) {
#pragma HLS INLINE off
    const ap_uint<8> cnt = succ_count[completed];
    const ap_uint<32> base = completed * OE_HLS_SUCC_CAP;

batch_slots:
    for (int b = 0; b < OE_HLS_SUCC_CAP; ++b) {
#pragma HLS UNROLL
        if (b < cnt) {
            const oe_hls_node_id_t succ = succ_slots[base + b];
            if (succ < num_nodes) {
                oe_hls_node_state_t st = node_state[succ];
                if (oe_hls_node_update(st)) {
                    ready_flags[succ] = 1;
                }
                node_state[succ] = st;
            }
        }
    }
}

// ---------------------------------------------------------------------------
// One-shot flat csynth/cosim anchor. No partitions: one RMW per cycle fits
// dual-port BRAM; partitions only add crossbar muxing to the clock path.
// ---------------------------------------------------------------------------
void oe_hls_scatter_kernel(
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t completed,
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &scatter_cycles) {
#pragma HLS INTERFACE s_axilite port = num_nodes bundle = control
#pragma HLS INTERFACE s_axilite port = completed bundle = control
#pragma HLS INTERFACE s_axilite port = scatter_cycles bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

    const ap_uint<8> cnt = succ_count[completed];
    oe_hls_walk_flat(
        completed, num_nodes, succ_count, succ_slots, node_state, ready_flags);
    scatter_cycles = 1 + cnt; // 1 + out_degree
}

// ---------------------------------------------------------------------------
// One-shot batch kernel (separate top; carries the 8-bank crossbar).
// ---------------------------------------------------------------------------
void oe_hls_scatter_batch_kernel(
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t completed,
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &scatter_cycles) {
#pragma HLS INTERFACE s_axilite port = num_nodes bundle = control
#pragma HLS INTERFACE s_axilite port = completed bundle = control
#pragma HLS INTERFACE s_axilite port = scatter_cycles bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

#pragma HLS ARRAY_PARTITION variable = node_state cyclic factor = 8
#pragma HLS ARRAY_PARTITION variable = ready_flags cyclic factor = 8
#pragma HLS ARRAY_PARTITION variable = succ_slots cyclic factor = 8

    const ap_uint<8> cnt = succ_count[completed];
    oe_hls_walk_batch(
        completed, num_nodes, succ_count, succ_slots, node_state, ready_flags);
    // 1 + ceil(out_degree / CAP): whole row updates in one wide cycle.
    scatter_cycles = 1 + ((cnt + OE_HLS_SUCC_CAP - 1) / OE_HLS_SUCC_CAP);
}

// ---------------------------------------------------------------------------
// Streaming steady-state kernel: batch of completions in one invocation,
// compact ready-event output (no O(N) host flag scan).
// ---------------------------------------------------------------------------
void oe_hls_scatter_stream(
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    hls::stream<oe_hls_node_id_t> &completions_in,
    hls::stream<oe_hls_node_id_t> &ready_out,
    oe_hls_cycle_t &completions_processed) {
#ifndef OE_LS_INTERNAL
#pragma HLS INTERFACE axis port = completions_in
#pragma HLS INTERFACE axis port = ready_out
#pragma HLS INTERFACE s_axilite port = num_nodes bundle = control
#pragma HLS INTERFACE s_axilite port = completions_processed bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control
#endif

    // Flat walk: one RMW per cycle -> dual-port BRAM, no partitions needed.
    oe_hls_cycle_t processed = 0;

event_loop:
    while (true) {
#pragma HLS LOOP_TRIPCOUNT min = 1 max = OE_HLS_MAX_OUTSTANDING
        const oe_hls_node_id_t completed = completions_in.read();
        if (completed == oe_hls_node_id_t(OE_HLS_STREAM_END)) {
            break;
        }
        if (completed < num_nodes) {
            const ap_uint<8> cnt = succ_count[completed];
            const ap_uint<32> base = completed * OE_HLS_SUCC_CAP;

        stream_slots:
            for (ap_uint<8> i = 0; i < cnt; ++i) {
#pragma HLS PIPELINE II = 1
#pragma HLS DEPENDENCE variable = node_state inter false
#pragma HLS LOOP_TRIPCOUNT min = 0 max = OE_HLS_SUCC_CAP
                const oe_hls_node_id_t succ = succ_slots[base + i];
                if (succ < num_nodes) {
                    oe_hls_node_state_t st = node_state[succ];
                    if (oe_hls_node_update(st)) {
                        ready_out.write(succ);
                    }
                    node_state[succ] = st;
                }
            }
        }
        processed = processed + 1;
    }

    ready_out.write(oe_hls_node_id_t(OE_HLS_STREAM_END));
    completions_processed = processed;
}

// ---------------------------------------------------------------------------
// Epoch-level engine (init ready + completion batch).
// ---------------------------------------------------------------------------
void orchestration_engine(
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t completion_nodes[OE_HLS_MAX_OUTSTANDING],
    const oe_hls_cycle_t completion_cycles[OE_HLS_MAX_OUTSTANDING],
    const oe_hls_node_id_t num_completions,
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &out_cycles) {
#pragma HLS INTERFACE s_axilite port = num_nodes bundle = control
#pragma HLS INTERFACE s_axilite port = num_completions bundle = control
#pragma HLS INTERFACE s_axilite port = out_cycles bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

    oe_hls_cycle_t cycle = 0;

init_ready:
    for (oe_hls_node_id_t n = 0; n < OE_HLS_MAX_NODES; ++n) {
#pragma HLS PIPELINE II = 1
        if (n >= num_nodes) {
            continue;
        }
        const oe_hls_node_state_t st = node_state[n];
        ready_flags[n] =
            (!oe_hls_node_fired(st) && !oe_hls_node_pruned(st) &&
             oe_hls_node_preds(st) == 0)
                ? 1
                : 0;
    }

// No PIPELINE here: the scatter walk has variable bounds and cannot be
// unrolled into a pipelined parent.
process_completions:
    for (oe_hls_node_id_t c = 0; c < OE_HLS_MAX_OUTSTANDING; ++c) {
        if (c >= num_completions) {
            break;
        }
        const oe_hls_node_id_t node = completion_nodes[c];
        const oe_hls_cycle_t done_at = completion_cycles[c];
        if (done_at > cycle) {
            cycle = done_at;
        }
        oe_hls_walk_flat(
            node, num_nodes, succ_count, succ_slots, node_state, ready_flags);
    }

    out_cycles = cycle;
}

// ---------------------------------------------------------------------------
// Banked scatter: cyclic partition on node_state; up to OE_HLS_SCATTER_BANKS
// completions read per outer iteration with per-lane slot walks.
// ---------------------------------------------------------------------------
static void oe_hls_banked_walk_lane(
    const oe_hls_node_id_t completed,
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    hls::stream<oe_hls_node_id_t> &ready_out) {
#pragma HLS INLINE off
    if (completed >= num_nodes) {
        return;
    }
    const ap_uint<8> cnt = succ_count[completed];
    const ap_uint<32> base = completed * OE_HLS_SUCC_CAP;

banked_slots:
    for (ap_uint<8> i = 0; i < cnt; ++i) {
#pragma HLS PIPELINE II = 1
#pragma HLS DEPENDENCE variable = node_state inter false
#pragma HLS LOOP_TRIPCOUNT min = 0 max = OE_HLS_SUCC_CAP
        const oe_hls_node_id_t succ = succ_slots[base + i];
        if (succ < num_nodes) {
            oe_hls_node_state_t st = node_state[succ];
            if (oe_hls_node_update(st)) {
                ready_out.write(succ);
            }
            node_state[succ] = st;
        }
    }
}

void oe_hls_scatter_banked_stream(
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    hls::stream<oe_hls_node_id_t> &completions_in,
    hls::stream<oe_hls_node_id_t> &ready_out,
    oe_hls_cycle_t &completions_processed) {
#ifndef OE_LS_INTERNAL
#pragma HLS INTERFACE axis port = completions_in
#pragma HLS INTERFACE axis port = ready_out
#pragma HLS INTERFACE s_axilite port = num_nodes bundle = control
#pragma HLS INTERFACE s_axilite port = completions_processed bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control
#endif

#pragma HLS ARRAY_PARTITION variable = node_state cyclic factor = OE_HLS_SCATTER_BANKS

    oe_hls_cycle_t processed = 0;
    ap_uint<1> saw_end = 0;

bank_event_loop:
    while (true) {
#pragma HLS LOOP_TRIPCOUNT min = 1 max = OE_HLS_MAX_OUTSTANDING
        oe_hls_node_id_t batch[OE_HLS_SCATTER_BANKS];
#pragma HLS ARRAY_PARTITION variable = batch complete
        ap_uint<4> batch_count = 0;

        for (int b = 0; b < OE_HLS_SCATTER_BANKS; ++b) {
#pragma HLS UNROLL
            batch[b] = 0;
        }

    read_batch:
        while (batch_count < OE_HLS_SCATTER_BANKS) {
#pragma HLS PIPELINE II = 1
            const oe_hls_node_id_t c = completions_in.read();
            if (c == oe_hls_node_id_t(OE_HLS_STREAM_END)) {
                saw_end = 1;
                break;
            }
            batch[batch_count] = c;
            batch_count = batch_count + 1;
        }

        if (batch_count == 0) {
            ready_out.write(oe_hls_node_id_t(OE_HLS_STREAM_END));
            completions_processed = processed;
            return;
        }

        for (int b = 0; b < OE_HLS_SCATTER_BANKS; ++b) {
#pragma HLS PIPELINE II = 1
            if (b < batch_count) {
                oe_hls_banked_walk_lane(
                    batch[b],
                    num_nodes,
                    succ_count,
                    succ_slots,
                    node_state,
                    ready_out);
                processed = processed + 1;
            }
        }

        if (saw_end) {
            ready_out.write(oe_hls_node_id_t(OE_HLS_STREAM_END));
            completions_processed = processed;
            return;
        }
    }
}
