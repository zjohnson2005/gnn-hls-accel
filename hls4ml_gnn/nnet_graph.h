#ifndef NNET_GRAPH_H_
#define NNET_GRAPH_H_

// ============================================================================
// hls4ml message-passing kernel for the GNN extension.
//
// This is the backend C++ source registered into hls4ml via
// `backend.register_source(...)`. It is the same gather/combine/aggregate math
// as our standalone src/mp_template.h, re-expressed in hls4ml's nnet idiom:
// a single `CONFIG_T`-templated function whose sizes and data types come from
// the config struct emitted by GraphConvConfigTemplate.
//
// Fixed-graph assumption: the adjacency is baked in as a (constant) weight, so
// the layer is a single-input/single-output node, which is what lets it flow
// through hls4ml's io_parallel writer like any other layer. This matches the
// fixed-topology graphs common in hls4ml's physics use cases.
//
//   aggregation = agg_sum   y_i = sum_{j: A_ij!=0} c_ij * comb_j
//   aggregation = agg_mean  y_i = (1/deg_i) sum_j comb_j
//   aggregation = agg_max   y_i = max_{j: A_ij!=0} comb_j   (elementwise)
//   normalize=true          c_ij = d_i^-0.5 d_j^-0.5  (symmetric GCN)
//   normalize=false         c_ij = A_ij               (raw adjacency weight)
// ============================================================================

#include "nnet_common.h"
#include <cmath>

namespace nnet {

enum graph_agg_t { agg_sum = 0, agg_mean = 1, agg_max = 2 };

struct graph_conv_config {
    // Internal data types (overridden by the generated config struct)
    typedef float accum_t;
    typedef float weight_t;
    typedef float bias_t;
    typedef float adj_t;

    // Layer sizes
    static const unsigned n_node = 4;
    static const unsigned n_in = 4;
    static const unsigned n_out = 4;
    static const unsigned n_edge = 8; // max edges (dynamic-graph kernel only)

    // Message-passing semantics
    static const unsigned aggregation = agg_sum;
    static const bool normalize = false;

    // hls4ml common knobs
    static const unsigned io_type = nnet::io_parallel;
    static const unsigned reuse_factor = 1;
    static const bool store_weights_in_bram = false;
};

template <class data_T, class res_T, typename CONFIG_T>
void graph_conv(data_T data[CONFIG_T::n_node * CONFIG_T::n_in],
                res_T res[CONFIG_T::n_node * CONFIG_T::n_out],
                typename CONFIG_T::weight_t weights[CONFIG_T::n_in * CONFIG_T::n_out],
                typename CONFIG_T::bias_t biases[CONFIG_T::n_out],
                typename CONFIG_T::adj_t adjacency[CONFIG_T::n_node * CONFIG_T::n_node]) {

    typedef typename CONFIG_T::accum_t accum_t;
    typedef typename CONFIG_T::adj_t adj_t;

    const unsigned N = CONFIG_T::n_node;
    const unsigned FI = CONFIG_T::n_in;
    const unsigned FO = CONFIG_T::n_out;

    // ---- combine: per-node linear  comb[i][o] = sum_k x[i][k] * W[k][o]  (bias post-agg) ----
    accum_t comb[CONFIG_T::n_node][CONFIG_T::n_out];
    #pragma HLS ARRAY_PARTITION variable=comb complete dim=2

combine_node:
    for (unsigned i = 0; i < N; i++) {
    combine_out:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS PIPELINE II=1
            accum_t acc = (accum_t)0;
        combine_in:
            for (unsigned k = 0; k < FI; k++) {
                #pragma HLS UNROLL
                acc += (accum_t)(data[i * FI + k] * weights[k * FO + o]);
            }
            comb[i][o] = acc;
        }
    }

    // ---- symmetric-normalization coefficients (only when normalize=true) ----
    accum_t dinv[CONFIG_T::n_node];
    #pragma HLS ARRAY_PARTITION variable=dinv complete dim=1
    if (CONFIG_T::normalize) {
    norm_deg:
        for (unsigned i = 0; i < N; i++) {
            #pragma HLS PIPELINE II=1
            accum_t deg = 0;
            for (unsigned j = 0; j < N; j++) {
                #pragma HLS UNROLL
                if (adjacency[i * N + j] != (adj_t)0)
                    deg += (accum_t)1;
            }
            dinv[i] = (deg > 0) ? (accum_t)(1.0 / std::sqrt((double)deg)) : (accum_t)0;
        }
    }

