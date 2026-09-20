"""H1-ANALYZE: aggregate sealed R2a/R2b, census, cost fit (no hardware).

Sealed trees are read-only. Writes only under derived/h1_hybrid/ (analysis).
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
R2A = ROOT / "derived/h1_hybrid/slo_escalate_86d0f4cf-e8c2-4ce5-96da-04c6a9c129f3"
R2B = ROOT / "derived/h1_hybrid/emission_escalate_8ffd8371-ac15-492b-afb7-a45e4fae2c1b"
W3 = ROOT / "derived/bfcl_feasibility/w3_weight_quality/6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a"
OUT_DIR = ROOT / "derived/h1_hybrid"

TTFT_SLO_S = 10.0
DECODE_SLO_TOK_S = 6.0

SCORER_CHECKER = "bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker"
SCORER_WRAPPER = "apu_characterization.cap01.bfcl_cap01_multi_turn_checker"
SCORER_VERSION = "2025.12.17"
W3_SEAL = "6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_scorer_matches_w3(plan: dict[str, Any]) -> dict[str, Any]:
    scorer = plan["scorer"]
    if scorer.get("checker") != SCORER_CHECKER:
        raise SystemExit(f"REFUSED -- checker mismatch: {scorer.get('checker')!r}")
    if scorer.get("wrapper") != SCORER_WRAPPER:
        raise SystemExit(f"REFUSED -- wrapper mismatch: {scorer.get('wrapper')!r}")
    if scorer.get("bfcl_eval_version") != SCORER_VERSION:
        raise SystemExit(
            f"REFUSED -- bfcl_eval_version mismatch: {scorer.get('bfcl_eval_version')!r}"
        )
    if W3_SEAL not in (scorer.get("w3_seal_refs") or []):
        raise SystemExit(f"REFUSED -- W-3 seal ref missing from plan scorer: {scorer}")
    wrapper_path = ROOT / "apu_characterization/cap01/bfcl_cap01_multi_turn_checker.py"
    wrapper_sha = _sha256_file(wrapper_path)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import tools.bfcl_feasibility_probe as probe

    inv = probe.inventory()
    checker_path = (
        Path(inv["unpacked_path"])
        / "bfcl_eval/eval_checker/multi_turn_eval/multi_turn_checker.py"
    )
    checker_sha = _sha256_file(checker_path)
    return {
        "plan_scorer": scorer,
        "wrapper_path": str(wrapper_path),
        "wrapper_sha256": wrapper_sha,
        "checker_path": str(checker_path),
        "checker_sha256": checker_sha,
        "bfcl_eval_version": SCORER_VERSION,
        "w3_seal_ref": W3_SEAL,
        "match": True,
        "note": (
            "Scorer identity matches W-3 pin. Sealed H1 trees do not persist "
            "model_result_decoded/score, so BFCL trajectory_pass cannot be "
            "recomputed from turn_ledger.json alone."
        ),
    }


def slo_ok(t: dict[str, Any]) -> bool:
    """MEASURED ttft/decode only - ctx is not an SLO escalate gate (H1-3POLICY)."""
    if t.get("ttft_s") is not None and float(t["ttft_s"]) > TTFT_SLO_S:
        return False
    if t.get("decode_tok_s") is not None and float(t["decode_tok_s"]) < DECODE_SLO_TOK_S:
        return False
    return True


def aggregate(entries: list[dict[str, Any]], label: str) -> dict[str, Any]:
    n = len(entries)
    entry_slo: list[float] = []
    turn_slo: list[bool] = []
    for e in entries:
        turns = e.get("turns") or []
        if not turns:
            continue
        oks = [slo_ok(t) for t in turns]
        entry_slo.append(sum(oks) / len(oks))
        turn_slo.extend(oks)
    emit_ok = sum(
        1
        for e in entries
        if (e.get("turns") or [])
        and all(t.get("emitted_parseable_tool_call") for t in e["turns"])
    )
    op_complete = sum(
        1
        for e in entries
        if e.get("status") == "complete"
        and int(e.get("turns_executed") or 0) >= int(e.get("turns_in_entry") or 0)
        and e.get("stop_reason") == "completed"
    )
    walls = [sum(float(t["turn_wall_s"]) for t in (e.get("turns") or [])) for e in entries]
    usd = sum(float(e.get("cloud_usd_entry") or 0.0) for e in entries)
    stop = Counter(e.get("stop_reason") for e in entries)
    esc: list[dict[str, Any]] = []
    for e in entries:
        for t in e.get("turns") or []:
            if t.get("escalated") and t.get("escalate_reason") not in (
                None,
                "stay_cloud",
                "cloud_only",
            ):
                esc.append(
                    {
                        "entry_id": e["entry_id"],
                        "turn": t["turn"],
                        "reason": t["escalate_reason"],
                        "n_ctx": t.get("n_ctx"),
                        "cloud_usd": float(e.get("cloud_usd_entry") or 0.0),
                        "n_cloud_turns": sum(
                            1 for x in e["turns"] if x.get("placement") == "cloud"
                        ),
                        "status": e.get("status"),
                        "stop_reason": e.get("stop_reason"),
                        "turns_executed": e.get("turns_executed"),
                        "turns_in_entry": e.get("turns_in_entry"),
                    }
                )
                break
    return {
        "label": label,
        "n": n,
        "slo_fraction_mean_over_entries": (
            sum(entry_slo) / len(entry_slo) if entry_slo else None
        ),
        "slo_fraction_mean_over_turns": (
            sum(1 for x in turn_slo if x) / len(turn_slo) if turn_slo else None
        ),
        "emission_rate_entry": emit_ok / n,
        "n_emit_ok": emit_ok,
        "operational_completion": op_complete / n,
        "n_operational_complete": op_complete,
        "bfcl_trajectory_completion": None,
        "bfcl_trajectory_note": (
            "UNAVAILABLE: sealed H1 turn_ledger has no model_result_decoded/score"
        ),
        "session_time_sum_s": sum(walls),
        "session_time_mean_s": sum(walls) / n,
        "cloud_usd": usd,
        "stop_reason": dict(stop),
        "n_escalated": len(esc),
        "escalations": esc,
        "n_turns_total": sum(len(e.get("turns") or []) for e in entries),
    }


def phase_timers(entries: list[dict[str, Any]]) -> dict[str, Any]:
    others: list[float] = []
    tools: list[float] = []
    for e in entries:
        for t in e.get("turns") or []:
            others.append(float(t["t_other"]))
            tools.append(float(t["t_tool_exec"]))
    others_s = sorted(others)
    tools_s = sorted(tools)

    def pct(xs: list[float], p: float) -> float:
        return xs[min(len(xs) - 1, int(p * len(xs)))]

    return {
        "t_other": {
            "n": len(others),
            "mean": statistics.mean(others),
            "median": statistics.median(others),
            "p95": pct(others_s, 0.95),
            "max": max(others),
            "min": min(others),
        },
        "t_tool_exec": {
            "n": len(tools),
            "mean": statistics.mean(tools),
            "median": statistics.median(tools),
            "p95": pct(tools_s, 0.95),
            "max": max(tools),
        },
        "entry0_t_other": [float(t["t_other"]) for t in entries[0]["turns"]],
        "x2_uncovered_s_per_turn": 4.8,
        "finding": (
            "X-2 ~4.8 s/turn gap is gone on R2a: median t_other is ~0.09 s "
            "(entry0 turn0 t_other~=0.094 s). Phase timers now capture "
            "t_template_build + t_tokenize + t_generate + t_tool_exec + t_other "
            "with residual closure; X-2 lacked these additive phases so the "
            "wall-(prefill+decode) remainder looked like ~4.8 s uncovered."
        ),
    }


def census_r2a(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Host-observable failure classes at zero cost from the sealed ledger.

    Class D (SILENT) requires BFCL trajectory failure with clean tool calls.
    Scores were not persisted -> D cannot be separated from pass among host-clear.
    """
    class_a: list[str] = []
    class_b: list[str] = []
    host_clear: list[str] = []
    first_a: Counter[int] = Counter()
    first_b: Counter[int] = Counter()
    for e in entries:
        eid = str(e["entry_id"])
        turns = e.get("turns") or []
        if e.get("stop_reason") == "max_steps":
            class_b.append(eid)
            first_b[int(turns[-1]["turn"]) if turns else -1] += 1
            continue
        no_emit = next(
            (int(t["turn"]) for t in turns if not t.get("emitted_parseable_tool_call")),
            None,
        )
        if no_emit is not None:
            class_a.append(eid)
            first_a[no_emit] += 1
            continue
        host_clear.append(eid)
    n = len(entries)
    return {
        "definition": (
            "A/B assigned from sealed turn_ledger only. C requires a tool_error "
            "field (absent). D requires BFCL fail with clean tools (score absent)."
        ),
        "A_no_parseable_tool_call": {
            "n": len(class_a),
            "frac": len(class_a) / n,
            "first_observable_turn_hist": {str(k): v for k, v in sorted(first_a.items())},
        },
        "B_max_steps": {
            "n": len(class_b),
            "frac": len(class_b) / n,
            "first_observable_turn_hist": {str(k): v for k, v in sorted(first_b.items())},
            "ids": class_b,
        },
        "C_tool_exec_error": {
            "n": 0,
            "frac": 0.0,
            "note": "No tool_error / exception field on sealed H1 turns",
        },
        "host_clear_emit_ok_not_max_steps": {
            "n": len(host_clear),
            "frac": len(host_clear) / n,
            "note": (
                "Pass vs D(SILENT) not separable without persisted BFCL score. "
                "These entries show no zero-cost host failure signal."
            ),
        },
        "D_silent": {
            "n": None,
            "frac": None,
            "status": "UNAVAILABLE",
            "router_implication": (
                "Class D is the only failure a router cannot see. Its share "
                "cannot be measured from this sealed tree; persisting "
                "score/model_result_decoded on future H1 seals is required."
            ),
        },
        "n_entries": n,
    }


