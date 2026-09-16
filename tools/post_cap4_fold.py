"""POST-CAP4 fold-in: prefill refit report, CV result, RES-DECOMP, headline.

Reads sealed CAP-4 / X-2 / C-2 / 41e419bd artifacts only. Writes derived notes.
Does not touch raw/.

Usage:
  .\\.venv-seam\\Scripts\\python.exe tools\\post_cap4_fold.py
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.fdr_replay import (  # noqa: E402
    CAP4_SID,
    CAP4_SUMMARY,
    CAP4_TAG,
    _eval_power,
    _eval_quad,
    load_models,
    run,
)

OUT = ROOT / "derived" / "cap4"
DP_41_SID = "41e419bd-f3e9-43b1-8364-0ebd89fa086b"
C2_TTFT_SID = "c647f0c7-5cc9-47bb-a491-3450533c34d1"
C2_FIT_SID = "62395fdb-1899-415f-b708-6adc81a24dda"
X2_NR = "cb781dbf-3486-4fbc-a69a-34026f801abe"
X2_R = "9fdedb46-3318-4abc-a56f-50b7d23d25ca"
CANARY_REPRO_SID = "c4ddfd55-f64f-4c72-842c-a6470daaf5ca"
W2_REF_T1 = 2.819416  # docs/PROJECT_STATE.md Amendment 2026-08-31
N1_MEAS_T1 = 2.820283  # same; relative error 0.03%


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def legacy_vs_cap4(models: Any, cap4: dict[str, Any]) -> dict[str, Any]:
    """Compare legacy C-2 quadratic to CAP-4 measured medians at depth."""
    depths = [20000, 46000, 76000]
    rows: dict[str, Any] = {}
    per = cap4["analysis"]["per_arm"]
    for arm_id, block in per.items():
        kv = arm_id.replace("gpu_only_", "")
        med = {int(k): float(v) for k, v in block["median_prefill_s_by_n"].items()}
        fit = block["power_law_fit"]
        arm_rows = []
        for n in depths:
            measured = med[n]
            old = _eval_quad(models.prefill_gpu_legacy_quad, float(n))
            new = _eval_power((float(fit["C"]), float(fit["b"])), float(n))
            # signed: positive => old underpredicted measured
            err = measured - old
            arm_rows.append(
                {
                    "n": n,
                    "measured_median_s": measured,
                    "legacy_quad_pred_s": old,
                    "cap4_power_pred_s": new,
                    "legacy_minus_measured_s": old - measured,
                    "measured_over_legacy": measured / old if old else None,
                    "legacy_error_sign": (
                        "underpredicted"
                        if err > 0
                        else "overpredicted"
                        if err < 0
                        else "exact"
                    ),
                }
            )
        rows[kv] = {
            "arm_id": arm_id,
            "fit": {
                "C": float(fit["C"]),
                "b": float(fit["b"]),
                "fit_range_n": list(fit["fit_range_n"]),
                "form": "prefill_s = C * n^b",
                "tag": CAP4_TAG,
                "run_id": CAP4_SID,
            },
            "depths": arm_rows,
        }
    # Headline n^1.6 model from CAP4_PREDICTIONS (also underpredicted at 46k)
    p1_anchor_s = 13.54
    p1_anchor_n = 12000
    p1_exp = 1.6
    headline_rows = []
    for n in depths:
        pred = p1_anchor_s * ((n / p1_anchor_n) ** p1_exp)
        measured_by_arm = {
            arm.replace("gpu_only_", ""): float(
                per[arm]["median_prefill_s_by_n"][str(n)]
            )
            for arm in per
        }
        headline_rows.append(
            {
                "n": n,
                "n16_pred_s": pred,
                "measured_median_s_by_kv": measured_by_arm,
                "measured_over_n16": {
                    k: measured_by_arm[k] / pred for k in measured_by_arm
                },
            }
        )
    return {
        "legacy_quad": {
            "coef": {
                "a": models.prefill_gpu_legacy_quad[0],
                "b": models.prefill_gpu_legacy_quad[1],
                "c": models.prefill_gpu_legacy_quad[2],
            },
            "tag": models.prefill_gpu_legacy_quad_tag,
            "fit_source_run_id": C2_FIT_SID,
            "note": (
                "C-2 gpu_only_f16 quadratic fitted on n∈"
                f"{list(models.sources.get('prefill_gpu_legacy_quad_points', {}))}; "
                "absolute error vs CAP-4 measured is reported with sign "
                "(legacy often overpredicts absolute seconds at depth while the "
                "pre-registered n^1.6 ~115 s headline underpredicted)."
            ),
        },
        "per_kv": rows,
        "n16_headline_vs_measured": {
            "anchor": {"n": p1_anchor_n, "prefill_s": p1_anchor_s, "exponent": p1_exp},
            "source": "derived/cap4/CAP4_PREDICTIONS.json P1",
            "rows": headline_rows,
        },
    }


def timing_variance(cap4: dict[str, Any]) -> dict[str, Any]:
    """Per-rung per-arm median/min/max/CV from sealed CAP-4 PASS probes."""
    probes_path = ROOT / f"derived/cap4/sealed_{CAP4_SID}" / "probes.ndjson"
    by: dict[tuple[str, int], list[float]] = defaultdict(list)
    for line in probes_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("outcome") != "pass" or row.get("prefill_s") is None:
            continue
        by[(str(row["arm_id"]), int(row["n_tokens"]))].append(float(row["prefill_s"]))

    table: list[dict[str, Any]] = []
    first_cv_gt_10: dict[str, int | None] = {}
    for (arm, n), vs in sorted(by.items()):
        if len(vs) < 2:
            continue
        mean = statistics.mean(vs)
        sd = statistics.stdev(vs)
        cv = sd / mean if mean > 0 else float("nan")
        row = {
            "arm_id": arm,
            "n": n,
            "n_repeats": len(vs),
            "median_s": statistics.median(vs),
            "min_s": min(vs),
            "max_s": max(vs),
            "mean_s": mean,
            "stdev_s": sd,
            "cv": cv,
            "cv_pct": 100.0 * cv,
            "values_s": sorted(vs),
            "run_id": CAP4_SID,
        }
        table.append(row)
        if arm not in first_cv_gt_10 and cv > 0.10:
            first_cv_gt_10[arm] = n
    for arm in sorted({r["arm_id"] for r in table}):
        first_cv_gt_10.setdefault(arm, None)

    # Cross-session low-n reproducibility citation (PROJECT_STATE amendment)
    rel = abs(N1_MEAS_T1 - W2_REF_T1) / W2_REF_T1
    return {
        "kind": "cap4_timing_variance_result",
        "run_id": CAP4_SID,
        "cv_definition": "sample_stdev / mean over PASS repeats (typically 3)",
        "table": table,
        "first_n_cv_gt_10pct": first_cv_gt_10,
        "result": (
            "On Platform A under CAP-4 interleaved gpu_only RESIDENT, within-rung "
            "prefill CV first exceeds ~10% at n=32000 on all three KV arms. That is "
            "the depth beyond which this platform stops reproducing prefill timing "
            "to the low-n instrument standard. CV is not monotonic thereafter "
            "(paging / quiescence pressure), but 32000 is the first crossing."
        ),
        "low_n_cross_session_reproducibility": {
            "claim": "0.03% relative agreement on canary turn-1 prefill",
            "ref_t1_s": W2_REF_T1,
            "ref_source": "W-2 calibrated gpu_only_u8 nc=4000 d=400 RESIDENT",
            "measured_t1_s": N1_MEAS_T1,
            "measured_session_id": CANARY_REPRO_SID,
            "relative_error": rel,
            "relative_error_pct": 100.0 * rel,
            "citation": "docs/PROJECT_STATE.md Amendment 2026-08-31",
            "contrast": (
                "Low-n timing reproduces across sessions to 0.03%; CAP-4 shows "
                "within-session CV >10% from n=32000."
            ),
        },
    }


def res_decomp() -> dict[str, Any]:
    """Decompose X-2 cpu-p 5.17× residency wall into avoided prefill vs rest."""
    base = ROOT / "derived/bfcl_feasibility/x2_feasibility_table"

    def load(sid: str, report: str) -> dict[str, Any]:
        return _read(base / f"sealed_{sid}" / "artifacts" / report)

    nr = load(X2_NR, "session_residency_A_NON_RESIDENT_report.json")
    r = load(X2_R, "session_residency_A_RESIDENT_report.json")

    def sums(rep: dict[str, Any]) -> dict[str, float]:
        sum_ttft_steps = 0.0
        sum_ttft_turn = 0.0
        sum_decode_s = 0.0
        sum_entry_wall = 0.0
        n_turns = 0
        n_steps = 0
        for e in rep["gpu_probe"]["per_entry"]:
            sum_entry_wall += float(e.get("wall_s") or 0.0)
            for tm in e.get("turn_metrics") or []:
                n_turns += 1
                sum_ttft_turn += float(tm.get("ttft_s") or 0.0)
                gen = int(tm.get("generated_tokens") or 0)
                dec = float(tm.get("decode_tok_s") or 0.0)
                if dec > 0:
                    sum_decode_s += gen / dec
                for st in tm.get("steps") or []:
                    n_steps += 1
                    sum_ttft_steps += float(st.get("ttft_s") or 0.0)
        st = rep["gpu_probe"]["session_total_latency_s"]["sum"]
        return {
            "session_wall_s": float(st),
            "sum_entry_wall_s": sum_entry_wall,
            "sum_ttft_steps_s": sum_ttft_steps,
            "sum_ttft_turn_field_s": sum_ttft_turn,
            "sum_decode_s": sum_decode_s,
            "n_turns": float(n_turns),
            "n_steps": float(n_steps),
            "non_generate_overhead_s": sum_entry_wall - sum_ttft_steps,
        }

    snr = sums(nr)
    sr = sums(r)
    wall_nr = snr["session_wall_s"]
    wall_r = sr["session_wall_s"]
    ratio = wall_nr / wall_r
    wall_delta = wall_nr - wall_r
    avoided_prefill = snr["sum_ttft_steps_s"] - sr["sum_ttft_steps_s"]
    rest = wall_delta - avoided_prefill
    decode_delta = snr["sum_decode_s"] - sr["sum_decode_s"]
    overhead_delta = snr["non_generate_overhead_s"] - sr["non_generate_overhead_s"]

    return {
        "kind": "res_decomp",
        "question": (
            "Of the X-2 cpu-p NON_RESIDENT/RESIDENT session-wall ratio, how much is "
            "avoided prefill vs everything else?"
        ),
        "cells": {
            "NON_RESIDENT": {"session_id": X2_NR, **snr},
            "RESIDENT": {"session_id": X2_R, **sr},
        },
        "ratio_wall": ratio,
        "wall_delta_s": wall_delta,
        "avoided_prefill_s": avoided_prefill,
        "everything_else_s": rest,
        "avoided_prefill_fraction_of_wall_delta": avoided_prefill / wall_delta,
        "everything_else_fraction_of_wall_delta": rest / wall_delta,
        "decode_delta_s": decode_delta,
        "non_generate_overhead_delta_s": overhead_delta,
        "method": (
            "Avoided prefill = sum over all generate() steps of ttft_s "
            "(NON_RESIDENT) minus the same sum (RESIDENT). Turn-level ttft_s "
            "undercounts NON_RESIDENT multi-generate turns; step-level is required. "
            "Session walls are sealed session_total_latency_s.sum."
        ),
        "mechanism_prior": {
            "run_id": DP_41_SID,
            "note": (
                "41e419bd: RESIDENT turn-2 delta-prefill << turn-1; NON_RESIDENT "
                "turn-2 ≈ full re-prefill. Residency is a session-management "
                "decision whose payoff is set by how expensive prefill is on that "
                "hardware (cpu-p X-2: ~5.17×; absolute TTFT tens of seconds)."
            ),
        },
        "result": (
            f"cpu-p X-2 wall ratio = {ratio:.3f}× "
            f"({wall_nr:.1f} s NON_RESIDENT / {wall_r:.1f} s RESIDENT). "
            f"Avoided prefill explains {100 * avoided_prefill / wall_delta:.1f}% of "
            f"the {wall_delta:.1f} s wall delta; everything else is "
            f"{rest:.1f} s ({100 * rest / wall_delta:.1f}%). "
            "Residency payoff on this platform is almost entirely avoided re-prefill."
        ),
    }


def headline_arithmetic(cap4: dict[str, Any]) -> dict[str, Any]:
    """Replace 9750→46000/~2 min extrapolation with measured CAP-4 range."""
    # C-2 TTFT limits from c647f0c7 plan / CAP4 citations
    slo_n = {
        "gpu_only_u8": 9750,
        "gpu_only_u4": 9750,
        "note": "C-2 TTFT limit n; f16 ALLOC at 8000 on same run",
        "run_id": C2_TTFT_SID,
        "slo_prefill_s": 10.0,
    }
    per = cap4["analysis"]["per_arm"]
    at_46k = {
        arm.replace("gpu_only_", ""): {
            "median_s": float(block["median_prefill_s_by_n"]["46000"]),
            "min_s": float(block["prefill_s_min_max_by_n"]["46000"]["min"]),
            "max_s": float(block["prefill_s_min_max_by_n"]["46000"]["max"]),
        }
        for arm, block in per.items()
    }
    medians = [v["median_s"] for v in at_46k.values()]
    mins = [v["min_s"] for v in at_46k.values()]
    maxs = [v["max_s"] for v in at_46k.values()]
    # Token ratio vs 9750
    token_ratio = 46000 / 9750
    # Time ratio vs 10 s SLO at 9750: measured range at 46k
    time_ratio_med = {
        k: at_46k[k]["median_s"] / 10.0 for k in at_46k
    }
    return {
        "kind": "headline_arithmetic_post_cap4",
        "old_extrapolation": {
            "claim": "9,750 tokens at 10 s → 46,000 at ~2 minutes (~115 s)",
            "status": "falsified_by_CAP4",
            "predicted_s_at_46000": 115.0,
            "source": "CAP4_PREDICTIONS P1 n^1.6",
        },
        "slo_anchor": slo_n,
        "measured_at_46000": {
            "run_id": CAP4_SID,
            "by_kv": at_46k,
            "median_range_s": [min(medians), max(medians)],
            "extrema_range_s": [min(mins), max(maxs)],
        },
        "ratios": {
            "token_ratio_46000_over_9750": token_ratio,
            "time_ratio_median_prefill_over_10s_slo": time_ratio_med,
            "time_ratio_median_range": [min(time_ratio_med.values()), max(time_ratio_med.values())],
            "statement": (
                "9,750 tokens @ 10 s TTFT SLO (c647f0c7 u8/u4) versus 46,000 tokens "
                f"@ median prefill {min(medians):.1f}–{max(medians):.1f} s "
                f"(full min–max across arms {min(mins):.1f}–{max(maxs):.1f} s; "
                f"{CAP4_SID}). Token depth ratio {token_ratio:.2f}×; time ratio vs "
                f"10 s SLO is {min(time_ratio_med.values()):.1f}–"
                f"{max(time_ratio_med.values()):.1f}× (not ~12× / ~2 min)."
            ),
        },
    }


def write_markdown(
    fit_cmp: dict[str, Any],
    variance: dict[str, Any],
    decomp: dict[str, Any],
    headline: dict[str, Any],
) -> Path:
    lines = [
        "# POST-CAP4 — fold CAP-4 into models + residency decomposition",
        "",
        f"Generated: {_utc()}",
        "",
        f"CAP-4 sealed run: `{CAP4_SID}` · tag `{CAP4_TAG}`",
        "",
        "## 1. Prefill model refit (fdr_replay)",
        "",
        "Form: `prefill_s = C · n^b` per KV arm, fitted on CAP-4 PASS medians.",
        "",
        "| arm | b | C | fit_range_n | tag |",
        "|---|---:|---:|---|---|",
    ]
    for kv, block in fit_cmp["per_kv"].items():
        f = block["fit"]
        lines.append(
            f"| `gpu_only_{kv}` | {f['b']:.4f} | {f['C']:.6e} | "
            f"{f['fit_range_n']} | `{f['tag']}` |"
        )
    lines.extend(
        [
            "",
            "### Legacy C-2 quadratic vs CAP-4 measured (signed)",
            "",
            f"Legacy source: `{fit_cmp['legacy_quad']['fit_source_run_id']}` "
            "(gpu_only_f16 quadratic; used for all-KV comparison as the prior "
            "fdr_replay gpu prefill).",
            "",
            "| kv | n | measured median s | legacy pred s | measured/legacy | sign |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for kv, block in fit_cmp["per_kv"].items():
        for d in block["depths"]:
            lines.append(
                f"| {kv} | {d['n']} | {d['measured_median_s']:.3f} | "
                f"{d['legacy_quad_pred_s']:.3f} | {d['measured_over_legacy']:.3f} | "
                f"{d['legacy_error_sign']} |"
            )
    lines.extend(
        [
            "",
            "Note: the **pre-registered n^1.6 ~115 s** headline underpredicted at 46k "
            "(measured/predicted ≈ 2.0–2.2×). The **legacy fdr_replay quadratic** "
            "extrapolated from n≤12k **overpredicts** absolute seconds at 20k/46k/76k "
            "relative to CAP-4 medians; both are wrong at depth — CAP-4 replaces them "
            "for `n ≥ 12000`. Below the fit range, `prefill_s` still uses the C-2 "
            "quadratic (BFCL / X-2 operating depths).",
            "",
            "Re-emitted artifacts (new model):",            "",
            "- `derived/d1_replay/X2_REPLAY_CHECK.md`",
            "- `derived/d1_replay/x2_decomposition.json` / `X2_DECOMPOSITION.md`",
            "- `derived/d1_replay/configs.json` (48-point table)",
            "",
            "## 2. Timing variance (result)",
            "",
            variance["result"],
            "",
            "### First n where CV > 10%",
            "",
        ]
    )
    for arm, n in variance["first_n_cv_gt_10pct"].items():
        lines.append(f"- `{arm}`: **{n}**")
    low = variance["low_n_cross_session_reproducibility"]
    lines.extend(
        [
            "",
            "### Contrast — low-n cross-session reproducibility",
            "",
            f"- W-2 ref turn-1: **{low['ref_t1_s']} s**",
            f"- N-1 measured: **{low['measured_t1_s']} s** "
            f"(session `{low['measured_session_id']}`)",
            f"- Relative error: **{low['relative_error_pct']:.3f}%** (~0.03%)",
            f"- Citation: {low['citation']}",
            "",
            "### CV table (PASS cells)",
            "",
            "| arm | n | median | min | max | CV% |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in variance["table"]:
        if row["n"] > 76000:
            continue
        lines.append(
            f"| `{row['arm_id']}` | {row['n']} | {row['median_s']:.3f} | "
            f"{row['min_s']:.3f} | {row['max_s']:.3f} | {row['cv_pct']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## 3. RES-DECOMP — residency as avoided prefill",
            "",
            decomp["result"],
            "",
            f"- NON_RESIDENT: `{X2_NR}` wall **{decomp['cells']['NON_RESIDENT']['session_wall_s']:.3f} s**",
            f"- RESIDENT: `{X2_R}` wall **{decomp['cells']['RESIDENT']['session_wall_s']:.3f} s**",
            f"- Ratio: **{decomp['ratio_wall']:.3f}×**",
            f"- Avoided prefill (step ttft sum): **{decomp['avoided_prefill_s']:.3f} s** "
            f"({100 * decomp['avoided_prefill_fraction_of_wall_delta']:.2f}% of wall delta)",
            f"- Everything else: **{decomp['everything_else_s']:.3f} s** "
            f"({100 * decomp['everything_else_fraction_of_wall_delta']:.2f}%)",
            f"- Mechanism prior: `{DP_41_SID}` (RESIDENT delta-prefill << full re-prefill)",
            "",
            "Residency is a **session-management decision** whose payoff is set by how "
            "expensive prefill is on that hardware.",
            "",
            "## 4. Headline arithmetic (measured range)",
            "",
            headline["ratios"]["statement"],
            "",
            "Old claim (~115 s / ~2 min at 46k) is **falsified** — see CAP-4 P1.",
            "",
        ]
    )
    out = OUT / "POST_CAP4.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def append_cap4_results(variance: dict[str, Any], headline: dict[str, Any]) -> None:
    path = OUT / "CAP4_RESULTS.md"
    text = path.read_text(encoding="utf-8")
    marker = "\n## POST-CAP4 fold-in\n"
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n"
    block = [
        "",
        "## POST-CAP4 fold-in",
        "",
        f"Generated: {_utc()}",
        "",
        "### Timing variance result",
        "",
        variance["result"],
        "",
        "First n with CV > 10%: "
        + ", ".join(
            f"`{a}`={n}" for a, n in variance["first_n_cv_gt_10pct"].items()
        ),
        "",
        "Low-n contrast: 0.03% cross-session canary agreement "
        f"(`{CANARY_REPRO_SID}` vs W-2 ref); see `POST_CAP4.md`.",
        "",
        "### Headline arithmetic (replaces 9,750→46,000 / ~2 min)",
        "",
        headline["ratios"]["statement"],
        "",
        f"Full note: `derived/cap4/POST_CAP4.md`. Prefill model tag: `{CAP4_TAG}`.",
        "",
    ]
    path.write_text(text.rstrip() + "\n" + "\n".join(block), encoding="utf-8")


def main() -> int:
    models = load_models()
    cap4 = _read(CAP4_SUMMARY)
    fit_cmp = legacy_vs_cap4(models, cap4)
    variance = timing_variance(cap4)
    decomp = res_decomp()
    headline = headline_arithmetic(cap4)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "POST_CAP4_FIT_COMPARISON.json").write_text(
        json.dumps(fit_cmp, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "POST_CAP4_TIMING_VARIANCE.json").write_text(
        json.dumps(variance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "POST_CAP4_RES_DECOMP.json").write_text(
        json.dumps(decomp, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "POST_CAP4_HEADLINE.json").write_text(
        json.dumps(headline, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    md = write_markdown(fit_cmp, variance, decomp, headline)
    append_cap4_results(variance, headline)

    # Re-emit X-2 + 48-point table under new prefill model
    art = run(write_outputs=True)
    print(
        json.dumps(
            {
                "ok": True,
                "post_cap4_md": str(md),
                "fit_tag": CAP4_TAG,
                "fits": {
                    kv: {
                        "C": models.prefill_gpu_power[kv][0],
                        "b": models.prefill_gpu_power[kv][1],
                    }
                    for kv in models.prefill_gpu_power
                },
                "fit_range_n": list(models.prefill_gpu_fit_range_n),
                "first_cv_gt_10": variance["first_n_cv_gt_10pct"],
                "res_decomp_ratio": decomp["ratio_wall"],
                "avoided_prefill_frac": decomp[
                    "avoided_prefill_fraction_of_wall_delta"
                ],
                "x2_errors_s": [r["error_s"] for r in art["x2_replay"]],
                "n_configs": art["configs"]["n_configs"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
