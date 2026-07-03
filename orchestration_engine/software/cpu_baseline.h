#ifndef OE_CPU_BASELINE_H
#define OE_CPU_BASELINE_H

#include "csr_graph.h"
#include "oe_types.h"

// Software scheduler baseline: global scan over waiting tasks each event.
// Models a conventional CPU thread-pool / event-loop coordinator.

struct oe_cpu_baseline {
    oe_csr_graph graph;
    oe_node_desc nodes[OE_MAX_NODES];
    oe_node_id_t num_nodes;

    struct {
        oe_node_id_t node_id;
        oe_cycle_t done_cycle;
        uint8_t valid;
    } outstanding[OE_MAX_OUTSTANDING];
    uint32_t outstanding_count;

    oe_cycle_t cycle;
    oe_engine_stats stats;
};

void oe_cpu_init(oe_cpu_baseline *cpu);
int oe_cpu_add_node(
    oe_cpu_baseline *cpu,
    oe_node_id_t id,
    oe_node_kind kind,
    oe_fire_mode mode,
    uint16_t threshold,
    oe_cycle_t predicted_latency);
int oe_cpu_add_edge(oe_cpu_baseline *cpu, oe_node_id_t src, oe_node_id_t dst);
void oe_cpu_seed_ready(oe_cpu_baseline *cpu, oe_node_id_t id);
oe_cycle_t oe_cpu_run(oe_cpu_baseline *cpu, oe_cycle_t max_cycles);
const oe_engine_stats *oe_cpu_stats(const oe_cpu_baseline *cpu);

#endif // OE_CPU_BASELINE_H
