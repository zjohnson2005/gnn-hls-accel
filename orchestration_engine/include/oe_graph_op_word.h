#ifndef OE_GRAPH_OP_WORD_H
#define OE_GRAPH_OP_WORD_H

// Packed graph-op word shared by software sim, cosim TB, and HLS graph_load.
// Layout (128 bits):
//   [7:0]     kind  (0xFF = stream end)
//   [23:8]    node_a
//   [39:24]   node_b
//   [47:40]   node_kind
//   [49:48]   fire_mode
//   [65:50]   fire_threshold
//   [97:66]   predicted_latency

#include "oe_types.h"

#ifdef ORCHESTRATION_ENGINE_H
#include "ap_int.h"
#else
#include <stdint.h>
typedef struct oe_graph_op_word {
    uint64_t lo;
    uint64_t hi;
} oe_graph_op_word_t;
#endif

#define OE_OP_WORD_END 0xFFu

static inline oe_graph_op_word_t oe_op_word_pack(const oe_graph_op *op) {
#ifdef ORCHESTRATION_ENGINE_H
    oe_graph_op_word_t w = 0;
    w.range(7, 0) = (ap_uint<8>)op->kind;
    w.range(23, 8) = (ap_uint<16>)op->node_a;
    w.range(39, 24) = (ap_uint<16>)op->node_b;
    w.range(47, 40) = (ap_uint<8>)op->node_kind;
    w.range(49, 48) = (ap_uint<2>)op->fire_mode;
    w.range(65, 50) = (ap_uint<16>)op->fire_threshold;
    w.range(97, 66) = (ap_uint<32>)op->predicted_latency;
    return w;
#else
    oe_graph_op_word_t w;
    w.lo = 0;
    w.hi = 0;
    w.lo |= (uint64_t)(uint8_t)op->kind;
    w.lo |= (uint64_t)(uint16_t)op->node_a << 8;
    w.lo |= (uint64_t)(uint16_t)op->node_b << 24;
    w.lo |= (uint64_t)(uint8_t)op->node_kind << 40;
    w.lo |= (uint64_t)(uint8_t)op->fire_mode << 48;
    w.lo |= (uint64_t)(uint16_t)op->fire_threshold << 50;
    w.hi |= ((uint64_t)(uint32_t)op->predicted_latency) << 2;
    return w;
#endif
}

static inline oe_graph_op_word_t oe_op_word_end(void) {
#ifdef ORCHESTRATION_ENGINE_H
    oe_graph_op_word_t w = 0;
    w.range(7, 0) = (ap_uint<8>)OE_OP_WORD_END;
    return w;
#else
    oe_graph_op_word_t w;
    w.lo = OE_OP_WORD_END;
    w.hi = 0;
    return w;
#endif
}

#endif // OE_GRAPH_OP_WORD_H
