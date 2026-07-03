#ifndef OE_TYPES_H
#define OE_TYPES_H

#include <stdint.h>

#include "oe_config.h"

typedef uint32_t oe_node_id_t;
typedef uint32_t oe_handle_t;
typedef uint32_t oe_cycle_t;

enum oe_node_kind : uint8_t {
    OE_KIND_COMPUTE = 0,
    OE_KIND_TOOL = 1,
    OE_KIND_COORDINATION = 2
};

// Readiness semantics for a node (generalizes strict all-of joins).
enum oe_fire_mode : uint8_t {
    OE_FIRE_ALL_OF = 0,
    OE_FIRE_ANY_OF = 1,
    OE_FIRE_THRESHOLD = 2
};

enum oe_node_state : uint8_t {
    OE_STATE_PENDING = 0,
    OE_STATE_READY = 1,
    OE_STATE_OUTSTANDING = 2,
    OE_STATE_DONE = 3,
    OE_STATE_PRUNED = 4
};

struct oe_node_desc {
    oe_node_id_t id;
    oe_node_kind kind;
    oe_fire_mode fire_mode;
    uint16_t fire_threshold;
    uint16_t preds_remaining;
    uint16_t preds_total;
    oe_node_state state;
    oe_cycle_t predicted_latency;
    uint8_t speculation_eligible;
    uint8_t pruned;
};

struct oe_completion {
    oe_node_id_t node_id;
    oe_handle_t result_handle;
    oe_cycle_t completion_cycle;
};

struct oe_dispatch {
    oe_node_id_t node_id;
    oe_node_kind kind;
    oe_handle_t result_handle;
    oe_cycle_t issue_cycle;
    oe_cycle_t expected_done_cycle;
};

// Dynamic graph mutation (runtime append / prune / conditional fan-out).
enum oe_graph_op_kind : uint8_t {
    OE_OP_APPEND_NODE = 0,
    OE_OP_APPEND_EDGE = 1,
    OE_OP_SET_FIRE_MODE = 2,
    OE_OP_PRUNE_SUBTREE = 3
};

struct oe_graph_op {
    oe_graph_op_kind kind;
    oe_node_id_t node_a;
    oe_node_id_t node_b;
    oe_node_kind node_kind;
    oe_fire_mode fire_mode;
    uint16_t fire_threshold;
    oe_cycle_t predicted_latency;
};

struct oe_engine_stats {
    oe_cycle_t total_cycles;
    oe_cycle_t dispatch_cycles;
    oe_cycle_t scatter_cycles;
    oe_cycle_t graph_mut_cycles;
    oe_cycle_t speculation_rollbacks;
    uint32_t nodes_dispatched;
    uint32_t nodes_completed;
    uint32_t coord_dispatches;
    uint32_t tool_dispatches;
    uint32_t compute_dispatches;
    uint32_t mshr_peak;
    uint32_t ready_queue_peak;
};

#endif // OE_TYPES_H
