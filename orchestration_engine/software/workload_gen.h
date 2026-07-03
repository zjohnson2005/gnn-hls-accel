#ifndef OE_WORKLOAD_GEN_H
#define OE_WORKLOAD_GEN_H

#include "engine_sim.h"

// Synthetic agentic DAG workloads for Phase 1/2 characterization.
// Models plan-act-observe fan-out, tool/coordination nodes, partial joins,
// runtime graph growth, and speculative branch pruning.

struct oe_workload_params {
    uint32_t seed;
    oe_node_id_t depth;
    oe_node_id_t fanout;
    oe_node_id_t num_roots;
    oe_cycle_t tool_latency_mean;
    oe_cycle_t tool_latency_spread;
    uint8_t include_coord_nodes;
    uint8_t include_dynamic_append;
    uint8_t include_speculative_branches;
    float any_of_fraction;
};

void oe_workload_build(oe_engine_sim *eng, const oe_workload_params *params);

// Mirror the same topology into the CPU baseline (static portion only).
void oe_workload_build_cpu(oe_cpu_baseline *cpu, const oe_workload_params *params);

#endif // OE_WORKLOAD_GEN_H
