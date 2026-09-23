"""D482 closeout. Read-only over the sealed tree. No model calls."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[4]
RUN_ID = "d482c621-4292-4281-b6a1-8635e5eeb6da"
SEAL = ROOT / "derived" / "h1_hybrid" / f"interleaved_{RUN_ID}"
OUT = Path(__file__).resolve().parent
POLICIES = ("slo_escalate", "emission_escalate", "full_signal_bounceback")
USD_PER_MTOK_IN = 3.0
USD_PER_MTOK_OUT = 15.0

# Provenance facts read from git in this closeout session. The seal does not
# store them; they are cited here so the JSON does not depend on a live git call.
HEAD_AT_START = {
    "sha": "a001b4529c91e490155ba09c13d184fd4b61a2a0",
    "committed_utc": "2026-09-23T10:23:42-04:00",
    "subject": "TURNWISE-STATE: reset BFCL tool instances on every session begin.",
}
PREDICTIONS = {
    "h1_3policy_json": {
        "path": "derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json",
        "first_commit": "5d290e92f60b1627ba4ea09a68c7c3a174139d8a",
        "first_commit_utc": "2026-09-20T17:10:14-04:00",
    },
    "h1_3policy_md": {
        "path": "derived/h1_hybrid/H1_3POLICY_PREDICTIONS.md",
        "first_commit": "5d290e92f60b1627ba4ea09a68c7c3a174139d8a",
        "first_commit_utc": "2026-09-20T17:10:14-04:00",
    },
    "h1_predictions_md": {
        "requested_path": "derived/h1_hybrid/H1_PREDICTIONS.md",
        "present_at_requested_path": False,
        "found_at": "derived/d1_replay/H1_PREDICTIONS.md",
        "first_commit": "f0f5a8c55c31392def1dbd86c48d044f03ceb361",
        "first_commit_utc": "2026-09-12T15:34:51-04:00",
    },
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _bucket(hybrid_pass: bool, error_type: str | None) -> str:
    if hybrid_pass:
        return "PASS"
    err = error_type or ""
    if err.startswith("multi_turn:"):
        err = err.split(":", 1)[1]
    if err == "instance_state_mismatch":
        return "MISMATCH"
    if err == "empty_turn_model_response":
        return "EMPTY"
    if err == "execution_response_mismatch":
        return "EXEC_RESP"
    return f"OTHER:{err or 'none'}"


def _ols(y: np.ndarray, x: np.ndarray) -> dict[str, float]:
    """Simple regression y = a + b x. x is one column."""
    n = int(y.shape[0])
    if n < 3:
        return {"n": float(n), "intercept": float("nan"), "slope": float("nan"), "r2": float("nan")}
    design = np.column_stack([np.ones(n), x])
    coef, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    pred = design @ coef
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return {
        "n": float(n),
        "intercept": float(coef[0]),
        "slope": float(coef[1]),
        "r2": float(r2),
    }


def _ols_multi(y: np.ndarray, columns: list[np.ndarray]) -> dict[str, Any]:
    n = int(y.shape[0])
    design = np.column_stack([np.ones(n), *columns])
    coef, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    pred = design @ coef
    resid = y - pred
    dof = n - design.shape[1]
    sigma2 = float(np.sum(resid**2) / dof) if dof > 0 else float("nan")
    try:
        xtx_inv = np.linalg.inv(design.T @ design)
        se = np.sqrt(np.maximum(np.diag(xtx_inv) * sigma2, 0.0))
    except np.linalg.LinAlgError:
        se = np.full(design.shape[1], float("nan"))
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return {
        "n": n,
        "coef": [float(c) for c in coef],
        "se": [float(s) for s in se],
        "r2": r2,
    }


def _ci_excludes_zero(coef: float, se: float) -> bool:
    if not np.isfinite(se):
        return False
    lo = coef - 1.96 * se
    hi = coef + 1.96 * se
    return lo > 0 or hi < 0


def _holo(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Holm adjustment over the listed tests. p_holm is monotone in rank."""
    order = sorted(range(len(pairs)), key=lambda i: pairs[i]["p_exact"])
    m = len(pairs)
    running = 0.0
    adjusted = [0.0] * m
    for rank, idx in enumerate(order):
        raw = pairs[idx]["p_exact"] * (m - rank)
        running = max(running, raw)
        adjusted[idx] = min(1.0, running)
    out = []
    for row, p_adj in zip(pairs, adjusted, strict=True):
        out.append({**row, "p_holm": p_adj})
    return out


