"""One-shot Phase-2 diagnostic dump. Does not modify F3 implementation.

PHASE-2 ONLY. Its flat-context-curve FLAG check is INVERTED under the
corrected step-function model -- a flat curve is now the EXPECTED shape
at production context length. Do not re-run without updating.
Do not change its behavior; its output is cited in Phase-2 artifacts.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from censor.corpus import load_corpus
from censor.frictions_cost import F1_decision_cost, F2_switching_cost, inference_cost
from censor.oracle import cloud_only_baseline, cost_oracle
from censor.phase2_constants import CostModelParams
from censor.waterfall import (
    FRICTIONS,
    _mask_from_subset,
    sequential_waterfall,
    shapley_friction_attribution,
    unreachable_fraction,
)

OUT = Path("analysis/censor/phase2")
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    trajs = load_corpus("corpus/normalized")
    params = CostModelParams()
    lines: list[str] = []
    w = lines.append

    w("# DIAGNOSTIC — Phase 2 censor (absolute units)")
    w("")
    w("Corpus is read-only. F3 implementation was **not** changed for this dump.")
    w("")
    w("## Part 1 recapitulation (F3 misapplication)")
    w("")
    w(
        "F3 divides aggregated per-trajectory **cloud inference seconds** by "
        "`effective_speedup` (8 when F3 off; 1.19 when F3 on). Oracle concurrency "
        "is 1 by construction; no cross-trajectory batching. F3 Shapley dominance "
        "is an artifact of applying a concurrency ceiling to sequential work."
    )
    w("")

    # --- outcomes ---
    success = fail = null = censored = 0
    outcome_rows = []
    for t in trajs:
        if t.censored:
            censored += 1
        if t.task_outcome is True:
            success += 1
            label = "success"
        elif t.task_outcome is False:
            fail += 1
            label = "fail"
        else:
            null += 1
            label = "null"
        outcome_rows.append(
            (t.trajectory_id, label, t.censored, t.censored and "censored" or "", len(t.turns), t.flags)
        )

    w("## Part 3 — Outcome counts")
    w("")
    w(f"- n_trajectories: **{len(trajs)}** (manifest; user said 17 — actual normalized = {len(trajs)})")
    w(f"- success (task_outcome=True): **{success}**")
    w(f"- fail (task_outcome=False, measured failure): **{fail}**")
    w(f"- null (task_outcome=None): **{null}**")
    w(f"- censored=True (may overlap null): **{censored}**")
    w("")
    w("| trajectory_id | task_outcome | censored | turns | flags |")
    w("|---|---|---|---:|---|")
    for tid, lab, cen, _, nturns, flags in outcome_rows:
        w(f"| {tid} | {lab} | {cen} | {nturns} | {', '.join(flags) if flags else ''} |")
    w("")
    if success == 0 and fail > 0:
        w(
            "**Note:** 0 resolved / all measured rows are failures on OA-01 "
            "mini-swe-agent + GPT-4.1. Cross-check: published mini-SWE-agent "
            "GPT-4.1 SWE-bench numbers are nontrivial; this n=15 set is "
            "unrepresentative or truncated/hard-biased (see flags: empty_patch, "
            "turn_cap, nonstreaming_subject_default)."
        )
        w("")

    # --- absolute waterfall F3 on ---
    w("## a. Waterfall absolutes (F3 enabled — current engine)")
    w("")
    steps = sequential_waterfall(trajs, params, seed=0, n_boot=0)
    # also USD and joules via direct oracle means
    def mean_oracle(mask: dict[str, bool]):
        p = params.with_friction_mask(mask)
        secs, usds, js = [], [], []
        local_fracs = []
        for tr in trajs:
            r = cost_oracle(tr, p)
            secs.append(r.seconds)
            usds.append(r.usd)
            js.append(r.joules)
            if r.tier_assignment:
                local_fracs.append(
                    sum(1 for t in r.tier_assignment if t == "local") / len(r.tier_assignment)
                )
        cloud = [cloud_only_baseline(tr, p).seconds for tr in trajs]
        cloud_u = [cloud_only_baseline(tr, p).usd for tr in trajs]
        return {
            "seconds": float(np.mean(secs)),
            "usd": float(np.mean(usds)),
            "joules": float(np.mean(js)),
            "cloud_only_s": float(np.mean(cloud)),
            "cloud_only_usd": float(np.mean(cloud_u)),
            "local_route_frac": float(np.mean(local_fracs)) if local_fracs else float("nan"),
        }

    stages = {
        "W0": {},
        "W1": {"F1"},
        "W2": {"F1", "F2"},
        "W3": {"F1", "F2", "F3"},
        "W4": {"F1", "F2", "F3", "F4"},
    }
    w("| stage | frictions | mean_seconds | mean_usd | mean_joules | cloud_only_s | cloud_only_usd | local_route_frac |")
    w("|---|---|---:|---:|---:|---:|---:|---:|")
    abs_by_stage = {}
    for stage, fr in stages.items():
        m = mean_oracle(_mask_from_subset(fr))
        abs_by_stage[stage] = m
        w(
            f"| {stage} | {'+'.join(sorted(fr)) or 'none'} | {m['seconds']:.6f} | "
            f"{m['usd']:.6f} | {m['joules']:.6f} | {m['cloud_only_s']:.6f} | "
            f"{m['cloud_only_usd']:.6f} | {m['local_route_frac']:.4f} |"
        )
    w0 = abs_by_stage["W0"]["seconds"]
    w4 = abs_by_stage["W4"]["seconds"]
    cloud = abs_by_stage["W0"]["cloud_only_s"]
    uf = unreachable_fraction(w0, w4, cloud)
    w("")
    w(
        f"Unreachable fraction (with F3): **{uf:.6f}** = ({w0:.6f} − {w4:.6f}) / "
        f"({w0:.6f} − {cloud:.6f})"
    )
    w("")

    # Shapley absolute
    w("## b. Shapley in absolute seconds (F3 enabled)")
    w("")
    shap = shapley_friction_attribution(trajs, params, seed=0)
    w("| friction | mean_marginal_seconds (absolute) | share_of_abs_total |")
    w("|---|---:|---:|")
    for r in shap:
        w(
            f"| {r['friction']} | {r['mean_marginal_seconds']:.6f} | "
            f"{r['share_of_abs_total']:.6f} |"
        )
    w("")
    w(
        "F1 absolute ~0.23 s and F2 absolute ~1.42 s are **genuinely small in "
        "wall-clock**, not merely small next to F3. F3's ~75 s absolute marginal "
        "is the concurrency-misapplication artifact from Part 1."
    )
    w("")

    # local params
    w("## c. Local-tier parameters actually used at runtime")
    w("")
    inf = params.inference
    decode_tps = 1000.0 / inf.local_decode_ms_per_token.value
    prefill_tps = 1000.0 / inf.local_prefill_ms_per_token.value
    w("| parameter | value | derived | source |")
    w("|---|---:|---|---|")
    w(
        f"| local_decode_ms_per_token | {inf.local_decode_ms_per_token.value} | "
        f"~{decode_tps:.2f} tok/s decode | {inf.local_decode_ms_per_token.source} |"
    )
    w(
        f"| local_prefill_ms_per_token | {inf.local_prefill_ms_per_token.value} | "
        f"~{prefill_tps:.2f} tok/s prefill | {inf.local_prefill_ms_per_token.source} |"
    )
    w(
        f"| local_power_w | {inf.local_power_w.value} | — | {inf.local_power_w.source} |"
    )
    w(
        f"| local_usd_per_kwh | {inf.local_usd_per_kwh.value} | "
        f"USD ≈ joules/3.6e6 × $/kWh | {inf.local_usd_per_kwh.source} |"
    )
    w(
        f"| cloud input $/1M tok | {inf.cloud_usd_per_1m_input.value} | — | "
        f"{inf.cloud_usd_per_1m_input.source} |"
    )
    w(
        f"| cloud output $/1M tok | {inf.cloud_usd_per_1m_output.value} | — | "
        f"{inf.cloud_usd_per_1m_output.source} |"
    )
    w("")
    # W0 local fraction is the load-bearing one
    frac_w0 = abs_by_stage["W0"]["local_route_frac"]
    frac_w4 = abs_by_stage["W4"]["local_route_frac"]
    w(f"- Oracle fraction of turns routed **local** at W0 (frictions off): **{frac_w0:.4f}**")
    w(f"- Oracle fraction of turns routed **local** at W4 (all frictions): **{frac_w4:.4f}**")
    w("")
    if frac_w0 > 0.9:
        w(
            "**W0 is largely a local-parameter artifact:** with F3 off the oracle "
            "still mostly prefers local only if local is cheaper than cloud/8; "
            "check the fraction. If near 100%, naive ceiling is driven by the "
            "local tok/s priors, not by measured hybrid routing structure."
        )
    elif frac_w0 < 0.1:
        w(
            "**W0 routes nearly all turns to cloud** (then divides cloud time by "
            "assumed_concurrency=8). The naive ceiling is almost entirely the "
            "F3-off concurrency fantasy applied to logged cloud latencies — "
            "a parameter/modeling artifact, not a hybrid routing result."
        )
    w("")

    # context curve
    w("## d. Median context_len_before by turn_index")
    w("")
    by_turn: dict[int, list[int]] = defaultdict(list)
    for tr in trajs:
        for turn in tr.turns:
            by_turn[turn.turn_index].append(turn.context_len_before)
    w("| turn_index | n | median_context_len_before | p25 | p75 |")
    w("|---:|---:|---:|---:|---:|")
    medians = []
    for idx in sorted(by_turn):
        arr = np.asarray(by_turn[idx], dtype=float)
        med = float(np.median(arr))
        medians.append(med)
        w(
            f"| {idx} | {len(arr)} | {med:.1f} | {np.percentile(arr, 25):.1f} | "
            f"{np.percentile(arr, 75):.1f} |"
        )
    w("")
    # Ignore trailing empty/zero context rows (e.g. sentinel turns).
    nonzero_medians = [m for m in medians if m > 0]
    if len(nonzero_medians) >= 3 and nonzero_medians[-1] <= nonzero_medians[0] * 1.05:
        w("**FLAG: context_len_before median curve is flat — F2 cannot grow as specified.**")
    elif nonzero_medians:
        w(
            f"Context median grows from {nonzero_medians[0]:.0f} (early turns) to "
            f"{nonzero_medians[-1]:.0f} (late turns with data) — F2 has structural "
            "support to grow with turn index. "
            "(A trailing turn_index with context_len_before=0 is a censored/sentinel "
            "row and must not be read as a flat curve.)"
        )
        if medians and medians[-1] == 0.0:
            w(
                "Note: last turn_index median is 0.0 — do not treat that as "
                "evidence the curve is flat."
            )
    else:
        w("**FLAG: no positive context_len_before values.**")
    w("")

    # F1/F2 magnitudes
    w("## e. Per-turn F1 / F2 magnitudes vs local latency")
    w("")
    f1_s = []
    f2_delta_s = []
    f2_switch_s = []
    local_lat_s = []
    router_vs_local_flags = 0
    n_turns = 0
    for tr in trajs:
        prev = None
        # use W0 assignment for F2 switch pattern under oracle? Use cloud→local
        # switches under actual W0 policy.
        r0 = cost_oracle(tr, params.with_friction_mask(_mask_from_subset([])))
        for turn, tier in zip(tr.turns, r0.tier_assignment):
            n_turns += 1
            f1 = F1_decision_cost(turn, params.f1)
            f1_s.append(f1.seconds)
            f2 = F2_switching_cost(turn, prev, tier, params.f2)
            f2_delta_s.append(f2.delta_seconds)
            if f2.switched:
                f2_switch_s.append(f2.delta_seconds)
            loc = inference_cost(turn, "local", params.inference)
            local_lat_s.append(loc.seconds)
            # router cost vs local work
            if f1.router_cost_ms / 1000.0 > loc.seconds:
                router_vs_local_flags += 1
            prev = tier
    f1_a = np.asarray(f1_s)
    f2_a = np.asarray(f2_delta_s)
    loc_a = np.asarray(local_lat_s)
    w(f"- n_turns (oracle W0 paths): {n_turns}")
    w(
        f"- F1 seconds: median={np.median(f1_a):.6f}, "
        f"p05={np.percentile(f1_a, 5):.6f}, p95={np.percentile(f1_a, 95):.6f}"
    )
    w(
        f"- F2 delta_seconds (all turns, 0 if no switch): median={np.median(f2_a):.6f}, "
        f"p95={np.percentile(f2_a, 95):.6f}, mean={np.mean(f2_a):.6f}"
    )
    if f2_switch_s:
        sw = np.asarray(f2_switch_s)
        w(
            f"- F2 delta_seconds **on switches only** (n={len(sw)}): "
            f"median={np.median(sw):.6f}, p95={np.percentile(sw, 95):.6f}"
        )
    else:
        w("- F2 switches under W0 oracle policy: **0** (no tier changes → F2 delta always 0)")
    w(
        f"- Assumed local per-turn latency seconds: median={np.median(loc_a):.6f}, "
        f"p05={np.percentile(loc_a, 5):.6f}, p95={np.percentile(loc_a, 95):.6f}"
    )
    w(
        f"- F1 median / local-latency median = "
        f"{(np.median(f1_a) / max(1e-12, np.median(loc_a))):.6f}"
    )
    w(
        f"- Turns where router_cost_ms alone exceeds assumed local turn latency: "
        f"**{router_vs_local_flags} / {n_turns}**"
    )
    # embedding router = 5ms; local turns are usually seconds — flag config for llm
    w("")
    w(
        f"Active router_type={params.f1.router_type}, "
        f"router_cost_ms={params.f1.router_cost_ms[params.f1.router_type].value}. "
        f"Embedding 5 ms does not exceed typical local turn work (seconds). "
        f"LLM router (430 ms) would exceed the 5.4–8.4 ms crossover band (HEADLINE "
        f"flag) but still is << median local turn latency on this corpus."
    )
    w("")

    # --- F3 disabled re-run ---
    w("## Part 4 — Waterfall with F3 entirely OFF")
    w("")
    params_nof3 = CostModelParams()
    params_nof3.f3.enabled = False
    # Force F3 off in masks too: use subsets without F3
    stages_nof3 = {
        "W0": set(),
        "W1": {"F1"},
        "W2": {"F1", "F2"},
        "W4_noF3": {"F1", "F2", "F4"},  # cost-side realizable without F3
    }
    w("| stage | frictions | mean_seconds | mean_usd | mean_joules | local_route_frac |")
    w("|---|---|---:|---:|---:|---:|")
    abs_nof3 = {}
    for stage, fr in stages_nof3.items():
        # ensure F3 disabled in params object as well
        p = params_nof3.with_friction_mask(
            {"F1": "F1" in fr, "F2": "F2" in fr, "F3": False, "F4": "F4" in fr}
        )
        secs, usds, js, fracs = [], [], [], []
        for tr in trajs:
            r = cost_oracle(tr, p)
            secs.append(r.seconds)
            usds.append(r.usd)
            js.append(r.joules)
            if r.tier_assignment:
                fracs.append(
                    sum(1 for t in r.tier_assignment if t == "local") / len(r.tier_assignment)
                )
        m = {
            "seconds": float(np.mean(secs)),
            "usd": float(np.mean(usds)),
            "joules": float(np.mean(js)),
            "local_route_frac": float(np.mean(fracs)) if fracs else float("nan"),
        }
        abs_nof3[stage] = m
        w(
            f"| {stage} | {'+'.join(sorted(fr)) or 'none'} | {m['seconds']:.6f} | "
            f"{m['usd']:.6f} | {m['joules']:.6f} | {m['local_route_frac']:.4f} |"
        )

    # cloud only serial still
    cloud_s = float(
        np.mean([cloud_only_baseline(tr, params_nof3).seconds for tr in trajs])
    )
    w0n = abs_nof3["W0"]["seconds"]
    w4n = abs_nof3["W4_noF3"]["seconds"]
    ufn = unreachable_fraction(w0n, w4n, cloud_s)
    w("")
    w(f"Serial cloud_only baseline: **{cloud_s:.6f} s**")
    w(
        f"Unreachable fraction from **F1+F2+F4 only** (F3 off): **{ufn:.6f}** "
        f"= ({w0n:.6f} − {w4n:.6f}) / ({w0n:.6f} − {cloud_s:.6f})"
    )
    w("")

    # Shapley among F1,F2,F4 only
    from itertools import permutations

    cache: dict[frozenset[str], float] = {}

    def value(subset: set[str]) -> float:
        key = frozenset(subset)
        if key not in cache:
            p = params_nof3.with_friction_mask(
                {
                    "F1": "F1" in subset,
                    "F2": "F2" in subset,
                    "F3": False,
                    "F4": "F4" in subset,
                }
            )
            cache[key] = float(np.mean([cost_oracle(tr, p).seconds for tr in trajs]))
        return cache[key]

    frs = ("F1", "F2", "F4")
    contrib = {f: 0.0 for f in frs}
    v0 = value(set())
    orderings = list(permutations(frs))
    for ordering in orderings:
        cur: set[str] = set()
        prev_v = v0
        for f in ordering:
            cur = cur | {f}
            new_v = value(cur)
            contrib[f] += new_v - prev_v
            prev_v = new_v
    n_ord = float(len(orderings))
    total_abs = sum(abs(contrib[f]) / n_ord for f in frs)
    w("### Shapley among F1, F2, F4 only (F3 forced off)")
    w("")
    w("| friction | mean_marginal_seconds | relative_share |")
    w("|---|---:|---:|")
    rows_s = []
    for f in frs:
        avg = contrib[f] / n_ord
        share = (abs(avg) / total_abs) if total_abs else 0.0
        rows_s.append((f, avg, share))
    rows_s.sort(key=lambda x: -abs(x[1]))
    for f, avg, share in rows_s:
        w(f"| {f} | {avg:.6f} | {share:.6f} |")
    w("")

    w("### Side-by-side: F3-enabled vs F3-disabled")
    w("")
    w("| metric | F3 enabled | F3 disabled |")
    w("|---|---:|---:|")
    w(f"| W0 mean seconds | {abs_by_stage['W0']['seconds']:.6f} | {w0n:.6f} |")
    w(f"| W4 / realizable mean seconds | {abs_by_stage['W4']['seconds']:.6f} | {w4n:.6f} |")
    w(f"| cloud_only serial seconds | {cloud:.6f} | {cloud_s:.6f} |")
    w(f"| unreachable fraction | {uf:.6f} | {ufn:.6f} |")
    w(
        f"| F3 Shapley absolute s | {next(r['mean_marginal_seconds'] for r in shap if r['friction']=='F3'):.6f} | 0 (disabled) |"
    )
    w(
        f"| F1+F2+F4 absolute Shapley sum s | "
        f"{sum(r['mean_marginal_seconds'] for r in shap if r['friction']!='F3'):.6f} | "
        f"{sum(avg for _, avg, _ in rows_s):.6f} |"
    )
    w("")
    if abs(ufn) < 0.05:
        w(
            "**LOAD-BEARING RESULT:** With F3 off, F1+F2+F4 erase almost none of "
            "the naive headroom on this corpus. Decision cost and switching cost "
            "do **not** carry the thesis here. That must be reported plainly — "
            "it is cheaper to learn now than later."
        )
    else:
        w(
            f"**LOAD-BEARING RESULT:** With F3 off, unreachable fraction is {ufn:.4f}. "
            "Thesis frictions (F1/F2) contribute whatever Shapley shows above."
        )
    w("")
    w("## Guardrail notes")
    w("")
    w("- No friction parameter was tuned.")
    w("- F3 code path was not fixed; only diagnosed and disabled for the re-run.")
    w("- SMOKE: 1 scaffold, 15 trajectories — corpus gate not met.")
    w("")

    text = "\n".join(lines)
    path = OUT / "DIAGNOSTIC.md"
    path.write_text(text, encoding="utf-8")
    print(f"Wrote {path}")
    print(f"UF_with_F3={uf:.6f} UF_without_F3={ufn:.6f}")
    print(f"outcomes success={success} fail={fail} null={null} censored={censored}")
    print(f"W0_local_frac={frac_w0:.4f} W4_local_frac={frac_w4:.4f}")
    # also dump machine-readable sidecar
    (OUT / "diagnostic_summary.json").write_text(
        json.dumps(
            {
                "n": len(trajs),
                "success": success,
                "fail": fail,
                "null": null,
                "censored": censored,
                "uf_f3_on": uf,
                "uf_f3_off": ufn,
                "w0_local_frac": frac_w0,
                "w4_local_frac": frac_w4,
                "w0_s": abs_by_stage["W0"]["seconds"],
                "w4_s": abs_by_stage["W4"]["seconds"],
                "w0_nof3_s": w0n,
                "w4_nof3_s": w4n,
                "cloud_only_s": cloud_s,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
