#include "cpu_baseline.h"
#include "engine_sim.h"
#include "workload_gen.h"

#include <stdio.h>
#include <stdlib.h>

static void print_stats(const char *label, const oe_engine_stats *s) {
    printf(
        "%s: cycles=%u dispatch=%u scatter=%u graph_mut=%u rollbacks=%u "
        "dispatched=%u completed=%u mshr_peak=%u ready_peak=%u "
        "(coord=%u tool=%u compute=%u)\n",
        label,
        s->total_cycles,
        s->dispatch_cycles,
        s->scatter_cycles,
        s->graph_mut_cycles,
        s->speculation_rollbacks,
        s->nodes_dispatched,
        s->nodes_completed,
        s->mshr_peak,
        s->ready_queue_peak,
        s->coord_dispatches,
        s->tool_dispatches,
        s->compute_dispatches);
}

int main(int argc, char **argv) {
    oe_workload_params params;
    params.seed = 42;
    params.depth = 4;
    params.fanout = 2;
    params.num_roots = 1;
    params.tool_latency_mean = 500;
    params.tool_latency_spread = 2000;
    params.include_coord_nodes = 1;
    params.include_dynamic_append = 1;
    params.include_speculative_branches = 1;
    params.any_of_fraction = 0.15f;

    if (argc > 1) {
        params.depth = (oe_node_id_t)atoi(argv[1]);
    }
    if (argc > 2) {
        params.fanout = (oe_node_id_t)atoi(argv[2]);
    }
    if (argc > 3) {
        params.seed = (uint32_t)atoi(argv[3]);
    }

    oe_engine_sim eng;
    oe_cpu_baseline cpu;

    oe_workload_build(&eng, &params);
    oe_workload_build_cpu(&cpu, &params);

    const oe_cycle_t eng_cycles = oe_sim_run(&eng, 100000000u);
    const oe_cycle_t cpu_cycles = oe_cpu_run(&cpu, 100000000u);

    print_stats("engine", oe_sim_stats(&eng));
    print_stats("cpu_baseline", oe_cpu_stats(&cpu));

    const oe_engine_stats *es = oe_sim_stats(&eng);
    const oe_engine_stats *cs = oe_cpu_stats(&cpu);
    const uint32_t coord_overhead = es->dispatch_cycles + es->scatter_cycles + es->graph_mut_cycles;
    const uint32_t cpu_coord_overhead = cs->dispatch_cycles + cs->scatter_cycles;

    printf(
        "summary: eng_total=%u cpu_total=%u coord_overhead_eng=%u coord_overhead_cpu=%u "
        "speedup_coord=%.2fx nodes=%u\n",
        eng_cycles,
        cpu_cycles,
        coord_overhead,
        cpu_coord_overhead,
        cpu_coord_overhead > 0 ? (double)cpu_coord_overhead / (double)coord_overhead : 0.0,
        eng.num_nodes);

    return (eng.done && cpu_cycles > 0) ? 0 : 1;
}
