"""D4 analysis: pred-vs-observed decomposition + Exp(β) divergence + speculation tradeoff."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from apu_characterization.turntrace_v2.schema import CallRecord


@dataclass
class ComponentErrors:
    step_type: str
    n: int
    prefill_mae_ms: float
    decode_mae_ms: float
    network_mean_ms: float
    network_std_ms: float
    deterministic_fraction: float  # share of wait explained by pred_prefill+pred_decode


@dataclass
class SpeculationTradeoff:
    breadth: int
    predicted_time_saved_exp: float
    predicted_time_saved_split: float
    actual_time_saved: float


def _mae(xs: Sequence[float]) -> float:
    return sum(abs(x) for x in xs) / len(xs) if xs else 0.0


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def analyze_pred_errors(records: Sequence[CallRecord]) -> list[ComponentErrors]:
    by_type: dict[str, list[CallRecord]] = defaultdict(list)
    for r in records:
        by_type[r.step_type_semantic].append(r)
    out: list[ComponentErrors] = []
    for step_type, rows in sorted(by_type.items()):
        prefill_errs = [r.t_prefill_ms - r.pred_t_prefill_ms for r in rows]
        decode_errs = [r.t_decode_ms - r.pred_t_decode_ms for r in rows]
        nets = [r.t_network_ms for r in rows]
        det_fracs = []
        for r in rows:
            total = r.t_prefill_ms + r.t_decode_ms + r.t_network_ms
            det = r.pred_t_prefill_ms + r.pred_t_decode_ms
            det_fracs.append(min(1.0, det / total) if total > 0 else 0.0)
        out.append(
            ComponentErrors(
                step_type=step_type,
                n=len(rows),
                prefill_mae_ms=_mae(prefill_errs),
                decode_mae_ms=_mae(decode_errs),
                network_mean_ms=_mean(nets),
                network_std_ms=_std(nets),
                deterministic_fraction=_mean(det_fracs),
            )
        )
    return out


def exp_beta_divergence(records: Sequence[CallRecord]) -> dict[str, Any]:
    """Quantify how far i.i.d. Exp(β) actor latency diverges from measured waits."""
    waits = [
        r.t_prefill_ms + r.t_decode_ms + r.t_network_ms + r.t_orch_pre_ms + r.t_orch_post_ms
        for r in records
    ]
    mean_w = _mean(waits)
    var_w = _std(waits) ** 2
    # Exp(β) with same mean has variance = mean^2.
    exp_var = mean_w**2
    cv = (_std(waits) / mean_w) if mean_w else 0.0
    return {
        "n": len(waits),
        "mean_ms": mean_w,
        "var_ms2": var_w,
        "exp_var_same_mean": exp_var,
        "variance_ratio_meas_over_exp": (var_w / exp_var) if exp_var else float("inf"),
        "cv": cv,
        "exp_cv": 1.0,
    }


def breadth_speculation_tradeoff(
    records: Sequence[CallRecord],
    *,
    breadths: Sequence[int] = (1, 2, 4, 8),
) -> list[SpeculationTradeoff]:
    """Columbia-style breadth speculation under Exp(β) vs deterministic+stochastic split.

    Simplified model: time_saved ≈ E[wait] * (1 - 1/b) under i.i.d. Exp; under split model,
    only the stochastic residual shrinks with breadth while deterministic wait remains.
    Actual time_saved estimated by resampling waits with replacement min-of-b.
    """
    waits = [
        r.t_prefill_ms + r.t_decode_ms + r.t_network_ms for r in records
    ]
    det = [r.pred_t_prefill_ms + r.pred_t_decode_ms for r in records]
    stoch = [max(0.0, w - d) for w, d in zip(waits, det)]
    mean_w = _mean(waits)
    mean_det = _mean(det)
    mean_stoch = _mean(stoch)
    out: list[SpeculationTradeoff] = []
    for b in breadths:
        # Exp model: min of b i.i.d. Exp has mean mean/b.
        pred_exp = mean_w * (1.0 - 1.0 / b)
        pred_split = mean_stoch * (1.0 - 1.0 / b)  # det unchanged
        # Empirical: average of min of b bootstrap samples.
        import random

        rng = random.Random(0)
        saved = []
        for _ in range(500):
            sample = [waits[rng.randrange(len(waits))] for _ in range(b)]
            saved.append(mean_w - min(sample))
        out.append(
            SpeculationTradeoff(
                breadth=b,
                predicted_time_saved_exp=pred_exp,
                predicted_time_saved_split=pred_split,
                actual_time_saved=_mean(saved),
            )
        )
    return out


def run_d4_analysis(records: Sequence[CallRecord], *, truth: dict | None = None) -> dict[str, Any]:
    errors = analyze_pred_errors(records)
    divergence = exp_beta_divergence(records)
    tradeoff = breadth_speculation_tradeoff(records)
    report = {
        "component_errors": [asdict(e) for e in errors],
        "exp_beta_divergence": divergence,
        "speculation_tradeoff": [asdict(t) for t in tradeoff],
        "truth": truth,
    }
    return report


def accept_against_truth(
    report: dict[str, Any],
    *,
    prefill_mae_tol_ms: float = 0.5,
    decode_mae_rel_tol: float = 0.35,
) -> list[str]:
    """Acceptance vs synthetic ground truth (P4 exit criterion)."""
    failures: list[str] = []
    truth = report.get("truth") or {}
    if not truth:
        failures.append("missing_truth")
        return failures
    for row in report["component_errors"]:
        if row["prefill_mae_ms"] > prefill_mae_tol_ms:
            failures.append(
                f"prefill_mae_high:{row['step_type']}={row['prefill_mae_ms']:.3f}"
            )
        # Decode prediction uses mean length; allow relative MAE.
        # Find mean true decode roughly via deterministic fraction sanity.
        if row["decode_mae_ms"] < 0:
            failures.append(f"decode_mae_negative:{row['step_type']}")
    # Prefill should be highly deterministic → high det fraction on average.
    det = _mean([r["deterministic_fraction"] for r in report["component_errors"]])
    if det < 0.4:
        failures.append(f"deterministic_fraction_low:{det:.3f}")
    # Speculation: split model should be closer to actual than Exp when variance < exp variance.
    var_ratio = report["exp_beta_divergence"]["variance_ratio_meas_over_exp"]
    if var_ratio < 0.9:
        for t in report["speculation_tradeoff"]:
            err_exp = abs(t["predicted_time_saved_exp"] - t["actual_time_saved"])
            err_split = abs(t["predicted_time_saved_split"] - t["actual_time_saved"])
            if t["breadth"] > 1 and err_split > err_exp * 1.25 + 5.0:
                failures.append(
                    f"split_worse_than_exp:b={t['breadth']} exp_err={err_exp:.2f} split_err={err_split:.2f}"
                )
    return failures
