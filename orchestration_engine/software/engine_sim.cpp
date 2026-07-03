#include "engine_sim.h"

#include <string.h>

static uint32_t ready_push(oe_engine_sim *eng, oe_node_id_t id) {
    if (eng->ready_count >= OE_READY_QUEUE_DEPTH) {
        return 0;
    }
    eng->ready_q[eng->ready_tail] = id;
    eng->ready_tail = (eng->ready_tail + 1) % OE_READY_QUEUE_DEPTH;
    eng->ready_count++;
    if (eng->ready_count > eng->stats.ready_queue_peak) {
        eng->stats.ready_queue_peak = eng->ready_count;
    }
    return 1;
}

static int ready_pop(oe_engine_sim *eng, oe_node_id_t *id) {
    if (eng->ready_count == 0) {
        return 0;
    }
    *id = eng->ready_q[eng->ready_head];
    eng->ready_head = (eng->ready_head + 1) % OE_READY_QUEUE_DEPTH;
    eng->ready_count--;
    return 1;
}

static int mshr_alloc(oe_engine_sim *eng) {
    for (uint32_t i = 0; i < OE_MAX_OUTSTANDING; ++i) {
        if (!eng->mshr[i].valid) {
            return (int)i;
        }
    }
    return -1;
}

static void mark_ready(oe_engine_sim *eng, oe_node_id_t id) {
    oe_node_desc *n = &eng->nodes[id];
    if (n->pruned || n->state == OE_STATE_DONE || n->state == OE_STATE_OUTSTANDING) {
        return;
    }
    n->state = OE_STATE_READY;
    (void)ready_push(eng, id);
}

static void rollback_speculation(oe_engine_sim *eng, oe_node_id_t node_id) {
    const uint32_t deg = oe_csr_out_degree(&eng->graph, node_id);
    for (uint32_t i = 0; i < deg; ++i) {
        const oe_node_id_t succ = oe_csr_successor_at(&eng->graph, node_id, i);
        if (succ >= eng->num_nodes) {
            continue;
        }
        oe_node_desc *d = &eng->nodes[succ];
        if (d->pruned || d->state == OE_STATE_DONE) {
            continue;
        }
        if (d->preds_remaining < d->preds_total) {
            d->preds_remaining++;
        }
        if (d->preds_remaining > 0 && d->state == OE_STATE_READY) {
            d->state = OE_STATE_PENDING;
        }
        eng->stats.speculation_rollbacks++;
    }
}

static void apply_scatter(
    oe_engine_sim *eng, oe_node_id_t completed, uint8_t speculative) {
    const uint32_t deg = oe_csr_out_degree(&eng->graph, completed);
    eng->stats.scatter_cycles++;

    for (uint32_t i = 0; i < deg && i < OE_MAX_SUCCESSORS; ++i) {
        const oe_node_id_t succ = oe_csr_successor_at(&eng->graph, completed, i);
        if (succ >= eng->num_nodes) {
            continue;
        }
        oe_node_desc *d = &eng->nodes[succ];
        if (d->pruned || d->state == OE_STATE_DONE || d->state == OE_STATE_OUTSTANDING) {
            continue;
        }

        switch (d->fire_mode) {
        case OE_FIRE_ANY_OF:
            mark_ready(eng, succ);
            break;
        case OE_FIRE_THRESHOLD:
            if (d->preds_remaining > 0) {
                d->preds_remaining--;
            }
            if (d->preds_remaining <= d->fire_threshold) {
                d->preds_remaining = 0;
                mark_ready(eng, succ);
            }
            break;
        case OE_FIRE_ALL_OF:
        default:
            if (d->preds_remaining > 0) {
                d->preds_remaining--;
            }
            if (d->preds_remaining == 0) {
                mark_ready(eng, succ);
            }
            break;
        }
    }
}

static void process_completions(oe_engine_sim *eng) {
    for (uint32_t i = 0; i < OE_MAX_OUTSTANDING; ++i) {
        if (!eng->mshr[i].valid) {
            continue;
        }
        if (eng->cycle < eng->mshr[i].done_cycle) {
            continue;
        }

        const oe_node_id_t nid = eng->mshr[i].node_id;
        oe_node_desc *n = &eng->nodes[nid];
        if (n->pruned) {
            rollback_speculation(eng, nid);
            eng->mshr[i].valid = 0;
            eng->mshr_count--;
            continue;
        }

        n->state = OE_STATE_DONE;
        eng->stats.nodes_completed++;
        apply_scatter(eng, nid, eng->mshr[i].speculative);
        eng->mshr[i].valid = 0;
        eng->mshr_count--;
    }
}

static void dispatch_ready(oe_engine_sim *eng) {
    oe_node_id_t id;
    while (ready_pop(eng, &id)) {
        oe_node_desc *n = &eng->nodes[id];
        if (n->pruned || n->state != OE_STATE_READY) {
            continue;
        }

        if (n->kind != OE_KIND_COORDINATION) {
            const int slot = mshr_alloc(eng);
            if (slot < 0) {
                (void)ready_push(eng, id);
                return;
            }
            const oe_cycle_t lat = n->predicted_latency > 0 ? n->predicted_latency : 1;
            eng->mshr[slot].node_id = id;
            eng->mshr[slot].result_handle = eng->next_handle++;
            eng->mshr[slot].issue_cycle = eng->cycle;
            eng->mshr[slot].done_cycle = eng->cycle + lat;
            eng->mshr[slot].valid = 1;
            eng->mshr[slot].speculative =
                n->speculation_eligible && (lat <= OE_LATENCY_MAX_CYCLES / 4);
            eng->mshr_count++;
            if (eng->mshr_count > eng->stats.mshr_peak) {
                eng->stats.mshr_peak = eng->mshr_count;
            }
        } else {
            n->state = OE_STATE_DONE;
            eng->stats.nodes_completed++;
            apply_scatter(eng, id, 0);
        }

        n->state = (n->kind == OE_KIND_COORDINATION) ? OE_STATE_DONE : OE_STATE_OUTSTANDING;
        eng->stats.nodes_dispatched++;
        eng->stats.dispatch_cycles++;

        switch (n->kind) {
        case OE_KIND_TOOL:
            eng->stats.tool_dispatches++;
            break;
        case OE_KIND_COORDINATION:
            eng->stats.coord_dispatches++;
            break;
        default:
            eng->stats.compute_dispatches++;
            break;
        }
    }
}

