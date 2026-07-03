#include "egnn_layer.h"

static inline data_t relu(acc_t v) {
#pragma HLS INLINE
    return (v > (acc_t)0) ? (data_t)v : (data_t)0;
}

// ----------------------------------------------------------------------------
// k_mlp1 -- edge MLP phi_e + coordinate gate phi_x (compute-bound).
//   For each edge p = (j -> i): build [h_i, h_j, dist2], run the 2-layer ReLU
//   MLP to a message msg[p], then the linear gate to a scalar xw[p].
// ----------------------------------------------------------------------------
static void k_mlp1(
    const egnn_weights_t &Wt,
    const data_t          h_in[EG_MAX_NODES][EG_H],
    const data_t          x_in[EG_MAX_NODES][EG_COORD],
    const idx_t           edge_src[EG_MAX_EDGES],
    const idx_t           edge_dst[EG_MAX_EDGES],
    idx_t                 num_edges,
    data_t                msg[EG_MAX_EDGES][EG_M],
    data_t                xw[EG_MAX_EDGES])
{
#pragma HLS ARRAY_PARTITION variable=Wt.e_w1 complete dim=2
#pragma HLS ARRAY_PARTITION variable=Wt.e_w2 complete dim=1
#pragma HLS ARRAY_PARTITION variable=h_in    complete dim=2
#pragma HLS ARRAY_PARTITION variable=x_in    complete dim=2

mlp1_edges:
    for (idx_t p = 0; p < num_edges; p++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=EG_MAX_EDGES
        idx_t i = edge_dst[p];
        idx_t j = edge_src[p];

        // invariant squared distance
        acc_t d2 = 0;
    dist:
        for (int c = 0; c < EG_COORD; c++) {
#pragma HLS UNROLL
            data_t diff = (data_t)(x_in[i][c] - x_in[j][c]);
            d2 += (acc_t)(diff * diff);
        }

        data_t in_e[EG_E_IN];
#pragma HLS ARRAY_PARTITION variable=in_e complete dim=1
    pack:
        for (int k = 0; k < EG_H; k++) {
#pragma HLS UNROLL
            in_e[k]        = h_in[i][k];
            in_e[EG_H + k] = h_in[j][k];
        }
        in_e[2 * EG_H] = (data_t)d2;

        // hidden = ReLU(W1^T in + b1)
        data_t hid[EG_HID];
#pragma HLS ARRAY_PARTITION variable=hid complete dim=1
    e_hidden:
        for (int o = 0; o < EG_HID; o++) {
#pragma HLS PIPELINE II=1
            acc_t a = (acc_t)Wt.e_b1[o];
            for (int k = 0; k < EG_E_IN; k++) {
#pragma HLS UNROLL
                a += (acc_t)(in_e[k] * Wt.e_w1[k][o]);
            }
            hid[o] = relu(a);
        }

        // message = W2^T hidden + b2
    e_out:
        for (int o = 0; o < EG_M; o++) {
#pragma HLS PIPELINE II=1
            acc_t a = (acc_t)Wt.e_b2[o];
            for (int k = 0; k < EG_HID; k++) {
#pragma HLS UNROLL
                a += (acc_t)(hid[k] * Wt.e_w2[k][o]);
            }
            msg[p][o] = (data_t)a;
        }

        // coordinate gate xw = phi_x(message)
        acc_t g = (acc_t)Wt.x_b;
    e_gate:
        for (int o = 0; o < EG_M; o++) {
#pragma HLS UNROLL
            g += (acc_t)(msg[p][o] * Wt.x_w[o]);
        }
        xw[p] = (data_t)g;
    }
}

// ----------------------------------------------------------------------------
// k_magg -- message + coordinate aggregation (memory-bound scatter).
//   m_i  += msg[p]                          for every edge p with dst i
//   dx_i += (x_i - x_j) * xw[p]
// ----------------------------------------------------------------------------
static void k_magg(
    const data_t  x_in[EG_MAX_NODES][EG_COORD],
    const idx_t   edge_src[EG_MAX_EDGES],
    const idx_t   edge_dst[EG_MAX_EDGES],
    const data_t  msg[EG_MAX_EDGES][EG_M],
    const data_t  xw[EG_MAX_EDGES],
    idx_t         num_nodes,
    idx_t         num_edges,
    data_t        m_node[EG_MAX_NODES][EG_M],
    data_t        dx[EG_MAX_NODES][EG_COORD])
{
#pragma HLS ARRAY_PARTITION variable=m_node complete dim=2
#pragma HLS ARRAY_PARTITION variable=dx     complete dim=2
#pragma HLS ARRAY_PARTITION variable=x_in   complete dim=2

magg_clear:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=EG_MAX_NODES
#pragma HLS PIPELINE II=1
        for (int o = 0; o < EG_M; o++) {
#pragma HLS UNROLL
            m_node[i][o] = (data_t)0;
        }
        for (int c = 0; c < EG_COORD; c++) {
#pragma HLS UNROLL
            dx[i][c] = (data_t)0;
        }
    }