    // ---- aggregate over neighbors ----
aggregate_node:
    for (unsigned i = 0; i < N; i++) {
        accum_t acc[CONFIG_T::n_out];
        #pragma HLS ARRAY_PARTITION variable=acc complete dim=1
    agg_init:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            acc[o] = (CONFIG_T::aggregation == nnet::agg_max) ? (accum_t)(-1e30) : (accum_t)0;
        }

        unsigned deg = 0;
    agg_neighbor:
        for (unsigned j = 0; j < N; j++) {
            #pragma HLS PIPELINE II=1
            adj_t a = adjacency[i * N + j];
            if (a == (adj_t)0)
                continue;
            deg++;
            accum_t coeff = CONFIG_T::normalize ? (accum_t)(dinv[i] * dinv[j]) : (accum_t)a;
        agg_feat:
            for (unsigned o = 0; o < FO; o++) {
                #pragma HLS UNROLL
                if (CONFIG_T::aggregation == nnet::agg_max) {
                    if (comb[j][o] > acc[o])
                        acc[o] = comb[j][o];
                } else {
                    acc[o] += (accum_t)(coeff * comb[j][o]);
                }
            }
        }

    agg_store:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            accum_t out = acc[o];
            if (CONFIG_T::aggregation == nnet::agg_mean && deg > 0)
                out = (accum_t)(out / (accum_t)deg);
            // PyG convention: bias is applied once per node, after aggregation
            out += (accum_t)biases[o];
            res[i * FO + o] = (res_T)out;
        }
    }
}

// ============================================================================
// Dynamic-graph message passing: the connectivity arrives at runtime as a COO
// edge_index (PyG convention), so the SAME compiled accelerator handles any
// graph up to (n_node, n_edge). This is the real GNN bar -- edge_index is an
// input port, not baked-in weights.
//
//   edge_index layout: flat [2 * n_edge], row 0 = source, row 1 = target,
//                      i.e. src(e) = edge_index[e], dst(e) = edge_index[n_edge + e]
//   variable edges:    pad unused slots with an out-of-range index (>= n_node);
//                      such slots are skipped, so any graph up to n_edge works
//                      with a pure tensor interface (no runtime scalar arg).
//
//   y_d = AGG_{e: dst(e)=d} c * comb[src(e)]
//   normalize=true  c = deg(src)^-0.5 * deg(dst)^-0.5   (symmetric GCN)
// ============================================================================
template <class data_T, class index_T, class res_T, typename CONFIG_T>
void graph_conv_dynamic(data_T data[CONFIG_T::n_node * CONFIG_T::n_in],
                        index_T edge_index[2 * CONFIG_T::n_edge],
                        res_T res[CONFIG_T::n_node * CONFIG_T::n_out],
                        typename CONFIG_T::weight_t weights[CONFIG_T::n_in * CONFIG_T::n_out],
                        typename CONFIG_T::bias_t biases[CONFIG_T::n_out]) {

    typedef typename CONFIG_T::accum_t accum_t;

    const unsigned N = CONFIG_T::n_node;
    const unsigned FI = CONFIG_T::n_in;
    const unsigned FO = CONFIG_T::n_out;
    const unsigned E = CONFIG_T::n_edge;

    // ---- combine: comb[i][o] = sum_k x[i][k] * W[k][o]  (bias added post-agg) ----
    accum_t comb[CONFIG_T::n_node][CONFIG_T::n_out];
    #pragma HLS ARRAY_PARTITION variable=comb complete dim=2
dyn_combine_node:
    for (unsigned i = 0; i < N; i++) {
    dyn_combine_out:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS PIPELINE II=1
            accum_t acc = (accum_t)0;
        dyn_combine_in:
            for (unsigned k = 0; k < FI; k++) {
                #pragma HLS UNROLL
                acc += (accum_t)(data[i * FI + k] * weights[k * FO + o]);
            }
            comb[i][o] = acc;
        }
    }

    // ---- degree pass (in-degree per target node) ----
    unsigned deg[CONFIG_T::n_node];
    #pragma HLS ARRAY_PARTITION variable=deg complete dim=1
dyn_deg_init:
    for (unsigned i = 0; i < N; i++) {
        #pragma HLS UNROLL
        deg[i] = 0;
    }
