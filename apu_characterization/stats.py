"""Replication statistics: median and IQR over seeds."""

from __future__ import annotations

from typing import Any

# Harness strict = ORCH_SETUP + ORCH_DISPATCH + TOKENIZATION + SERIALIZATION.
# TOOL_COMPUTE is never part of any harness metric.
HARNESS_STRICT_LABEL = "harness_strict (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION)"
# Harness broad = strict + HTTP_CLIENT + PROMPT_ASSEMBLY + CONTEXT_MGMT + LOGGING.
HARNESS_BROAD_LABEL = (
    "harness_broad (strict + HTTP_CLIENT + PROMPT_ASSEMBLY + CONTEXT_MGMT + LOGGING)"
)
HARNESS_BROAD_EXTRA_CATEGORIES = (
    "HTTP_CLIENT",
    "CLIENT_HTTP",
    "CLIENT_PARSE",
    "FRAMEWORK",
    "THREADPOOL",
    "EVENT_LOOP",
    "PROMPT_ASSEMBLY",
    "CONTEXT_MGMT",
    "LOGGING",
)


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def p50_p99(values: list[float]) -> dict[str, float | int]:
    """p50/p99 summary for latency samples (ms)."""
    xs = sorted(values)
    return {
        "p50": _percentile(xs, 0.50),
        "p99": _percentile(xs, 0.99),
        "n": len(xs),
        "max": xs[-1] if xs else 0.0,
    }


def median_iqr(values: list[float]) -> dict[str, float]:
    xs = sorted(values)
    q1 = _percentile(xs, 0.25)
    q3 = _percentile(xs, 0.75)
    med = _percentile(xs, 0.5)
    return {
        "median": med,
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "n": float(len(xs)),
        "min": xs[0] if xs else 0.0,
        "max": xs[-1] if xs else 0.0,
    }


def batch_attribution_summary(run: dict[str, Any], total_ns: int) -> dict[str, Any]:
    """Headline CPU shares plus ORCH measured/reconcile split for one batch."""
    shares = _pooled_shares_from_run(run, total_ns)
    orch_total, orch_measured, orch_reconcile = _orch_split_ns(run)
    orch_total = orch_total or 1
    return {
        **shares,
        "batch_host_cpu_ms": total_ns / 1e6,
        "orch_measured_pct_of_orch": 100 * orch_measured / orch_total,
        "orch_reconcile_pct_of_orch": 100 * orch_reconcile / orch_total,
        "harness_strict_definition": HARNESS_STRICT_LABEL,
        "harness_broad_definition": HARNESS_BROAD_LABEL,
        "execution_note": (
            f"workers={run.get('config', {}).get('workers', 1)}; "
            f"concurrency={run.get('config', {}).get('concurrency', '?')} sessions"
        ),
    }


def backfill_run_orch_fields(run: dict[str, Any]) -> int:
    """Backfill session ORCH split on a batch run dict; returns sessions updated."""
    from .attribution import backfill_session_orch_fields

    per_session_category = run.get("per_session_category") or {}
    updated = 0
    for session in run.get("per_session") or []:
        if backfill_session_orch_fields(session, per_session_category):
            updated += 1
    return updated


def _orch_split_ns(run: dict[str, Any]) -> tuple[int, int, int]:
    """Return (orch_total, orch_measured, orch_reconcile) ns for a batch run."""
    per_session = run.get("per_session") or []
    measured = sum(s.get("orch_measured_cpu_ns", 0) for s in per_session)
    reconcile = sum(s.get("orch_reconcile_cpu_ns", 0) for s in per_session)
    if measured or reconcile:
        return measured + reconcile, measured, reconcile
    cats = run["per_category"]
    orch_ns = cats.get("ORCH_SETUP", {}).get("cpu_ns", 0) + cats.get(
        "ORCH_DISPATCH", {}
    ).get("cpu_ns", 0)
    return orch_ns, orch_ns, 0


def harness_strict_ns_from_run(run: dict[str, Any]) -> int:
    """harness_strict CPU ns: ORCH_SETUP + ORCH_DISPATCH + TOKENIZATION + SERIALIZATION."""
    orch_ns, _m, _r = _orch_split_ns(run)
    ns = orch_ns
    ns += run["per_category"].get("TOKENIZATION", {}).get("cpu_ns", 0)
    ns += run["per_category"].get("SERIALIZATION", {}).get("cpu_ns", 0)
    return ns


def harness_broad_ns_from_run(run: dict[str, Any]) -> int:
    """harness_broad CPU ns: strict + HTTP_CLIENT + PROMPT_ASSEMBLY + CONTEXT_MGMT + LOGGING."""
    ns = harness_strict_ns_from_run(run)
    for cat in HARNESS_BROAD_EXTRA_CATEGORIES:
        ns += run["per_category"].get(cat, {}).get("cpu_ns", 0)
    return ns