magg_edges:
    for (idx_t p = 0; p < num_edges; p++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=EG_MAX_EDGES
        idx_t i = edge_dst[p];
        idx_t j = edge_src[p];
    magg_msg:
        for (int o = 0; o < EG_M; o++) {
#pragma HLS UNROLL
            m_node[i][o] = (data_t)(m_node[i][o] + msg[p][o]);
        }
        data_t w = xw[p];
    magg_coord:
        for (int c = 0; c < EG_COORD; c++) {
#pragma HLS UNROLL
            data_t rel = (data_t)(x_in[i][c] - x_in[j][c]);
            dx[i][c] = (data_t)(dx[i][c] + (data_t)(rel * w));
        }
    }
}

// ----------------------------------------------------------------------------
// k_mlp2 -- node MLP phi_h + residual updates (compute-bound).
//   h_i' = h_i + phi_h([h_i, m_i]),   x_i' = x_i + dx_i
// ----------------------------------------------------------------------------
static void k_mlp2(
    const egnn_weights_t &Wt,
    const data_t          h_in[EG_MAX_NODES][EG_H],
    const data_t          x_in[EG_MAX_NODES][EG_COORD],
    const data_t          m_node[EG_MAX_NODES][EG_M],
    const data_t          dx[EG_MAX_NODES][EG_COORD],
    idx_t                 num_nodes,
    data_t                h_out[EG_MAX_NODES][EG_H],
    data_t                x_out[EG_MAX_NODES][EG_COORD])
{
#pragma HLS ARRAY_PARTITION variable=Wt.h_w1 complete dim=2
#pragma HLS ARRAY_PARTITION variable=Wt.h_w2 complete dim=1
#pragma HLS ARRAY_PARTITION variable=h_in    complete dim=2
#pragma HLS ARRAY_PARTITION variable=m_node  complete dim=2

mlp2_nodes:
    for (idx_t i = 0; i < num_nodes; i++) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=EG_MAX_NODES
        data_t in_h[EG_H_IN];
#pragma HLS ARRAY_PARTITION variable=in_h complete dim=1
    pack_h:
        for (int k = 0; k < EG_H; k++) {
#pragma HLS UNROLL
            in_h[k]        = h_in[i][k];
            in_h[EG_H + k] = m_node[i][k];
        }

        data_t hid[EG_HID];
#pragma HLS ARRAY_PARTITION variable=hid complete dim=1
    h_hidden:
        for (int o = 0; o < EG_HID; o++) {
#pragma HLS PIPELINE II=1
            acc_t a = (acc_t)Wt.h_b1[o];
            for (int k = 0; k < EG_H_IN; k++) {
#pragma HLS UNROLL
                a += (acc_t)(in_h[k] * Wt.h_w1[k][o]);
            }
            hid[o] = relu(a);
        }

    h_out_feat:
        for (int o = 0; o < EG_H; o++) {
#pragma HLS PIPELINE II=1
            acc_t a = (acc_t)Wt.h_b2[o];
            for (int k = 0; k < EG_HID; k++) {
#pragma HLS UNROLL
                a += (acc_t)(hid[k] * Wt.h_w2[k][o]);
            }
            h_out[i][o] = (data_t)(h_in[i][o] + (data_t)a);   // residual
        }

    x_update:
        for (int c = 0; c < EG_COORD; c++) {
#pragma HLS UNROLL
            x_out[i][c] = (data_t)(x_in[i][c] + dx[i][c]);
        }
    }
}

// ----------------------------------------------------------------------------
// Top level. The three kernels are kept as separate tasks so Phase B can map
// k_mlp1/k_mlp2 (compute tier) and k_magg (near-memory tier) to different dies.
// ----------------------------------------------------------------------------
void egnn_layer(
    const egnn_weights_t &Wt,
    const data_t          h_in[EG_MAX_NODES][EG_H],
    const data_t          x_in[EG_MAX_NODES][EG_COORD],
    const idx_t           edge_src[EG_MAX_EDGES],
    const idx_t           edge_dst[EG_MAX_EDGES],
    idx_t                 num_nodes,
    idx_t                 num_edges,
    data_t                h_out[EG_MAX_NODES][EG_H],
    data_t                x_out[EG_MAX_NODES][EG_COORD])
{
    static data_t msg[EG_MAX_EDGES][EG_M];
    static data_t xw[EG_MAX_EDGES];
    static data_t m_node[EG_MAX_NODES][EG_M];
    static data_t dx[EG_MAX_NODES][EG_COORD];

    k_mlp1(Wt, h_in, x_in, edge_src, edge_dst, num_edges, msg, xw);
    k_magg(x_in, edge_src, edge_dst, msg, xw, num_nodes, num_edges, m_node, dx);
    k_mlp2(Wt, h_in, x_in, m_node, dx, num_nodes, h_out, x_out);
}