dyn_deg_count:
    for (unsigned e = 0; e < E; e++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=E
        unsigned d = (unsigned)edge_index[E + e];
        if (d < N)
            deg[d]++;
    }

    accum_t dinv[CONFIG_T::n_node];
    #pragma HLS ARRAY_PARTITION variable=dinv complete dim=1
    if (CONFIG_T::normalize) {
    dyn_dinv:
        for (unsigned i = 0; i < N; i++) {
            #pragma HLS UNROLL
            dinv[i] = (deg[i] > 0) ? (accum_t)(1.0 / std::sqrt((double)deg[i])) : (accum_t)0;
        }
    }

    // ---- init outputs ----
    accum_t out[CONFIG_T::n_node][CONFIG_T::n_out];
    #pragma HLS ARRAY_PARTITION variable=out complete dim=2
dyn_out_init:
    for (unsigned i = 0; i < N; i++) {
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            out[i][o] = (CONFIG_T::aggregation == nnet::agg_max) ? (accum_t)(-1e30) : (accum_t)0;
        }
    }

    // ---- scatter-aggregate over edges ----
dyn_scatter:
    for (unsigned e = 0; e < E; e++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=E
        unsigned s = (unsigned)edge_index[e];
        unsigned d = (unsigned)edge_index[E + e];
        if (s >= N || d >= N)
            continue;
        accum_t coeff = CONFIG_T::normalize ? (accum_t)(dinv[s] * dinv[d]) : (accum_t)1;
    dyn_scatter_feat:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            if (CONFIG_T::aggregation == nnet::agg_max) {
                if (comb[s][o] > out[d][o])
                    out[d][o] = comb[s][o];
            } else {
                out[d][o] += (accum_t)(coeff * comb[s][o]);
            }
        }
    }

    // ---- finalize (mean divides by degree) and write ----
dyn_store_node:
    for (unsigned i = 0; i < N; i++) {
    dyn_store_feat:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            accum_t v = out[i][o];
            if (CONFIG_T::aggregation == nnet::agg_mean && deg[i] > 0)
                v = (accum_t)(v / (accum_t)deg[i]);
            if (CONFIG_T::aggregation == nnet::agg_max && deg[i] == 0)
                v = (accum_t)0;
            // PyG convention: bias is applied once per node, after aggregation
            v += (accum_t)biases[o];
            res[i * FO + o] = (res_T)v;
        }
    }
}

// ============================================================================
// GraphSAGE message passing (dynamic graph). Two weight matrices:
//   W_l (neighbor / "lin_l") and W_r (root-self / "lin_r"), PyG SAGEConv:
//     out_i = AGG_{j in N(i)}(x_j W_l) + x_i W_r + b
//   aggregation = mean (default) or sum. No symmetric normalization, no
//   self-loops in edge_index (the self term is the explicit root weight).
// ============================================================================
template <class data_T, class index_T, class res_T, typename CONFIG_T>
void graph_sage_dynamic(data_T data[CONFIG_T::n_node * CONFIG_T::n_in],
                        index_T edge_index[2 * CONFIG_T::n_edge],
                        res_T res[CONFIG_T::n_node * CONFIG_T::n_out],
                        typename CONFIG_T::weight_t weights[CONFIG_T::n_in * CONFIG_T::n_out],
                        typename CONFIG_T::weight_t root_weights[CONFIG_T::n_in * CONFIG_T::n_out],
                        typename CONFIG_T::bias_t biases[CONFIG_T::n_out]) {

    typedef typename CONFIG_T::accum_t accum_t;

    const unsigned N = CONFIG_T::n_node;
    const unsigned FI = CONFIG_T::n_in;
    const unsigned FO = CONFIG_T::n_out;
    const unsigned E = CONFIG_T::n_edge;

    // ---- neighbor transform comb[i] = x_i W_l  and  root[i] = x_i W_r ----
    accum_t comb[CONFIG_T::n_node][CONFIG_T::n_out];
    accum_t root[CONFIG_T::n_node][CONFIG_T::n_out];
    #pragma HLS ARRAY_PARTITION variable=comb complete dim=2
    #pragma HLS ARRAY_PARTITION variable=root complete dim=2
sage_combine_node:
    for (unsigned i = 0; i < N; i++) {
    sage_combine_out:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS PIPELINE II=1
            accum_t an = 0;
            accum_t ar = 0;
        sage_combine_in:
            for (unsigned k = 0; k < FI; k++) {
                #pragma HLS UNROLL
                data_T xv = data[i * FI + k];
                an += (accum_t)(xv * weights[k * FO + o]);
                ar += (accum_t)(xv * root_weights[k * FO + o]);
            }
            comb[i][o] = an;
            root[i][o] = ar;
        }
    }

    // ---- degree (in-degree per target) ----
    unsigned deg[CONFIG_T::n_node];
    #pragma HLS ARRAY_PARTITION variable=deg complete dim=1