def linear_fit(xs: list[float], ys: list[float]) -> dict[str, float]:
    n = len(xs)
    meanx = sum(xs) / n
    meany = sum(ys) / n
    num = sum((x - meanx) * (y - meany) for x, y in zip(xs, ys, strict=True))
    den = sum((x - meanx) ** 2 for x in xs)
    b = num / den if den else float("nan")
    a = meany - b * meanx
    ss_tot = sum((y - meany) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys, strict=True))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else float("nan")
    return {"a": a, "b": b, "r2": r2, "n": float(n), "mean_x": meanx, "mean_y": meany}


def cost_fit(esc: list[dict[str, Any]]) -> dict[str, Any]:
    xs_ctx = [float(r["n_ctx"] or 0) for r in esc]
    xs_turns = [float(r["n_cloud_turns"]) for r in esc]
    ys = [float(r["cloud_usd"]) for r in esc]
    return {
        "usd_vs_context_at_escalation": linear_fit(xs_ctx, ys),
        "usd_vs_n_cloud_turns": linear_fit(xs_turns, ys),
        "n_escalated": len(esc),
        "measured_usd_sum": sum(ys),
        "mean_cloud_usd_per_escalated": sum(ys) / len(ys),
        "mean_ctx_at_escalation": sum(xs_ctx) / len(xs_ctx),
        "mean_n_cloud_turns": sum(xs_turns) / len(xs_turns),
    }