def _pooled_shares_from_run(run: dict[str, Any], total_ns: int) -> dict[str, float]:
    """Pooled TOOL / ORCH / harness-strict / harness-broad CPU shares for one batch run."""
    total = total_ns or 1
    tool_ns = run["per_category"].get("TOOL_COMPUTE", {}).get("cpu_ns", 0)
    orch_ns, orch_measured_ns, orch_reconcile_ns = _orch_split_ns(run)
    strict_ns = harness_strict_ns_from_run(run)
    broad_ns = harness_broad_ns_from_run(run)
    residual_ns = run["per_category"].get("RESIDUAL_UNATTRIBUTED", {}).get("cpu_ns", 0)
    prov = run.get("provenance_totals") or {}
    measured_ns = prov.get("measured", 0)
    step_infer_ns = prov.get("step_inferred", 0)
    residual_prov_ns = prov.get("residual", 0)
    out: dict[str, float] = {
        "pooled_tool_compute_pct": 100 * tool_ns / total,
        "pooled_orch_pct": 100 * orch_ns / total,
        "pooled_orch_measured_pct": 100 * orch_measured_ns / total,
        "pooled_orch_reconcile_pct": 100 * orch_reconcile_ns / total,
        "pooled_residual_unattributed_pct": 100 * residual_ns / total,
        "pooled_measured_pct": 100 * measured_ns / total,
        "pooled_step_inferred_pct": 100 * step_infer_ns / total,
        "pooled_residual_provenance_pct": 100 * residual_prov_ns / total,
        "pooled_harness_apu_pct": 100 * strict_ns / total,
        "pooled_harness_strict_pct": 100 * strict_ns / total,
        "pooled_harness_broad_pct": 100 * broad_ns / total,
    }
    for cat in (
        "CLIENT_HTTP",
        "CLIENT_PARSE",
        "FRAMEWORK",
        "THREADPOOL",
        "EVENT_LOOP",
    ):
        ns = run["per_category"].get(cat, {}).get("cpu_ns", 0)
        out[f"pooled_{cat.lower()}_pct"] = 100 * ns / total
    return out