sage_deg_init:
    for (unsigned i = 0; i < N; i++) {
        #pragma HLS UNROLL
        deg[i] = 0;
    }
sage_deg_count:
    for (unsigned e = 0; e < E; e++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=E
        unsigned d = (unsigned)edge_index[E + e];
        if (d < N)
            deg[d]++;
    }

    // ---- scatter-aggregate neighbor transforms ----
    accum_t out[CONFIG_T::n_node][CONFIG_T::n_out];
    #pragma HLS ARRAY_PARTITION variable=out complete dim=2
sage_out_init:
    for (unsigned i = 0; i < N; i++) {
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            out[i][o] = (accum_t)0;
        }
    }
sage_scatter:
    for (unsigned e = 0; e < E; e++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=E
        unsigned s = (unsigned)edge_index[e];
        unsigned d = (unsigned)edge_index[E + e];
        if (s >= N || d >= N)
            continue;
    sage_scatter_feat:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            out[d][o] += comb[s][o];
        }
    }

    // ---- finalize: mean over neighbors + root self-term + bias ----
sage_store_node:
    for (unsigned i = 0; i < N; i++) {
    sage_store_feat:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            accum_t v = out[i][o];
            if (CONFIG_T::aggregation == nnet::agg_mean && deg[i] > 0)
                v = (accum_t)(v / (accum_t)deg[i]);
            v += root[i][o];
            v += (accum_t)biases[o];
            res[i * FO + o] = (res_T)v;
        }
    }
}

// ============================================================================
// GINConv aggregation (dynamic graph), no weights:
//     agg_i = self_coeff * x_i + sum_{j in N(i)} x_j      (self_coeff = 1 + eps)
// The learnable MLP that GINConv applies afterwards is emitted as ordinary
// hls4ml Dense/activation layers, so only this weightless aggregation is
// custom. n_in == n_out (aggregation preserves feature width).
// ============================================================================
template <class data_T, class index_T, class res_T, typename CONFIG_T>
void graph_gin_aggregate(data_T data[CONFIG_T::n_node * CONFIG_T::n_in],
                         index_T edge_index[2 * CONFIG_T::n_edge],
                         res_T res[CONFIG_T::n_node * CONFIG_T::n_out],
                         typename CONFIG_T::accum_t self_coeff) {

    typedef typename CONFIG_T::accum_t accum_t;

    const unsigned N = CONFIG_T::n_node;
    const unsigned F = CONFIG_T::n_in; // n_in == n_out
    const unsigned E = CONFIG_T::n_edge;

    accum_t acc[CONFIG_T::n_node][CONFIG_T::n_in];
    #pragma HLS ARRAY_PARTITION variable=acc complete dim=2

    // init with the scaled self term (1+eps) * x_i
gin_self:
    for (unsigned i = 0; i < N; i++) {
        for (unsigned f = 0; f < F; f++) {
            #pragma HLS UNROLL
            acc[i][f] = (accum_t)(self_coeff * (accum_t)data[i * F + f]);
        }
    }

    // sum (add) over neighbors
gin_scatter:
    for (unsigned e = 0; e < E; e++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=E
        unsigned s = (unsigned)edge_index[e];
        unsigned d = (unsigned)edge_index[E + e];
        if (s >= N || d >= N)
            continue;
    gin_scatter_feat:
        for (unsigned f = 0; f < F; f++) {
            #pragma HLS UNROLL
            acc[d][f] += (accum_t)data[s * F + f];
        }
    }

gin_store:
    for (unsigned i = 0; i < N; i++) {
        for (unsigned f = 0; f < F; f++) {
            #pragma HLS UNROLL
            res[i * F + f] = (res_T)acc[i][f];
        }
    }
}

