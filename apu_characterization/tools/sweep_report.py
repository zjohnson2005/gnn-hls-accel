"""Report generator for the c-ladder concurrency sweep.

Reads ONLY ``out/concurrency_sweep.json`` (levels mode) and writes
``out/concurrency_sweep_report.md``. Every headline row carries its
denominators (c level, n seeds, platform, model, search locality). Rows with
n=1 are explicitly marked and never presented as findings. Trend statements
are fitted (least squares on log2 c) and monotonicity is checked against
per-level IQR: if any level breaks monotonicity beyond the previous level's
IQR, the report says so instead of claiming monotonic scaling.

Usage (run as a plain script; the tools package __init__ has heavy imports):
  python apu_characterization/tools/sweep_report.py \\
      [--artifact apu_characterization/out/concurrency_sweep.json] \\
      [--out apu_characterization/out/concurrency_sweep_report.md]
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

DEFAULT_ARTIFACT = Path("apu_characterization/out/concurrency_sweep.json")
DEFAULT_OUT = Path("apu_characterization/out/concurrency_sweep_report.md")


def _median(row: dict[str, Any], key: str) -> float | None:
    val = row.get(key)
    if isinstance(val, dict):
        return val.get("median")
    return val


def _iqr(row: dict[str, Any], key: str) -> float:
    val = row.get(key)
    if isinstance(val, dict):
        return val.get("iqr", 0.0) or 0.0
    return 0.0


def _fmt(mi: dict[str, Any] | float | None, digits: int = 1) -> str:
    if mi is None:
        return "n/a"
    if isinstance(mi, dict):
        med = mi.get("median")
        if med is None:
            return "n/a"
        return f"{med:.{digits}f} [{mi.get('q1', 0):.{digits}f}-{mi.get('q3', 0):.{digits}f}]"
    return f"{mi:.{digits}f}"


def _fit_trend(points: list[tuple[int, float]]) -> tuple[float, float] | None:
    """Least-squares fit y = a + b * log2(c). Returns (intercept, slope)."""
    if len(points) < 2:
        return None
    xs = [math.log2(c) for c, _ in points]
    ys = [y for _, y in points]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return (my - b * mx, b)


def _monotonicity(
    rows: list[dict[str, Any]], key: str, *, increasing: bool
) -> tuple[bool, list[str]]:
    """Check monotonic trend over levels; deviations beyond previous IQR flag it.

    Returns (is_monotonic_beyond_iqr, deviation_notes). A step that moves
    against the expected direction by more than the previous level's IQR is a
    deviation; smaller wiggles are within noise and noted separately.
    """
    deviations: list[str] = []
    monotonic = True
    prev: dict[str, Any] | None = None
    for row in rows:
        med = _median(row, key)
        if med is None:
            continue
        if prev is not None:
            prev_med = _median(prev, key)
            prev_iqr = _iqr(prev, key)
            if prev_med is not None:
                delta = med - prev_med
                against = (delta < 0) if increasing else (delta > 0)
                if against and abs(delta) > prev_iqr:
                    monotonic = False
                    deviations.append(
                        f"c={prev['level']} -> c={row['level']}: {key} moved "
                        f"{delta:+.2f} against the trend, beyond the previous "
                        f"level IQR ({prev_iqr:.2f})"
                    )
                elif against:
                    deviations.append(
                        f"c={prev['level']} -> c={row['level']}: {key} wiggled "
                        f"{delta:+.2f} (within previous level IQR {prev_iqr:.2f})"
                    )
        prev = row
    return monotonic, deviations


def _trend_section(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["## Fitted trends and monotonicity", ""]
    metrics = [
        ("host_cpu_ms_per_session", "host CPU ms per session", True, "ms/session"),
        ("throughput_sessions_per_min", "throughput", True, "sessions/min"),
        ("pooled_harness_strict_pct", "harness strict share", True, "% of host CPU"),
        ("turn_transition_p99_ms", "p99 turn-transition latency", True, "ms"),
    ]
    for key, label, increasing, unit in metrics:
        pts = [
            (r["level"], _median(r, key))
            for r in rows
            if _median(r, key) is not None
        ]
        pts = [(c, v) for c, v in pts if v is not None]
        if len(pts) < 2:
            lines.append(f"- **{label}:** not enough levels with data to fit a trend.")
            continue
        fit = _fit_trend(pts)
        slope_txt = (
            f"fitted slope {fit[1]:+.3f} {unit} per doubling of c"
            if fit
            else "no fit available"
        )
        n1_levels = [r["level"] for r in rows if r.get("n_seeds", 0) == 1]
        mono, devs = _monotonicity(
            [r for r in rows if _median(r, key) is not None], key, increasing=increasing
        )
        if mono and not devs:
            shape = "monotonic across measured levels"
        elif mono:
            shape = "monotonic beyond IQR, with within-noise wiggles"
        else:
            shape = (
                "NOT monotonic: at least one level breaks the trend beyond IQR, "
                "so no monotonic-scaling claim is made"
            )
        lines.append(f"- **{label}:** {slope_txt}; {shape}.")
        for d in devs:
            lines.append(f"  - deviation: {d}")
        if n1_levels:
            lines.append(
                f"  - caution: levels {n1_levels} have n=1 and cannot support a "
                "trend claim on their own"
            )
    lines.append("")
    return lines


def build_report(combined: dict[str, Any]) -> str:
    cfg = combined.get("config", {})
    env = combined.get("env", {})
    audit = combined.get("audit", {})
    by_level = combined.get("by_level", {})
    sat = combined.get("saturation")
    cap = combined.get("capacity") or {}
    rows = [by_level[k] for k in sorted(by_level, key=lambda k: int(k))]

    platform = env.get("platform", "unknown")
    model = cfg.get("model") or (
        "live OpenAI (OPENAI_MODEL, default gpt-4o-mini)"
        if cfg.get("backend") == "openai"
        else "scripted (synthetic LLM, debug only)"
    )
    validity = combined.get("result_validity", "unknown")

    lines = [
        f"# Concurrency sweep report (c-ladder) [{validity}]",
        "",
        "## Denominators (apply to every row below)",
        "",
        f"- platform: `{platform}`",
        f"- backend: `{cfg.get('backend')}`, model: {model}",
        f"- search locality: `{cfg.get('search_locality')}` "
        f"(payload: `{cfg.get('payload_profile')}`)",
        f"- task sampling: {cfg.get('task_sampling')}",
        f"- instr_version: {cfg.get('instr_version')}",
        f"- seeds per ladder level: `{cfg.get('seeds')}`",
        f"- levels requested: `{cfg.get('levels')}`, completed: `{cfg.get('levels_run')}`",
        f"- audit pass: **{'YES' if audit.get('pass') else 'NO'}**, "
        f"publishable_ok: **{'YES' if audit.get('publishable_ok') else 'NO'}**",
        "",
        "Level 1 is the ingested v3.1 replication anchor (10 sessions, workers=1, "
        "sequential, n=5 seeds); it is not rerun by the sweep.",
        "",
        "## Headline results by level (median [IQR] over seeds)",
        "",
        "| c | n seeds | sessions/batch | host CPU ms/session | throughput sess/min | util % | TOOL % | ORCH % | harness strict % | harness broad % | p99 turn ms | GC ms/sess | residual ms/sess | source |",
        "|--:|--------:|---------------:|--------------------:|--------------------:|-------:|-------:|-------:|-----------------:|----------------:|------------:|-----------:|-----------------:|--------|",
    ]
    for row in rows:
        n = row.get("n_seeds", 0)
        n_txt = f"**{n} (n=1, not a finding)**" if n == 1 else str(n)
        src = row.get("source", "sweep run")
        lines.append(
            f"| {row['level']} | {n_txt} | {row.get('sessions_per_batch', row['level'])} | "
            f"{_fmt(row.get('host_cpu_ms_per_session'))} | "
            f"{_fmt(row.get('throughput_sessions_per_min'), 2)} | "
            f"{_fmt(row.get('cpu_pct_median'))} | "
            f"{_fmt(row.get('pooled_tool_compute_pct'))} | "
            f"{_fmt(row.get('pooled_orch_pct'))} | "
            f"{_fmt(row.get('pooled_harness_strict_pct'))} | "
            f"{_fmt(row.get('pooled_harness_broad_pct'))} | "
            f"{_fmt(row.get('turn_transition_p99_ms'))} | "
            f"{_fmt(row.get('gc_ms_per_session'), 2)} | "
            f"{_fmt(row.get('residual_provenance_ms_per_session'), 2)} | {src} |"
        )
    lines.extend(
        [
            "",
            "Denominator definitions: host CPU ms = sum(session process_time) over "
            "the batch; pooled % = category CPU / batch host CPU; util % = median of "
            "1 s psutil samples over the batch window; throughput = sessions / "
            "(batch wall / 60).",
            "",
        ]
    )

    lines.extend(_trend_section(rows))

    lines.extend(["## Saturation and capacity (B3)", ""])
    lines.append(
        "Saturation criterion: median CPU utilization over the batch window > 85%, "
        "or throughput (sessions/min) stops increasing vs the previous level."
    )
    if sat:
        lines.append(f"- **tripped at level {sat['level']}:** {sat['reason']}")
    else:
        lines.append("- criterion **not tripped** within the completed ladder")
    if cap:
        lines.extend(
            [
                f"- N_max (measured): **{cap.get('n_max_measured')}**",
                f"- harness_strict fraction at N_max: "
                f"{100 * (cap.get('harness_strict_fraction') or 0):.1f}% "
                f"-> k_strict = {_fmt(cap.get('k_strict'), 3)}, "
                f"N_max counterfactual = {_fmt(cap.get('n_max_counterfactual_strict'), 1)}",
                f"- harness_broad fraction at N_max: "
                f"{100 * (cap.get('harness_broad_fraction') or 0):.1f}% "
                f"-> k_broad = {_fmt(cap.get('k_broad'), 3)}, "
                f"N_max counterfactual = {_fmt(cap.get('n_max_counterfactual_broad'), 1)}",
                f"- host CPU ms/session measured {_fmt(cap.get('host_cpu_ms_per_session_measured'))}, "
                f"strict removed {_fmt(cap.get('host_cpu_ms_per_session_strict_removed'))}, "
                f"broad removed {_fmt(cap.get('host_cpu_ms_per_session_broad_removed'))}",
                f"- formula: {cap.get('formula')}",
            ]
        )
    lines.append("")

    violations = audit.get("violations", [])
    warnings = audit.get("warnings", [])
    lines.extend(["## Audit", ""])
    lines.append(f"- violations: {len(violations)}, warnings: {len(warnings)}")
    for v in violations[:10]:
        lines.append(f"- **VIOLATION:** {v}")
    if len(violations) > 10:
        lines.append(f"- ... and {len(violations) - 10} more violations")
    for w in warnings[:5]:
        lines.append(f"- warn: {w}")
    if len(warnings) > 5:
        lines.append(f"- ... and {len(warnings) - 5} more warnings")

    lines.extend(
        [
            "",
            f"Source artifact: `concurrency_sweep.json` "
            f"(generated {combined.get('generated_utc')})",
            f"Reproduce: `{combined.get('reproduce_cmd')}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    combined = json.loads(args.artifact.read_text(encoding="utf-8"))
    if combined.get("mode") != "levels" or "by_level" not in combined:
        raise SystemExit(
            "sweep_report requires a levels-mode artifact (run the sweep with --levels)"
        )
    report = build_report(combined)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"wrote: {args.out}")


if __name__ == "__main__":
    main()