def aggregate_replication_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize a list of per-seed real_agent artifacts."""
    batch_cpus = []
    tool_shares = []
    orch_shares = []
    orch_measured_shares = []
    orch_reconcile_shares = []
    harness_shares = []
    harness_broad_shares = []
    residual_unattributed_shares = []
    measured_shares: list[float] = []
    step_inferred_shares: list[float] = []
    residual_prov_shares: list[float] = []
    v2_cat_shares: dict[str, list[float]] = {}
    per_task_host: dict[str, list[float]] = {}

    orch_reconcile_of_orch: list[float] = []

    for art in runs:
        run = art["run"]
        total = art["invariant"]["total_thread_cpu_ns"] or 1
        batch_cpus.append(total / 1e6)
        shares = _pooled_shares_from_run(run, total)
        tool_shares.append(shares["pooled_tool_compute_pct"])
        orch_shares.append(shares["pooled_orch_pct"])
        orch_measured_shares.append(shares["pooled_orch_measured_pct"])
        orch_reconcile_shares.append(shares["pooled_orch_reconcile_pct"])
        harness_shares.append(shares["pooled_harness_strict_pct"])
        harness_broad_shares.append(shares["pooled_harness_broad_pct"])
        residual_unattributed_shares.append(shares.get("pooled_residual_unattributed_pct", 0.0))
        measured_shares.append(shares.get("pooled_measured_pct", 0.0))
        step_inferred_shares.append(shares.get("pooled_step_inferred_pct", 0.0))
        residual_prov_shares.append(shares.get("pooled_residual_provenance_pct", 0.0))
        for cat in (
            "CLIENT_HTTP",
            "CLIENT_PARSE",
            "FRAMEWORK",
            "THREADPOOL",
            "EVENT_LOOP",
        ):
            key = f"pooled_{cat.lower()}_pct"
            v2_cat_shares.setdefault(key, []).append(shares.get(key, 0.0))
        ba = art.get("batch_attribution") or {}
        if ba.get("orch_reconcile_pct_of_orch") is not None:
            orch_reconcile_of_orch.append(ba["orch_reconcile_pct_of_orch"])

        wall = art.get("per_task_wall_cpu", {}).get("per_task", {})
        for tid, row in wall.items():
            per_task_host.setdefault(tid, []).append(row["host_cpu_ms"])

    return {
        "n_seeds": len(runs),
        "seeds": [r["config"].get("seed") for r in runs],
        "batch_host_cpu_ms": median_iqr(batch_cpus),
        "pooled_tool_compute_pct": median_iqr(tool_shares),
        "pooled_orch_pct": median_iqr(orch_shares),
        "pooled_orch_measured_pct": median_iqr(orch_measured_shares),
        "pooled_orch_reconcile_pct": median_iqr(orch_reconcile_shares),
        "pooled_harness_apu_pct": median_iqr(harness_shares),
        "pooled_harness_strict_pct": median_iqr(harness_shares),
        "pooled_harness_broad_pct": median_iqr(harness_broad_shares),
        "pooled_residual_unattributed_pct": median_iqr(residual_unattributed_shares)
        if residual_unattributed_shares
        else {"median": 0.0, "q1": 0.0, "q3": 0.0, "iqr": 0.0, "n": 0.0, "min": 0.0, "max": 0.0},
        "pooled_measured_pct": median_iqr(measured_shares) if measured_shares else {"median": 0.0},
        "pooled_step_inferred_pct": median_iqr(step_inferred_shares)
        if step_inferred_shares
        else {"median": 0.0},
        "pooled_residual_provenance_pct": median_iqr(residual_prov_shares)
        if residual_prov_shares
        else {"median": 0.0},
        **{k: median_iqr(v) for k, v in sorted(v2_cat_shares.items())},
        "harness_strict_definition": HARNESS_STRICT_LABEL,
        "harness_broad_definition": HARNESS_BROAD_LABEL,
        "orch_reconcile_share_of_orch_pct": median_iqr(orch_reconcile_of_orch)
        if orch_reconcile_of_orch
        else {"median": 0.0, "q1": 0.0, "q3": 0.0, "iqr": 0.0, "n": 0.0, "min": 0.0, "max": 0.0},
        "attribution_doc": "apu_characterization/ATTRIBUTION.md",
        "per_task_host_cpu_ms": {tid: median_iqr(vs) for tid, vs in sorted(per_task_host.items())},
        "comparison_type": "distribution_over_seeds",
    }


def summarize_concurrency_run(artifact: dict[str, Any]) -> dict[str, Any]:
    """Extract headline metrics from one per-(workers, seed) artifact."""
    run = artifact["run"]
    total_ns = artifact["invariant"]["total_thread_cpu_ns"]
    shares = _pooled_shares_from_run(run, total_ns)
    per_session = [
        {
            "session_id": s["session_id"],
            "task_id": s.get("task_id"),
            "wall_s": s.get("wall_s"),
            "process_cpu_ms": s.get("process_cpu_ns", 0) / 1e6,
            "turns": s.get("turns"),
            "tool_call_counts": s.get("tool_call_counts"),
            "orch_measured_ms": s.get("orch_measured_cpu_ns", 0) / 1e6,
            "orch_reconcile_ms": s.get("orch_reconcile_cpu_ns", 0) / 1e6,
        }
        for s in run.get("per_session", [])
    ]
    return {
        "workers": run["config"].get("workers"),
        "seed": artifact["config"].get("seed"),
        "batch_host_cpu_ms": total_ns / 1e6,
        "batch_wall_s": artifact.get("batch_wall_s"),
        **shares,
        "residual_fraction": artifact["invariant"].get("residual_fraction"),
        "invariant_pass": artifact["invariant"].get("pass"),
        "audit_pass": artifact.get("audit", {}).get("pass"),
        "per_session": per_session,
    }


def aggregate_concurrency_by_workers(
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Median/IQR over seeds for each workers level in a concurrency sweep."""
    by_workers: dict[int, list[dict[str, Any]]] = {}
    for row in runs:
        w = row["workers"]
        by_workers.setdefault(w, []).append(row)

    out: dict[str, Any] = {}
    for workers in sorted(by_workers):
        rows = by_workers[workers]
        out[str(workers)] = {
            "workers": workers,
            "n_seeds": len(rows),
            "seeds": [r["seed"] for r in rows],
            "batch_host_cpu_ms": median_iqr([r["batch_host_cpu_ms"] for r in rows]),
            "batch_wall_s": median_iqr([r["batch_wall_s"] for r in rows]),
            "pooled_tool_compute_pct": median_iqr(
                [r["pooled_tool_compute_pct"] for r in rows]
            ),
            "pooled_orch_pct": median_iqr([r["pooled_orch_pct"] for r in rows]),
            "pooled_orch_measured_pct": median_iqr(
                [r["pooled_orch_measured_pct"] for r in rows]
            ),
            "pooled_orch_reconcile_pct": median_iqr(
                [r["pooled_orch_reconcile_pct"] for r in rows]
            ),
            "pooled_harness_apu_pct": median_iqr(
                [r["pooled_harness_strict_pct"] for r in rows]
            ),
            "pooled_harness_strict_pct": median_iqr(
                [r["pooled_harness_strict_pct"] for r in rows]
            ),
            "pooled_harness_broad_pct": median_iqr(
                [r.get("pooled_harness_broad_pct", 0.0) for r in rows]
            ),
            "comparison_type": "distribution_over_seeds",
        }
    return out