// ============================================================================
// Full GINConv (dynamic graph) with a 2-layer ReLU MLP, self-contained so it
// synthesizes without relying on per-node native Dense:
//     agg_i = (1+eps) x_i + sum_{j in N(i)} x_j           [N, n_in]
//     h_i   = relu(agg_i W1 + b1)                         [N, n_hidden]
//     out_i = h_i W2 + b2                                 [N, n_out]
// W1: [n_in, n_hidden], W2: [n_hidden, n_out].
// ============================================================================
template <class data_T, class index_T, class res_T, typename CONFIG_T>
void graph_gin_conv_dynamic(data_T data[CONFIG_T::n_node * CONFIG_T::n_in],
                            index_T edge_index[2 * CONFIG_T::n_edge],
                            res_T res[CONFIG_T::n_node * CONFIG_T::n_out],
                            typename CONFIG_T::weight_t weights1[CONFIG_T::n_in * CONFIG_T::n_hidden],
                            typename CONFIG_T::bias_t biases1[CONFIG_T::n_hidden],
                            typename CONFIG_T::weight_t weights2[CONFIG_T::n_hidden * CONFIG_T::n_out],
                            typename CONFIG_T::bias_t biases2[CONFIG_T::n_out],
                            typename CONFIG_T::accum_t self_coeff) {

    typedef typename CONFIG_T::accum_t accum_t;

    const unsigned N = CONFIG_T::n_node;
    const unsigned FI = CONFIG_T::n_in;
    const unsigned H = CONFIG_T::n_hidden;
    const unsigned FO = CONFIG_T::n_out;
    const unsigned E = CONFIG_T::n_edge;

    // ---- aggregate: agg_i = (1+eps) x_i + sum_j x_j ----
    accum_t agg[CONFIG_T::n_node][CONFIG_T::n_in];
    #pragma HLS ARRAY_PARTITION variable=agg complete dim=2
ginc_self:
    for (unsigned i = 0; i < N; i++) {
        for (unsigned f = 0; f < FI; f++) {
            #pragma HLS UNROLL
            agg[i][f] = (accum_t)(self_coeff * (accum_t)data[i * FI + f]);
        }
    }
ginc_scatter:
    for (unsigned e = 0; e < E; e++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=E
        unsigned s = (unsigned)edge_index[e];
        unsigned d = (unsigned)edge_index[E + e];
        if (s >= N || d >= N)
            continue;
        for (unsigned f = 0; f < FI; f++) {
            #pragma HLS UNROLL
            agg[d][f] += (accum_t)data[s * FI + f];
        }
    }

    // ---- MLP layer 1 + ReLU: h_i = relu(agg_i W1 + b1) ----
    accum_t hidden[CONFIG_T::n_node][CONFIG_T::n_hidden];
    #pragma HLS ARRAY_PARTITION variable=hidden complete dim=2
ginc_mlp1_node:
    for (unsigned i = 0; i < N; i++) {
    ginc_mlp1_out:
        for (unsigned o = 0; o < H; o++) {
            #pragma HLS PIPELINE II=1
            accum_t a = (accum_t)biases1[o];
        ginc_mlp1_in:
            for (unsigned k = 0; k < FI; k++) {
                #pragma HLS UNROLL
                a += (accum_t)(agg[i][k] * weights1[k * H + o]);
            }
            hidden[i][o] = (a > (accum_t)0) ? a : (accum_t)0; // ReLU
        }
    }

    // ---- MLP layer 2: out_i = h_i W2 + b2 ----
ginc_mlp2_node:
    for (unsigned i = 0; i < N; i++) {
    ginc_mlp2_out:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS PIPELINE II=1
            accum_t a = (accum_t)biases2[o];
        ginc_mlp2_in:
            for (unsigned k = 0; k < H; k++) {
                #pragma HLS UNROLL
                a += (accum_t)(hidden[i][k] * weights2[k * FO + o]);
            }
            res[i * FO + o] = (res_T)a;
        }
    }
}

