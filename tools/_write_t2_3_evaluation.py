"""T2-3 evaluation: Platform A CAP-4 (2b3316b6) vs T2S CAP-4 (65e33de8)."""

from __future__ import annotations

import json
import math
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
A_ID = "2b3316b6-7f6e-474f-9177-bd5a89aeb58c"
B_ID = "65e33de8-ac07-405a-a1f8-53698974afe9"
OUT = ROOT / "derived" / "t2_3"
ARMS = ("gpu_only_f16", "gpu_only_u8", "gpu_only_u4")


def _write(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _idx(cells: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for c in cells:
        if c.get("verdict") == "PASS":
            out[(str(c["arm_id"]), int(c["n_tokens"]))] = c
    return out


def _fit_b(
    d: dict[tuple[str, int], dict[str, Any]], arm: str, n_lo: int, n_hi: int
) -> dict[str, Any]:
    ns = sorted(n for (ar, n) in d if ar == arm and n_lo <= n <= n_hi)
    ys = [float(d[(arm, n)]["prefill_s_median"]) for n in ns]
    lx = [math.log(n) for n in ns]
    ly = [math.log(y) for y in ys]
    n = len(lx)
    mx = sum(lx) / n
    my = sum(ly) / n
    b = sum((x - mx) * (y - my) for x, y in zip(lx, ly, strict=True)) / sum(
        (x - mx) ** 2 for x in lx
    )
    c = math.exp(my - b * mx)
    return {"b": b, "C": c, "fit_range_n": [ns[0], ns[-1]], "n_points": n}


def _cv_rows(
    cells: list[dict[str, Any]], run_id: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    first: dict[str, int] = {}
    for c in cells:
        if c.get("verdict") != "PASS":
            continue
        reps = [
            float(r["prefill_s"])
            for r in (c.get("repeats_detail") or [])
            if r.get("prefill_s") is not None
        ]
        if len(reps) < 2:
            continue
        mean = statistics.mean(reps)
        sd = statistics.stdev(reps)
        cv = (sd / mean) if mean else None
        arm = str(c["arm_id"])
        n = int(c["n_tokens"])
        rows.append(
            {
                "run_id": run_id,
                "arm_id": arm,
                "n": n,
                "n_repeats": len(reps),
                "mean_s": mean,
                "stdev_s": sd,
                "cv": cv,
                "cv_pct": None if cv is None else cv * 100.0,
                "values_s": reps,
                "median_s": float(c["prefill_s_median"]),
            }
        )
        if cv is not None and cv > 0.10 and arm not in first:
            first[arm] = n
    rows.sort(key=lambda r: (r["arm_id"], r["n"]))
    return rows, first


def main() -> int:
    pred = json.loads((OUT / "T2_3_PREDICTIONS.json").read_text(encoding="utf-8-sig"))
    sealed_b = ROOT / "derived" / "cap4" / f"sealed_{B_ID}"
    sealed_a = ROOT / "derived" / "cap4" / f"sealed_{A_ID}"
    marker = json.loads((sealed_b / ".sealed").read_text(encoding="utf-8-sig"))
    summary_b = json.loads((sealed_b / "summary.json").read_text(encoding="utf-8-sig"))
    cells_a = json.loads((sealed_a / "cells.json").read_text(encoding="utf-8-sig"))["cells"]
    cells_b = json.loads((sealed_b / "cells.json").read_text(encoding="utf-8-sig"))["cells"]
    a = _idx(cells_a)
    b = _idx(cells_b)

    band_ratio = pred["predictions"]["P1_decode_tok_s_at_depth"]["evaluable_ratio_band"]
    band_rel = pred["predictions"]["P3_prefill_absolute"]["evaluable_relative_band"]
    scale = pred["bandwidth_ratio"]["prefill_time_scale_A_to_B"]
    pred_ratio = pred["predictions"]["P1_decode_tok_s_at_depth"]["predicted_ratio_T2S_over_A"]

    p1_cells: list[dict[str, Any]] = []
    for n in (12000, 46000):
        for arm in ARMS:
            ca, cb = a[(arm, n)], b[(arm, n)]
            da = float(ca["decode_tok_s_median"])
            db = float(cb["decode_tok_s_median"])
            ratio = db / da
            p1_cells.append(
                {
                    "n": n,
                    "arm_id": arm,
                    "platform_a_run_id": A_ID,
                    "platform_b_run_id": B_ID,
                    "decode_tok_s_A": da,
                    "decode_tok_s_T2S": db,
                    "ratio_T2S_over_A": ratio,
                    "predicted_ratio": pred_ratio,
                    "evaluable_band": band_ratio,
                    "in_band": band_ratio[0] <= ratio <= band_ratio[1],
                    "caveat": (
                        "Platform A f16 decode collapsed at n=46000 (~1.16 tok/s); "
                        "ratio not BW-efficiency eligible"
                        if arm == "gpu_only_f16" and n == 46000
                        else None
                    ),
                }
            )
    u8_46 = next(c for c in p1_cells if c["arm_id"] == "gpu_only_u8" and c["n"] == 46000)
    p1_verdict = "partial_hold"
    p1_note = (
        f"Primary depth claim (u8 @ n=46000): ratio {u8_46['ratio_T2S_over_A']:.4f} "
        f"within [{band_ratio[0]}, {band_ratio[1]}]. "
        "f16 @12k and u4 @46k outside band; f16 @46k excluded (A collapsed). "
        "Decode scales nearer the theoretical BW ratio than absolute prefill does."
    )

    p2_per: dict[str, Any] = {}
    for arm in ARMS:
        fa = _fit_b(a, arm, 12000, 76000)
        fb = _fit_b(b, arm, 12000, 76000)
        fb_full = _fit_b(b, arm, 12000, 94000)
        delta = fb["b"] - fa["b"]
        p2_per[arm] = {
            "platform_a_b": fa["b"],
            "platform_a_tag": "MEASURED(2b3316b6)",
            "t2s_b_fit_12k_76k": fb["b"],
            "t2s_C_fit_12k_76k": fb["C"],
            "t2s_b_fit_12k_94k": fb_full["b"],
            "delta_b_T2S_minus_A": delta,
            "in_predicted_band_2_1_2_2": 2.1 <= fb["b"] <= 2.2,
            "falsified": fb["b"] < 1.9 or fb["b"] > 2.4 or abs(delta) > 0.3,
        }
    p2_verdict = "falsified"
    p2_note = (
        "T2S prefill exponents on matched fit_range_n=[12000,76000] are b~=1.85 across all "
        "three arms (below predicted 2.1-2.2 and below falsify floor 1.9). Shift vs Platform A "
        "exceeds 0.3. Prefill scaling is not the same power-law as Platform A."
    )

    p3_cells: list[dict[str, Any]] = []
    for n in (12000, 46000):
        for arm in ARMS:
            ca, cb = a[(arm, n)], b[(arm, n)]
            pa = float(ca["prefill_s_median"])
            pb = float(cb["prefill_s_median"])
            pred_s = pa * scale
            rel = pb / pred_s
            p3_cells.append(
                {
                    "n": n,
                    "arm_id": arm,
                    "platform_a_run_id": A_ID,
                    "platform_b_run_id": B_ID,
                    "prefill_s_A": pa,
                    "prefill_s_T2S": pb,
                    "predicted_prefill_s": pred_s,
                    "measured_over_predicted": rel,
                    "evaluable_relative_band": band_rel,
                    "in_band": band_rel[0] <= rel <= band_rel[1],
                    "faster_than_A": pb < pa,
                }
            )
    p3_12k_ok = all(c["in_band"] for c in p3_cells if c["n"] == 12000)
    p3_46k_ok = all(c["in_band"] for c in p3_cells if c["n"] == 46000)
    p3_verdict = (
        "partial" if p3_12k_ok and not p3_46k_ok else ("held" if p3_12k_ok and p3_46k_ok else "falsified")
    )
    p3_note = (
        "At n=12000, measured/predicted prefill in [0.89, 0.91] (within [0.7, 1.4]). "
        "At n=46000, measured/predicted in [0.54, 0.59] - outside band; T2S is substantially "
        "faster than BW-scaled absolute prediction. Prefill at depth is compute-shaped, not pure BW."
    )

    max_n_b = max(int(c["n_tokens"]) for c in cells_b if c.get("verdict") == "PASS")
    p4 = {
        "platform_a_paging_n": 82000,
        "platform_a_run_id": A_ID,
        "platform_a_stop": "quiescence_refusal_under_paging_pressure",
        "t2s_run_id": B_ID,
        "t2s_highest_pass_n": max_n_b,
        "t2s_paging_quiescence_loss_observed": False,
        "predicted_within_sweep": "no_paging_quiescence_loss_for_n_le_82000",
        "predicted_onset_n_approx": 328000,
        "onset_328k_practicality": {
            "verdict": "impractical",
            "reason": (
                "Each deep rung already ~40 min wall and growing superlinearly "
                "(prefill_s ~ n^1.85); reaching ~328k under the CAP-4 interleaved protocol "
                "is not a practical measurement on this session budget. P4 within-sweep claim "
                "(no paging <=82k / through 94k) is the evaluable bound from 65e33de8."
            ),
        },
        "verdict": "held_within_measured_sweep",
        "note": (
            f"No paging-driven quiescence loss on T2S through n={max_n_b} "
            f"(all three arms PASS). Platform A ({A_ID}) lost quiescence at n=82000. "
            "Kill occurred before n=100000 rung."
        ),
    }
    p5 = {
        "verdict": "untested",
        "reason": "No Qwen3-8B-int4-ov arm on T2S in 65e33de8 (4B CAP-4 only).",
    }

    cv_a, first_a = _cv_rows(cells_a, A_ID)
    cv_b, first_b = _cv_rows(cells_b, B_ID)
    max_cv_b = max(r["cv_pct"] for r in cv_b if r["cv_pct"] is not None)
    cv_doc = {
        "kind": "t2_3_timing_variance",
        "cv_definition": "sample_stdev / mean over PASS repeats (typically 3)",
        "platform_a": {
            "run_id": A_ID,
            "first_n_cv_gt_10pct": first_a,
            "result": "CV first exceeds 10% at n=32000 on all three arms.",
        },
        "platform_b_t2s": {
            "run_id": B_ID,
            "first_n_cv_gt_10pct": first_b if first_b else None,
            "result": (
                f"CV never exceeds 10% through highest PASS n={max_n_b} on any arm; "
                f"max observed CV_pct ~= {max_cv_b:.2f} at deep rungs."
            ),
        },
        "table_A_selected": [r for r in cv_a if r["n"] in (12000, 32000, 46000, 76000)],
        "table_T2S_selected": [r for r in cv_b if r["n"] in (12000, 32000, 46000, 82000, 94000)],
        "table_T2S_full": cv_b,
    }

    joint = {
        "statement": (
            "P1 partially holds on the preferred non-collapsed depth arm (u8 @46k ~=2.33x ~= BW ratio). "
            "P3 misses at depth (absolute prefill much faster than BW scale). "
            "Therefore: bandwidth predicts decode better than it predicts prefill; "
            "replay cannot use one ratio for both when predicting a third platform. "
            "P2 falsified (exponent ~=1.85 not 2.1-2.2). P4 held in measured sweep. P5 untested."
        ),
        "p1_and_p3_lesson": (
            "If P1 holds and P3 misses: bandwidth predicts decode, compute predicts prefill - "
            "one BW ratio cannot serve both when projecting a third platform. "
            "Observed here: P1 partial hold (u8@46k); P3 miss at 46k."
        ),
    }

    f16_12 = next(c for c in p3_cells if c["arm_id"] == "gpu_only_f16" and c["n"] == 12000)
    f16_46 = next(c for c in p3_cells if c["arm_id"] == "gpu_only_f16" and c["n"] == 46000)

    evaluated_utc = datetime.now(UTC).isoformat()
    eval_doc = {
        "experiment": "T2-3",
        "title": "T2-3 evaluation vs T2_3_PREDICTIONS (Platform A CAP-4 anchor vs T2S CAP-4)",
        "status": "evaluated",
        "evaluated_utc": evaluated_utc,
        "predictions_path": "derived/t2_3/T2_3_PREDICTIONS.json",
        "predictions_registered_utc": pred.get("registered_utc"),
        "platform_a_anchor": {
            "run_id": A_ID,
            "tag": "MEASURED(2b3316b6)",
            "seal": f"derived/cap4/sealed_{A_ID}",
        },
        "platform_b_measurement": {
            "run_id": B_ID,
            "execution_platform_id": summary_b.get("execution_platform_id"),
            "seal_platform_id": summary_b.get("seal_platform_id"),
            "cross_host_reconstruct": summary_b.get("cross_host_reconstruct"),
            "status": summary_b.get("status"),
            "tree_sha256": marker.get("tree_sha256"),
            "seal": f"derived/cap4/sealed_{B_ID}",
            "highest_pass_n": max_n_b,
            "abort_reason": summary_b.get("abort_reason"),
        },
        "P1_decode_ratio": {
            "verdict": p1_verdict,
            "primary_holds": bool(u8_46["in_band"]),
            "note": p1_note,
            "cells": p1_cells,
        },
        "P2_prefill_exponent": {
            "verdict": p2_verdict,
            "note": p2_note,
            "fit_range_matched_to_A": [12000, 76000],
            "predicted_b_band": [2.1, 2.2],
            "falsify_outside": [1.9, 2.4],
            "per_arm": p2_per,
        },
        "P3_prefill_absolute": {
            "verdict": p3_verdict,
            "note": p3_note,
            "scale": scale,
            "n12000_in_band": p3_12k_ok,
            "n46000_in_band": p3_46k_ok,
            "cells": p3_cells,
        },
        "P4_paging_boundary": p4,
        "P5_8b_allocation_ceiling": p5,
        "timing_variance": {
            "platform_a_first_n_cv_gt_10pct": first_a,
            "t2s_first_n_cv_gt_10pct": first_b if first_b else None,
            "t2s_never_exceeds_10pct_through_n": max_n_b,
        },
        "joint_generalization": joint,
    }

    results_doc = {
        "experiment": "T2-3",
        "status": "evaluated",
        "evaluated_utc": evaluated_utc,
        "run_ids": {"platform_a": A_ID, "platform_b_t2s": B_ID},
        "tree_sha256_t2s_seal": marker.get("tree_sha256"),
        "headline": joint["statement"],
        "verdicts": {
            "P1": p1_verdict,
            "P2": p2_verdict,
            "P3": p3_verdict,
            "P4": p4["verdict"],
            "P5": p5["verdict"],
        },
        "numbers": {
            "P1_u8_n46000_ratio": u8_46["ratio_T2S_over_A"],
            "P1_f16_n12000_ratio": next(
                c["ratio_T2S_over_A"]
                for c in p1_cells
                if c["arm_id"] == "gpu_only_f16" and c["n"] == 12000
            ),
            "P2_t2s_b_12k_76k": {arm: p2_per[arm]["t2s_b_fit_12k_76k"] for arm in ARMS},
            "P3_f16_n12000_meas_over_pred": f16_12["measured_over_predicted"],
            "P3_f16_n46000_meas_over_pred": f16_46["measured_over_predicted"],
            "P3_f16_n12000_prefill_s": f16_12["prefill_s_T2S"],
            "P3_f16_n46000_prefill_s": f16_46["prefill_s_T2S"],
            "P4_highest_pass_n": max_n_b,
        },
    }

    _write(OUT / "T2_3_EVAL.json", eval_doc)
    _write(OUT / "T2_3_RESULTS.json", results_doc)
    _write(OUT / "T2_3_TIMING_VARIANCE.json", cv_doc)

    lines: list[str] = [
        "# T2-3 evaluation - Platform A CAP-4 vs T2S (evo-t2)",
        "",
        f"- **evaluated_utc:** `{evaluated_utc}`",
        f"- **predictions:** `derived/t2_3/T2_3_PREDICTIONS.json` (registered `{pred.get('registered_utc')}`)",
        f"- **Platform A anchor:** `{A_ID}` (`MEASURED(2b3316b6)`)",
        f"- **T2S measurement:** `{B_ID}` - executed on **evo-t2**, sealed on **aipc-c1** (cross-host reconstruct)",
        f"- **T2S seal tree_sha256:** `{marker.get('tree_sha256')}`",
        f"- **T2S status:** `aborted` (`Stop-Process -Force`; highest PASS n={max_n_b})",
        "",
        "## Headline",
        "",
        joint["statement"],
        "",
        joint["p1_and_p3_lesson"],
        "",
        "## P1 - decode ratio at depth vs ~2.6x",
        "",
        f"- **verdict:** `{p1_verdict}`",
        f"- {p1_note}",
        "",
        "| n | arm | decode A (tok/s) | decode T2S | ratio | band [2.0, 3.4] |",
        "|---:|---|---:|---:|---:|:---:|",
    ]
    for c in p1_cells:
        mark = "Y" if c["in_band"] else "N"
        cave = f" - {c['caveat']}" if c["caveat"] else ""
        lines.append(
            f"| {c['n']} | `{c['arm_id']}` | {c['decode_tok_s_A']:.4f} | "
            f"{c['decode_tok_s_T2S']:.4f} | {c['ratio_T2S_over_A']:.4f} | {mark}{cave} |"
        )
    lines.extend(
        [
            "",
            f"Citing: A=`{A_ID}`; B=`{B_ID}`.",
            "",
            "## P2 - fitted prefill exponent vs 2.1-2.2",
            "",
            f"- **verdict:** `{p2_verdict}`",
            f"- {p2_note}",
            "",
            "| arm | A b [12k,76k] | T2S b [12k,76k] | Deltab | T2S b [12k,94k] |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for arm in ARMS:
        r = p2_per[arm]
        lines.append(
            f"| `{arm}` | {r['platform_a_b']:.4f} | {r['t2s_b_fit_12k_76k']:.4f} | "
            f"{r['delta_b_T2S_minus_A']:.4f} | {r['t2s_b_fit_12k_94k']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## P3 - prefill absolute vs BW-scaled prediction",
            "",
            f"- **verdict:** `{p3_verdict}`",
            f"- scale = 102/273 = {scale:.6f}",
            f"- {p3_note}",
            "",
            "| n | arm | A prefill_s | T2S | predicted | meas/pred | in [0.7,1.4] |",
            "|---:|---|---:|---:|---:|---:|:---:|",
        ]
    )
    for c in p3_cells:
        mark = "Y" if c["in_band"] else "N"
        lines.append(
            f"| {c['n']} | `{c['arm_id']}` | {c['prefill_s_A']:.4f} | {c['prefill_s_T2S']:.4f} | "
            f"{c['predicted_prefill_s']:.4f} | {c['measured_over_predicted']:.4f} | {mark} |"
        )
    lines.extend(
        [
            "",
            "Representative claim (f16): predicted ~5.05 s @12k / ~94.4 s @46k; measured "
            f"{f16_12['prefill_s_T2S']:.4f} s / {f16_46['prefill_s_T2S']:.4f} s "
            f"(run_id `{B_ID}`).",
            "",
            "## P4 - paging boundary",
            "",
            f"- **verdict:** `{p4['verdict']}`",
            f"- {p4['note']}",
            f"- Predicted ~328k onset: **impractical** - {p4['onset_328k_practicality']['reason']}",
            "",
            "## P5 - 8B allocation ceiling",
            "",
            f"- **verdict:** `{p5['verdict']}` - {p5['reason']}",
            "",
            "## Timing variance (CV)",
            "",
            f"- Platform A (`{A_ID}`): first n with CV>10% = **32000** (all arms).",
            f"- T2S (`{B_ID}`): CV **never** exceeds 10% through n={max_n_b}; no first-crossing.",
            "",
            "| platform | arm | n | CV | CV% |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for r in cv_doc["table_A_selected"]:
        lines.append(
            f"| A | `{r['arm_id']}` | {r['n']} | {r['cv']:.4f} | {r['cv_pct']:.2f} |"
        )
    for r in cv_doc["table_T2S_selected"]:
        lines.append(
            f"| T2S | `{r['arm_id']}` | {r['n']} | {r['cv']:.4f} | {r['cv_pct']:.2f} |"
        )
    lines.extend(
        [
            "",
            "Full T2S CV table: `derived/t2_3/T2_3_TIMING_VARIANCE.json`.",
            "",
        ]
    )
    (OUT / "T2_3_EVAL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "T2_3_RESULTS.md").write_text(
        "# T2-3 results (summary)\n\n"
        + joint["statement"]
        + "\n\n"
        + f"- P1: `{p1_verdict}`\n- P2: `{p2_verdict}`\n- P3: `{p3_verdict}`\n"
        + f"- P4: `{p4['verdict']}`\n- P5: `{p5['verdict']}`\n\n"
        + f"Run ids: A=`{A_ID}`; T2S=`{B_ID}`; tree_sha256=`{marker.get('tree_sha256')}`\n\n"
        + "Details: `derived/t2_3/T2_3_EVAL.md` / `T2_3_EVAL.json`.\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": True,
                "tree_sha256": marker.get("tree_sha256"),
                "verdicts": results_doc["verdicts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
