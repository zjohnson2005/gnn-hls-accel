"""Classify real OpenAI scaling: plateau vs inflection vs mock mismatch."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from orchestration_engine.characterization.analyze import analyze_profile
from orchestration_engine.characterization.phase1_gate.metrics import (
    cores_equivalent,
    orchestration_setup_steady_us,
    per_agent_orchestration_us,
    steady_orchestration_pct_of_accelerable,
    steady_orchestration_us_per_decision,
)
from orchestration_engine.characterization.trace_io import load_trace
from orchestration_engine.characterization.taxonomy import WorkloadProfile

GATE_DIR = Path("orchestration_engine/characterization/out/gate")


def _load_mock_for_conc(conc: int) -> WorkloadProfile:
    path = GATE_DIR / f"mock_action_heavy_c{conc}.json"
    if path.is_file():
        return load_trace(path)
    from orchestration_engine.characterization.langgraph_react.agent import run_concurrent

    return run_concurrent(
        preset="action_heavy", backend="mock", concurrency=conc, calibrated=True, wall_clock=False
    )


@dataclass
class RealAnchor:
    concurrency: int
    orch_pct_accelerable: float
    orch_ms_per_agent: float
    cores_equivalent: float
    parallel_workers: int
    execution_mode: str
    react_steps: str | None = None
    steady_pct_accelerable: float = 0.0
    steady_us_per_decision: float = 0.0
    setup_ms_per_agent: float = 0.0
    orch_pct_std: float | None = None
    n_repeats: int = 1


def _anchors_from_profiles(real_profiles: list[WorkloadProfile]) -> list[RealAnchor]:
    rows: list[RealAnchor] = []
    for prof in sorted(real_profiles, key=lambda p: p.concurrency):
        rep = analyze_profile(prof)
        setup_us, _ = orchestration_setup_steady_us(prof)
        rows.append(
            RealAnchor(
                concurrency=prof.concurrency,
                orch_pct_accelerable=rep.orchestration_pct_of_accelerable_cpu,
                orch_ms_per_agent=per_agent_orchestration_us(prof) / 1000.0,
                cores_equivalent=cores_equivalent(prof),
                parallel_workers=int(prof.meta.get("parallel_workers", "1")),
                execution_mode=prof.meta.get("execution_mode", "unknown"),
                react_steps=prof.meta.get("react_steps_override"),
                steady_pct_accelerable=steady_orchestration_pct_of_accelerable(prof),
                steady_us_per_decision=steady_orchestration_us_per_decision(prof),
                setup_ms_per_agent=setup_us / max(1, prof.concurrency) / 1000.0,
            )
        )
    return rows


def _attach_repeat_stats(anchors: list[RealAnchor]) -> None:
    """Fold openai_action_heavy_c{c}_rep*.json repeats into mean/std per anchor."""
    for a in anchors:
        rep_paths = sorted(GATE_DIR.glob(f"openai_action_heavy_c{a.concurrency}_rep*.json"))
        if len(rep_paths) < 2:
            continue
        pcts = []
        for path in rep_paths:
            prof = load_trace(path)
            pcts.append(analyze_profile(prof).orchestration_pct_of_accelerable_cpu)
        n = len(pcts)
        mean = sum(pcts) / n
        std = (sum((x - mean) ** 2 for x in pcts) / (n - 1)) ** 0.5
        a.orch_pct_accelerable = mean
        a.orch_pct_std = std
        a.n_repeats = n


def _methodology_audit(anchors: list[RealAnchor]) -> dict:
    modes = {a.execution_mode for a in anchors}
    steps = {a.react_steps for a in anchors}
    # Legacy = pre-ladder traces missing react_steps metadata (not c=1 sequential).
    legacy = [a.concurrency for a in anchors if a.react_steps is None]
    same_steps = len(steps) == 1 and None not in steps
    allowed_modes = modes <= {"parallel", "sequential", "single_agent"}
    consistent = same_steps and not legacy and allowed_modes
    issues: list[str] = []
    if legacy:
        issues.append(
            f"legacy anchors at c={legacy} (missing react_steps_override / ladder metadata)"
        )
    if not same_steps:
        issues.append(
            f"mixed react_steps_override: {sorted(steps, key=lambda x: (x is None, x or ''))}"
        )
    if not allowed_modes:
        issues.append(f"unexpected execution modes: {sorted(modes)}")
    return {
        "consistent": consistent,
        "issues": issues,
        "execution_modes": sorted(modes),
        "react_steps_values": sorted(steps, key=lambda x: (x is None, x or "")),
    }


def _linear_slope(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0


def _classify_regime(anchors: list[RealAnchor], mock_points: list[dict]) -> dict:
    if len(anchors) < 2:
        return {
            "verdict": "INSUFFICIENT_DATA",
            "note": "Need at least two real OpenAI anchors beyond c=1.",
            "anchors": [asdict(a) for a in anchors],
        }

    conc = [float(a.concurrency) for a in anchors]
    pct = [a.orch_pct_accelerable for a in anchors]
    ms = [a.orch_ms_per_agent for a in anchors]
    steady_pct = [a.steady_pct_accelerable for a in anchors]
    slope_pct = _linear_slope(conc, pct)
    slope_ms = _linear_slope(conc, ms)
    slope_steady = _linear_slope(conc, steady_pct)

    # Hypothesis 1: falling / plateau (negative or near-zero slope on %)
    h1_score = 1.0 if slope_pct <= 0 else max(0.0, 1.0 - slope_pct / 2.0)

    # Hypothesis 2: inflection (quadratic coefficient on conc^2 positive after decline)
    h2_score = 0.0
    if len(anchors) >= 3:
        # Simple: last segment slope vs first segment slope
        mid = len(anchors) // 2
        early = _linear_slope(conc[: mid + 1], pct[: mid + 1])
        late = _linear_slope(conc[mid:], pct[mid:])
        if early < 0 and late > 0:
            h2_score = 1.0
        elif early < 0 and late > early:
            h2_score = 0.5

    # Hypothesis 3: mock mismatch (mock slope positive while real slope negative)
    mock_slope = 0.0
    if len(mock_points) >= 2:
        mc = [float(p["concurrency"]) for p in mock_points]
        mp = [p["mock_orch_pct_accelerable"] for p in mock_points]
        mock_slope = _linear_slope(mc, mp)
    h3_score = 1.0 if (mock_slope > 0.05 and slope_pct < 0) or (mock_slope > 0.1 and slope_pct < 0.1) else 0.3

    scores = {
        "plateau_or_falling_share": round(h1_score, 3),
        "late_inflection": round(h2_score, 3),
        "mock_model_mismatch": round(h3_score, 3),
    }
    best = max(scores, key=scores.get)

    extrapol_c100 = pct[-1] + slope_pct * (100 - conc[-1]) if conc else None
    extrapol_c500 = pct[-1] + slope_pct * (500 - conc[-1]) if conc else None
    extrapol_c1000 = pct[-1] + slope_pct * (1000 - conc[-1]) if conc else None

    has_c100 = any(a.concurrency == 100 for a in anchors)
    has_c500 = any(a.concurrency == 500 for a in anchors)
    has_c1000 = any(a.concurrency == 1000 for a in anchors)
    max_conc = max(conc)
    c500 = next((a for a in anchors if a.concurrency == 500), None)
    c1000 = next((a for a in anchors if a.concurrency == 1000), None)
    c500_pct = c500.orch_pct_accelerable if c500 else pct[-1]
    methodology = _methodology_audit(anchors)
    measurement_suspect = bool(
        c500
        and (c500.orch_pct_accelerable >= 85.0 or c500.orch_ms_per_agent >= 100.0)
    )

    if has_c500 and measurement_suspect:
        verdict = "MEASUREMENT_ARTIFACT_C500"
        headline = (
            f"c=500 anchor ({c500.orch_pct_accelerable:.1f}% orch/accel, "
            f"{c500.orch_ms_per_agent:.0f} ms/agent) likely mis-attributes API queue wait "
            "as orchestration — re-run after rate-limit accounting fix."
        )
    elif has_c500 and not methodology["consistent"]:
        verdict = "MIXED_METHODOLOGY"
        headline = (
            f"Real orch/accel at c=500 is {c500_pct:.1f}%, but anchors mix measurement setups "
            f"({'; '.join(methodology['issues'])}). "
            "Re-run --full-ladder --fast --force before citing the scaling curve."
        )
    elif has_c500:
        if c500_pct >= 30 and slope_pct > 0.05:
            verdict = "INFLECTION_OR_MOCK_LIKE_RISE"
            headline = (
                f"Real orch/accel at c=500 is {c500_pct:.1f}% — rising/high regime; "
                "trace-calibrated crossover may hold."
            )
        elif c500_pct < 20 and slope_pct <= 0:
            verdict = "PLATEAU_LOW_SHARE"
            headline = (
                f"Real orch/accel at c=500 is {c500_pct:.1f}% — coordination share stays "
                "modest; lead with structural proof (check 9), not E2E percentage."
            )
        else:
            verdict = "MIXED_MID_REGIME"
            headline = (
                f"Real orch/accel at c=500 is {c500_pct:.1f}%; combine structural crossover "
                "with measured absolute cores."
            )
    elif has_c100:
        verdict = "PARTIAL_ANCHOR_C100"
        headline = (
            f"Real c=100 anchor: {next(a.orch_pct_accelerable for a in anchors if a.concurrency==100):.1f}% "
            "orch/accel — c=500 still required to distinguish plateau vs inflection."
        )
    elif max_conc <= 20:
        verdict = "PRE_SCALE_UNRESOLVED"
        headline = (
            f"Real data only to c={int(max_conc)}; slope={slope_pct:+.3f} pp/agent. "
            "Cannot distinguish plateau vs inflection without c>=100."
        )
        if best == "mock_model_mismatch":
            headline += " Mock rising slope conflicts with real trend — rebuild mock from anchors."
    else:
        verdict = "INSUFFICIENT_HIGH_C"
        headline = "Need c=100 and preferably c=500 real anchors."

    sequential = any(a.execution_mode == "sequential" for a in anchors if a.concurrency > 1)
    if sequential:
        headline += " WARNING: some multi-agent traces used sequential OpenAI execution."

    # A rise driven by per-agent setup cost is not dispatch-side inflection.
    if slope_pct > 0.01 and slope_steady <= 0.005:
        headline += (
            " NOTE: headline rise is driven by per-agent session setup, not steady-state "
            "dispatch (steady slope ~flat) — do not cite as dispatch-side inflection."
        )

    if c1000 and c500 and c1000.orch_pct_accelerable + 5 < c500_pct:
        headline += (
            f" NOTE: c=1000 measured {c1000.orch_pct_accelerable:.1f}% (back to plateau) "
            f"vs c=500 {c500_pct:.1f}% - do not cite monotonic rise; c=500 spike may be "
            "latency variance or mid-scale contention, not sustained scaling."
        )

    return {
        "verdict": verdict,
        "headline": headline,
        "methodology_consistent": methodology["consistent"],
        "methodology_issues": methodology["issues"],
        "real_slope_pct_per_conc": round(slope_pct, 4),
        "real_slope_steady_pct_per_conc": round(slope_steady, 4),
        "real_slope_ms_per_agent_per_conc": round(slope_ms, 4),
        "mock_slope_pct_per_conc": round(mock_slope, 4),
        "hypothesis_scores": scores,
        "leading_hypothesis": best,
        "linear_extrapolation_orch_pct_at_c100": round(extrapol_c100, 2) if extrapol_c100 else None,
        "linear_extrapolation_orch_pct_at_c500": round(extrapol_c500, 2) if extrapol_c500 else None,
        "linear_extrapolation_orch_pct_at_c1000": round(extrapol_c1000, 2) if extrapol_c1000 else None,
        "anchors": [asdict(a) for a in anchors],
        "has_real_c100": has_c100,
        "has_real_c500": has_c500,
        "has_real_c1000": has_c1000,
        "measurement_suspect_c500": measurement_suspect,
    }


def build_scaling_regime_report(real_profiles: list[WorkloadProfile]) -> dict:
    anchors = _anchors_from_profiles(real_profiles)
    _attach_repeat_stats(anchors)
    mock_points = []
    for a in anchors:
        mock = _load_mock_for_conc(a.concurrency)
        mock_points.append(
            {
                "concurrency": a.concurrency,
                "mock_orch_pct_accelerable": analyze_profile(mock).orchestration_pct_of_accelerable_cpu,
            }
        )
    return _classify_regime(anchors, mock_points)


def render_scaling_regime_markdown(data: dict) -> str:
    lines = [
        "## 10. Real scaling regime (headline discriminator)",
        "",
        f"**Verdict:** `{data.get('verdict', 'unknown')}`",
        "",
        f"{data.get('headline', '')}",
        "",
        f"- Real slope (orch/accel % per +1 conc): **{data.get('real_slope_pct_per_conc', 0):+.4f}** pp",
        f"- Real steady-state slope (setup excluded): **{data.get('real_slope_steady_pct_per_conc', 0):+.4f}** pp",
        f"- Mock slope (same range): **{data.get('mock_slope_pct_per_conc', 0):+.4f}** pp",
        f"- Leading hypothesis: **{data.get('leading_hypothesis', '?')}**",
        f"- Has real c=100: **{data.get('has_real_c100')}** | c=500: **{data.get('has_real_c500')}** | "
        f"c=1000: **{data.get('has_real_c1000', False)}**",
        f"- Methodology consistent: **{data.get('methodology_consistent', '?')}**",
        "",
    ]
    issues = data.get("methodology_issues") or []
    if issues:
        lines.append("_Methodology gaps (must fix before paper headline):_")
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("")
    if data.get("linear_extrapolation_orch_pct_at_c100") is not None:
        lines.append(
            f"_Linear extrapolation from anchors (do not cite as measured): "
            f"c=100 ~{data['linear_extrapolation_orch_pct_at_c100']:.1f}%, "
            f"c=500 ~{data['linear_extrapolation_orch_pct_at_c500']:.1f}%_"
        )
        lines.append("")
    anchors = data.get("anchors", [])
    if anchors:
        lines.append(
            "| c | orch/accel % (incl. setup) | steady-state % | steady µs/decision | "
            "setup ms/agent | workers | mode |"
        )
        lines.append("|---|------|------|------|------|------|------|")
        for a in anchors:
            pct = f"{a['orch_pct_accelerable']:.1f}%"
            if a.get("orch_pct_std") is not None:
                pct += f" ±{a['orch_pct_std']:.1f} (n={a['n_repeats']})"
            lines.append(
                f"| {a['concurrency']} | {pct} | "
                f"{a.get('steady_pct_accelerable', 0):.1f}% | "
                f"{a.get('steady_us_per_decision', 0):.0f} | "
                f"{a.get('setup_ms_per_agent', 0):.2f} | "
                f"{a['parallel_workers']} | {a['execution_mode']} |"
            )
        lines.extend(
            [
                "",
                "_Setup = each agent's first orchestration span (LangGraph session/graph init); "
                "steady-state = dispatch decisions after init. Both are coordination work; "
                "setup maps to the engine's dynamic graph-load path, steady-state to "
                "scatter-on-completion._",
            ]
        )
    return "\n".join(lines)