// ============================================================================
// GATConv single-head attention (dynamic graph), PyG semantics:
//     h_i        = x_i W
//     e_ij       = LeakyReLU( a_src . h_src(e) + a_dst . h_dst(e) )
//     alpha_ij   = softmax_{e: dst=i}( e_ij )
//     out_i      = sum_{e: dst=i} alpha_ij * h_src(e)  + b
// att_src / att_dst are [n_out] attention vectors; leaky_slope is the
// LeakyReLU negative slope (default 0.2). Self-loops (GAT default) must be in
// edge_index. Softmax is over the in-edges of each target node.
// ============================================================================
template <class data_T, class index_T, class res_T, typename CONFIG_T>
void graph_gat_dynamic(data_T data[CONFIG_T::n_node * CONFIG_T::n_in],
                       index_T edge_index[2 * CONFIG_T::n_edge],
                       res_T res[CONFIG_T::n_node * CONFIG_T::n_out],
                       typename CONFIG_T::weight_t weights[CONFIG_T::n_in * CONFIG_T::n_out],
                       typename CONFIG_T::weight_t att_src[CONFIG_T::n_out],
                       typename CONFIG_T::weight_t att_dst[CONFIG_T::n_out],
                       typename CONFIG_T::bias_t biases[CONFIG_T::n_out],
                       typename CONFIG_T::accum_t leaky_slope) {

    typedef typename CONFIG_T::accum_t accum_t;

    const unsigned N = CONFIG_T::n_node;
    const unsigned FI = CONFIG_T::n_in;
    const unsigned FO = CONFIG_T::n_out;
    const unsigned E = CONFIG_T::n_edge;

    // ---- linear transform h = x W ----
    accum_t h[CONFIG_T::n_node][CONFIG_T::n_out];
    #pragma HLS ARRAY_PARTITION variable=h complete dim=2
gat_lin_node:
    for (unsigned i = 0; i < N; i++) {
    gat_lin_out:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS PIPELINE II=1
            accum_t a = 0;
            for (unsigned k = 0; k < FI; k++) {
                #pragma HLS UNROLL
                a += (accum_t)(data[i * FI + k] * weights[k * FO + o]);
            }
            h[i][o] = a;
        }
    }

    // ---- per-node attention projections a_src.h_i and a_dst.h_i ----
    accum_t asrc[CONFIG_T::n_node];
    accum_t adst[CONFIG_T::n_node];
    #pragma HLS ARRAY_PARTITION variable=asrc complete dim=1
    #pragma HLS ARRAY_PARTITION variable=adst complete dim=1
gat_attn_node:
    for (unsigned i = 0; i < N; i++) {
        #pragma HLS PIPELINE II=1
        accum_t s = 0, d = 0;
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            s += (accum_t)(h[i][o] * att_src[o]);
            d += (accum_t)(h[i][o] * att_dst[o]);
        }
        asrc[i] = s;
        adst[i] = d;
    }

    // ---- per-edge raw scores e_ij = LeakyReLU(asrc[s] + adst[d]) ----
    accum_t escore[CONFIG_T::n_edge];
    #pragma HLS ARRAY_PARTITION variable=escore complete dim=1
    accum_t emax[CONFIG_T::n_node];
    #pragma HLS ARRAY_PARTITION variable=emax complete dim=1
gat_emax_init:
    for (unsigned i = 0; i < N; i++) {
        #pragma HLS UNROLL
        emax[i] = (accum_t)(-1e30);
    }
gat_score:
    for (unsigned e = 0; e < E; e++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=E
        unsigned s = (unsigned)edge_index[e];
        unsigned d = (unsigned)edge_index[E + e];
        if (s >= N || d >= N) {
            escore[e] = (accum_t)(-1e30); // padded slot -> excluded from softmax
            continue;
        }
        accum_t z = asrc[s] + adst[d];
        accum_t lr = (z > (accum_t)0) ? z : (accum_t)(leaky_slope * z); // LeakyReLU
        escore[e] = lr;
        if (lr > emax[d])
            emax[d] = lr;
    }

    // ---- softmax denominators per target node ----
    accum_t denom[CONFIG_T::n_node];
    #pragma HLS ARRAY_PARTITION variable=denom complete dim=1
gat_denom_init:
    for (unsigned i = 0; i < N; i++) {
        #pragma HLS UNROLL
        denom[i] = (accum_t)0;
    }
gat_denom:
    for (unsigned e = 0; e < E; e++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=E
        unsigned d = (unsigned)edge_index[E + e];
        if (d >= N)
            continue;
        accum_t ex = (accum_t)std::exp((double)(escore[e] - emax[d]));
        denom[d] += ex;
    }

    // ---- weighted aggregation: out_d = sum_e (exp/denom) * h[s] ----
    accum_t out[CONFIG_T::n_node][CONFIG_T::n_out];
    #pragma HLS ARRAY_PARTITION variable=out complete dim=2
gat_out_init:
    for (unsigned i = 0; i < N; i++) {
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            out[i][o] = (accum_t)0;
        }
    }
