#include "mp_layers.h"
#include <cstdio>
#include <cmath>

// GraphSAGE (mean) testbench: 6-node ring with self-loops, double golden.
#define N 6

int main() {
    static data_t   X[MP_MAX_NODES][MP_F];
    static weight_t Ws[MP_F][MP_F];
    static weight_t Wn[MP_F][MP_F];
    static weight_t bias[MP_F];
    static idx_t    row_ptr[MP_MAX_NODES + 1];
    static idx_t    col_idx[MP_MAX_EDGES];
    static data_t   Y[MP_MAX_NODES][MP_F];

    for (int i = 0; i < N; i++)
        for (int k = 0; k < MP_F; k++)
            X[i][k] = (data_t)(0.05 * ((i + 1) + 0.5 * k - 2.0));
    for (int k = 0; k < MP_F; k++)
        for (int o = 0; o < MP_F; o++) {
            Ws[k][o] = (weight_t)(0.02 * ((k - o) % 5) + 0.01 * o);
            Wn[k][o] = (weight_t)(0.015 * ((k + o) % 4) - 0.01 * k);
        }
    for (int o = 0; o < MP_F; o++)
        bias[o] = (weight_t)(0.01 * (o - 8));

    idx_t e = 0;
    for (int i = 0; i < N; i++) {
        row_ptr[i] = e;
        col_idx[e++] = (idx_t)i;
        col_idx[e++] = (idx_t)((i - 1 + N) % N);
        col_idx[e++] = (idx_t)((i + 1) % N);
    }
    row_ptr[N] = e;

    sage_layer(X, Ws, Wn, bias, row_ptr, col_idx, (idx_t)N, Y);

    double agg[N][MP_F], Y_g[N][MP_F];
    for (int i = 0; i < N; i++) {
        int deg = (int)(row_ptr[i + 1] - row_ptr[i]);
        for (int o = 0; o < MP_F; o++) agg[i][o] = 0.0;
        for (idx_t p = row_ptr[i]; p < row_ptr[i + 1]; p++) {
            int j = (int)col_idx[p];
            for (int o = 0; o < MP_F; o++) agg[i][o] += (double)X[j][o];
        }
        for (int o = 0; o < MP_F; o++) agg[i][o] /= (double)deg;
    }
    for (int i = 0; i < N; i++)
        for (int o = 0; o < MP_F; o++) {
            double acc = (double)bias[o];
            for (int k = 0; k < MP_F; k++)
                acc += (double)X[i][k] * (double)Ws[k][o] + agg[i][k] * (double)Wn[k][o];
            Y_g[i][o] = acc;
        }

    const double TOL = 0.05;
    double max_err = 0.0; int fails = 0;
    for (int i = 0; i < N; i++)
        for (int o = 0; o < MP_F; o++) {
            double err = std::fabs((double)Y[i][o] - Y_g[i][o]);
            if (err > max_err) max_err = err;
            if (err > TOL) { if (fails < 16) printf("MISMATCH Y[%d][%d]: %.5f vs %.5f\n", i, o, (double)Y[i][o], Y_g[i][o]); fails++; }
        }
    printf("----------------------------------------\n");
    printf("SAGE max abs error = %.6f (tol %.6f)\n", max_err, TOL);
    if (fails == 0) { printf("TEST PASSED\n"); return 0; }
    printf("TEST FAILED: %d element(s)\n", fails);
    return 1;
}
