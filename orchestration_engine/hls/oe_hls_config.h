#ifndef OE_HLS_CONFIG_H
#define OE_HLS_CONFIG_H

// Tighter bounds for first HLS synthesis (expand after csynth closes).
#define OE_HLS_MAX_NODES       256
#define OE_HLS_MAX_EDGES       2048
#define OE_HLS_MAX_OUTSTANDING 64
#define OE_HLS_READY_DEPTH     64
#define OE_HLS_MAX_OUT_DEGREE  8
#define OE_HLS_BATCH_WIDTH     8
#define OE_HLS_CLOCK_MHZ       300

// Segmented successor pool (append-safe dynamic graph).
// Each segment holds OE_HLS_SEG_WIDTH successor slots; nodes chain segments.
// 512 segments x 8 slots = 4096 edge capacity (25% slack over MAX_EDGES,
// matching the ~25% free-list overhead in dynamic_graph_cost_model.md).
#define OE_HLS_SEG_WIDTH       8
#define OE_HLS_MAX_SEGS        512
#define OE_HLS_MAX_SEG_SLOTS   (OE_HLS_MAX_SEGS * OE_HLS_SEG_WIDTH)
#define OE_HLS_NULL_SEG        0xFFFF

// Sentinel node id terminating a completion stream transaction batch.
#define OE_HLS_STREAM_END      0xFFFF

#endif // OE_HLS_CONFIG_H
