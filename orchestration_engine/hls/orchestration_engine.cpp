#include "orchestration_engine.h"

// ---------------------------------------------------------------------------
// Segmented pool append (host/graph-load path; O(1), append-safe mid-graph).
// ---------------------------------------------------------------------------
ap_uint<8> oe_hls_append_edge(
    const oe_hls_node_id_t src,
    const oe_hls_node_id_t dst,
    oe_hls_seg_id_t head_seg[OE_HLS_MAX_NODES],
    oe_hls_seg_id_t tail_seg[OE_HLS_MAX_NODES],
    oe_hls_seg_id_t seg_next[OE_HLS_MAX_SEGS],
    ap_uint<8> seg_count[OE_HLS_MAX_SEGS],
    oe_hls_node_id_t seg_slots[OE_HLS_MAX_SEG_SLOTS],
    ap_uint<32> &seg_alloc) {
#pragma HLS INLINE off
    oe_hls_seg_id_t tail = tail_seg[src];
    const bool need_seg =
        (tail == oe_hls_seg_id_t(OE_HLS_NULL_SEG)) ||
        (seg_count[tail] >= OE_HLS_SEG_WIDTH);

    if (need_seg) {
        if (seg_alloc >= OE_HLS_MAX_SEGS) {
            return 1; // pool full
        }
        const oe_hls_seg_id_t fresh = seg_alloc;
        seg_alloc = seg_alloc + 1;
        seg_next[fresh] = OE_HLS_NULL_SEG;
        seg_count[fresh] = 0;
        if (tail == oe_hls_seg_id_t(OE_HLS_NULL_SEG)) {
            head_seg[src] = fresh;
        } else {
            seg_next[tail] = fresh;
        }
        tail_seg[src] = fresh;
        tail = fresh;
    }

    const ap_uint<8> slot = seg_count[tail];
    seg_slots[tail * OE_HLS_SEG_WIDTH + slot] = dst;
    seg_count[tail] = slot + 1;
    return 0;
}

