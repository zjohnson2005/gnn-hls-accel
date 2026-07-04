#ifndef ORCHESTRATION_ENGINE_H
#define ORCHESTRATION_ENGINE_H

#include "ap_int.h"
#include "hls_stream.h"
#include "oe_hls_config.h"

typedef ap_uint<16> oe_hls_node_id_t;
typedef ap_uint<32> oe_hls_cycle_t;
typedef ap_uint<8> oe_hls_kind_t;
typedef ap_uint<2> oe_hls_fire_t;
typedef ap_uint<128> oe_graph_op_word_t;

#define OE_HLS_OP_APPEND_NODE   0
#define OE_HLS_OP_APPEND_EDGE   1
#define OE_HLS_OP_SET_FIRE_MODE 2
#define OE_HLS_OP_WORD_END      0xFF
#define OE_HLS_SCATTER_BANKS    4

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
// Fixed-capacity successor rows (replaces CSR row_ptr/col_idx).
// succ_slots[node * OE_HLS_SUCC_CAP + i] for i < succ_count[node].
// Append is O(1) into the node's own row and NEVER touches other nodes'
// rows, so mid-graph runtime append is safe (the CSR tail-append was only
// correct for the highest-numbered node). Contiguous rows mean the 8-wide
// batch walk hits banks 0..7 exactly once — no pointer chasing, no chain
// dependence (the earlier segmented-pool design serialized on seg_next and
// cost ~2x Fmax).
// ---------------------------------------------------------------------------

// O(1) row append. Returns 0 on success, 1 = row full (out-degree > CAP).
ap_uint<8> oe_hls_append_edge(
    const oe_hls_node_id_t src,
    const oe_hls_node_id_t dst,
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS]);

// ---------------------------------------------------------------------------
// One-shot FLAT scatter kernel (csynth/cosim anchor; ap_ctrl_hs).
// II=1 per successor -> analytic 1 + out_degree cycles.
// Deliberately contains NO batch path and NO array partitions: one update
// per cycle needs only dual-port BRAM, and the 8-wide batch crossbar in a
// combined kernel set the kernel-wide clock estimate (measured 415 -> 210
// MHz). The wide variant is a separate top below.
// ---------------------------------------------------------------------------
void oe_hls_scatter_kernel(
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t completed,
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &scatter_cycles);

// ---------------------------------------------------------------------------
// One-shot BATCH scatter kernel (own top, synthesized separately).
// Whole row (OE_HLS_SUCC_CAP successors) in one wide cycle; needs the
// 8-bank partition + crossbar, so it carries its own (lower) Fmax and must
// not share a top with the flat anchor.
// ---------------------------------------------------------------------------
void oe_hls_scatter_batch_kernel(
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t completed,
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
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    hls::stream<oe_hls_node_id_t> &completions_in,
    hls::stream<oe_hls_node_id_t> &ready_out,
    oe_hls_cycle_t &completions_processed);

// ---------------------------------------------------------------------------
// Epoch-level engine: init ready flags from preds, then process a completion
// batch. Outer completion loop is intentionally NOT pipelined: the scatter
// walk has variable bounds and cannot be unrolled into a pipelined parent.
// ---------------------------------------------------------------------------
// Streamed session graph load (packed op words; layout matches scatter arrays).
void oe_hls_graph_load(
    oe_hls_node_id_t &num_nodes,
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    hls::stream<oe_graph_op_word_t> &ops_in,
    oe_hls_cycle_t &load_cycles,
    ap_uint<32> &ops_processed);

void oe_hls_graph_load_batch(
    const oe_hls_node_id_t num_sessions,
    oe_hls_node_id_t &num_nodes,
    ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    hls::stream<oe_graph_op_word_t> &ops_in,
    oe_hls_cycle_t &load_cycles,
    oe_hls_cycle_t &sessions_loaded,
    ap_uint<32> &ops_processed);

// Banked scatter variant (B=OE_HLS_SCATTER_BANKS); baseline kept separate.
void oe_hls_scatter_banked_stream(
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    hls::stream<oe_hls_node_id_t> &completions_in,
    hls::stream<oe_hls_node_id_t> &ready_out,
    oe_hls_cycle_t &completions_processed);

// C2 LS top: array ports feeding INTERNAL DATAFLOW FIFOs (ops/completions/
// ready). LightningSim 2023.1 cannot link instrumented TBs against top-level
// hls::stream ports (fpga_fifo_* undefined), and graph BRAM must stay inside
// one dataflow process (HLS 200-968) — hence feeders -> engine -> sink.
#define OE_LS_ENGINE_MAX_OPS 512

void oe_hls_engine_stream(
    const oe_graph_op_word_t ops_in[OE_LS_ENGINE_MAX_OPS],
    const ap_uint<16> num_ops,
    const oe_hls_node_id_t completions_in[OE_HLS_MAX_OUTSTANDING],
    const ap_uint<16> num_completions,
    oe_hls_node_id_t ready_out[OE_HLS_MAX_NODES],
    oe_hls_node_id_t &num_ready,
    oe_hls_cycle_t &load_cycles,
    oe_hls_cycle_t &scatter_processed,
    ap_uint<32> &ops_processed);

void orchestration_engine(
    const oe_hls_node_id_t num_nodes,
    const ap_uint<8> succ_count[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t succ_slots[OE_HLS_SUCC_SLOTS],
    oe_hls_node_state_t node_state[OE_HLS_MAX_NODES],
    const oe_hls_node_id_t completion_nodes[OE_HLS_MAX_OUTSTANDING],
    const oe_hls_cycle_t completion_cycles[OE_HLS_MAX_OUTSTANDING],
    const oe_hls_node_id_t num_completions,
    ap_uint<1> ready_flags[OE_HLS_MAX_NODES],
    oe_hls_cycle_t &out_cycles);

#endif // ORCHESTRATION_ENGINE_H
