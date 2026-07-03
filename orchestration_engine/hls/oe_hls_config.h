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

// Fixed-capacity successor rows (append-safe dynamic graph, no pointer chase).
// Each node owns a contiguous row of OE_HLS_SUCC_CAP slots; append is O(1)
// and never touches other nodes' rows. 256 nodes x 8 slots x 2 B = 4 KB.
#define OE_HLS_SUCC_CAP        OE_HLS_MAX_OUT_DEGREE
#define OE_HLS_SUCC_SLOTS      (OE_HLS_MAX_NODES * OE_HLS_SUCC_CAP)

// Sentinel node id terminating a completion stream transaction batch.
#define OE_HLS_STREAM_END      0xFFFF

#endif // OE_HLS_CONFIG_H
