"""B4: dependency-free graph-regression QoR surrogate.

A full per-candidate evaluation in DSE is, in the real flow, hours of HLS
synthesis + 3D place-and-route. The surrogate learns design-graph -> QoR so the
co-design loop can score thousands of candidates cheaply -- this is the 2D->3D
extension of the lui-gnn / wa-hls4ml surrogate line.

This implementation is a ridge regression over pooled graph features, written in
pure standard-library Python (no numpy / torch) so it runs anywhere the cost
model does. It is intentionally a strong, no-dependency *baseline* for the GNN
surrogate: the roadmap notes labeled 3D data barely exists, so an analytical /
classical predictor that needs no data stack is the right first rung. The
feature vector is exactly what a graph-pooling GNN surrogate would consume, so
swapping in a learned GNN later is a drop-in replacement for `Surrogate`.

    python -m cost_model_3d.surrogate        # trains on the B4 corpus, reports error
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Sequence, Tuple

from .sweep import SweepRecord, run_sweep

# Targets the surrogate predicts (the expensive labels).
TARGETS = ["energy3d_nj", "latency3d_ns", "temp3d_c"]


def featurize(r: SweepRecord) -> List[float]:
    """Pooled graph features. Large magnitudes are log-compressed so the linear
    model is well conditioned; this mirrors graph-pooling readout features."""
    return [
        math.log1p(r.macs_total),
        math.log1p(r.mem_bytes_total),
        math.log1p(r.seam_bits_parallel),
        math.log1p(r.seam_bits_total),
        r.compute_memory_ratio,
        float(r.data_bits),
        float(r.edges_per_node),
        math.log1p(r.num_nodes),
    ]


# ---------------------------------------------------------------------------
# Minimal linear algebra (Gaussian elimination) -- small feature counts only.
# ---------------------------------------------------------------------------
def _solve(A: List[List[float]], b: List[float]) -> List[float]:
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            continue
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= pv
        for r in range(n):
            if r != col and M[r][col] != 0.0:
                f = M[r][col]
                for j in range(col, n + 1):
                    M[r][j] -= f * M[col][j]
    return [M[i][n] for i in range(n)]


def _ridge_fit(X: List[List[float]], y: List[float], lam: float) -> List[float]:
    """Return weights (with bias as last term) for [X|1] -> y."""
    Xa = [row + [1.0] for row in X]
    p = len(Xa[0])
    AtA = [[0.0] * p for _ in range(p)]
    Atb = [0.0] * p
    for i in range(len(Xa)):
        xi = Xa[i]
        yi = y[i]
        for a in range(p):
            Atb[a] += xi[a] * yi
            xa = xi[a]
            for b_ in range(p):
                AtA[a][b_] += xa * xi[b_]
    for a in range(p - 1):  # do not regularize the bias term
        AtA[a][a] += lam
    return _solve(AtA, Atb)


def _standardizer(X: List[List[float]]) -> Tuple[Callable, List[float], List[float]]:
    p = len(X[0])
    n = len(X)
    mean = [sum(row[j] for row in X) / n for j in range(p)]
    var = [sum((row[j] - mean[j]) ** 2 for row in X) / max(1, n - 1) for j in range(p)]
    std = [math.sqrt(v) if v > 1e-12 else 1.0 for v in var]

    def apply(row: Sequence[float]) -> List[float]:
        return [(row[j] - mean[j]) / std[j] for j in range(p)]

    return apply, mean, std


@dataclass
class Surrogate:
    weights: dict           # target -> weight vector (last term is bias)
    standardize: Callable

    def predict(self, r: SweepRecord) -> dict:
        x = self.standardize(featurize(r))
        out = {}
        for t, w in self.weights.items():
            out[t] = sum(x[i] * w[i] for i in range(len(x))) + w[-1]
        return out


def train(records: List[SweepRecord], lam: float = 1.0) -> Surrogate:
    X = [featurize(r) for r in records]
    std_fn, _, _ = _standardizer(X)
    Xs = [std_fn(row) for row in X]
    weights = {}
    for t in TARGETS:
        y = [getattr(r, t) for r in records]
        weights[t] = _ridge_fit(Xs, y, lam)
    return Surrogate(weights=weights, standardize=std_fn)


def evaluate_accuracy(model: Surrogate, records: List[SweepRecord]) -> dict:
    """Mean absolute and mean relative error per target on `records`."""
    report = {}
    for t in TARGETS:
        abs_err = 0.0
        rel_err = 0.0
        for r in records:
            pred = model.predict(r)[t]
            true = getattr(r, t)
            abs_err += abs(pred - true)
            rel_err += abs(pred - true) / (abs(true) + 1e-9)
        n = len(records)
        report[t] = {"mae": abs_err / n, "mre_pct": 100.0 * rel_err / n}
    return report


def main() -> None:
    recs = run_sweep()
    # deterministic train/test split (every 4th sample held out)
    test = recs[::4]
    train_set = [r for i, r in enumerate(recs) if i % 4 != 0]

    model = train(train_set, lam=1.0)
    rep = evaluate_accuracy(model, test)

    print(f"=== B4 QoR surrogate (ridge over graph features) ===")
    print(f"train={len(train_set)}  test={len(test)}  features={len(featurize(recs[0]))}\n")
    print("target        MAE          mean-rel-err")
    print("-" * 44)
    for t in TARGETS:
        print(f"{t:<12} {rep[t]['mae']:>10.4f}   {rep[t]['mre_pct']:>8.2f}%")
    print("\nUse Surrogate.predict() in place of tier_model.evaluate() inside the "
          "DSE inner loop; retrain on csynth+P&R labels when available.")


if __name__ == "__main__":
    main()
