#include "gcn_layer_stream.h"
#include <cstdio>
#include <cmath>

// ----------------------------------------------------------------------------
// Testbench for the DATAFLOW/streaming GCN layer (A3).
// Identical 6-node ring + double-precision golden as the baseline TB, so the
// streaming top must reproduce the baseline output within the same tolerance.
// ----------------------------------------------------------------------------

#define N 6

int main() {
    static data_t   X[MAX_NODES][F_IN];
    static weight_t W[F_IN][F_OUT];
    static weight_t bias[F_OUT];
    static idx_t    row_ptr[MAX_NODES + 1];
    static idx_t    col_idx[MAX_EDGES];
    static data_t   Y[MAX_NODES][F_OUT];

    for (int i = 0; i < N; i++)
        for (int k = 0; k < F_IN; k++)
            X[i][k] = (data_t)(0.1 * ((i + 1) + 0.5 * k - 2.0));

    for (int k = 0; k < F_IN; k++)
        for (int o = 0; o < F_OUT; o++)
            W[k][o] = (weight_t)(0.05 * ((k - o) % 5) + 0.02 * o);
    for (int o = 0; o < F_OUT; o++)
        bias[o] = (weight_t)(0.01 * (o - 8));

    idx_t e = 0;
    for (int i = 0; i < N; i++) {
        row_ptr[i] = e;
        int left  = (i - 1 + N) % N;
        int right = (i + 1) % N;
        col_idx[e++] = (idx_t)i;
        col_idx[e++] = (idx_t)left;
        col_idx[e++] = (idx_t)right;
    }
    row_ptr[N] = e;

#ifdef GNN_LS_LITE
    gcn_layer_stream(&X[0][0], &W[0][0], bias, row_ptr, col_idx, (idx_t)N, &Y[0][0]);
#else
    gcn_layer_stream(X, W, bias, row_ptr, col_idx, (idx_t)N, Y);
#endif

    double Xt_g[N][F_OUT];
    for (int i = 0; i < N; i++)
        for (int o = 0; o < F_OUT; o++) {
            double acc = (double)bias[o];
            for (int k = 0; k < F_IN; k++)
                acc += (double)X[i][k] * (double)W[k][o];
            Xt_g[i][o] = acc;
        }

    double inv_sqrt_deg_g[N];
    for (int i = 0; i < N; i++) {
        int deg = (int)(row_ptr[i + 1] - row_ptr[i]);
        inv_sqrt_deg_g[i] = (deg == 0) ? 0.0 : 1.0 / std::sqrt((double)deg);
    }

    double Y_g[N][F_OUT];
    for (int i = 0; i < N; i++) {
        for (int o = 0; o < F_OUT; o++) Y_g[i][o] = 0.0;
        for (idx_t p = row_ptr[i]; p < row_ptr[i + 1]; p++) {
            int j = (int)col_idx[p];
            double c = inv_sqrt_deg_g[i] * inv_sqrt_deg_g[j];
            for (int o = 0; o < F_OUT; o++)
                Y_g[i][o] += c * Xt_g[j][o];
        }
    }

    const double TOL = 0.03;
    double max_err = 0.0;
    int    fails   = 0;
    for (int i = 0; i < N; i++) {
        for (int o = 0; o < F_OUT; o++) {
            double got = (double)Y[i][o];
            double err = std::fabs(got - Y_g[i][o]);
            if (err > max_err) max_err = err;
            if (err > TOL) {
                if (fails < 16)
                    printf("MISMATCH Y[%d][%d]: got %.6f  expected %.6f  err %.6f\n",
                           i, o, got, Y_g[i][o], err);
                fails++;
            }
        }
    }

    printf("----------------------------------------\n");
    printf("max abs error = %.6f (tol %.6f)\n", max_err, TOL);
    if (fails == 0) { printf("TEST PASSED\n"); return 0; }
    printf("TEST FAILED: %d element(s) out of tolerance\n", fails);
    return 1;
}
