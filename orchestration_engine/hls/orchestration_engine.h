#ifndef ORCHESTRATION_ENGINE_H
#define ORCHESTRATION_ENGINE_H

#include "ap_int.h"
#include "hls_stream.h"
#include "oe_hls_config.h"

typedef ap_uint<16> oe_hls_node_id_t;
typedef ap_uint<16> oe_hls_seg_id_t;
typedef ap_uint<32> oe_hls_cycle_t;
typedef ap_uint<8> oe_hls_kind_t;
typedef ap_uint<2> oe_hls_fire_t;

// ---------------------------------------------------------------------------
// Packed per-node scheduling state: one BRAM word per node so the scatter
// update is a single read-modify-write (was 4 separate arrays / ~7 accesses).
//
//   [7:0]   preds_remaining (fan-in <= 255, matches cost-model record)
//   [15:8]  fire_threshold
//   [17:16] fire_mode (0 = all-of, 1 = any-of, 2 = threshold)
//   [18]    fired  (exactly-once dispatch guard)
//   [19]    pruned (lazy prune: node never fires)
// ---------------------------------------------------------------------------
typedef ap_uint<32> oe_hls_node_state_t;

static inline oe_hls_node_state_t oe_hls_make_node(
    const ap_uint<8> preds_remaining,
    const oe_hls_fire_t fire_mode,
    const ap_uint<8> fire_threshold,
    const ap_uint<1> pruned = 0) {
#pragma HLS INLINE
    oe_hls_node_state_t st = 0;
    st.range(7, 0) = preds_remaining;
    st.range(15, 8) = fire_threshold;
    st.range(17, 16) = fire_mode;
    st[18] = 0;
    st[19] = pruned;
    return st;
}

static inline ap_uint<8> oe_hls_node_preds(const oe_hls_node_state_t st) {
#pragma HLS INLINE
    return st.range(7, 0);
}

static inline ap_uint<1> oe_hls_node_fired(const oe_hls_node_state_t st) {
#pragma HLS INLINE
    return st[18];
}

static inline ap_uint<1> oe_hls_node_pruned(const oe_hls_node_state_t st) {
#pragma HLS INLINE
    return st[19];
}

// Core readiness update. Returns 1 iff the node fires NOW (first time only).
// fired/pruned guards give exactly-once semantics for all fire modes.
static inline ap_uint<1> oe_hls_node_update(oe_hls_node_state_t &st) {
#pragma HLS INLINE
    if (st[18] || st[19]) { // fired || pruned
        return 0;
    }
    const oe_hls_fire_t mode = st.range(17, 16);
    ap_uint<8> preds = st.range(7, 0);
    const ap_uint<8> thr = st.range(15, 8);
    ap_uint<1> fire_now = 0;

    if (mode == 1) { // any-of
        preds = 0;
        fire_now = 1;
    } else if (mode == 2) { // threshold
        if (preds > 0) {
            preds = preds - 1;
        }
        if (preds <= thr) {
            preds = 0;
            fire_now = 1;
        }
    } else { // all-of
        if (preds > 0) {
            preds = preds - 1;
        }
        if (preds == 0) {
            fire_now = 1;
        }
    }

    st.range(7, 0) = preds;
    if (fire_now) {
        st[18] = 1;
    }
    return fire_now;
}

// ---------------------------------------------------------------------------
// Segmented successor pool (replaces CSR row_ptr/col_idx).
// Append is O(1) into a node's tail segment and NEVER touches other nodes'
// rows, so mid-graph runtime append is safe (the CSR tail-append was only
// correct for the highest-numbered node).
//
// Bank note: batch scatter updates OE_HLS_SEG_WIDTH successors per cycle via
// cyclic partitioning of node_state (factor OE_HLS_SEG_WIDTH). The host
// should order successors within a segment so succ % OE_HLS_SEG_WIDTH values
// are distinct (bank-aware load ordering); duplicates in one segment are
// serialized by HLS dependence analysis, costing II, never correctness
// (the fired bit makes duplicate updates idempotent).
// ---------------------------------------------------------------------------

// O(1) tail append. Allocates a fresh segment from the bump allocator when
// the node has none or its tail is full. Returns 0 on success, 1 = pool full.
// v1 uses bump allocation; free-list reclaim of pruned segments is follow-on.
ap_uint<8> oe_hls_append_edge(
    const oe_hls_node_id_t src,
    const oe_hls_node_id_t dst,
    oe_hls_seg_id_t head_seg[OE_HLS_MAX_NODES],
    oe_hls_seg_id_t tail_seg[OE_HLS_MAX_NODES],
    oe_hls_seg_id_t seg_next[OE_HLS_MAX_SEGS],
    ap_uint<8> seg_count[OE_HLS_MAX_SEGS],
    oe_hls_node_id_t seg_slots[OE_HLS_MAX_SEG_SLOTS],
    ap_uint<32> &seg_alloc);

// ---------------------------------------------------------------------------
// One-shot scatter kernel (csynth/cosim anchor; ap_ctrl_hs).
// Flat mode: II=1 per successor -> analytic 1 + out_degree cycles.
// Batch mode: OE_HLS_SEG_WIDTH-wide unroll per segment -> 1 + n_segments.
// scatter_cycles reports the analytic count for gate parity.
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
    oe_hls_cycle_t &scatter_cycles);

// ---------------------------------------------------------------------------
// Streaming scatter kernel (steady-state / deployment shape).
// Reads completion node ids from completions_in until OE_HLS_STREAM_END,
// scatters each, and emits ONLY newly-fired node ids on ready_out
// (terminated by OE_HLS_STREAM_END). Output is O(fired), not an O(N) flag
// scan, so the host never pays scan-class cost at the interface.
// One invocation processes a whole batch of completions back-to-back:
// cosim latency / n_completions = measured steady-state cycles/completion.
// For deployment the same body runs free-running (ap_ctrl_none).
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
    oe_hls_cycle_t &completions_processed);

// ---------------------------------------------------------------------------
// Epoch-level engine: init ready flags from preds, then process a completion
// batch. Outer completion loop is intentionally NOT pipelined: the scatter
// walk has variable bounds and cannot be unrolled into a pipelined parent.
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
    oe_hls_cycle_t &out_cycles);

#endif // ORCHESTRATION_ENGINE_H
