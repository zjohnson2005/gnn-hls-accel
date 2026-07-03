#include "gcn_layer.h"
#include <cstdio>
#include <cmath>

// ----------------------------------------------------------------------------
// Testbench: 6-node ring graph with self-loops (A + I).
//   Ring edges: i <-> (i+1) mod N, plus a self-loop on every node.
//   => deg_i = 3 for all i, so every normalization coefficient c(i,j) = 1/3.
//
//   The golden reference recomputes the layer in double precision and we
//   compare against the ap_fixed kernel output within an absolute tolerance.
// ----------------------------------------------------------------------------

#define N 6   // actual number of nodes used (<= MAX_NODES)

int main() {
    // ---- Host-side graph (CSR with self-loops baked in) ----
    static data_t   X[MAX_NODES][F_IN];
    static weight_t W[F_IN][F_OUT];
    static weight_t bias[F_OUT];
    static idx_t    row_ptr[MAX_NODES + 1];
    static idx_t    col_idx[MAX_EDGES];
    static data_t   Y[MAX_NODES][F_OUT];

    // Deterministic node features in a modest range.
    for (int i = 0; i < N; i++)
        for (int k = 0; k < F_IN; k++)
            X[i][k] = (data_t)(0.1 * ((i + 1) + 0.5 * k - 2.0));

    // Deterministic weights / bias.
    for (int k = 0; k < F_IN; k++)
        for (int o = 0; o < F_OUT; o++)
            W[k][o] = (weight_t)(0.05 * ((k - o) % 5) + 0.02 * o);
    for (int o = 0; o < F_OUT; o++)
        bias[o] = (weight_t)(0.01 * (o - 8));

    // Build CSR: for each node push {self, left, right}.
    idx_t e = 0;
    for (int i = 0; i < N; i++) {
        row_ptr[i] = e;
        int left  = (i - 1 + N) % N;
        int right = (i + 1) % N;
        col_idx[e++] = (idx_t)i;      // self-loop
        col_idx[e++] = (idx_t)left;
        col_idx[e++] = (idx_t)right;
    }
    row_ptr[N] = e;

    // ---- Run the kernel under test ----
    gcn_layer(X, W, bias, row_ptr, col_idx, (idx_t)N, Y);

    // ---- Double-precision golden ----
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

    // ---- Compare ----
    // Strict by default (baseline reference). The precision sweep overrides this
    // with -DGCN_TB_TOL=... so narrow-precision arms record their accuracy via
    // "max abs error" instead of aborting csim (the degradation is the result).
#ifndef GCN_TB_TOL
#define GCN_TB_TOL 0.03            // ap_fixed<16,6> has ~2^-10 resolution; allow margin
#endif
    const double TOL = GCN_TB_TOL;
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
    if (fails == 0) {
        printf("TEST PASSED\n");
        return 0;
    } else {
        printf("TEST FAILED: %d element(s) out of tolerance\n", fails);
        return 1;
    }
}