// ---------------------------------------------------------------------------
// Flat scatter walk: II=1 per successor slot. Loop-carried dependence on
// node_state is left to HLS dependence analysis (duplicate successors are
// legal and idempotent via the fired bit, at an II cost only).
// ---------------------------------------------------------------------------
static void oe_hls_walk_flat(
    const oe_hls_node_id_t completed,
    const oe_hls_node_id_t num_nodes,
    const oe_hls_seg_id_t head_seg[OE_HLS_MAX_NODES],
    const oe_hls_seg_id_t seg_next[OE_HLS_MAX_SEGS],
    const ap_uint<8> seg_count[OE_HLS_MAX_SEGS],
    const oe_hls_node_id_t seg_slots[OE_HLS_MAX_SEG_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &edges_visited) {
#pragma HLS INLINE off
    oe_hls_cycle_t edges = 0;
    oe_hls_seg_id_t seg = head_seg[completed];

walk_segments:
    while (seg != oe_hls_seg_id_t(OE_HLS_NULL_SEG)) {
#pragma HLS LOOP_TRIPCOUNT min = 0 max = 8
        const ap_uint<8> cnt = seg_count[seg];
        const ap_uint<32> base = seg * OE_HLS_SEG_WIDTH;

    walk_slots:
        for (ap_uint<8> i = 0; i < cnt; ++i) {
#pragma HLS PIPELINE II = 1
#pragma HLS LOOP_TRIPCOUNT min = 0 max = OE_HLS_SEG_WIDTH
            const oe_hls_node_id_t succ = seg_slots[base + i];
            if (succ < num_nodes) {
                oe_hls_node_state_t st = node_state[succ];
                if (oe_hls_node_update(st)) {
                    ready_flags[succ] = 1;
                }
                node_state[succ] = st;
            }
            edges = edges + 1;
        }
        seg = seg_next[seg];
    }
    edges_visited = edges;
}

// ---------------------------------------------------------------------------
// Batch scatter walk: one segment (OE_HLS_SEG_WIDTH successors) per cycle.
// Requires bank-distinct successors within a segment for full parallelism
// (host load ordering); see header bank note.
// ---------------------------------------------------------------------------
static void oe_hls_walk_batch(
    const oe_hls_node_id_t completed,
    const oe_hls_node_id_t num_nodes,
    const oe_hls_seg_id_t head_seg[OE_HLS_MAX_NODES],
    const oe_hls_seg_id_t seg_next[OE_HLS_MAX_SEGS],
    const ap_uint<8> seg_count[OE_HLS_MAX_SEGS],
    const oe_hls_node_id_t seg_slots[OE_HLS_MAX_SEG_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &segs_visited) {
#pragma HLS INLINE off
    oe_hls_cycle_t segs = 0;
    oe_hls_seg_id_t seg = head_seg[completed];

batch_segments:
    while (seg != oe_hls_seg_id_t(OE_HLS_NULL_SEG)) {
#pragma HLS LOOP_TRIPCOUNT min = 0 max = 8
        const ap_uint<8> cnt = seg_count[seg];
        const ap_uint<32> base = seg * OE_HLS_SEG_WIDTH;

    batch_slots:
        for (int b = 0; b < OE_HLS_SEG_WIDTH; ++b) {
#pragma HLS UNROLL
            if (b < cnt) {
                const oe_hls_node_id_t succ = seg_slots[base + b];
                if (succ < num_nodes) {
                    oe_hls_node_state_t st = node_state[succ];
                    if (oe_hls_node_update(st)) {
                        ready_flags[succ] = 1;
                    }
                    node_state[succ] = st;
                }
            }
        }
        segs = segs + 1;
        seg = seg_next[seg];
    }
    segs_visited = segs;
}

// ---------------------------------------------------------------------------
// One-shot csynth/cosim anchor.
// ---------------------------------------------------------------------------
void oe_hls_scatter_kernel(
    const oe_hls_node_id_t num_nodes,
    const oe_hls_seg_id_t head_seg[OE_HLS_MAX_NODES],
    const oe_hls_seg_id_t seg_next[OE_HLS_MAX_SEGS],
    const ap_uint<8> seg_count[OE_HLS_MAX_SEGS],
    const oe_hls_node_id_t seg_slots[OE_HLS_MAX_SEG_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t completed,
    const ap_uint<8> use_batch,
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &scatter_cycles) {
#pragma HLS INTERFACE s_axilite port = num_nodes bundle = control
#pragma HLS INTERFACE s_axilite port = completed bundle = control
#pragma HLS INTERFACE s_axilite port = use_batch bundle = control
#pragma HLS INTERFACE s_axilite port = scatter_cycles bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

// Single partition factor everywhere (= OE_HLS_SEG_WIDTH); the old code mixed
// factor 4 and 8 on the same interface arrays across functions.
#pragma HLS ARRAY_PARTITION variable = node_state cyclic factor = 8
#pragma HLS ARRAY_PARTITION variable = ready_flags cyclic factor = 8

    oe_hls_cycle_t visited = 0;
    if (use_batch) {
        oe_hls_walk_batch(
            completed, num_nodes, head_seg, seg_next, seg_count, seg_slots,
            node_state, ready_flags, visited);
        scatter_cycles = 1 + visited; // 1 + n_segments
    } else {
        oe_hls_walk_flat(
            completed, num_nodes, head_seg, seg_next, seg_count, seg_slots,
            node_state, ready_flags, visited);
        scatter_cycles = 1 + visited; // 1 + out_degree
    }
}

// ---------------------------------------------------------------------------
// Streaming steady-state kernel: batch of completions in one invocation,
// compact ready-event output (no O(N) host flag scan).
// ---------------------------------------------------------------------------
void oe_hls_scatter_stream(
    const oe_hls_node_id_t num_nodes,
    const oe_hls_seg_id_t head_seg[OE_HLS_MAX_NODES],
    const oe_hls_seg_id_t seg_next[OE_HLS_MAX_SEGS],
    const ap_uint<8> seg_count[OE_HLS_MAX_SEGS],
    const oe_hls_node_id_t seg_slots[OE_HLS_MAX_SEG_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    hls::stream<oe_hls_node_id_t> &completions_in,
    hls::stream<oe_hls_node_id_t> &ready_out,
    oe_hls_cycle_t &completions_processed) {
#pragma HLS INTERFACE axis port = completions_in
#pragma HLS INTERFACE axis port = ready_out
#pragma HLS INTERFACE s_axilite port = num_nodes bundle = control
#pragma HLS INTERFACE s_axilite port = completions_processed bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control

#pragma HLS ARRAY_PARTITION variable = node_state cyclic factor = 8

    oe_hls_cycle_t processed = 0;

event_loop:
    while (true) {
#pragma HLS LOOP_TRIPCOUNT min = 1 max = OE_HLS_MAX_OUTSTANDING
        const oe_hls_node_id_t completed = completions_in.read();
        if (completed == oe_hls_node_id_t(OE_HLS_STREAM_END)) {
            break;
        }
        if (completed < num_nodes) {
            oe_hls_seg_id_t seg = head_seg[completed];

        stream_segments:
            while (seg != oe_hls_seg_id_t(OE_HLS_NULL_SEG)) {
#pragma HLS LOOP_TRIPCOUNT min = 0 max = 8
                const ap_uint<8> cnt = seg_count[seg];
                const ap_uint<32> base = seg * OE_HLS_SEG_WIDTH;

            stream_slots:
                for (ap_uint<8> i = 0; i < cnt; ++i) {
#pragma HLS PIPELINE II = 1
#pragma HLS LOOP_TRIPCOUNT min = 0 max = OE_HLS_SEG_WIDTH
                    const oe_hls_node_id_t succ = seg_slots[base + i];
                    if (succ < num_nodes) {
                        oe_hls_node_state_t st = node_state[succ];
                        if (oe_hls_node_update(st)) {
                            ready_out.write(succ);
                        }
                        node_state[succ] = st;
                    }
                }
                seg = seg_next[seg];
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
    const oe_hls_seg_id_t head_seg[OE_HLS_MAX_NODES],
    const oe_hls_seg_id_t seg_next[OE_HLS_MAX_SEGS],
    const ap_uint<8> seg_count[OE_HLS_MAX_SEGS],
    const oe_hls_node_id_t seg_slots[OE_HLS_MAX_SEG_SLOTS],
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

#pragma HLS ARRAY_PARTITION variable = node_state cyclic factor = 8
#pragma HLS ARRAY_PARTITION variable = ready_flags cyclic factor = 8

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
// unrolled into a pipelined parent (the old pragma was unsatisfiable).
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
        oe_hls_cycle_t visited = 0;
        oe_hls_walk_flat(
            node, num_nodes, head_seg, seg_next, seg_count, seg_slots,
            node_state, ready_flags, visited);
    }

    out_cycles = cycle;
}