gat_scatter:
    for (unsigned e = 0; e < E; e++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=E
        unsigned s = (unsigned)edge_index[e];
        unsigned d = (unsigned)edge_index[E + e];
        if (s >= N || d >= N)
            continue;
        accum_t ex = (accum_t)std::exp((double)(escore[e] - emax[d]));
        accum_t alpha = (denom[d] > (accum_t)0) ? (accum_t)(ex / denom[d]) : (accum_t)0;
    gat_scatter_feat:
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            out[d][o] += (accum_t)(alpha * h[s][o]);
        }
    }

gat_store:
    for (unsigned i = 0; i < N; i++) {
        for (unsigned o = 0; o < FO; o++) {
            #pragma HLS UNROLL
            res[i * FO + o] = (res_T)(out[i][o] + (accum_t)biases[o]);
        }
    }
}

// ============================================================================
// E(n)-equivariant GNN layer (EGNN, Satorras et al. 2021), dynamic graph.
// Three inputs: node features h [N, n_h], coordinates x [N, n_coord], and the
// COO edge_index. One concatenated output [N, n_h + n_coord] = [h' | x'].
//
//   m_e   = phi_e([h_d, h_s, ||x_d - x_s||^2])     (2-layer ReLU MLP -> n_msg)
//   w_e   = phi_x(m_e)                              (linear -> scalar)
//   m_i   = sum_{e: dst=i} m_e
//   dx_i  = sum_{e: dst=i} (x_i - x_s) * w_e
//   h_i'  = h_i + phi_h([h_i, m_i])                 (2-layer ReLU MLP -> n_h)
//   x_i'  = x_i + dx_i
// Equivariant: coords enter only via the invariant distance and move along
// relative vectors, so rotating/translating x rotates/translates x' and leaves
// h' unchanged.
// ============================================================================
template <class data_T, class index_T, class res_T, typename CONFIG_T>
void graph_egnn_dynamic(data_T h_in[CONFIG_T::n_node * CONFIG_T::n_h],
                        data_T x_in[CONFIG_T::n_node * CONFIG_T::n_coord],
                        index_T edge_index[2 * CONFIG_T::n_edge],
                        res_T res[CONFIG_T::n_node * (CONFIG_T::n_h + CONFIG_T::n_coord)],
                        typename CONFIG_T::weight_t e_w1[(2 * CONFIG_T::n_h + 1) * CONFIG_T::n_hidden],
                        typename CONFIG_T::bias_t e_b1[CONFIG_T::n_hidden],
                        typename CONFIG_T::weight_t e_w2[CONFIG_T::n_hidden * CONFIG_T::n_msg],
                        typename CONFIG_T::bias_t e_b2[CONFIG_T::n_msg],
                        typename CONFIG_T::weight_t x_w[CONFIG_T::n_msg],
                        typename CONFIG_T::bias_t x_b[1],
                        typename CONFIG_T::weight_t h_w1[(CONFIG_T::n_h + CONFIG_T::n_msg) * CONFIG_T::n_hidden],
                        typename CONFIG_T::bias_t h_b1[CONFIG_T::n_hidden],
                        typename CONFIG_T::weight_t h_w2[CONFIG_T::n_hidden * CONFIG_T::n_h],
                        typename CONFIG_T::bias_t h_b2[CONFIG_T::n_h]) {

    typedef typename CONFIG_T::accum_t accum_t;

    const unsigned N = CONFIG_T::n_node;
    const unsigned H = CONFIG_T::n_h;
    const unsigned C = CONFIG_T::n_coord;
    const unsigned M = CONFIG_T::n_msg;
    const unsigned HID = CONFIG_T::n_hidden;
    const unsigned E = CONFIG_T::n_edge;
    const unsigned EIN = 2 * H + 1;
    const unsigned FO = H + C;

    // message + coordinate-delta accumulators
    accum_t m_node[CONFIG_T::n_node][CONFIG_T::n_msg];
    accum_t dx[CONFIG_T::n_node][CONFIG_T::n_coord];
    #pragma HLS ARRAY_PARTITION variable=m_node complete dim=2
    #pragma HLS ARRAY_PARTITION variable=dx complete dim=2
egnn_acc_init:
    for (unsigned i = 0; i < N; i++) {
        for (unsigned o = 0; o < M; o++) {
            #pragma HLS UNROLL
            m_node[i][o] = (accum_t)0;
        }
        for (unsigned c = 0; c < C; c++) {
            #pragma HLS UNROLL
            dx[i][c] = (accum_t)0;
        }
    }

    // ---- per-edge edge-MLP phi_e + coordinate gate phi_x, then scatter ----
egnn_edge:
    for (unsigned e = 0; e < E; e++) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=E
        unsigned s = (unsigned)edge_index[e];
        unsigned d = (unsigned)edge_index[E + e];
        if (s >= N || d >= N)
            continue;

        // invariant squared distance ||x_d - x_s||^2 and relative vector
        accum_t dist2 = 0;
        accum_t rel[CONFIG_T::n_coord];
        #pragma HLS ARRAY_PARTITION variable=rel complete dim=1
        for (unsigned c = 0; c < C; c++) {
            #pragma HLS UNROLL
            accum_t r = (accum_t)x_in[d * C + c] - (accum_t)x_in[s * C + c];
            rel[c] = r;
            dist2 += (accum_t)(r * r);
        }

        // phi_e layer 1 + ReLU:  in = [h_d, h_s, dist2]  (len 2H+1)
        accum_t hid[CONFIG_T::n_hidden];
        #pragma HLS ARRAY_PARTITION variable=hid complete dim=1
        for (unsigned o = 0; o < HID; o++) {
            #pragma HLS UNROLL
            accum_t a = (accum_t)e_b1[o];
            for (unsigned k = 0; k < H; k++) {
                #pragma HLS UNROLL
                a += (accum_t)(h_in[d * H + k] * e_w1[k * HID + o]);          // h_d
                a += (accum_t)(h_in[s * H + k] * e_w1[(H + k) * HID + o]);    // h_s
            }
            a += (accum_t)(dist2 * e_w1[(2 * H) * HID + o]);                  // dist2
            hid[o] = (a > (accum_t)0) ? a : (accum_t)0;
        }

        // phi_e layer 2 (linear) -> message m_e [M]; and phi_x -> scalar gate
        accum_t wcoef = (accum_t)x_b[0];
        for (unsigned o = 0; o < M; o++) {
            #pragma HLS UNROLL
            accum_t me = (accum_t)e_b2[o];
            for (unsigned k = 0; k < HID; k++) {
                #pragma HLS UNROLL
                me += (accum_t)(hid[k] * e_w2[k * M + o]);
            }
            m_node[d][o] += me;                       // aggregate message
            wcoef += (accum_t)(me * x_w[o]);          // phi_x linear gate
        }

        // coordinate delta along the relative vector
        for (unsigned c = 0; c < C; c++) {
            #pragma HLS UNROLL
            dx[d][c] += (accum_t)(rel[c] * wcoef);
        }
    }

    // ---- node update phi_h and residual adds, write [h' | x'] ----
