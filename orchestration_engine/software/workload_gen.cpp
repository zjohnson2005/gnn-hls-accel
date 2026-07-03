#include "workload_gen.h"

#include "cpu_baseline.h"

#include <stdlib.h>

static uint32_t wl_rng(uint32_t *state) {
    *state ^= *state << 13;
    *state ^= *state >> 17;
    *state ^= *state << 5;
    return *state;
}

static oe_cycle_t sample_latency(const oe_workload_params *p, uint32_t *rng) {
    const uint32_t r = wl_rng(rng);
    const oe_cycle_t spread = p->tool_latency_spread;
    const oe_cycle_t base = p->tool_latency_mean;
    if (spread == 0) {
        return base;
    }
    return base + (r % (spread + 1));
}

static oe_node_kind pick_kind(const oe_workload_params *p, uint32_t *rng, oe_node_id_t depth) {
    if (p->include_coord_nodes && (wl_rng(rng) % 5 == 0)) {
        return OE_KIND_COORDINATION;
    }
    if (depth == 0) {
        return OE_KIND_COMPUTE;
    }
    return (wl_rng(rng) % 3 == 0) ? OE_KIND_TOOL : OE_KIND_COMPUTE;
}

static oe_fire_mode pick_fire_mode(const oe_workload_params *p, uint32_t *rng) {
    const uint32_t r = wl_rng(rng) % 100;
    if (r < (uint32_t)(p->any_of_fraction * 100.0f)) {
        return OE_FIRE_ANY_OF;
    }
    if (r < (uint32_t)(p->any_of_fraction * 100.0f) + 10) {
        return OE_FIRE_THRESHOLD;
    }
    return OE_FIRE_ALL_OF;
}

static oe_node_id_t build_layer(
    oe_engine_sim *eng,
    const oe_workload_params *p,
    uint32_t *rng,
    oe_node_id_t depth,
    oe_node_id_t base_id,
    oe_node_id_t count) {
    oe_node_id_t next_base = base_id + count;
    for (oe_node_id_t i = 0; i < count; ++i) {
        const oe_node_id_t id = base_id + i;
        const oe_node_kind kind = pick_kind(p, rng, depth);
        const oe_fire_mode mode = pick_fire_mode(p, rng);
        const uint16_t threshold = (mode == OE_FIRE_THRESHOLD) ? 1 : 0;
        const oe_cycle_t lat = (kind == OE_KIND_COORDINATION) ? 0 : sample_latency(p, rng);
        const uint8_t spec = p->include_speculative_branches && (wl_rng(rng) % 4 == 0);
        (void)oe_sim_add_node(eng, id, kind, mode, threshold, lat, spec);

        if (depth > 0) {
            const oe_node_id_t parent_base = base_id - p->fanout;
            for (oe_node_id_t f = 0; f < p->fanout; ++f) {
                const oe_node_id_t parent = parent_base + (i + f) % p->fanout;
                (void)oe_sim_add_edge(eng, parent, id);
            }
        }
    }

    if (p->include_dynamic_append && depth == p->depth / 2) {
        oe_graph_op op;
        op.kind = OE_OP_APPEND_NODE;
        op.node_a = next_base;
        op.node_b = 0;
        op.node_kind = OE_KIND_TOOL;
        op.fire_mode = OE_FIRE_ALL_OF;
        op.fire_threshold = 0;
        op.predicted_latency = sample_latency(p, rng);
        (void)oe_sim_enqueue_op(eng, &op);
        next_base++;
    }

    if (depth + 1 < p->depth) {
        return build_layer(eng, p, rng, depth + 1, next_base, count * p->fanout);
    }
    return next_base;
}

void oe_workload_build(oe_engine_sim *eng, const oe_workload_params *params) {
    oe_sim_reset(eng);
    uint32_t rng = params->seed ? params->seed : 1u;
    (void)build_layer(eng, params, &rng, 0, 0, params->num_roots ? params->num_roots : 1);

    for (oe_node_id_t r = 0; r < (params->num_roots ? params->num_roots : 1); ++r) {
        oe_sim_seed_ready(eng, r);
    }

    if (params->include_speculative_branches && eng->num_nodes > 4) {
        oe_graph_op prune;
        prune.kind = OE_OP_PRUNE_SUBTREE;
        prune.node_a = eng->num_nodes - 1;
        prune.node_b = 0;
        prune.node_kind = OE_KIND_TOOL;
        prune.fire_mode = OE_FIRE_ALL_OF;
        prune.fire_threshold = 0;
        prune.predicted_latency = 0;
        (void)oe_sim_enqueue_op(eng, &prune);
    }
}

static oe_node_id_t build_layer_cpu(
    oe_cpu_baseline *cpu,
    const oe_workload_params *p,
    uint32_t *rng,
    oe_node_id_t depth,
    oe_node_id_t base_id,
    oe_node_id_t count) {
    oe_node_id_t next_base = base_id + count;
    for (oe_node_id_t i = 0; i < count; ++i) {
        const oe_node_id_t id = base_id + i;
        const oe_node_kind kind = pick_kind(p, rng, depth);
        const oe_fire_mode mode = pick_fire_mode(p, rng);
        const uint16_t threshold = (mode == OE_FIRE_THRESHOLD) ? 1 : 0;
        const oe_cycle_t lat = (kind == OE_KIND_COORDINATION) ? 0 : sample_latency(p, rng);
        (void)oe_cpu_add_node(cpu, id, kind, mode, threshold, lat);

        if (depth > 0) {
            const oe_node_id_t parent_base = base_id - p->fanout;
            for (oe_node_id_t f = 0; f < p->fanout; ++f) {
                const oe_node_id_t parent = parent_base + (i + f) % p->fanout;
                (void)oe_cpu_add_edge(cpu, parent, id);
            }
        }
    }
    if (depth + 1 < p->depth) {
        return build_layer_cpu(cpu, p, rng, depth + 1, next_base, count * p->fanout);
    }
    return next_base;
}

void oe_workload_build_cpu(oe_cpu_baseline *cpu, const oe_workload_params *params) {
    oe_cpu_init(cpu);
    uint32_t rng = params->seed ? params->seed : 1u;
    (void)build_layer_cpu(cpu, params, &rng, 0, 0, params->num_roots ? params->num_roots : 1);
    for (oe_node_id_t r = 0; r < (params->num_roots ? params->num_roots : 1); ++r) {
        oe_cpu_seed_ready(cpu, r);
    }
}
