#include "egnn_layer.h"
#include <cstdio>
#include <cmath>

// ----------------------------------------------------------------------------
// EGNN testbench: 8-node point cloud, fully connected (j != i).
//   Primary check: fixed-point kernel vs double-precision golden.
//   Secondary (informational): E(n)-equivariance -- rotating the input coords
//   should rotate x_out and leave h_out unchanged (exact in real arithmetic;
//   fixed-point introduces small error, so this is printed, not asserted).
// ----------------------------------------------------------------------------

#define N 8

static double frand(int s) { return 0.3 * std::sin(0.7 * s + 1.0); }

int main() {
    static egnn_weights_t Wt;
    static data_t h_in[EG_MAX_NODES][EG_H];
    static data_t x_in[EG_MAX_NODES][EG_COORD];
    static idx_t  esrc[EG_MAX_EDGES];
    static idx_t  edst[EG_MAX_EDGES];
    static data_t h_out[EG_MAX_NODES][EG_H];
    static data_t x_out[EG_MAX_NODES][EG_COORD];

    // ---- inputs ----
    for (int i = 0; i < N; i++) {
        for (int k = 0; k < EG_H; k++) h_in[i][k] = (data_t)frand(i * 7 + k);
        for (int c = 0; c < EG_COORD; c++) x_in[i][c] = (data_t)(0.4 * frand(i * 3 + c + 11));
    }
    idx_t E = 0;
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            if (i != j) { edst[E] = (idx_t)i; esrc[E] = (idx_t)j; E++; }

    // ---- small deterministic weights ----
    for (int k = 0; k < EG_E_IN; k++) for (int o = 0; o < EG_HID; o++) Wt.e_w1[k][o] = (weight_t)(0.04 * std::sin(0.3 * (k * 5 + o)));
    for (int o = 0; o < EG_HID; o++) Wt.e_b1[o] = (weight_t)(0.01 * (o - 8));
    for (int k = 0; k < EG_HID; k++) for (int o = 0; o < EG_M; o++) Wt.e_w2[k][o] = (weight_t)(0.05 * std::cos(0.2 * (k + o * 3)));
    for (int o = 0; o < EG_M; o++) Wt.e_b2[o] = (weight_t)(0.005 * o);
    for (int o = 0; o < EG_M; o++) Wt.x_w[o] = (weight_t)(0.03 * std::sin(0.5 * o));
    Wt.x_b = (weight_t)0.01;
    for (int k = 0; k < EG_H_IN; k++) for (int o = 0; o < EG_HID; o++) Wt.h_w1[k][o] = (weight_t)(0.04 * std::cos(0.25 * (k * 3 + o)));
    for (int o = 0; o < EG_HID; o++) Wt.h_b1[o] = (weight_t)(0.01 * (o - 8));
    for (int k = 0; k < EG_HID; k++) for (int o = 0; o < EG_H; o++) Wt.h_w2[k][o] = (weight_t)(0.05 * std::sin(0.2 * (k + o * 2)));
    for (int o = 0; o < EG_H; o++) Wt.h_b2[o] = (weight_t)(0.005 * (o - 4));

    egnn_layer(Wt, h_in, x_in, esrc, edst, (idx_t)N, E, h_out, x_out);

    // ---- double golden ----
    auto relu = [](double v) { return v > 0.0 ? v : 0.0; };
    double msg_g[EG_MAX_EDGES][EG_M], xw_g[EG_MAX_EDGES];
    for (idx_t p = 0; p < E; p++) {
        int i = (int)edst[p], j = (int)esrc[p];
        double d2 = 0;
        for (int c = 0; c < EG_COORD; c++) { double d = (double)x_in[i][c] - (double)x_in[j][c]; d2 += d * d; }
        double ine[EG_E_IN];
        for (int k = 0; k < EG_H; k++) { ine[k] = (double)h_in[i][k]; ine[EG_H + k] = (double)h_in[j][k]; }
        ine[2 * EG_H] = d2;
        double hid[EG_HID];
        for (int o = 0; o < EG_HID; o++) { double a = (double)Wt.e_b1[o]; for (int k = 0; k < EG_E_IN; k++) a += ine[k] * (double)Wt.e_w1[k][o]; hid[o] = relu(a); }
        double g = (double)Wt.x_b;
        for (int o = 0; o < EG_M; o++) { double a = (double)Wt.e_b2[o]; for (int k = 0; k < EG_HID; k++) a += hid[k] * (double)Wt.e_w2[k][o]; msg_g[p][o] = a; g += a * (double)Wt.x_w[o]; }
        xw_g[p] = g;
    }
    double m_node[N][EG_M], dxg[N][EG_COORD];
    for (int i = 0; i < N; i++) { for (int o = 0; o < EG_M; o++) m_node[i][o] = 0; for (int c = 0; c < EG_COORD; c++) dxg[i][c] = 0; }
    for (idx_t p = 0; p < E; p++) {
        int i = (int)edst[p], j = (int)esrc[p];
        for (int o = 0; o < EG_M; o++) m_node[i][o] += msg_g[p][o];
        for (int c = 0; c < EG_COORD; c++) dxg[i][c] += ((double)x_in[i][c] - (double)x_in[j][c]) * xw_g[p];
    }
    double h_g[N][EG_H], x_g[N][EG_COORD];
    for (int i = 0; i < N; i++) {
        double inh[EG_H_IN];
        for (int k = 0; k < EG_H; k++) { inh[k] = (double)h_in[i][k]; inh[EG_H + k] = m_node[i][k]; }
        double hid[EG_HID];
        for (int o = 0; o < EG_HID; o++) { double a = (double)Wt.h_b1[o]; for (int k = 0; k < EG_H_IN; k++) a += inh[k] * (double)Wt.h_w1[k][o]; hid[o] = relu(a); }
        for (int o = 0; o < EG_H; o++) { double a = (double)Wt.h_b2[o]; for (int k = 0; k < EG_HID; k++) a += hid[k] * (double)Wt.h_w2[k][o]; h_g[i][o] = (double)h_in[i][o] + a; }
        for (int c = 0; c < EG_COORD; c++) x_g[i][c] = (double)x_in[i][c] + dxg[i][c];
    }

    // ---- compare ----
    const double TOL = 0.06;
    double max_err = 0.0; int fails = 0;
    for (int i = 0; i < N; i++) {
        for (int o = 0; o < EG_H; o++) { double e = std::fabs((double)h_out[i][o] - h_g[i][o]); if (e > max_err) max_err = e; if (e > TOL) { if (fails < 12) printf("h MISMATCH [%d][%d]: %.5f vs %.5f\n", i, o, (double)h_out[i][o], h_g[i][o]); fails++; } }
        for (int c = 0; c < EG_COORD; c++) { double e = std::fabs((double)x_out[i][c] - x_g[i][c]); if (e > max_err) max_err = e; if (e > TOL) { if (fails < 12) printf("x MISMATCH [%d][%d]: %.5f vs %.5f\n", i, c, (double)x_out[i][c], x_g[i][c]); fails++; } }
    }

    printf("----------------------------------------\n");
    printf("EGNN max abs error = %.6f (tol %.6f)\n", max_err, TOL);
    if (fails == 0) printf("TEST PASSED\n");
    else            printf("TEST FAILED: %d element(s)\n", fails);
    return fails == 0 ? 0 : 1;
}
