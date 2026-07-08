"""Run-level accounting audits: refuse to publish impossible numbers.

Checks per-task category sums, process vs instrumented CPU, tick-quantization
warnings, and wall-axis labeling requirements. Experiments attach the audit
result to every artifact; publishable validity requires audit pass on Linux
(or explicit --allow-windows-footnote for cross-platform debug only).
"""

from __future__ import annotations

import sys
from typing import Any

WINDOWS_TICK_MS = 15.625
MIN_LINUX_QUOTABLE_SESSION_CPU_MS = 50.0
MIN_WINDOWS_QUOTABLE_SESSION_CPU_MS = 200.0
CATEGORY_SUM_TOLERANCE = 0.05  # 5% of instrumented or 1 tick, whichever larger
PROCESS_INSTR_TOLERANCE = 0.20  # reconcile may land in ORCH_DISPATCH
# Hard impossibility threshold — no tick slack (category cannot exceed process CPU).
IMPOSSIBILITY_EPS_MS = 0.5


def _is_tick_quantized(values: list[float], tick_ms: float = WINDOWS_TICK_MS) -> bool:
    """True if every nonzero value is within 0.5 ms of a tick multiple."""
    if not values:
        return False
    for v in values:
        if v <= 0:
            continue
        ticks = v / tick_ms
        if abs(ticks - round(ticks)) > 0.04:
            return False
    return True


def _tick_slack_ms(host_cpu_ms: float) -> float:
    return max(WINDOWS_TICK_MS, host_cpu_ms * CATEGORY_SUM_TOLERANCE)


def _platform_is_windows(platform: str | None = None) -> bool:
    """True if platform string or current runtime is Windows."""
    if platform:
        p = platform.lower()
        return p.startswith("windows") or "win32" in p
    return sys.platform == "win32"


def _artifact_capture_platform(artifact: dict[str, Any]) -> str | None:
    env = artifact.get("env") or {}
    plat = env.get("platform")
    if isinstance(plat, str) and plat:
        return plat
    audit_plat = (artifact.get("audit") or {}).get("platform")
    if isinstance(audit_plat, str) and audit_plat:
        return audit_plat
    return None


def _repro_checks(combined: dict[str, Any], *, allow_dirty: bool) -> dict[str, Any]:
    """Git/setup reproducibility gates for publishable replication."""
    warnings: list[str] = []
    violations: list[str] = []
    git = combined.get("git") or {}
    measurement_git = combined.get("measurement_git") or {}
    if git.get("dirty") == "yes" and not allow_dirty:
        violations.append(
            "git tree is dirty; commit all changes then re-run "
            "`replication_batch --refresh-only` (or pass --allow-dirty for exploratory only)"
        )
    elif git.get("dirty") == "yes":
        warnings.append("git tree dirty; numbers are valid but not reproducible from commit")
    if measurement_git.get("dirty") == "yes" and git.get("dirty") == "no":
        warnings.append(
            "OpenAI sessions were captured under a dirty git tree; "
            "refresh re-stamped git to current clean commit — full Linux re-run "
            "recommended for strict reproducibility"
        )
    if git.get("commit") in (None, "", "unknown"):
        violations.append("git commit unknown; install Git and re-run capture_setup")
    n_seeds = len(combined.get("per_seed_artifacts") or [])
    if n_seeds < 5:
        violations.append(f"replication has n={n_seeds} seeds; publishable requires n≥5")
    return {"warnings": warnings, "violations": violations}


