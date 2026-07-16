"""Prefill/decode/network calibration artifacts for TurnTrace v2."""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class FitReport:
    model_name: str
    params: dict[str, float]
    r2_train: float
    r2_held_out: float
    residuals: list[float]
    passed_r2_gate: bool


@dataclass
class PrefillProfile:
    """f(n): prefill time (ms) vs context tokens."""

    model_id: str
    quantization: str
    engine: str
    hardware: str
    points: list[tuple[int, float]] = field(default_factory=list)
    quadratic: FitReport | None = None
    piecewise: FitReport | None = None
    power_mode_w: float | None = None

    def add_observation(self, n_tokens: int, t_prefill_ms: float) -> None:
        self.points.append((int(n_tokens), float(t_prefill_ms)))

    def fit(self, *, held_out_fraction: float = 0.2, r2_gate: float = 0.99, seed: int = 0) -> None:
        if len(self.points) < 5:
            raise ValueError("need >=5 prefill points to fit")
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        idx = list(range(len(xs)))
        rng = random.Random(seed)
        rng.shuffle(idx)
        n_hold = max(1, int(round(len(idx) * held_out_fraction)))
        hold = set(idx[:n_hold])
        train_x = [xs[i] for i in idx if i not in hold]
        train_y = [ys[i] for i in idx if i not in hold]
        hold_x = [xs[i] for i in idx if i in hold]
        hold_y = [ys[i] for i in idx if i in hold]

        quad = _fit_quadratic(train_x, train_y)
        self.quadratic = FitReport(
            model_name="quadratic",
            params=quad,
            r2_train=_r2(train_y, [_quad_eval(quad, x) for x in train_x]),
            r2_held_out=_r2(hold_y, [_quad_eval(quad, x) for x in hold_x]),
            residuals=[y - _quad_eval(quad, x) for x, y in zip(xs, ys)],
            passed_r2_gate=False,
        )
        self.quadratic = FitReport(
            **{**asdict(self.quadratic), "passed_r2_gate": self.quadratic.r2_held_out >= r2_gate}
        )

        pw = _fit_piecewise_linear(train_x, train_y)
        pred_train = [_piecewise_eval(pw, x) for x in train_x]
        pred_hold = [_piecewise_eval(pw, x) for x in hold_x]
        self.piecewise = FitReport(
            model_name="piecewise_linear",
            params={"n_segments": float(len(pw) - 1)},
            r2_train=_r2(train_y, pred_train),
            r2_held_out=_r2(hold_y, pred_hold),
            residuals=[y - _piecewise_eval(pw, x) for x, y in zip(xs, ys)],
            passed_r2_gate=_r2(hold_y, pred_hold) >= r2_gate,
        )
        self._piecewise_knots = pw  # type: ignore[attr-defined]

    def predict_ms(self, n_tokens: int, *, prefer: str | None = None) -> float:
        """Predict prefill ms. Prefer piecewise when it passed the R² gate."""
        n = max(0, int(n_tokens))
        choice = prefer
        if choice is None:
            if self.piecewise and self.piecewise.passed_r2_gate and getattr(
                self, "_piecewise_knots", None
            ):
                choice = "piecewise"
            else:
                choice = "quadratic"
        if choice == "piecewise" and getattr(self, "_piecewise_knots", None):
            return _piecewise_eval(self._piecewise_knots, n)  # type: ignore[attr-defined]
        if self.quadratic is None:
            raise RuntimeError("profile not fitted")
        return _quad_eval(self.quadratic.params, n)

    def acceptance_passed(self) -> bool:
        return bool(
            (self.quadratic and self.quadratic.passed_r2_gate)
            or (self.piecewise and self.piecewise.passed_r2_gate)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "quantization": self.quantization,
            "engine": self.engine,
            "hardware": self.hardware,
            "power_mode_w": self.power_mode_w,
            "points": [{"n": n, "t_prefill_ms": t} for n, t in self.points],
            "quadratic": asdict(self.quadratic) if self.quadratic else None,
            "piecewise": asdict(self.piecewise) if self.piecewise else None,
            "acceptance_passed": self.acceptance_passed(),
        }


@dataclass
class DecodeProfile:
    """g(m): decode time vs output length at fixed KV depths."""

    model_id: str
    quantization: str
    engine: str
    hardware: str
    # (kv_depth, tokens_out, tokens_per_sec)
    points: list[tuple[int, int, float]] = field(default_factory=list)

    def add_observation(self, *, kv_depth: int, tokens_out: int, tokens_per_sec: float) -> None:
        self.points.append((int(kv_depth), int(tokens_out), float(tokens_per_sec)))

    def tokens_per_sec_at(self, kv_depth: int) -> float:
        if not self.points:
            raise RuntimeError("decode profile empty")
        # Nearest KV depth average.
        depths = sorted({p[0] for p in self.points})
        nearest = min(depths, key=lambda d: abs(d - kv_depth))
        rates = [p[2] for p in self.points if p[0] == nearest]
        return sum(rates) / len(rates)

    def predict_decode_ms(self, tokens_out: float, *, kv_depth: int) -> float:
        rate = self.tokens_per_sec_at(kv_depth)
        if rate <= 0:
            return float("inf")
        return 1000.0 * float(tokens_out) / rate

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "quantization": self.quantization,
            "engine": self.engine,
            "hardware": self.hardware,
            "points": [
                {"kv_depth": d, "tokens_out": m, "tokens_per_sec": r}
                for d, m, r in self.points
            ],
        }