egnn_node:
    for (unsigned i = 0; i < N; i++) {
        // phi_h layer 1 + ReLU:  in = [h_i, m_i]  (len H+M)
        accum_t hid2[CONFIG_T::n_hidden];
        #pragma HLS ARRAY_PARTITION variable=hid2 complete dim=1
        for (unsigned o = 0; o < HID; o++) {
            #pragma HLS UNROLL
            accum_t a = (accum_t)h_b1[o];
            for (unsigned k = 0; k < H; k++) {
                #pragma HLS UNROLL
                a += (accum_t)(h_in[i * H + k] * h_w1[k * HID + o]);
            }
            for (unsigned k = 0; k < M; k++) {
                #pragma HLS UNROLL
                a += (accum_t)(m_node[i][k] * h_w1[(H + k) * HID + o]);
            }
            hid2[o] = (a > (accum_t)0) ? a : (accum_t)0;
        }

        // phi_h layer 2 -> dh, residual h' = h + dh
        for (unsigned o = 0; o < H; o++) {
            #pragma HLS UNROLL
            accum_t dh = (accum_t)h_b2[o];
            for (unsigned k = 0; k < HID; k++) {
                #pragma HLS UNROLL
                dh += (accum_t)(hid2[k] * h_w2[k * H + o]);
            }
            res[i * FO + o] = (res_T)((accum_t)h_in[i * H + o] + dh);
        }

        // x' = x + dx
        for (unsigned c = 0; c < C; c++) {
            #pragma HLS UNROLL
            res[i * FO + H + c] = (res_T)((accum_t)x_in[i * C + c] + dx[i][c]);
        }
    }
}

} // namespace nnet

#endif // NNET_GRAPH_H_