def audit_real_agent_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Audit a real_agent_breakdown (or replication aggregate) artifact."""
    run = artifact.get("run", {})
    per_session = run.get("per_session", [])
    per_task = artifact.get("per_task", {})
    per_session_category = run.get("per_session_category", {})
    cfg = artifact.get("config", {})
    inv = artifact.get("invariant", {})

    violations: list[str] = []
    warnings: list[str] = []

    capture_platform = _artifact_capture_platform(artifact)
    is_windows = _platform_is_windows(capture_platform)
    min_quotable = (
        MIN_WINDOWS_QUOTABLE_SESSION_CPU_MS if is_windows else MIN_LINUX_QUOTABLE_SESSION_CPU_MS
    )

    host_cpu_values = [s.get("process_cpu_ns", 0) / 1e6 for s in per_session]
    if is_windows and _is_tick_quantized([v for v in host_cpu_values if v > 0]):
        warnings.append(
            f"Host CPU values appear quantized to {WINDOWS_TICK_MS} ms Windows thread-time "
            "ticks; per-task shares below ~200 ms/session are not quotable. "
            "Re-run on Linux with test_resolution PASS before publishing."
        )

    tick_quantized = is_windows and _is_tick_quantized(
        [v for v in host_cpu_values if v > 0]
    )

    # Session-level audit (authoritative; per_task may merge multiple sessions).
    for sess in per_session:
        sid = sess.get("session_id", "?")
        label = sess.get("task_id") or sid
        host_cpu_ms = sess.get("process_cpu_ns", 0) / 1e6
        instr_sess_ms = sess.get("instrumented_cpu_ns", 0) / 1e6
        reconcile_ms = sess.get("reconcile_cpu_ns", 0) / 1e6
        cats = per_session_category.get(sid, {})
        cat_sum_ms = sum(c.get("cpu_ns", 0) for c in cats.values()) / 1e6
        slack = _tick_slack_ms(max(host_cpu_ms, instr_sess_ms, 1.0))

        if cat_sum_ms > instr_sess_ms + slack:
            violations.append(
                f"{label} ({sid}): category CPU sum {cat_sum_ms:.1f} ms exceeds "
                f"instrumented {instr_sess_ms:.1f} ms (slack {slack:.1f} ms)"
            )

        for cat, vals in cats.items():
            cms = vals.get("cpu_ns", 0) / 1e6
            if cms > host_cpu_ms + IMPOSSIBILITY_EPS_MS and host_cpu_ms > 0:
                diag = (
                    "cross-counter tick artifact (thread_time category vs process_time "
                    "host CPU)"
                    if tick_quantized
                    else "category exceeds process CPU"
                )
                violations.append(
                    f"{label}/{cat}: {cms:.1f} ms exceeds session host CPU "
                    f"{host_cpu_ms:.1f} ms — {diag}"
                )

        if host_cpu_ms > 0 and instr_sess_ms > host_cpu_ms + IMPOSSIBILITY_EPS_MS:
            trim_ms = sess.get("parallel_cpu_trim_ns", 0) / 1e6
            if trim_ms > 0 and instr_sess_ms <= host_cpu_ms + max(2.0, host_cpu_ms * 0.02):
                warnings.append(
                    f"{label}: parallel tool-thread CPU trimmed by {trim_ms:.1f} ms "
                    "to align category sum with process clock"
                )
            else:
                violations.append(
                    f"{label}: instrumented {instr_sess_ms:.1f} ms > process CPU "
                    f"{host_cpu_ms:.1f} ms"
                    + (
                        " — thread_time timers vs process_time host basis; "
                        "diagnose before quoting shares"
                        if tick_quantized or instr_sess_ms > host_cpu_ms * 1.5
                        else ""
                    )
                )

        if reconcile_ms > host_cpu_ms * PROCESS_INSTR_TOLERANCE + slack and host_cpu_ms > min_quotable:
            orch_recon_ms = sess.get("orch_reconcile_cpu_ns", 0) / 1e6
            orch_meas_ms = sess.get("orch_measured_cpu_ns", 0) / 1e6
            if orch_recon_ms > 0:
                warnings.append(
                    f"{label}: ORCH reconcile {orch_recon_ms:.1f} ms "
                    f"({100 * orch_recon_ms / host_cpu_ms:.0f}% of host CPU) vs "
                    f"ORCH measured {orch_meas_ms:.1f} ms — see ATTRIBUTION.md"
                )
            else:
                warnings.append(
                    f"{label}: reconcile gap {reconcile_ms:.1f} ms is "
                    f"{100 * reconcile_ms / host_cpu_ms:.0f}% of process CPU — check attribution"
                )

        if is_windows and host_cpu_ms > 0 and host_cpu_ms < min_quotable:
            warnings.append(
                f"{label}: host CPU {host_cpu_ms:.1f} ms below Windows quotable floor "
                f"({min_quotable:.0f} ms); per-task shares not publishable"
            )

        instr_version = int(cfg.get("instr_version") or run.get("config", {}).get("instr_version", 1))
        prov = sess.get("provenance") or {}
        residual_prov_ms = prov.get("residual", 0) / 1e6
        step_infer_ms = prov.get("step_inferred", 0) / 1e6
        if instr_version >= 2 and host_cpu_ms > min_quotable:
            res_ms = sess.get("residual_unattributed_cpu_ns", 0) / 1e6
            res_limit = inv.get("limit", 0.15)
            # True residual provenance only (not step-inferred mass).
            if residual_prov_ms > host_cpu_ms * res_limit + slack:
                violations.append(
                    f"{label}: residual-provenance {residual_prov_ms:.1f} ms "
                    f"({100 * residual_prov_ms / host_cpu_ms:.0f}% of host) exceeds "
                    f"{res_limit * 100:.0f}% gate"
                )
            if step_infer_ms > host_cpu_ms * 0.05 + slack:
                warnings.append(
                    f"{label}: step-inferred {step_infer_ms:.1f} ms "
                    f"({100 * step_infer_ms / host_cpu_ms:.0f}% of host) — "
                    "corroborating tier only; run step_infer_calibration"
                )

    # Per-task rollup (single-session tasks only; skip merged multi-arm rows).
    session_by_task: dict[str, list[dict[str, Any]]] = {}
    for s in per_session:
        if s.get("task_id"):
            session_by_task.setdefault(s["task_id"], []).append(s)

    for task_id, entry in sorted(per_task.items()):
        if len(session_by_task.get(task_id, [])) > 1:
            continue
        sid = entry["sessions"][0]
        sess = next((s for s in per_session if s.get("session_id") == sid), {})
        host_cpu_ms = sess.get("process_cpu_ns", 0) / 1e6
        instr_ms = entry.get("instrumented_cpu_ns", 0) / 1e6
        cats = entry.get("categories", {})
        cat_sum_ms = sum(c.get("cpu_ns", 0) for c in cats.values()) / 1e6
        slack = _tick_slack_ms(max(host_cpu_ms, instr_ms, 1.0))

        if cat_sum_ms > instr_ms + slack:
            violations.append(
                f"{task_id}: per_task category sum {cat_sum_ms:.1f} ms exceeds "
                f"instrumented {instr_ms:.1f} ms"
            )

    wall_cpu = artifact.get("per_task_wall_cpu", {})
    for task_id, row in wall_cpu.get("per_task", {}).items():
        io_pct = row.get("llm_io_pct_of_session_wall", 0)
        if io_pct > 100.5:
            warnings.append(
                f"{task_id}: I/O % of wall is {io_pct:.1f}% (>100%) — HTTP_CLIENT wall "
                "includes remote-tool waits concurrent with session clock; not an additive "
                "partition (see wall integrity table)"
            )

    residual_frac = inv.get("residual_fraction", 0)
    if residual_frac >= inv.get("limit", 0.15):
        violations.append(
            f"Accounting invariant FAIL: residual {residual_frac * 100:.1f}% "
            f">= limit {inv.get('limit', 0.15) * 100:.0f}%"
        )

    backend = cfg.get("backend") or run.get("config", {}).get("backend")
    if artifact.get("result_validity") == "publishable" and backend not in (None, "openai"):
        violations.append(
            f"publishable artifact has backend={backend!r}; verifiable runs require "
            "openai (see VERIFIABLE_DATA.md)"
        )

    seeds = cfg.get("seeds") or [cfg.get("seed")]
    if isinstance(seeds, int):
        seeds = [seeds]
    n_seeds = len(seeds) if seeds else 1
    if n_seeds < 5 and artifact.get("result_validity") == "publishable":
        warnings.append(
            f"Single-seed run (n={n_seeds}); replication requires n≥5 seeds with "
            "medians and IQR before headline numbers are quotable"
        )

    publishable_ok = len(violations) == 0 and not (
        is_windows and artifact.get("result_validity") == "publishable"
        and not cfg.get("allow_windows_footnote")
    )

    per_session = run.get("per_session") or []
    batch_host = sum(s.get("process_cpu_ns", 0) for s in per_session) or inv.get(
        "total_thread_cpu_ns", 0
    )
    orch_meas = sum(s.get("orch_measured_cpu_ns", 0) for s in per_session)
    orch_recon = sum(s.get("orch_reconcile_cpu_ns", 0) for s in per_session)
    orch_total = orch_meas + orch_recon
    attribution_summary: dict[str, Any] = {}
    if orch_total > 0 and batch_host > 0:
        attribution_summary = {
            "orch_measured_pct_of_host": 100 * orch_meas / batch_host,
            "orch_reconcile_pct_of_host": 100 * orch_recon / batch_host,
            "orch_reconcile_pct_of_orch": 100 * orch_recon / orch_total,
        }

    return {
        "pass": len(violations) == 0,
        "publishable_ok": publishable_ok,
        "violations": violations,
        "warnings": warnings,
        "platform": "win32" if is_windows else "linux",
        "windows_tick_ms": WINDOWS_TICK_MS if is_windows else None,
        "min_quotable_session_cpu_ms": min_quotable,
        "n_seeds": n_seeds,
        "attribution_summary": attribution_summary,
    }


def apply_audit_to_artifact(artifact: dict[str, Any], *, allow_windows_footnote: bool = False) -> dict[str, Any]:
    """Run audit and adjust result_validity if needed."""
    if allow_windows_footnote:
        artifact.setdefault("config", {})["allow_windows_footnote"] = True
    audit = audit_real_agent_artifact(artifact)
    artifact["audit"] = audit
    if artifact.get("result_validity") == "publishable" and not audit["publishable_ok"]:
        if audit["violations"]:
            artifact["result_validity"] = "audit_failed"
        elif _platform_is_windows(_artifact_capture_platform(artifact)) and not allow_windows_footnote:
            artifact["result_validity"] = "windows_footnote_only"
    return audit


def apply_audit_to_replication_batch(
    combined: dict[str, Any], *, allow_dirty: bool = False
) -> dict[str, Any]:
    """Audit every per-seed artifact; combined pass requires all seeds pass on Linux."""
    per_seed = combined.get("per_seed_artifacts") or []
    seed_audits: list[dict[str, Any]] = []
    all_violations: list[str] = []
    all_warnings: list[str] = []

    for art in per_seed:
        seed = art.get("config", {}).get("seed", "?")
        audit = apply_audit_to_artifact(art)
        seed_audits.append({"seed": seed, "audit": audit, "validity": art.get("result_validity")})
        for v in audit.get("violations", []):
            all_violations.append(f"seed {seed}: {v}")
        for w in audit.get("warnings", []):
            if w not in all_warnings:
                all_warnings.append(w)

    capture_platform = _artifact_capture_platform(combined)
    is_windows = _platform_is_windows(capture_platform)
    n_seeds = len(per_seed)
    repro = _repro_checks(combined, allow_dirty=allow_dirty)
    for v in repro["violations"]:
        all_violations.append(v)
    combined_audit = {
        "pass": len(all_violations) == 0,
        "publishable_ok": len(all_violations) == 0 and not is_windows,
        "violations": all_violations,
        "warnings": all_warnings,
        "platform": "win32" if is_windows else "linux",
        "n_seeds": n_seeds,
        "per_seed": seed_audits,
        "repro": repro,
    }
    instr_v = int((combined.get("config") or {}).get("instr_version") or 1)
    agg = combined.get("aggregate") or {}
    step_pct = (agg.get("pooled_step_inferred_pct") or {}).get("median", 0.0)
    measured_pct = (agg.get("pooled_measured_pct") or {}).get("median", 0.0)
    if instr_v >= 3 and step_pct > 5.0:
        all_violations.append(
            f"instr v3 must not use step-inferred booking; median step-inferred {step_pct:.1f}%"
        )
    if instr_v >= 3 and measured_pct < 20.0:
        all_warnings.append(
            f"instr v3 measured tier only {measured_pct:.1f}% of host; check thread registration"
        )
    if instr_v == 2 and step_pct > 50.0:
        cal_path = combined.get("config", {}).get("step_infer_calibration")
        if not cal_path:
            all_violations.append(
                f"step-inferred median {step_pct:.1f}% of host dominates; "
                "headline claims require measured tier or "
                "step_infer_calibration.json with false rate <= 5%"
            )
            combined_audit["pass"] = False
            combined_audit["publishable_ok"] = False
    combined_audit["pass"] = len(all_violations) == 0
    combined_audit["publishable_ok"] = len(all_violations) == 0 and not is_windows
    combined_audit["violations"] = all_violations
    combined_audit["warnings"] = all_warnings
    combined["audit"] = combined_audit

    if combined.get("result_validity") == "publishable":
        if all_violations:
            combined["result_validity"] = "audit_failed"
        elif is_windows:
            combined["result_validity"] = "windows_footnote_only"
    return combined_audit


def apply_audit_to_concurrency_sweep(combined: dict[str, Any]) -> dict[str, Any]:
    """Audit every per-(workers, seed) artifact in a concurrency sweep."""
    per_run = combined.get("per_run_artifacts") or []
    run_audits: list[dict[str, Any]] = []
    all_violations: list[str] = []
    all_warnings: list[str] = []

    for art in per_run:
        cfg = art.get("config", {})
        workers = cfg.get("workers", "?")
        seed = cfg.get("seed", "?")
        audit = apply_audit_to_artifact(art)
        run_audits.append(
            {"workers": workers, "seed": seed, "audit": audit, "validity": art.get("result_validity")}
        )
        for v in audit.get("violations", []):
            all_violations.append(f"workers={workers} seed={seed}: {v}")
        for w in audit.get("warnings", []):
            if w not in all_warnings:
                all_warnings.append(w)

    is_windows = sys.platform == "win32"
    combined_audit = {
        "pass": len(all_violations) == 0,
        "publishable_ok": len(all_violations) == 0 and not is_windows,
        "violations": all_violations,
        "warnings": all_warnings,
        "platform": sys.platform,
        "n_runs": len(per_run),
        "per_run": run_audits,
    }
    combined["audit"] = combined_audit

    if combined.get("result_validity") == "publishable":
        if all_violations:
            combined["result_validity"] = "audit_failed"
        elif is_windows:
            combined["result_validity"] = "windows_footnote_only"
    return combined_audit