def main() -> None:
    for p in (R2A, R2B):
        if not (p / ".sealed").is_file():
            raise SystemExit(f"REFUSED -- missing seal marker {p / '.sealed'}")
        if not (p / "turn_ledger.json").is_file():
            raise SystemExit(f"REFUSED -- missing turn_ledger {p}")

    plan_a = json.loads((R2A / "plan.json").read_text(encoding="utf-8"))
    plan_b = json.loads((R2B / "plan.json").read_text(encoding="utf-8"))
    scorer = assert_scorer_matches_w3(plan_a)
    assert_scorer_matches_w3(plan_b)

    led_a = json.loads((R2A / "turn_ledger.json").read_text(encoding="utf-8"))["entries"]
    led_b = json.loads((R2B / "turn_ledger.json").read_text(encoding="utf-8"))["entries"]
    if len(led_a) != 200 or len(led_b) != 200:
        raise SystemExit(f"REFUSED -- expected 200 entries, got {len(led_a)}/{len(led_b)}")

    agg_a = aggregate(led_a, "R2a")
    agg_b = aggregate(led_b, "R2b")
    phases = phase_timers(led_a)
    census = census_r2a(led_a)
    fit = cost_fit(agg_b["escalations"])
    rescued = [
        x
        for x in agg_b["escalations"]
        if x["status"] == "complete"
        and int(x["turns_executed"] or 0) >= int(x["turns_in_entry"] or 0)
    ]
    rescue = {
        "n_escalated": len(agg_b["escalations"]),
        "n_rescued_operational": len(rescued),
        "rescue_rate_operational": (
            len(rescued) / len(agg_b["escalations"]) if agg_b["escalations"] else None
        ),
        "escalation_turn_hist": dict(
            Counter(int(x["turn"]) for x in agg_b["escalations"])
        ),
        "cloud_baseline_completion_n20": 0.65,
        "bfcl_quality_rescue": None,
        "bfcl_quality_rescue_note": (
            "UNAVAILABLE without persisted scores; operational rescue = "
            "entry finished all turns after escalate"
        ),
        "independence_vs_correlation": (
            "Operational rescue=1.0 >> 0.65 baseline means cloud finished "
            "remaining turns whenever local emission failed - not a BFCL "
            "quality statement. Quality correlation still unknown."
        ),
    }

    pred = json.loads(
        (ROOT / "derived/d1_replay/h1_predictions.json").read_text(encoding="utf-8")
    )
    pred_by = {p["label"]: p for p in pred["rows"]}

    def row(
        label: str,
        field: str,
        predicted: Any,
        measured: Any,
        lo: Any = None,
        hi: Any = None,
        *,
        falsified: bool = False,
        note: str = "",
    ) -> dict[str, Any]:
        err = None
        inside = None
        if isinstance(predicted, (int, float)) and isinstance(measured, (int, float)):
            err = float(measured) - float(predicted)
            if lo is not None and hi is not None:
                inside = float(lo) <= float(measured) <= float(hi)
        return {
            "arm": label,
            "field": field,
            "predicted": predicted,
            "lo": lo,
            "hi": hi,
            "measured": measured,
            "error": err,
            "inside_interval": inside,
            "falsified": falsified,
            "note": note,
        }

    pa, pb = pred_by["R2a"], pred_by["R2b"]
    table = [
        row(
            "R2a",
            "cloud_usd",
            pa["cloud_usd_total"],
            agg_a["cloud_usd"],
            pa["cloud_usd_lo"],
            pa["cloud_usd_hi"],
        ),
        row(
            "R2a",
            "completion",
            pa["completion"]["value"],
            None,
            note="BFCL trajectory_pass UNAVAILABLE from sealed H1 ledger",
        ),
        row(
            "R2a",
            "operational_completion",
            None,
            agg_a["operational_completion"],
            note="secondary ledger metric (not the predicted BFCL field)",
        ),
        row(
            "R2a",
            "emission",
            pa["emission"]["value"],
            agg_a["emission_rate_entry"],
            note="entry-level all-turns emitted_parseable_tool_call",
        ),
        row(
            "R2a",
            "slo_fraction_local",
            pa["slo_fraction_local_turns"],
            agg_a["slo_fraction_mean_over_turns"],
        ),
        row(
            "R2a",
            "slo_fraction_mean_over_entries",
            pa["slo_fraction_local_turns"],
            agg_a["slo_fraction_mean_over_entries"],
        ),
        row(
            "R2a",
            "session_time_sum_s",
            pa["session_time_s_sum"],
            agg_a["session_time_sum_s"],
        ),
        row(
            "R2b",
            "cloud_usd",
            pb["cloud_usd_total"],
            agg_b["cloud_usd"],
            pb["cloud_usd_lo"],
            pb["cloud_usd_hi"],
            falsified=True,
            note=(
                f"FALSIFIED: measured ${agg_b['cloud_usd']:.4f} outside "
                f"[{pb['cloud_usd_lo']:.4f}, {pb['cloud_usd_hi']:.4f}]; "
                f"predicted ${pb['cloud_usd_total']:.4f}"
            ),
        ),
        row(
            "R2b",
            "completion_floor",
            pb["completion_range"]["floor"]["value"],
            None,
            note="BFCL UNAVAILABLE",
        ),
        row(
            "R2b",
            "completion_indep",
            pb["completion_range"]["indep"]["value"],
            None,
            note="BFCL UNAVAILABLE",
        ),
        row(
            "R2b",
            "operational_completion",
            None,
            agg_b["operational_completion"],
            note="secondary",
        ),
        row(
            "R2b",
            "emission_floor",
            pb["emission_range"]["floor"]["value"],
            agg_b["emission_rate_entry"],
            note="measured=entry-level emit after hybrid (cloud may fill gaps)",
        ),
        row(
            "R2b",
            "emission_indep",
            pb["emission_range"]["indep"]["value"],
            agg_b["emission_rate_entry"],
        ),
        row(
            "R2b",
            "slo_fraction_local",
            pb["slo_fraction_local_turns"],
            agg_b["slo_fraction_mean_over_turns"],
        ),
        row(
            "R2b",
            "session_time_sum_s",
            pb["session_time_s_sum"],
            agg_b["session_time_sum_s"],
        ),
        row(
            "R2b",
            "n_escalated",
            pb["cloud_billing"]["n_escalated"],
            agg_b["n_escalated"],
        ),
    ]

    payload = {
        "run_ids": {
            "R2a": "86d0f4cf-e8c2-4ce5-96da-04c6a9c129f3",
            "R2b": "8ffd8371-ac15-492b-afb7-a45e4fae2c1b",
            "w3_scorer_pin": W3_SEAL,
        },
        "scorer": scorer,
        "R2a": {k: v for k, v in agg_a.items() if k != "escalations"},
        "R2b": {k: v for k, v in agg_b.items() if k != "escalations"},
        "R2b_escalations": agg_b["escalations"],
        "phase_timers_r2a": phases,
        "census_r2a": census,
        "rescue_r2b": rescue,
        "cost_fit_r2b": fit,
        "pred_vs_meas": table,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "h1_analyze.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "out": str(OUT_DIR / "h1_analyze.json")}, indent=2))


if __name__ == "__main__":
    main()