static void process_graph_ops(oe_engine_sim *eng) {
    while (eng->op_count > 0) {
        const oe_graph_op op = eng->op_queue[eng->op_head];
        eng->op_head = (eng->op_head + 1) % OE_GRAPH_OP_QUEUE;
        eng->op_count--;
        eng->stats.graph_mut_cycles++;

        switch (op.kind) {
        case OE_OP_APPEND_NODE:
            (void)oe_sim_add_node(
                eng,
                op.node_a,
                op.node_kind,
                op.fire_mode,
                op.fire_threshold,
                op.predicted_latency,
                1);
            break;
        case OE_OP_APPEND_EDGE:
            (void)oe_sim_add_edge(eng, op.node_a, op.node_b);
            break;
        case OE_OP_SET_FIRE_MODE:
            if (op.node_a < eng->num_nodes) {
                eng->nodes[op.node_a].fire_mode = op.fire_mode;
                eng->nodes[op.node_a].fire_threshold = op.fire_threshold;
            }
            break;
        case OE_OP_PRUNE_SUBTREE:
            if (op.node_a < eng->num_nodes) {
                eng->nodes[op.node_a].pruned = 1;
                eng->nodes[op.node_a].state = OE_STATE_PRUNED;
                rollback_speculation(eng, op.node_a);
            }
            break;
        default:
            break;
        }
    }
}

static int is_quiescent(const oe_engine_sim *eng) {
    if (eng->ready_count > 0 || eng->mshr_count > 0 || eng->op_count > 0) {
        return 0;
    }
    for (oe_node_id_t i = 0; i < eng->num_nodes; ++i) {
        const oe_node_desc *n = &eng->nodes[i];
        if (n->pruned) {
            continue;
        }
        if (n->state != OE_STATE_DONE) {
            return 0;
        }
    }
    return eng->num_nodes > 0;
}

void oe_sim_init(oe_engine_sim *eng) {
    memset(eng, 0, sizeof(*eng));
    oe_csr_init(&eng->graph);
    eng->next_handle = 1;
}

void oe_sim_reset(oe_engine_sim *eng) {
    oe_sim_init(eng);
}

int oe_sim_add_node(
    oe_engine_sim *eng,
    oe_node_id_t id,
    oe_node_kind kind,
    oe_fire_mode mode,
    uint16_t threshold,
    oe_cycle_t predicted_latency,
    uint8_t speculation_eligible) {
    if (id >= OE_MAX_NODES) {
        return -1;
    }
    if (id >= eng->num_nodes) {
        eng->num_nodes = id + 1;
    }
    oe_node_desc *n = &eng->nodes[id];
    n->id = id;
    n->kind = kind;
    n->fire_mode = mode;
    n->fire_threshold = threshold;
    n->preds_remaining = 0;
    n->preds_total = 0;
    n->state = OE_STATE_PENDING;
    n->predicted_latency = predicted_latency;
    n->speculation_eligible = speculation_eligible;
    n->pruned = 0;
    return 0;
}

int oe_sim_add_edge(oe_engine_sim *eng, oe_node_id_t src, oe_node_id_t dst) {
    if (oe_csr_append_edge(&eng->graph, src, dst) != 0) {
        return -1;
    }
    if (dst >= eng->num_nodes) {
        eng->num_nodes = dst + 1;
    }
    eng->nodes[dst].preds_total++;
    eng->nodes[dst].preds_remaining++;
    return 0;
}

int oe_sim_enqueue_op(oe_engine_sim *eng, const oe_graph_op *op) {
    if (eng->op_count >= OE_GRAPH_OP_QUEUE) {
        return -1;
    }
    eng->op_queue[eng->op_tail] = *op;
    eng->op_tail = (eng->op_tail + 1) % OE_GRAPH_OP_QUEUE;
    eng->op_count++;
    return 0;
}

void oe_sim_seed_ready(oe_engine_sim *eng, oe_node_id_t id) {
    if (id >= eng->num_nodes) {
        return;
    }
    eng->nodes[id].preds_remaining = 0;
    mark_ready(eng, id);
}

int oe_sim_step(oe_engine_sim *eng) {
    eng->cycle++;
    eng->stats.total_cycles = eng->cycle;

    process_graph_ops(eng);
    dispatch_ready(eng);
    process_completions(eng);

    if (is_quiescent(eng)) {
        eng->done = 1;
        return 0;
    }
    return 1;
}

oe_cycle_t oe_sim_run(oe_engine_sim *eng, oe_cycle_t max_cycles) {
    while (eng->cycle < max_cycles && oe_sim_step(eng)) {
    }
    return eng->cycle;
}

const oe_engine_stats *oe_sim_stats(const oe_engine_sim *eng) {
    return &eng->stats;
}
