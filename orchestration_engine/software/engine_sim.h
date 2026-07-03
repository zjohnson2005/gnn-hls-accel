#ifndef OE_ENGINE_SIM_H
#define OE_ENGINE_SIM_H

#include "csr_graph.h"
#include "oe_types.h"

// Cycle-approximate software model of the hardware orchestration engine.
// External tasks (GPU inference, tools) are modeled as latency-only; the
// engine tracks readiness, MSHR-style outstanding waits, dynamic graph ops,
// partial firing, and speculative downstream prep with rollback.

struct oe_engine_sim {
    oe_csr_graph graph;
    oe_node_desc nodes[OE_MAX_NODES];
    oe_node_id_t num_nodes;

    oe_node_id_t ready_q[OE_READY_QUEUE_DEPTH];
    uint32_t ready_head;
    uint32_t ready_tail;
    uint32_t ready_count;

    struct {
        oe_node_id_t node_id;
        oe_handle_t result_handle;
        oe_cycle_t issue_cycle;
        oe_cycle_t done_cycle;
        uint8_t valid;
        uint8_t speculative;
    } mshr[OE_MAX_OUTSTANDING];
    uint32_t mshr_count;

    oe_graph_op op_queue[OE_GRAPH_OP_QUEUE];
    uint32_t op_head;
    uint32_t op_tail;
    uint32_t op_count;

    oe_handle_t next_handle;
    oe_cycle_t cycle;
    oe_engine_stats stats;
    uint8_t done;
};

void oe_sim_init(oe_engine_sim *eng);
void oe_sim_reset(oe_engine_sim *eng);

int oe_sim_add_node(
    oe_engine_sim *eng,
    oe_node_id_t id,
    oe_node_kind kind,
    oe_fire_mode mode,
    uint16_t threshold,
    oe_cycle_t predicted_latency,
    uint8_t speculation_eligible);

int oe_sim_add_edge(oe_engine_sim *eng, oe_node_id_t src, oe_node_id_t dst);

int oe_sim_enqueue_op(oe_engine_sim *eng, const oe_graph_op *op);

void oe_sim_seed_ready(oe_engine_sim *eng, oe_node_id_t id);

// Advance one engine cycle; returns 0 when the graph is quiescent (done).
int oe_sim_step(oe_engine_sim *eng);

// Run until quiescent or max_cycles exceeded. Returns final cycle count.
oe_cycle_t oe_sim_run(oe_engine_sim *eng, oe_cycle_t max_cycles);

const oe_engine_stats *oe_sim_stats(const oe_engine_sim *eng);

#endif // OE_ENGINE_SIM_H