@dataclass
class NetworkBaseline:
    endpoint_id: str
    samples_ms: list[float] = field(default_factory=list)
    tod_slots: list[str] = field(default_factory=list)

    def add_probe(self, rtt_ms: float, *, tod_slot: str) -> None:
        self.samples_ms.append(float(rtt_ms))
        if tod_slot not in self.tod_slots:
            self.tod_slots.append(tod_slot)

    def summary(self) -> dict[str, Any]:
        xs = sorted(self.samples_ms)
        if not xs:
            raise RuntimeError("no network probes")
        return {
            "endpoint_id": self.endpoint_id,
            "n": len(xs),
            "tod_slots": list(self.tod_slots),
            "median_ms": _percentile(xs, 0.50),
            "p95_ms": _percentile(xs, 0.95),
            "variance": _variance(xs),
            "meets_min_probes": len(xs) >= 100,
            "meets_tod_slots": len(self.tod_slots) >= 3,
        }


def synthesize_prefill_sweep(
    *,
    true_a: float = 1e-8,
    true_b: float = 2e-3,
    true_c: float = 0.5,
    noise_std: float = 0.05,
    n_grid: Sequence[int] | None = None,
    reps: int = 10,
    seed: int = 0,
) -> PrefillProfile:
    """Generate a near-deterministic synthetic sweep for CI (R² gate must pass)."""
    grid = list(n_grid or [256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536])
    rng = random.Random(seed)
    profile = PrefillProfile(
        model_id="synthetic-local",
        quantization="fp16",
        engine="mock",
        hardware="ci",
        power_mode_w=120.0,
    )
    for n in grid:
        mean = true_a * (n**2) + true_b * n + true_c
        for _ in range(reps):
            profile.add_observation(n, max(0.0, rng.gauss(mean, noise_std)))
    profile.fit(held_out_fraction=0.2, r2_gate=0.99, seed=seed)
    return profile


def synthesize_decode_profile(*, seed: int = 0) -> DecodeProfile:
    rng = random.Random(seed)
    profile = DecodeProfile(
        model_id="synthetic-local",
        quantization="fp16",
        engine="mock",
        hardware="ci",
    )
    for depth, base_rate in ((0, 80.0), (8192, 60.0), (32768, 40.0), (65536, 25.0)):
        for m in (16, 64, 256):
            profile.add_observation(
                kv_depth=depth,
                tokens_out=m,
                tokens_per_sec=max(1.0, rng.gauss(base_rate, 1.0)),
            )
    return profile


def _quad_eval(params: Mapping[str, float], x: float) -> float:
    return params["a"] * (x**2) + params["b"] * x + params["c"]


def _fit_quadratic(xs: Sequence[float], ys: Sequence[float]) -> dict[str, float]:
    # Normal equations for y = a x^2 + b x + c
    n = len(xs)
    s1 = float(n)
    sx = sum(xs)
    sx2 = sum(x * x for x in xs)
    sx3 = sum(x**3 for x in xs)
    sx4 = sum(x**4 for x in xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2y = sum((x * x) * y for x, y in zip(xs, ys))
    # Solve 3x3 via Cramer's / Gaussian elimination
    mat = [
        [sx4, sx3, sx2, sx2y],
        [sx3, sx2, sx, sxy],
        [sx2, sx, s1, sy],
    ]
    a, b, c = _solve3(mat)
    return {"a": a, "b": b, "c": c}


def _solve3(aug: list[list[float]]) -> tuple[float, float, float]:
    m = [row[:] for row in aug]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        div = m[col][col]
        if abs(div) < 1e-18:
            return 0.0, 0.0, sum(row[3] for row in m) / 3.0
        for j in range(col, 4):
            m[col][j] /= div
        for r in range(3):
            if r == col:
                continue
            factor = m[r][col]
            for j in range(col, 4):
                m[r][j] -= factor * m[col][j]
    return m[0][3], m[1][3], m[2][3]


def _fit_piecewise_linear(
    xs: Sequence[float], ys: Sequence[float]
) -> list[tuple[float, float]]:
    paired = sorted(zip(xs, ys), key=lambda p: p[0])
    # Average y per unique x, then connect.
    buckets: dict[float, list[float]] = {}
    for x, y in paired:
        buckets.setdefault(float(x), []).append(float(y))
    knots = [(x, sum(vs) / len(vs)) for x, vs in sorted(buckets.items())]
    if len(knots) == 1:
        knots = [(0.0, knots[0][1]), knots[0]]
    return knots


def _piecewise_eval(knots: Sequence[tuple[float, float]], x: float) -> float:
    if x <= knots[0][0]:
        return knots[0][1]
    if x >= knots[-1][0]:
        # Extrapolate with last segment slope.
        x0, y0 = knots[-2]
        x1, y1 = knots[-1]
        if x1 == x0:
            return y1
        return y1 + (y1 - y0) * (x - x1) / (x1 - x0)
    for i in range(1, len(knots)):
        x0, y0 = knots[i - 1]
        x1, y1 = knots[i]
        if x0 <= x <= x1:
            if x1 == x0:
                return y1
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return knots[-1][1]


def _r2(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    if not y_true:
        return 0.0
    mean = sum(y_true) / len(y_true)
    ss_tot = sum((y - mean) ** 2 for y in y_true)
    ss_res = sum((y - p) ** 2 for y, p in zip(y_true, y_pred))
    if ss_tot <= 1e-18:
        return 1.0 if ss_res <= 1e-18 else 0.0
    return 1.0 - ss_res / ss_tot


def _percentile(sorted_xs: Sequence[float], q: float) -> float:
    if not sorted_xs:
        return float("nan")
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    pos = q * (len(sorted_xs) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_xs[lo]
    w = pos - lo
    return sorted_xs[lo] * (1 - w) + sorted_xs[hi] * w


def _variance(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    return sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
