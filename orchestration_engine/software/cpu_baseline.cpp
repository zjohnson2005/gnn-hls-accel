#include "cpu_baseline.h"

#include <string.h>

static int node_ready(const oe_cpu_baseline *cpu, oe_node_id_t id) {
    const oe_node_desc *n = &cpu->nodes[id];
    if (n->pruned || n->state == OE_STATE_DONE || n->state == OE_STATE_OUTSTANDING) {
        return 0;
    }
    switch (n->fire_mode) {
    case OE_FIRE_ANY_OF:
        return n->preds_remaining < n->preds_total;
    case OE_FIRE_THRESHOLD:
        return n->preds_remaining <= n->fire_threshold;
    case OE_FIRE_ALL_OF:
    default:
        return n->preds_remaining == 0;
    }
}

static void cpu_scatter(oe_cpu_baseline *cpu, oe_node_id_t completed) {
    const uint32_t deg = oe_csr_out_degree(&cpu->graph, completed);
    cpu->stats.scatter_cycles++;
    for (uint32_t i = 0; i < deg; ++i) {
        const oe_node_id_t succ = oe_csr_successor_at(&cpu->graph, completed, i);
        if (succ >= cpu->num_nodes) {
            continue;
        }
        oe_node_desc *d = &cpu->nodes[succ];
        if (d->pruned || d->state == OE_STATE_DONE || d->state == OE_STATE_OUTSTANDING) {
            continue;
        }
        switch (d->fire_mode) {
        case OE_FIRE_ANY_OF:
            d->preds_remaining = 0;
            break;
        case OE_FIRE_THRESHOLD:
            if (d->preds_remaining > 0) {
                d->preds_remaining--;
            }
            break;
        case OE_FIRE_ALL_OF:
        default:
            if (d->preds_remaining > 0) {
                d->preds_remaining--;
            }
            break;
        }
    }
    cpu->stats.dispatch_cycles++;
}

static void cpu_global_scan_dispatch(oe_cpu_baseline *cpu) {
    for (oe_node_id_t id = 0; id < cpu->num_nodes; ++id) {
        if (!node_ready(cpu, id)) {
            continue;
        }
        oe_node_desc *n = &cpu->nodes[id];
        if (n->kind == OE_KIND_COORDINATION) {
            n->state = OE_STATE_DONE;
            cpu->stats.nodes_completed++;
            cpu->stats.coord_dispatches++;
            cpu_scatter(cpu, id);
            continue;
        }
        if (cpu->outstanding_count >= OE_MAX_OUTSTANDING) {
            return;
        }
        uint32_t slot = cpu->outstanding_count;
        for (uint32_t i = 0; i < OE_MAX_OUTSTANDING; ++i) {
            if (!cpu->outstanding[i].valid) {
                slot = i;
                break;
            }
        }
        const oe_cycle_t lat = n->predicted_latency > 0 ? n->predicted_latency : 1;
        cpu->outstanding[slot].node_id = id;
        cpu->outstanding[slot].done_cycle = cpu->cycle + lat;
        cpu->outstanding[slot].valid = 1;
        cpu->outstanding_count++;
        n->state = OE_STATE_OUTSTANDING;
        cpu->stats.nodes_dispatched++;
        if (n->kind == OE_KIND_TOOL) {
            cpu->stats.tool_dispatches++;
        } else {
            cpu->stats.compute_dispatches++;
        }
    }
}

void oe_cpu_init(oe_cpu_baseline *cpu) {
    memset(cpu, 0, sizeof(*cpu));
    oe_csr_init(&cpu->graph);
}

int oe_cpu_add_node(
    oe_cpu_baseline *cpu,
    oe_node_id_t id,
    oe_node_kind kind,
    oe_fire_mode mode,
    uint16_t threshold,
    oe_cycle_t predicted_latency) {
    if (id >= OE_MAX_NODES) {
        return -1;
    }
    if (id >= cpu->num_nodes) {
        cpu->num_nodes = id + 1;
    }
    oe_node_desc *n = &cpu->nodes[id];
    n->id = id;
    n->kind = kind;
    n->fire_mode = mode;
    n->fire_threshold = threshold;
    n->preds_remaining = 0;
    n->preds_total = 0;
    n->state = OE_STATE_PENDING;
    n->predicted_latency = predicted_latency;
    n->pruned = 0;
    return 0;
}

int oe_cpu_add_edge(oe_cpu_baseline *cpu, oe_node_id_t src, oe_node_id_t dst) {
    if (oe_csr_append_edge(&cpu->graph, src, dst) != 0) {
        return -1;
    }
    if (dst >= cpu->num_nodes) {
        cpu->num_nodes = dst + 1;
    }
    cpu->nodes[dst].preds_total++;
    cpu->nodes[dst].preds_remaining++;
    return 0;
}

void oe_cpu_seed_ready(oe_cpu_baseline *cpu, oe_node_id_t id) {
    if (id >= cpu->num_nodes) {
        return;
    }
    cpu->nodes[id].preds_remaining = 0;
    cpu->nodes[id].state = OE_STATE_READY;
}

static int cpu_done(const oe_cpu_baseline *cpu) {
    for (oe_node_id_t i = 0; i < cpu->num_nodes; ++i) {
        if (!cpu->nodes[i].pruned && cpu->nodes[i].state != OE_STATE_DONE) {
            return 0;
        }
    }
    return cpu->num_nodes > 0 && cpu->outstanding_count == 0;
}

oe_cycle_t oe_cpu_run(oe_cpu_baseline *cpu, oe_cycle_t max_cycles) {
    while (cpu->cycle < max_cycles && !cpu_done(cpu)) {
        cpu->cycle++;
        cpu->stats.total_cycles = cpu->cycle;

        for (uint32_t i = 0; i < OE_MAX_OUTSTANDING; ++i) {
            if (!cpu->outstanding[i].valid) {
                continue;
            }
            if (cpu->cycle < cpu->outstanding[i].done_cycle) {
                continue;
            }
            const oe_node_id_t nid = cpu->outstanding[i].node_id;
            cpu->nodes[nid].state = OE_STATE_DONE;
            cpu->stats.nodes_completed++;
            cpu_scatter(cpu, nid);
            cpu->outstanding[i].valid = 0;
            cpu->outstanding_count--;
        }

        cpu_global_scan_dispatch(cpu);
    }
    return cpu->cycle;
}

const oe_engine_stats *oe_cpu_stats(const oe_cpu_baseline *cpu) {
    return &cpu->stats;
}
