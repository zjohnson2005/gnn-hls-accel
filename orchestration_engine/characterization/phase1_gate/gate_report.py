"""Phase 1 gate report — pre-HLS checks + structural thesis proof."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from orchestration_engine.characterization.analyze import analyze_profile
from orchestration_engine.characterization.langgraph_react.agent import run_concurrent
from orchestration_engine.characterization.langgraph_react.study import openai_key_configured
from orchestration_engine.characterization.phase1_gate.crossover import (
    build_crossover_grid,
    render_crossover_markdown,
)
from orchestration_engine.characterization.phase1_gate.fanout_analysis import (
    build_fanout_resolution,
    render_fanout_markdown,
)
from orchestration_engine.characterization.phase1_gate.graph_shape import all_graph_shapes
from orchestration_engine.characterization.phase1_gate.metrics import (
    cores_equivalent,
    orchestration_decisions,
    orchestration_us,
    per_agent_orchestration_us,
    per_decision_orchestration_us,
    wall_batch_us,
)
from orchestration_engine.characterization.phase1_gate.software_baseline import compare_schedulers
from orchestration_engine.characterization.phase1_gate.scaling_regime import (
    build_scaling_regime_report,
    render_scaling_regime_markdown,
)
from orchestration_engine.characterization.phase1_gate.dispatch_stress import (
    OUT_PATH as DISPATCH_STRESS_PATH,
    render_stress_markdown,
)
from orchestration_engine.characterization.phase1_gate.structural_proof import (
    build_structural_proof,
    render_structural_markdown,
)
from orchestration_engine.characterization.trace_io import load_trace, save_trace
from orchestration_engine.characterization.taxonomy import WorkloadProfile

GATE_DIR = Path("orchestration_engine/characterization/out/gate")

EXTENDED_LEVELS = [1, 10, 100, 500, 1000, 5000]
OPENAI_CONC_LEVELS = [1, 10, 20]


def _load_or_run_mock(preset: str, conc: int, calibrated: bool = True) -> WorkloadProfile:
    path = GATE_DIR / f"mock_{preset}_c{conc}.json"
    if path.is_file():
        return load_trace(path)
    prof = run_concurrent(
        preset=preset, backend="mock", concurrency=conc, calibrated=calibrated, wall_clock=False
    )
    prof.name = f"langgraph_{preset}_calibrated_c{conc}"
    save_trace(prof, path)
    return prof


def check1_absolute_and_software(profiles: dict[tuple[str, int], WorkloadProfile]) -> dict:
    rows = []
    for (preset, conc), prof in sorted(profiles.items()):
        schedulers = compare_schedulers(prof, preset)
        wall = wall_batch_us(prof)
        cores = cores_equivalent(prof)
        orch = orchestration_us(prof)
        rows.append(
            {
                "preset": preset,
                "concurrency": conc,
                "orchestration_us": orch,
                "orchestration_ms_per_agent": round(per_agent_orchestration_us(prof) / 1000, 3),
                "orchestration_us_per_decision": round(per_decision_orchestration_us(prof), 1),
                "wall_batch_s": round(wall / 1_000_000, 3),
                "cores_equivalent": round(cores, 3),
                "schedulers": [asdict(s) for s in schedulers],
                "verdict": (
                    "WEAK_ABSOLUTE"
                    if cores < 0.5
                    else "MODERATE"
                    if cores < 2.0
                    else "STRONG_ABSOLUTE"
                ),
            }
        )

    # Deployment extrapolation at c=500 action_heavy
    ref = profiles.get(("action_heavy", 500))
    deploy = {}
    if ref:
        per_agent = per_agent_orchestration_us(ref)
        for agents in (1000, 10_000, 50_000):
            orch_cpu_s = (per_agent * agents) / 1_000_000
            deploy[str(agents)] = {
                "aggregate_orchestration_cpu_seconds": round(orch_cpu_s, 2),
                "cores_if_serialized_on_one_core": round(orch_cpu_s, 2),
                "note": "Upper bound if all coord work piled on one core; parallel batch lowers duty cycle.",
            }

    return {"rows": rows, "deployment_extrapolation_from_c500_per_agent": deploy}


def check2_extended_curve(profiles: dict[tuple[str, int], WorkloadProfile]) -> dict:
    points = []
    for conc in EXTENDED_LEVELS:
        prof = profiles.get(("action_heavy", conc))
        if not prof:
            continue
        rep = analyze_profile(prof)
        points.append(
            {
                "concurrency": conc,
                "orch_pct_accelerable": rep.orchestration_pct_of_accelerable_cpu,
                "cores_equivalent": round(cores_equivalent(prof), 4),
                "orchestration_us": orchestration_us(prof),
            }
        )
    plateau = False
    if len(points) >= 2:
        last = points[-1]["orch_pct_accelerable"]
        prev = points[-2]["orch_pct_accelerable"]
        plateau = abs(last - prev) < 2.0
    return {
        "action_heavy_curve": points,
        "plateau_detected": plateau,
        "note": "Plateau if last step gain < 2 percentage points.",
    }


def _orch_instrumentation_note(prof: WorkloadProfile) -> str:
    if prof.meta.get("orch_measurement"):
        return prof.meta["orch_measurement"]
    orch = [s.end_us - s.start_us for s in prof.spans if s.bucket.value == "cpu_orchestration"]
    if orch and len(set(orch)) == 1 and orch[0] == 250:
        return "placeholder_250us"
    sample = next((s for s in prof.spans if s.bucket.value == "cpu_orchestration"), None)
    if sample and sample.meta.get("measured") == "wall_residual":
        return "wall_residual"
    return "unknown"


def check3_mock_vs_real(real_profiles: list[WorkloadProfile]) -> dict:
    comparisons = []
    seen_conc: set[int] = set()
    for prof in real_profiles:
        conc = prof.concurrency
        if conc in seen_conc:
            continue
        seen_conc.add(conc)
        mock = _load_or_run_mock("action_heavy", conc, calibrated=True)
        mock_rep = analyze_profile(mock)
        real_rep = analyze_profile(prof)
        comparisons.append(
            {
                "concurrency": conc,
                "backend": prof.meta.get("backend", "unknown"),
                "mock_orch_pct_accelerable": round(mock_rep.orchestration_pct_of_accelerable_cpu, 2),
                "real_orch_pct_accelerable": round(real_rep.orchestration_pct_of_accelerable_cpu, 2),
                "delta_pct_points": round(
                    real_rep.orchestration_pct_of_accelerable_cpu
                    - mock_rep.orchestration_pct_of_accelerable_cpu,
                    2,
                ),
                "mock_cores_eq": round(cores_equivalent(mock), 4),
                "real_cores_eq": round(cores_equivalent(prof), 4),
                "mock_ms_per_agent": round(per_agent_orchestration_us(mock) / 1000, 3),
                "real_ms_per_agent": round(per_agent_orchestration_us(prof) / 1000, 3),
                "real_instrumentation": _orch_instrumentation_note(prof),
            }
        )
    comparisons.sort(key=lambda r: r["concurrency"])
    anchor_count = len(comparisons)
    max_delta = max((abs(r["delta_pct_points"]) for r in comparisons), default=0.0)
    placeholder = any(r.get("real_instrumentation") == "placeholder_250us" for r in comparisons)
    real_pcts = [r["real_orch_pct_accelerable"] for r in comparisons]
    real_scaling = (
        len(real_pcts) >= 2 and max(real_pcts) - min(real_pcts) >= 1.0
    )
    if placeholder:
        trust = "LOW — OpenAI traces used 250us placeholder; re-run after wall_residual fix"
    elif anchor_count >= 3 and max_delta <= 2.0 and real_scaling:
        trust = "HIGH — mock scaling confirmed by real concurrent runs"
    elif anchor_count >= 3 and max_delta <= 2.0:
        trust = "MEDIUM — anchors agree on level but real curve flat; mock 100-5000 still extrapolated"
    elif anchor_count >= 2:
        trust = f"MEDIUM — {anchor_count} anchors, max delta {max_delta:.1f} pp"
    else:
        trust = "LOW — single anchor; mock curve 10-5000 is extrapolation only"
    return {
        "comparisons": comparisons,
        "anchor_points": anchor_count,
        "max_delta_pct_points": round(max_delta, 2),
        "curve_trust": trust,
    }


def check4_workload_axis(profiles: dict[tuple[str, int], WorkloadProfile]) -> dict:
    rows = []
    for preset in ("action_heavy", "reasoning_heavy"):
        for conc in (1, 100, 500):
            prof = profiles.get((preset, conc))
            if not prof:
                continue
            rep = analyze_profile(prof)
            rows.append(
                {
                    "preset": preset,
                    "concurrency": conc,
                    "cpu_tool_pct_e2e": round(rep.cpu_tool_pct_of_e2e, 2),
                    "orch_pct_accelerable": round(rep.orchestration_pct_of_accelerable_cpu, 2),
                    "cores_equivalent": round(cores_equivalent(prof), 4),
                }
            )
    return {
        "rows": rows,
        "claim_scope": (
            "Tool-heavy / action-heavy agents show higher CPU-tool share and rising orchestration "
            "at scale; reasoning-heavy agents are GPU-dominated with smaller absolute orchestration "
            "but similar % of accelerable CPU at high concurrency (check rows)."
        ),
    }


def check5_software_closes_gap(profiles: dict[tuple[str, int], WorkloadProfile]) -> dict:
    rows = []
    for conc in EXTENDED_LEVELS:
        prof = profiles.get(("action_heavy", conc))
        if not prof:
            continue
        wall = wall_batch_us(prof)
        sched = compare_schedulers(prof, "action_heavy")
        measured = sched[0].total_orchestration_us
        opt4 = sched[3].total_orchestration_us
        opt15 = sched[4].total_orchestration_us
        hw = sched[2].total_orchestration_us
        hw_cores = hw / wall if wall else 0
        opt4_cores = opt4 / wall if wall else 0
        rows.append(
            {
                "concurrency": conc,
                "langgraph_us": measured,
                "optimized_4x_us": opt4,
                "optimized_15x_us": opt15,
                "hardware_scatter_model_us": hw,
                "cores_eq_langgraph": round(cores_equivalent(prof), 4),
                "cores_eq_optimized_4x": round(opt4_cores, 4),
                "cores_eq_hardware_model": round(hw_cores, 4),
                "hardware_beats_optimized_4x": hw_cores < opt4_cores,
            }
        )
    return {
        "rows": rows,
        "literature_note": (
            "Autellix-class claims 4-15x software orchestration speedups; hardware must beat "
            "4x optimized in absolute cores, not just unoptimized LangGraph."
        ),
    }


def check6_graph_shapes() -> dict:
    return {"shapes": [asdict(s) for s in all_graph_shapes()]}


def run_openai_concurrent(
    levels: list[int],
    *,
    force: bool = False,
    max_workers: int | None = None,
) -> list[WorkloadProfile]:
    import os

    if not openai_key_configured():
        print("Skipping real concurrent OpenAI (no valid OPENAI_API_KEY).")
        return []
    if max_workers is None and os.getenv("OE_OPENAI_MAX_WORKERS"):
        max_workers = int(os.getenv("OE_OPENAI_MAX_WORKERS", "16"))
    profiles = []
    for conc in levels:
        out = GATE_DIR / f"openai_action_heavy_c{conc}.json"
        if out.is_file() and not force:
            print(f"Using cached OpenAI trace c={conc} ({out.name})")
            p = load_trace(out)
            p.meta["backend"] = "openai"
            profiles.append(p)
            continue
        print(f"OpenAI real concurrent c={conc} (parallel workers)...")
        try:
            prof = run_concurrent(
                preset="action_heavy",
                backend="openai",
                concurrency=conc,
                calibrated=False,
                wall_clock=True,
                max_workers=max_workers,
            )
        except Exception as exc:
            print(f"  failed: {exc}")
            continue
        prof.name = f"langgraph_openai_action_heavy_c{conc}"
        prof.meta["backend"] = "openai"
        save_trace(prof, out)
        if conc == 1:
            study = Path("orchestration_engine/characterization/out/study")
            study.mkdir(parents=True, exist_ok=True)
            save_trace(prof, study / "langgraph_openai_action_heavy_c1.json")
        profiles.append(prof)
    return profiles


def render_markdown(report: dict) -> str:
    c1 = report["check1_absolute_and_software"]
    c2 = report["check2_extended_curve"]
    c3 = report["check3_mock_vs_real"]
    c4 = report["check4_workload_axis"]
    c5 = report["check5_software_closes_gap"]
    c6 = report["check6_graph_shapes"]

    lines = [
        "# Phase 1 gate report (pre-HLS)",
        "",
        "## Thesis (scoped, provable)",
        "",
        report.get(
            "thesis_statement",
            "O(live agents) software dispatch vs O(fan-out) hardware scatter; prove crossover with structural sim + HLS.",
        ),
        "",
        "**Evidence hierarchy:** (9) structural sim is primary proof; (7) trace crossover is "
        "calibration/projection; (3) OpenAI anchors workload realism.",
        "",
        "## 1. Absolute orchestration cost vs software models",
        "",
        "| preset | c | orch (s) | ms/agent | cores eq | verdict |",
        "|--------|---|----------|----------|----------|---------|",
    ]
    for r in c1["rows"]:
        if r["concurrency"] not in (1, 100, 500, 1000, 5000):
            continue
        lines.append(
            f"| {r['preset']} | {r['concurrency']} | {r['orchestration_us']/1e6:.2f} | "
            f"{r['orchestration_ms_per_agent']:.2f} | {r['cores_equivalent']:.3f} | {r['verdict']} |"
        )
    lines.extend(["", "### Deployment extrapolation (from c=500 per-agent orch cost)", ""])
    for k, v in c1.get("deployment_extrapolation_from_c500_per_agent", {}).items():
        lines.append(f"- **{k} agents**: {v['aggregate_orchestration_cpu_seconds']} CPU-seconds orchestration (serialized upper bound)")

    lines.extend(["", "## 2. Extended concurrency curve (action-heavy mock)", ""])
    lines.append("| c | orch / accelerable CPU | cores eq |")
    lines.append("|---|------------------------|----------|")
    for p in c2["action_heavy_curve"]:
        lines.append(f"| {p['concurrency']} | {p['orch_pct_accelerable']:.1f}% | {p['cores_equivalent']:.3f} |")
    lines.append(f"\nPlateau detected: **{c2['plateau_detected']}**")

    lines.extend(["", "## 3. Mock vs real OpenAI", ""])
    lines.append(f"Anchor points: **{c3.get('anchor_points', 0)}** — curve trust: **{c3.get('curve_trust', 'unknown')}**")
    if c3.get("max_delta_pct_points") is not None:
        lines.append(f"Max |delta|: **{c3['max_delta_pct_points']:.1f}** percentage points")
    lines.append("")
    if c3["comparisons"]:
        lines.append("| c | mock % | real % | Δ pp | real ms/agent | instrumentation |")
        lines.append("|---|--------|--------|------|---------------|-----------------|")
        for r in c3["comparisons"]:
            lines.append(
                f"| {r['concurrency']} | {r['mock_orch_pct_accelerable']:.1f}% | "
                f"{r['real_orch_pct_accelerable']:.1f}% | {r['delta_pct_points']:+.1f} | "
                f"{r['real_ms_per_agent']:.2f} | {r.get('real_instrumentation', '?')} |"
            )
    else:
        lines.append("_No real concurrent OpenAI traces yet._")

    lines.extend(["", "## 4. Action vs reasoning axis", ""])
    lines.append("| preset | c | CPU tool/E2E | orch/accel | cores eq |")
    lines.append("|--------|---|--------------|------------|----------|")
    for r in c4["rows"]:
        lines.append(
            f"| {r['preset']} | {r['concurrency']} | {r['cpu_tool_pct_e2e']:.1f}% | "
            f"{r['orch_pct_accelerable']:.1f}% | {r['cores_equivalent']:.3f} |"
        )

    lines.extend(["", "## 5. Three-way comparison (LangGraph vs 4× opt vs HW flat)", ""])
    lines.append("| c | LangGraph | 4× opt | HW flat | HW beats 4×? |")
    lines.append("|---|-----------|--------|---------|--------------|")
    for r in c5["rows"]:
        win = "yes" if r.get("hardware_beats_optimized_4x") else "no"
        lines.append(
            f"| {r['concurrency']} | {r['cores_eq_langgraph']:.3f} | "
            f"{r['cores_eq_optimized_4x']:.3f} | "
            f"{r['cores_eq_hardware_model']:.3f} | {win} |"
        )

    lines.extend(["", "## 6. Graph out-degree shapes", ""])
    lines.append("| graph | max out-deg | mean | p95 |")
    lines.append("|-------|-------------|------|-----|")
    for s in c6["shapes"]:
        lines.append(
            f"| {s['name']} | {s['max_out_degree']} | {s['mean_out_degree']:.2f} | {s['p95_out_degree']:.0f} |"
        )

    if "check7_crossover" in report:
        lines.extend(["", render_crossover_markdown(report["check7_crossover"])])
    if "check8_fanout_resolution" in report:
        lines.extend(["", render_fanout_markdown(report["check8_fanout_resolution"])])
    if "check9_structural_proof" in report:
        lines.extend(["", render_structural_markdown(report["check9_structural_proof"])])
    if "check10_scaling_regime" in report:
        lines.extend(["", render_scaling_regime_markdown(report["check10_scaling_regime"])])
    if report.get("check11_dispatch_stress"):
        lines.extend(["", render_stress_markdown(report["check11_dispatch_stress"])])

    lines.extend(["", "## Gate recommendation", "", report.get("recommendation", ""), ""])
    return "\n".join(lines)


def _recommendation(report: dict) -> str:
    structural = report.get("check9_structural_proof", {})
    struct_headline = structural.get("headline", "")
    min_live = structural.get("min_live_nodes_hw_flat_beats_optimized")

    c3 = report.get("check3_mock_vs_real", {})
    c10 = report.get("check10_scaling_regime", {})
    regime_headline = c10.get("headline", "")

    if c10.get("measurement_suspect_c500"):
        gate = "INVALID c=500 anchor — re-run OpenAI sweep after measurement fix."
    elif not c10.get("methodology_consistent", True):
        gate = (
            "HEADLINE BLOCKED: scaling curve mixes sequential/legacy low-c traces with "
            "parallel --fast high-c traces. Run --full-ladder --fast --force."
        )
    elif c10.get("has_real_c500") and c10.get("verdict") not in (
        "MEASUREMENT_ARTIFACT_C500",
        "MIXED_METHODOLOGY",
    ):
        gate = "HEADLINE REGIME RESOLVED at c=500 real anchor (consistent methodology)."
    elif c10.get("has_real_c100"):
        gate = "PARTIAL: real c=100 anchor captured — run c=500 to resolve headline."
    elif c10.get("verdict") == "PRE_SCALE_UNRESOLVED":
        gate = "BLOCKED ON DATA: run real OpenAI at c=100 (and c=500) before headline claim."
    else:
        gate = "PROCEED TO PHASE 2 (structural proof); trace headline still unresolved."

    c11 = report.get("check11_dispatch_stress") or {}
    stress_note = ""
    if c11.get("verdict") == "LANGGRAPH_FLAT":
        stress_note = (
            " Check 11 measured: real-framework dispatch is ~flat with live_n "
            "(constant-factor + energy case), while a scan-class scheduler grows "
            f"{c11.get('growth_global_scan', '?')}x - frame the hardware win as "
            "constant factor vs deployed frameworks, complexity class vs scan schedulers."
        )
    elif c11.get("verdict") == "LANGGRAPH_SCALES_WITH_LIVE_N":
        stress_note = (
            " Check 11 measured: real-framework dispatch grows with live_n — "
            "the O(live) software claim is empirically grounded."
        )

    return (
        f"{gate} {regime_headline} Structural: hardware beats 4x optimized scan at "
        f"live_nodes >= {structural.get('min_live_nodes_hw_flat_beats_optimized', '?')}. "
        "Lead with check 9 crossover; check 10 picks percentage headline."
        f"{stress_note}"
    )


def run_gate(
    *,
    run_extended: bool = True,
    run_openai: bool = True,
    openai_levels: list[int] | None = None,
    force_openai: bool = False,
) -> Path:
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    profiles: dict[tuple[str, int], WorkloadProfile] = {}

    if run_extended:
        print("Extended mock sweep (action_heavy)...")
        for conc in EXTENDED_LEVELS:
            profiles[("action_heavy", conc)] = _load_or_run_mock("action_heavy", conc)
        print("Mock sweep (reasoning_heavy c=1,100,500)...")
        for conc in (1, 100, 500):
            profiles[("reasoning_heavy", conc)] = _load_or_run_mock("reasoning_heavy", conc)
    else:
        for preset, levels in (
            ("action_heavy", EXTENDED_LEVELS),
            ("reasoning_heavy", [1, 100, 500]),
        ):
            for conc in levels:
                path = GATE_DIR / f"mock_{preset}_c{conc}.json"
                if path.is_file():
                    profiles[(preset, conc)] = load_trace(path)

    study = Path("orchestration_engine/characterization/out/study")
    real_profiles: list[WorkloadProfile] = []

    if run_openai:
        levels = openai_levels or OPENAI_CONC_LEVELS
        real_profiles = run_openai_concurrent(levels, force=force_openai)

    if not run_openai or not force_openai:
        gate_paths = [GATE_DIR / f"openai_action_heavy_c{c}.json" for c in (1, 10, 20, 100, 500, 1000)]
        fallback_paths = [
            study / "langgraph_openai_action_heavy_c1.json",
            Path("orchestration_engine/characterization/out/langgraph_react.json"),
        ]
        seen: set[int] = set()
        for path in gate_paths + fallback_paths:
            if not path.is_file():
                continue
            p = load_trace(path)
            p.meta["backend"] = "openai"
            if p.concurrency in seen:
                continue
            real_profiles.append(p)
            seen.add(p.concurrency)

    deduped: dict[int, WorkloadProfile] = {}
    for prof in real_profiles:
        deduped[prof.concurrency] = prof
    real_profiles = [deduped[c] for c in sorted(deduped)]

    lg_per_dec = 1746.0
    prof500 = profiles.get(("action_heavy", 500))
    if prof500:
        d = max(1, orchestration_decisions(prof500))
        lg_per_dec = orchestration_us(prof500) / d

    structural = build_structural_proof()
    report = {
        "thesis_statement": structural["thesis_statement"],
        "check1_absolute_and_software": check1_absolute_and_software(profiles),
        "check2_extended_curve": check2_extended_curve(profiles),
        "check3_mock_vs_real": check3_mock_vs_real(real_profiles),
        "check4_workload_axis": check4_workload_axis(profiles),
        "check5_software_closes_gap": check5_software_closes_gap(profiles),
        "check6_graph_shapes": check6_graph_shapes(),
        "check7_crossover": build_crossover_grid(profiles),
        "check8_fanout_resolution": build_fanout_resolution(
            langgraph_us_per_decision_at_c500=lg_per_dec
        ),
        "check9_structural_proof": structural,
        "check10_scaling_regime": build_scaling_regime_report(real_profiles),
    }
    if DISPATCH_STRESS_PATH.is_file():
        report["check11_dispatch_stress"] = json.loads(
            DISPATCH_STRESS_PATH.read_text(encoding="utf-8")
        )
    report["recommendation"] = _recommendation(report)

    json_path = GATE_DIR / "gate_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path = GATE_DIR / "gate_report.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"\nWrote {md_path.resolve()}")
    print(f"\n{report['recommendation']}")
    return md_path


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Phase 1 pre-HLS gate checks")
    parser.add_argument("--skip-extended", action="store_true")
    parser.add_argument("--skip-openai", action="store_true")
    parser.add_argument("--openai-levels", default="10,20")
    parser.add_argument("--openai-only", action="store_true", help="Only run OpenAI traces + report")
    parser.add_argument(
        "--force-openai",
        action="store_true",
        help="Re-run OpenAI levels (ignore cached gate/openai_*.json)",
    )
    args = parser.parse_args()
    levels = [int(x) for x in args.openai_levels.split(",") if x.strip()]
    run_gate(
        run_extended=not args.skip_extended and not args.openai_only,
        run_openai=not args.skip_openai,
        openai_levels=levels,
        force_openai=args.force_openai,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
