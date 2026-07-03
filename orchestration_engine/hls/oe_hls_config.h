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

#endif // OE_HLS_CONFIG_H
