#include "cpu_baseline.h"
#include "engine_sim.h"
#include "workload_gen.h"

#include <cstdio>

static int failures = 0;

#define CHECK(cond, msg)            \
    do {                            \
        if (!(cond)) {              \
            std::printf("FAIL: %s\n", msg); \
            failures++;             \
        }                           \
    } while (0)

static void test_small_dag() {
    oe_engine_sim eng;
    oe_sim_init(&eng);

    (void)oe_sim_add_node(&eng, 0, OE_KIND_COMPUTE, OE_FIRE_ALL_OF, 0, 10, 0);
    (void)oe_sim_add_node(&eng, 1, OE_KIND_TOOL, OE_FIRE_ALL_OF, 0, 20, 0);
    (void)oe_sim_add_node(&eng, 2, OE_KIND_COORDINATION, OE_FIRE_ALL_OF, 0, 0, 0);
    (void)oe_sim_add_edge(&eng, 0, 1);
    (void)oe_sim_add_edge(&eng, 1, 2);
    oe_sim_seed_ready(&eng, 0);

    (void)oe_sim_run(&eng, 100000);
    const oe_engine_stats *st = oe_sim_stats(&eng);
    CHECK(st->nodes_completed == 3, "small dag completes 3 nodes");
    CHECK(st->coord_dispatches == 1, "coord node dispatched");
    CHECK(st->total_cycles >= 30, "latency lower bound respected");
}

static void test_any_of_join() {
    oe_engine_sim eng;
    oe_sim_init(&eng);

    (void)oe_sim_add_node(&eng, 0, OE_KIND_TOOL, OE_FIRE_ALL_OF, 0, 5, 0);
    (void)oe_sim_add_node(&eng, 1, OE_KIND_TOOL, OE_FIRE_ALL_OF, 0, 50, 0);
    (void)oe_sim_add_node(&eng, 2, OE_KIND_COMPUTE, OE_FIRE_ANY_OF, 0, 5, 0);
    (void)oe_sim_add_edge(&eng, 0, 2);
    (void)oe_sim_add_edge(&eng, 1, 2);
    eng.nodes[2].preds_total = 2;
    eng.nodes[2].preds_remaining = 2;
    oe_sim_seed_ready(&eng, 0);
    oe_sim_seed_ready(&eng, 1);

    (void)oe_sim_run(&eng, 100000);
    CHECK(oe_sim_stats(&eng)->total_cycles < 60, "any-of fires after fast predecessor");
}

static void test_workload_smoke() {
    oe_workload_params p{};
    p.seed = 7;
    p.depth = 3;
    p.fanout = 2;
    p.tool_latency_mean = 100;
    p.include_coord_nodes = 1;
    p.include_dynamic_append = 1;
    p.include_speculative_branches = 0;

    oe_engine_sim eng;
    oe_workload_build(&eng, &p);
    (void)oe_sim_run(&eng, 10000000);
    CHECK(eng.done, "synthetic workload quiesces");
}

int main() {
    test_small_dag();
    test_any_of_join();
    test_workload_smoke();
    if (failures == 0) {
        std::printf("ALL TESTS PASSED\n");
        return 0;
    }
    std::printf("%d TEST(S) FAILED\n", failures);
    return 1;
}