def _mcnemar(
    left: dict[str, bool], right: dict[str, bool], left_name: str, right_name: str
) -> dict[str, Any]:
    ids = sorted(set(left) & set(right))
    b = sum(1 for i in ids if left[i] and not right[i])
    c = sum(1 for i in ids if (not left[i]) and right[i])
    n_disc = b + c
    p = float(binomtest(min(b, c), n_disc, 0.5, alternative="two-sided").pvalue) if n_disc else 1.0
    return {
        "run_id": RUN_ID,
        "left": left_name,
        "right": right_name,
        "n": len(ids),
        "b_left_pass_right_fail": b,
        "c_left_fail_right_pass": c,
        "p_exact": p,
    }


def _new_tokens(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Uncached/new prompt tokens = increase in n_ctx since the previous local turn.

    Turn 0 uses n_ctx itself. A drop in n_ctx is recorded as new_tokens 0 and
    a negative delta, which is a cache reset rather than new prompt text.
    """
    rows = []
    prev: int | None = None
    for t in turns:
        if t.get("placement") != "local":
            prev = None
            continue
        n_ctx = int(t.get("n_ctx") or 0)
        if prev is None:
            delta = n_ctx
            new = n_ctx
        else:
            delta = n_ctx - prev
            new = delta if delta > 0 else 0
        prev = n_ctx
        ttft = t.get("ttft_s")
        rows.append(
            {
                "turn": int(t["turn"]),
                "n_ctx": n_ctx,
                "delta_n_ctx": delta,
                "new_tokens": new,
                "ttft_s": None if ttft is None else float(ttft),
                "turn_wall_s": float(t.get("turn_wall_s") or 0.0),
            }
        )
    return rows


def main() -> None:
    plan = _load(SEAL / "plan.json")
    summary = _load(SEAL / "summary.json")
    started = str(plan["started_utc"])

    qualities: dict[str, list[dict[str, Any]]] = {}
    ledgers: dict[str, dict[str, dict[str, Any]]] = {}
    for policy in POLICIES:
        qpath = SEAL / "policies" / policy / "entry_quality.json"
        lpath = SEAL / "policies" / policy / "turn_ledger.json"
        qualities[policy] = _load(qpath)["entries"]
        ledgers[policy] = {str(r["entry_id"]): r for r in _load(lpath)["entries"]}

    # --- B.1 buckets ---
    failturn_path = (
        ROOT / "derived" / "h1_hybrid" / "analysis_d482c621" / "failturn" / "FAILTURN_RESULTS.json"
    )
    failturn = _load(failturn_path)
    first_from_failturn: dict[str, Counter[str]] = {p: Counter() for p in POLICIES}
    for row in failturn["per_entry"]:
        first_from_failturn[str(row["policy"])][str(row["first_fail_bucket"])] += 1

    labels = ["PASS", "MISMATCH", "EMPTY", "EXEC_RESP"]
    full_counts: dict[str, Counter[str]] = {p: Counter() for p in POLICIES}
    buckets: dict[str, dict[str, str]] = {p: {} for p in POLICIES}
    hybrid_pass: dict[str, dict[str, bool]] = {p: {} for p in POLICIES}
    escalated: dict[str, dict[str, bool]] = {p: {} for p in POLICIES}
    assertion: dict[str, Any] = {}
    for policy in POLICIES:
        qrows = qualities[policy]
        n_pass = 0
        for q in qrows:
            eid = str(q["entry_id"])
            hp = bool(q["hybrid_pass"])
            if hp:
                n_pass += 1
            err = q.get("hybrid_score_error_type")
            bkt = _bucket(hp, None if err is None else str(err))
            full_counts[policy][bkt] += 1
            buckets[policy][eid] = bkt
            hybrid_pass[policy][eid] = hp
            turns = ledgers[policy][eid]["turns"]
            escalated[policy][eid] = any(t.get("escalated") is True for t in turns)
        summary_h = int(
            _load(SEAL / "policies" / policy / "summary.json")["quality"]["hybrid"]["n_hybrid_pass"]
        )
        assertion[policy] = {
            "n_rows": len(qrows),
            "n_hybrid_pass_true": n_pass,
            "summary_n_hybrid_pass": summary_h,
            "pass": len(qrows) == 200 and n_pass == summary_h,
        }
        if not assertion[policy]["pass"]:
            raise SystemExit(f"FAIL assertion {policy}: {assertion[policy]}")
        if sum(full_counts[policy][lab] for lab in labels) != 200:
            raise SystemExit(f"FAIL full-trajectory sum {policy}: {full_counts[policy]}")
        if sum(first_from_failturn[policy].values()) != 200:
            raise SystemExit(f"FAIL first-failure sum {policy}")

    bucket_table = []
    for policy in POLICIES:
        row: dict[str, Any] = {"run_id": RUN_ID, "policy": policy}
        for lab in labels:
            row[f"first_fail_{lab}"] = int(first_from_failturn[policy][lab])
            row[f"full_trajectory_{lab}"] = int(full_counts[policy][lab])
        row["first_fail_sum"] = sum(first_from_failturn[policy].values())
        row["full_sum"] = sum(full_counts[policy].values())
        row["columns_equal"] = all(
            first_from_failturn[policy][lab] == full_counts[policy][lab] for lab in labels
        )
        bucket_table.append(row)

    # --- B.2 net recovery + McNemar ---
    slo_pass = hybrid_pass["slo_escalate"]
    recovery = []
    for policy in POLICIES:
        usd = float(_load(SEAL / "policies" / policy / "summary.json")["running_usd"])
        gross = sum(1 for i, hp in hybrid_pass[policy].items() if hp and not slo_pass[i])
        regressions = sum(1 for i, hp in hybrid_pass[policy].items() if slo_pass[i] and not hp)
        net = gross - regressions
        recovery.append(
            {
                "run_id": RUN_ID,
                "policy": policy,
                "gross_recovered": gross,
                "regressions": regressions,
                "net": net,
                "cloud_usd": usd,
                "usd_per_net_recovered": None if net == 0 else usd / net,
            }
        )
    mcnemar = _holo(
        [
            _mcnemar(
                hybrid_pass["emission_escalate"],
                slo_pass,
                "emission_escalate",
                "slo_escalate",
            ),
            _mcnemar(
                hybrid_pass["full_signal_bounceback"],
                slo_pass,
                "full_signal_bounceback",
                "slo_escalate",
            ),
            _mcnemar(
                hybrid_pass["emission_escalate"],
                hybrid_pass["full_signal_bounceback"],
                "emission_escalate",
                "full_signal_bounceback",
            ),
        ]
    )

    # --- C divergence ---
    # Prompt render hashes are not a field on sealed turns.
    sample_turn = next(iter(ledgers["slo_escalate"].values()))["turns"][0]
    prompt_keys = [k for k in sample_turn if "prompt" in k.lower() or "sha" in k.lower()]
    prompt_recorded = len(prompt_keys) > 0

    def _divergent(policy: str) -> list[str]:
        out = []
        for eid, bkt in buckets[policy].items():
            if escalated[policy][eid]:
                continue
            if bkt != buckets["slo_escalate"][eid]:
                out.append(eid)
        return sorted(out)

    divergent = {p: _divergent(p) for p in ("emission_escalate", "full_signal_bounceback")}
    control_pool = []
    for eid in sorted(buckets["slo_escalate"]):
        if escalated["emission_escalate"][eid] or escalated["full_signal_bounceback"][eid]:
            continue
        if eid in divergent["emission_escalate"] or eid in divergent["full_signal_bounceback"]:
            continue
        same = (
            buckets["emission_escalate"][eid] == buckets["slo_escalate"][eid]
            and buckets["full_signal_bounceback"][eid] == buckets["slo_escalate"][eid]
        )
        if same:
            control_pool.append(eid)
    controls = control_pool[:20]

    def _first_diff_turn(eid: str, policy: str) -> int | None:
        a = ledgers["slo_escalate"][eid]["turns"]
        b = ledgers[policy][eid]["turns"]
        n = min(len(a), len(b))
        for i in range(n):
            da = a[i].get("decoded_steps")
            db = b[i].get("decoded_steps")
            if da != db:
                return int(a[i]["turn"])
        if len(a) != len(b):
            return n
        return None

    divergence_rows = []
    for policy, ids in divergent.items():
        for eid in ids:
            divergence_rows.append(
                {
                    "run_id": RUN_ID,
                    "role": "outcome_differs",
                    "policy": policy,
                    "entry_id": eid,
                    "slo_bucket": buckets["slo_escalate"][eid],
                    "policy_bucket": buckets[policy][eid],
                    "first_differing_turn": _first_diff_turn(eid, policy),
                    "prompt_sha256": "NOT_IN_SEAL",
                    "classification": "NOT_IN_SEAL",
                }
            )
    for eid in controls:
        divergence_rows.append(
            {
                "run_id": RUN_ID,
                "role": "matched_control",
                "policy": "both_non_escalated_same_bucket",
                "entry_id": eid,
                "slo_bucket": buckets["slo_escalate"][eid],
                "policy_bucket": buckets["slo_escalate"][eid],
                "first_differing_turn_emission": _first_diff_turn(eid, "emission_escalate"),
                "first_differing_turn_bounceback": _first_diff_turn(eid, "full_signal_bounceback"),
                "prompt_sha256": "NOT_IN_SEAL",
                "classification": "NOT_IN_SEAL",
            }
        )
    class_counts = Counter(r["classification"] for r in divergence_rows)

    # --- D TTFT ---
    local_rows: dict[str, list[dict[str, Any]]] = {p: [] for p in POLICIES}
    by_key: dict[str, dict[tuple[str, int], dict[str, Any]]] = {p: {} for p in POLICIES}
    order_clock = 0.0
    # Interleaved order is entry order, then arm_order, then turn.
    entry_ids = [
        str(r["entry_id"])
        for r in _load(SEAL / "policies" / "slo_escalate" / "turn_ledger.json")["entries"]
    ]
    timestamp_fields = [
        k
        for k in sample_turn
        if "utc" in k.lower() or k.endswith("_at") or "timestamp" in k.lower()
    ]
    for eid in entry_ids:
        for policy in POLICIES:
            for rec in _new_tokens(ledgers[policy][eid]["turns"]):
                if rec["ttft_s"] is None:
                    continue
                order_clock += rec["turn_wall_s"]
                row = {
                    **rec,
                    "entry_id": eid,
                    "policy": policy,
                    "order_index": len(local_rows[policy]),
                    "cumulative_turn_wall_s": order_clock,
                }
                local_rows[policy].append(row)
                by_key[policy][(eid, rec["turn"])] = row

    fits = []
    for policy in POLICIES:
        rows = local_rows[policy]
        y = np.array([r["ttft_s"] for r in rows], dtype=float)
        x = np.array([r["new_tokens"] for r in rows], dtype=float)
        fit = _ols(y, x)
        fits.append(
            {
                "run_id": RUN_ID,
                "policy": policy,
                "n_local_turns": int(fit["n"]),
                "mean_ttft_s": float(np.mean(y)) if len(y) else None,
                "mean_new_tokens": float(np.mean(x)) if len(x) else None,
                "intercept": fit["intercept"],
                "slope_per_new_token": fit["slope"],
                "r2": fit["r2"],
            }
        )

    common = (
        set(by_key["slo_escalate"])
        & set(by_key["emission_escalate"])
        & set(by_key["full_signal_bounceback"])
    )
    matched = []
    for key in sorted(common):
        matched.append(
            {
                "slo": by_key["slo_escalate"][key],
                "emission": by_key["emission_escalate"][key],
                "bounceback": by_key["full_signal_bounceback"][key],
            }
        )
    matched_ttft = {
        "slo_escalate": float(np.mean([m["slo"]["ttft_s"] for m in matched])) if matched else None,
        "emission_escalate": float(np.mean([m["emission"]["ttft_s"] for m in matched]))
        if matched
        else None,
        "full_signal_bounceback": float(np.mean([m["bounceback"]["ttft_s"] for m in matched]))
        if matched
        else None,
        "n_pairs": len(matched),
    }

    y_m = np.array(
        [m["slo"]["ttft_s"] for m in matched]
        + [m["emission"]["ttft_s"] for m in matched]
        + [m["bounceback"]["ttft_s"] for m in matched],
        dtype=float,
    )
    new_m = np.array(
        [m["slo"]["new_tokens"] for m in matched]
        + [m["emission"]["new_tokens"] for m in matched]
        + [m["bounceback"]["new_tokens"] for m in matched],
        dtype=float,
    )
    em_dummy = np.array([0] * len(matched) + [1] * len(matched) + [0] * len(matched), dtype=float)
    bb_dummy = np.array([0] * len(matched) + [0] * len(matched) + [1] * len(matched), dtype=float)
    order_m = np.array(
        [m["slo"]["cumulative_turn_wall_s"] for m in matched]
        + [m["emission"]["cumulative_turn_wall_s"] for m in matched]
        + [m["bounceback"]["cumulative_turn_wall_s"] for m in matched],
        dtype=float,
    )
    tokens_model = _ols_multi(y_m, [new_m, em_dummy, bb_dummy])
    order_model = _ols_multi(y_m, [new_m, order_m, em_dummy, bb_dummy])
    # coef: intercept, new_tokens, emission, bounceback
    em_coef, bb_coef = tokens_model["coef"][2], tokens_model["coef"][3]
    em_se, bb_se = tokens_model["se"][2], tokens_model["se"][3]
    policy_effect_after_tokens = _ci_excludes_zero(em_coef, em_se) or _ci_excludes_zero(
        bb_coef, bb_se
    )
    em_after_order = order_model["coef"][3]
    bb_after_order = order_model["coef"][4]
    em_se_o, bb_se_o = order_model["se"][3], order_model["se"][4]
    policy_effect_after_order = _ci_excludes_zero(em_after_order, em_se_o) or _ci_excludes_zero(
        bb_after_order, bb_se_o
    )

    all_means = {row["policy"]: row["mean_ttft_s"] for row in fits}
    selection_gap = (
        all_means["slo_escalate"] is not None
        and all_means["emission_escalate"] is not None
        and (all_means["slo_escalate"] - all_means["emission_escalate"]) > 0.2
    )
    if not policy_effect_after_tokens and selection_gap:
        verdict = "EXPLAINED_BY_SELECTION"
    elif policy_effect_after_tokens and not policy_effect_after_order:
        verdict = "UNEXPLAINED"
    elif policy_effect_after_tokens:
        # Tokens did not remove the matched policy gap.
        slope_r2 = max(row["r2"] for row in fits)
        verdict = "EXPLAINED_BY_TOKENS" if slope_r2 > 0.5 and not selection_gap else "UNEXPLAINED"
    else:
        verdict = "UNEXPLAINED"

    # --- E cost ---
    cloud_turns = []
    for policy in POLICIES:
        for eid, led in ledgers[policy].items():
            for t in led["turns"]:
                if t.get("placement") != "cloud":
                    continue
                cloud_turns.append(
                    {
                        "policy": policy,
                        "entry_id": eid,
                        "turn": int(t["turn"]),
                        "cloud_tokens_in": int(t.get("cloud_tokens_in") or 0),
                        "cloud_tokens_out": int(t.get("cloud_tokens_out") or 0),
                        "cloud_usd": float(t.get("cloud_usd") or 0.0),
                        "n_ctx": int(t.get("n_ctx") or 0),
                    }
                )
    usage_fields = {
        "input_tokens": "cloud_tokens_in on the turn (sum across calls in the turn)",
        "output_tokens": "cloud_tokens_out on the turn (sum across calls in the turn)",
        "cache_creation_input_tokens": "MISSING",
        "cache_read_input_tokens": "MISSING",
        "calls_per_escalated_turn": "MISSING",
    }
    y_usd = np.array([c["cloud_usd"] for c in cloud_turns], dtype=float)
    x_in = np.array([c["cloud_tokens_in"] for c in cloud_turns], dtype=float)
    x_turn = np.array([c["turn"] for c in cloud_turns], dtype=float)
    fit_usd_in = _ols(y_usd, x_in)
    fit_usd_turn = _ols(y_usd, x_turn)
    fit_in_turn = _ols(x_in, x_turn)
    fit_out_turn = _ols(
        np.array([c["cloud_tokens_out"] for c in cloud_turns], dtype=float),
        x_turn,
    )

    by_turn: dict[int, list[dict[str, Any]]] = {}
    for c in cloud_turns:
        by_turn.setdefault(c["turn"], []).append(c)
    depth_means = []
    for k in sorted(by_turn):
        rows = by_turn[k]
        depth_means.append(
            {
                "turn": k,
                "n_cloud_turns": len(rows),
                "mean_tokens_in": float(np.mean([r["cloud_tokens_in"] for r in rows])),
                "mean_tokens_out": float(np.mean([r["cloud_tokens_out"] for r in rows])),
                "mean_usd": float(np.mean([r["cloud_usd"] for r in rows])),
            }
        )
    mean_by_k = {row["turn"]: row for row in depth_means}
    slo_turn_counts: Counter[int] = Counter()
    for led in ledgers["slo_escalate"].values():
        for t in led["turns"]:
            slo_turn_counts[int(t["turn"])] += 1
    covered = 0
    uncovered = 0
    expected = 0.0
    expected_from_price = 0.0
    for k, n_k in sorted(slo_turn_counts.items()):
        if k not in mean_by_k:
            uncovered += n_k
            continue
        covered += n_k
        row = mean_by_k[k]
        expected += n_k * row["mean_usd"]
        expected_from_price += (
            n_k
            * (USD_PER_MTOK_IN * row["mean_tokens_in"] + USD_PER_MTOK_OUT * row["mean_tokens_out"])
            / 1_000_000.0
        )

    r0 = {
        "run_id": RUN_ID,
        "formula": (
            "expected_usd = sum_k N_slo(k) * mean_usd(k). "
            "k is the user-turn index. N_slo(k) is the number of slo turns at that index "
            "(slo ran every turn locally). mean_usd(k) is the mean sealed cloud_usd of "
            "cloud turns at index k. Price check uses 3.0 USD/MTok in and 15.0 USD/MTok out "
            "on the same mean token depths."
        ),
        "price_usd_per_mtok_in": USD_PER_MTOK_IN,
        "price_usd_per_mtok_out": USD_PER_MTOK_OUT,
        "n_cloud_turns_in_fit": len(cloud_turns),
        "n_slo_turns_covered": covered,
        "n_slo_turns_uncovered": uncovered,
        "expected_usd": expected,
        "expected_usd_from_price_list": expected_from_price,
        "usd_vs_tokens_in": fit_usd_in,
        "usd_vs_turn_index": fit_usd_turn,
        "tokens_in_vs_turn_index": fit_in_turn,
        "tokens_out_vs_turn_index": fit_out_turn,
        "depth_means": depth_means,
    }

    ov = plan.get("openvino") or {}
    generation = {
        "source": "plan.json openvino",
        "max_new_tokens": ov.get("max_new_tokens"),
        "kv": ov.get("kv"),
        "residency": ov.get("residency"),
        "placement": plan.get("placement"),
        "do_sample": "NOT_IN_SEAL",
        "temperature": "NOT_IN_SEAL",
        "same_plan_for_all_policies": True,
    }

    doc: dict[str, Any] = {
        "run_id": RUN_ID,
        "started_utc": started,
        "finished_utc": summary.get("finished_utc"),
        "provenance": {
            "seal_recorded_git_sha": None,
            "seal_recorded_dirty": None,
            "seal_recorded_dirty_files": None,
            "seal_tree_sha256": summary.get("tree_sha256"),
            "runner_file_dirty_at_launch": (
                "YES_UNRECORDED_LIST: sealed entry_quality has hybrid_pass, which is "
                "absent from the git commit that was HEAD at started_utc. The seal "
                "does not list dirty files. The uncommitted scoring diff on "
                "tools/run_h1_hybrid.py is the implementation that produces hybrid_pass."
            ),
            "head_at_started_utc": HEAD_AT_START,
            "predictions": PREDICTIONS,
            "predictions_committed_before_start": True,
            "analysis_imports_run_h1_hybrid": False,
        },
        "assertion": assertion,
        "buckets": bucket_table,
        "recovery": recovery,
        "mcnemar": mcnemar,
        "divergence": {
            "n_emission_non_escalated_bucket_diff": len(divergent["emission_escalate"]),
            "n_bounceback_non_escalated_bucket_diff": len(divergent["full_signal_bounceback"]),
            "n_controls": len(controls),
            "control_rule": (
                "first 20 entry ids, sorted, that are non-escalated under emission "
                "and bounceback and share slo's 4-way bucket under both"
            ),
            "prompt_fields_on_turn": prompt_keys,
            "prompt_sha256_recorded": prompt_recorded,
            "classification_counts": dict(class_counts),
            "generation_config": generation,
            "rows": divergence_rows,
        },
        "ttft": {
            "new_token_definition": (
                "On local turns, new_tokens is n_ctx at turn 0 and the positive "
                "increase in n_ctx versus the previous local turn otherwise. "
                "n_ctx on a local turn is the runner's prompt token count."
            ),
            "per_policy": fits,
            "matched_local_under_all_three": matched_ttft,
            "matched_regression_ttft_on_new_tokens_and_policy": {
                "coef_names": ["intercept", "new_tokens", "emission", "bounceback"],
                **{k: tokens_model[k] for k in ("n", "coef", "se", "r2")},
                "policy_ci_excludes_zero": policy_effect_after_tokens,
            },
            "timestamps_on_turn": timestamp_fields,
            "wall_clock_proxy": (
                "Per-turn timestamps are absent. Order uses cumulative turn_wall_s "
                "in interleaved arm order (slo, emission, bounceback) within entry order."
            ),
            "matched_regression_with_cumulative_wall": {
                "coef_names": [
                    "intercept",
                    "new_tokens",
                    "cumulative_turn_wall_s",
                    "emission",
                    "bounceback",
                ],
                **{k: order_model[k] for k in ("n", "coef", "se", "r2")},
                "policy_ci_excludes_zero": policy_effect_after_order,
            },
            "verdict": verdict,
        },
        "cloud_usage": usage_fields,
        "r0_cap": r0,
        "cache_control_in_harness": False,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "CLOSEOUT.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    (OUT / "PLATFORM_ADDENDUM.json").write_text(
        json.dumps(
            {
                "run_id": RUN_ID,
                "seal_contains_platform_id": False,
                "platform_id": "aipc-c1",
                "evidence": (
                    "Not inside the sealed tree. Gate probe "
                    "derived/_gate_probes/gates_20260923_105530.json records "
                    "platform_id aipc-c1. The filename timestamp 10:55:30 local "
                    "is before started_utc 2026-09-23T14:56:10Z (10:56:10-04:00)."
                ),
                "written_outside_seal": "derived/h1_hybrid/analysis_d482c621/closeout/PLATFORM_ADDENDUM.json",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "CLOSEOUT.md").write_text(_markdown(doc), encoding="utf-8")
    print(
        json.dumps(
            {
                "assertion": assertion,
                "buckets_equal": [r["columns_equal"] for r in bucket_table],
                "recovery": recovery,
                "mcnemar_p": [(m["left"], m["p_exact"], m["p_holm"]) for m in mcnemar],
                "divergence_n": {
                    "emission": len(divergent["emission_escalate"]),
                    "bounceback": len(divergent["full_signal_bounceback"]),
                    "controls": len(controls),
                    "classes": dict(class_counts),
                },
                "ttft_verdict": verdict,
                "matched_n": len(matched),
                "r0_expected_usd": expected,
                "uncovered_turns": uncovered,
            },
            indent=2,
        )
    )


def _markdown(doc: dict[str, Any]) -> str:
    lines = [
        f"# D482 closeout ({doc['run_id']})",
        "",
        f"started_utc `{doc['started_utc']}`. Artifact tree `{doc['provenance']['seal_tree_sha256']}`.",
        "",
        "The seal does not record a runner git SHA, dirty flag, or dirty-file list.",
        "",
        doc["provenance"]["runner_file_dirty_at_launch"],
        "",
        "## Buckets",
        "",
        "First-failure buckets are the fail-turn rescore. Full-trajectory buckets are sealed hybrid_pass and hybrid_score_error_type. Each column sums to 200.",
        "",
        "| policy | PASS | MISMATCH | EMPTY | EXEC_RESP | columns equal |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in doc["buckets"]:
        lines.append(
            f"| {row['policy']} first | {row['first_fail_PASS']} | {row['first_fail_MISMATCH']} | "
            f"{row['first_fail_EMPTY']} | {row['first_fail_EXEC_RESP']} | {row['columns_equal']} |"
        )
        lines.append(
            f"| {row['policy']} full | {row['full_trajectory_PASS']} | {row['full_trajectory_MISMATCH']} | "
            f"{row['full_trajectory_EMPTY']} | {row['full_trajectory_EXEC_RESP']} | {row['columns_equal']} |"
        )
    lines.extend(["", "## Recovery", ""])
    lines.append("| policy | gross | regressions | net | USD | USD per net |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in doc["recovery"]:
        per = row["usd_per_net_recovered"]
        per_s = "" if per is None else f"{per:.6f}"
        lines.append(
            f"| {row['policy']} | {row['gross_recovered']} | {row['regressions']} | "
            f"{row['net']} | {row['cloud_usd']:.6f} | {per_s} |"
        )
    lines.extend(["", "## McNemar", ""])
    lines.append("| left | right | b | c | p | p Holm |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for row in doc["mcnemar"]:
        lines.append(
            f"| {row['left']} | {row['right']} | {row['b_left_pass_right_fail']} | "
            f"{row['c_left_fail_right_pass']} | {row['p_exact']:.6g} | {row['p_holm']:.6g} |"
        )
    div = doc["divergence"]
    lines.extend(
        [
            "",
            "## Divergence",
            "",
            f"Non-escalated bucket differs from slo: emission {div['n_emission_non_escalated_bucket_diff']}, "
            f"bounceback {div['n_bounceback_non_escalated_bucket_diff']}. Controls: {div['n_controls']}.",
            "",
            f"Prompt sha256 recorded: {div['prompt_sha256_recorded']}. "
            f"Classification counts: {div['classification_counts']}.",
            "",
            f"TTFT verdict: **{doc['ttft']['verdict']}**.",
            "",
            "## R0 expected cloud USD",
            "",
            doc["r0_cap"]["formula"],
            "",
            f"Covered slo turns {doc['r0_cap']['n_slo_turns_covered']}, "
            f"uncovered {doc['r0_cap']['n_slo_turns_uncovered']}, "
            f"expected USD {doc['r0_cap']['expected_usd']:.6f}. "
            f"Price-list check {doc['r0_cap']['expected_usd_from_price_list']:.6f}.",
            "",
            "usd versus cloud_tokens_in r2 "
            f"{doc['r0_cap']['usd_vs_tokens_in']['r2']:.4f}, slope "
            f"{doc['r0_cap']['usd_vs_tokens_in']['slope']:.6e}. "
            "usd versus turn index r2 "
            f"{doc['r0_cap']['usd_vs_turn_index']['r2']:.4f}.",
            "",
            "| turn | n cloud | mean tokens in | mean tokens out | mean USD |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for row in doc["r0_cap"]["depth_means"]:
        lines.append(
            f"| {row['turn']} | {row['n_cloud_turns']} | {row['mean_tokens_in']:.1f} | "
            f"{row['mean_tokens_out']:.1f} | {row['mean_usd']:.6f} |"
        )
    lines.extend(
        [
            "",
            "Cache token fields and per-call records: MISSING. "
            f"cache_control set by the harness: {doc['cache_control_in_harness']}.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
