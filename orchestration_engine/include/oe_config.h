#ifndef OE_CONFIG_H
#define OE_CONFIG_H

// Compile-time bounds for the orchestration engine (software + HLS).
// Sized for datacenter-scale agent graphs in simulation; tighten for synthesis.

#define OE_MAX_NODES           4096
#define OE_MAX_EDGES           32768
#define OE_MAX_OUTSTANDING     1024
#define OE_READY_QUEUE_DEPTH   512
#define OE_MAX_SUCCESSORS      64
#define OE_MAX_PREDECESSORS    64
#define OE_GRAPH_OP_QUEUE      128
#define OE_SPEC_DEPTH          8
#define OE_MAX_RESULT_HANDLES  4096

// Simulated external task latency (cycles) for synthetic workloads.
#define OE_LATENCY_MIN_CYCLES  100
#define OE_LATENCY_MAX_CYCLES  100000

#endif // OE_CONFIG_H
