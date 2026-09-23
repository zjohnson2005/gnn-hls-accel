"""Read-only analysis of sealed run d482c621. Does not write under the seal."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import binomtest
from scipy.stats import t as student_t

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "d482c621-4292-4281-b6a1-8635e5eeb6da"
SEAL = ROOT / "derived" / "h1_hybrid" / f"interleaved_{RUN_ID}"
OUT = ROOT / "derived" / "h1_hybrid" / "analysis_d482c621"
POLICIES = ("slo_escalate", "emission_escalate", "full_signal_bounceback")
TTFT_SLO_S = 10.0
DECODE_SLO_TOK_S = 6.0

# Prediction sources. derived/h1_hybrid/H1_PREDICTIONS.md is not in the tree.
# The session pre-registration is H1_3POLICY_PREDICTIONS; the superseded
# H-1 file is derived/d1_replay/H1_PREDICTIONS.md. R2B_8B is an 8B filing.
H1_3P = ROOT / "derived" / "h1_hybrid" / "H1_3POLICY_PREDICTIONS.json"
H1_D1 = ROOT / "derived" / "d1_replay" / "H1_PREDICTIONS.md"
R2B_8B = ROOT / "derived" / "h1_hybrid" / "R2B_8B_PREDICTIONS.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _failure_class(hybrid_pass: bool, error_type: str | None) -> str | None:
    if hybrid_pass:
        return None
    text = error_type or ""
    if "instance_state_mismatch" in text:
        return "instance_state_mismatch"
    return "other"


def _quantile(xs: list[float], q: float) -> float:
    return float(np.quantile(np.asarray(xs, dtype=float), q))


def _ols(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Simple OLS y = a + b x. Returns slope, intercept, r2, n."""
    n = int(x.shape[0])
    x_mean = float(x.mean())
    y_mean = float(y.mean())
    var_x = float(((x - x_mean) ** 2).sum())
    if var_x == 0.0 or n < 3:
        raise RuntimeError("OLS refused: degenerate prompt-token column")
    slope = float(((x - x_mean) * (y - y_mean)).sum() / var_x)
    intercept = y_mean - slope * x_mean
    fitted = intercept + slope * x
    resid = y - fitted
    ss_tot = float(((y - y_mean) ** 2).sum())
    ss_res = float((resid**2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot else float("nan")
    return {
        "n": n,
        "slope_ttft_s_per_prompt_token": slope,
        "intercept_ttft_s": intercept,
        "r2": r2,
        "mean_ttft_s": y_mean,
        "mean_prompt_tokens": x_mean,
        "residual_sd": math.sqrt(ss_res / (n - 2)),
    }


def _policy_effect_test(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """TTFT ~ centered prompt tokens + policy dummies (slo reference).

    A policy coefficient whose 95% CI excludes 0 is a TTFT difference that
    prompt length does not account for.
    """
    y = np.asarray([r["ttft_s"] for r in rows], dtype=float)
    n_ctx = np.asarray([r["prompt_tokens"] for r in rows], dtype=float)
    centered = n_ctx - float(n_ctx.mean())
    d_em = np.asarray([1.0 if r["policy"] == "emission_escalate" else 0.0 for r in rows])
    d_bb = np.asarray([1.0 if r["policy"] == "full_signal_bounceback" else 0.0 for r in rows])
    x = np.column_stack([np.ones(len(rows)), centered, d_em, d_bb])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    n, k = x.shape
    dof = n - k
    sigma2 = float((resid @ resid) / dof)
    cov = sigma2 * np.linalg.inv(x.T @ x)
    se = np.sqrt(np.diag(cov))
    tcrit = float(student_t.ppf(0.975, dof))
    names = ("intercept", "prompt_tokens_centered", "emission_escalate", "full_signal_bounceback")
    coefs: dict[str, Any] = {}
    unexplained: list[str] = []
    for i, name in enumerate(names):
        lo = float(beta[i] - tcrit * se[i])
        hi = float(beta[i] + tcrit * se[i])
        excludes_0 = lo > 0.0 or hi < 0.0
        coefs[name] = {
            "estimate": float(beta[i]),
            "se": float(se[i]),
            "ci95": [lo, hi],
            "excludes_0": excludes_0,
        }
        if name != "intercept" and name != "prompt_tokens_centered" and excludes_0:
            unexplained.append(name)
    return {
        "n": n,
        "dof": dof,
        "reference_policy": "slo_escalate",
        "coefficients": coefs,
        "flag": "UNEXPLAINED" if unexplained else "EXPLAINED_BY_PROMPT_LENGTH",
        "policies_whose_ttft_differs_after_prompt_length": unexplained,
    }


def _mcnemar(a: dict[str, bool], b: dict[str, bool], *, left: str, right: str) -> dict[str, Any]:
    ids = sorted(set(a) & set(b))
    if len(ids) != 200:
        raise RuntimeError(f"McNemar pair {left} vs {right} has {len(ids)} shared ids")
    # b: left pass, right fail. c: left fail, right pass.
    n_b = sum(1 for i in ids if a[i] and not b[i])
    n_c = sum(1 for i in ids if (not a[i]) and b[i])
    n_disc = n_b + n_c
    p = 1.0 if n_disc == 0 else float(binomtest(n_b, n_disc, 0.5, alternative="two-sided").pvalue)
    return {
        "run_id": RUN_ID,
        "outcome": "hybrid_pass",
        "left": left,
        "right": right,
        "n_paired": len(ids),
        "b_left_pass_right_fail": n_b,
        "c_left_fail_right_pass": n_c,
        "p_exact_binomial": p,
    }


def _hit_interval(measured: float, lo: float, hi: float) -> str:
    return "HIT" if lo <= measured <= hi else "MISS"


def _hit_point(measured: float, predicted: float, *, atol: float) -> str:
    return "HIT" if math.isclose(measured, predicted, rel_tol=0.0, abs_tol=atol) else "MISS"


def main() -> None:
    summaries = {p: _load(SEAL / "policies" / p / "summary.json") for p in POLICIES}
    qualities = {
        p: _load(SEAL / "policies" / p / "entry_quality.json")["entries"] for p in POLICIES
    }
    ledgers = {p: _load(SEAL / "policies" / p / "turn_ledger.json")["entries"] for p in POLICIES}
    plan = _load(SEAL / "plan.json")
    preds = _load(H1_3P)

    ledger_by: dict[str, dict[str, dict[str, Any]]] = {}
    for policy, rows in ledgers.items():
        ledger_by[policy] = {str(r["entry_id"]): r for r in rows}

    per_entry: list[dict[str, Any]] = []
    hybrid: dict[str, dict[str, bool]] = {p: {} for p in POLICIES}
    local: dict[str, dict[str, bool]] = {p: {} for p in POLICIES}
    ism_ids: dict[str, set[str]] = {p: set() for p in POLICIES}

    assertion_rows: dict[str, Any] = {}
    for policy in POLICIES:
        qrows = qualities[policy]
        ids = [str(r["entry_id"]) for r in qrows]
        if len(qrows) != 200 or len(set(ids)) != 200:
            raise SystemExit(f"FAIL row count {policy}: n={len(qrows)} unique={len(set(ids))}")
        n_hybrid = sum(1 for r in qrows if r.get("hybrid_pass") is True)
        n_local = sum(1 for r in qrows if r.get("local_pass") is True)
        summary_h = int(summaries[policy]["quality"]["hybrid"]["n_hybrid_pass"])
        summary_l = int(summaries[policy]["quality"]["local_probe"]["n_local_pass"])
        assertion_rows[policy] = {
            "run_id": RUN_ID,
            "n_rows": len(qrows),
            "n_hybrid_pass": n_hybrid,
            "n_local_pass": n_local,
            "summary_n_hybrid_pass": summary_h,
            "summary_n_local_pass": summary_l,
            "equals_summary": n_hybrid == summary_h and n_local == summary_l,
            "equals_summary_divided_by_3": (n_hybrid == summary_h / 3 and n_local == summary_l / 3),
        }
        for q in qrows:
            eid = str(q["entry_id"])
            led = ledger_by[policy][eid]
            turns = led["turns"]
            err = q.get("hybrid_score_error_type")
            err_s = str(err) if err is not None else None
            hp = bool(q["hybrid_pass"])
            lp = bool(q["local_pass"])
            hybrid[policy][eid] = hp
            local[policy][eid] = lp
            fclass = _failure_class(hp, err_s)
            if fclass == "instance_state_mismatch":
                ism_ids[policy].add(eid)
            n_esc = sum(1 for t in turns if t.get("escalated") is True)
            per_entry.append(
                {
                    "run_id": RUN_ID,
                    "entry_id": eid,
                    "policy": policy,
                    "hybrid_pass": hp,
                    "local_pass": lp,
                    "n_turns": len(turns),
                    "n_escalated_turns": n_esc,
                    "cloud_usd": float(led.get("cloud_usd_entry") or 0.0),
                    "cloud_tokens_in": int(sum(int(t.get("cloud_tokens_in") or 0) for t in turns)),
                    "cloud_tokens_out": int(
                        sum(int(t.get("cloud_tokens_out") or 0) for t in turns)
                    ),
                    "failure_class": fclass,
                }
            )

    div3_ok = all(v["equals_summary_divided_by_3"] for v in assertion_rows.values())
    summary_ok = all(v["equals_summary"] for v in assertion_rows.values())
    if not summary_ok:
        raise SystemExit("FAIL: entry_quality pass counts do not match policy summaries")

    # McNemar on hybrid_pass.
    pairs = (
        ("emission_escalate", "slo_escalate"),
        ("full_signal_bounceback", "slo_escalate"),
        ("emission_escalate", "full_signal_bounceback"),
    )
    mcnemar = [
        _mcnemar(hybrid[left], hybrid[right], left=left, right=right) for left, right in pairs
    ]

    # Cost frontier. Recovered = hybrid pass in X and hybrid fail in slo.
    frontier_rows: list[dict[str, Any]] = []
    slo_fail = {i for i, ok in hybrid["slo_escalate"].items() if not ok}
    for policy in POLICIES:
        rows = [r for r in per_entry if r["policy"] == policy]
        n = len(rows)
        n_pass = sum(1 for r in rows if r["hybrid_pass"])
        usd = float(sum(r["cloud_usd"] for r in rows))
        n_turns = sum(r["n_turns"] for r in rows)
        n_esc_turns = sum(r["n_escalated_turns"] for r in rows)
        tok_in = sum(r["cloud_tokens_in"] for r in rows)
        tok_out = sum(r["cloud_tokens_out"] for r in rows)
        recovered_ids = [
            r["entry_id"] for r in rows if r["hybrid_pass"] and r["entry_id"] in slo_fail
        ]
        # slo vs itself: recovered is empty by definition.
        n_recovered = len(recovered_ids)
        tok_on_esc = 0
        tok_in_esc = 0
        tok_out_esc = 0
        for led in ledgers[policy]:
            for t in led["turns"]:
                if t.get("escalated") is True:
                    tok_in_esc += int(t.get("cloud_tokens_in") or 0)
                    tok_out_esc += int(t.get("cloud_tokens_out") or 0)
        tok_on_esc = tok_in_esc + tok_out_esc
        frontier_rows.append(
            {
                "run_id": RUN_ID,
                "tier": "4B",
                "policy": policy,
                "n_entries": n,
                "n_hybrid_pass": n_pass,
                "pass_rate": n_pass / n,
                "usd_total": usd,
                "summary_running_usd": float(summaries[policy]["running_usd"]),
                "usd_per_entry": usd / n,
                "n_recovered_vs_slo": n_recovered,
                "usd_per_recovered_entry": (usd / n_recovered) if n_recovered else None,
                "n_turns": n_turns,
                "n_escalated_turns": n_esc_turns,
                "escalated_turn_fraction": n_esc_turns / n_turns if n_turns else None,
                "cloud_tokens_in": tok_in,
                "cloud_tokens_out": tok_out,
                "cloud_tokens_per_escalated_turn": (
                    tok_on_esc / n_esc_turns if n_esc_turns else None
                ),
                "cloud_tokens_in_per_escalated_turn": (
                    tok_in_esc / n_esc_turns if n_esc_turns else None
                ),
                "cloud_tokens_out_per_escalated_turn": (
                    tok_out_esc / n_esc_turns if n_esc_turns else None
                ),
            }
        )

    # SLO audit on slo_escalate turns.
    slo_turns: list[dict[str, Any]] = []
    n_escalations = 0
    for led in ledgers["slo_escalate"]:
        for t in led["turns"]:
            slo_turns.append(t)
            if t.get("escalated") is True:
                n_escalations += 1
    ttfts = [float(t["ttft_s"]) for t in slo_turns if t.get("ttft_s") is not None]
    decodes = [float(t["decode_tok_s"]) for t in slo_turns if t.get("decode_tok_s") is not None]
    n_ttft_violate = sum(1 for v in ttfts if v > TTFT_SLO_S)
    n_decode_violate = sum(1 for v in decodes if v < DECODE_SLO_TOK_S)
    n_either = 0
    for t in slo_turns:
        bad = False
        if t.get("ttft_s") is not None and float(t["ttft_s"]) > TTFT_SLO_S:
            bad = True
        if t.get("decode_tok_s") is not None and float(t["decode_tok_s"]) < DECODE_SLO_TOK_S:
            bad = True
        if bad:
            n_either += 1
    if n_escalations != 0:
        raise SystemExit(f"FAIL SLO escalation assert: {n_escalations} != 0")
    arm = summaries["slo_escalate"]["arm_config"]
    slo_audit = {
        "run_id": RUN_ID,
        "label": "SLO_INERT_ON_CONFIG",
        "policy": "slo_escalate",
        "n_turns": len(slo_turns),
        "n_ttft_observed": len(ttfts),
        "n_decode_observed": len(decodes),
        "ttft_s_max": max(ttfts),
        "ttft_s_median": float(np.median(np.asarray(ttfts))),
        "ttft_s_p99": _quantile(ttfts, 0.99),
        "decode_tok_s_min": min(decodes),
        "slo_clauses": {
            "ttft_s_gt": TTFT_SLO_S,
            "decode_tok_s_lt": DECODE_SLO_TOK_S,
            "source": "tools/run_h1_hybrid.py TTFT_SLO_S / DECODE_SLO_TOK_S",
        },
        "n_turns_ttft_violate": n_ttft_violate,
        "n_turns_decode_violate": n_decode_violate,
        "n_turns_either_clause": n_either,
        "n_escalations": n_escalations,
        "escalation_assert_0": n_escalations == 0,
        "config": {
            "model": arm["model"],
            "precision": arm["weight"],
            "placement": arm["placement"],
            "residency": arm["residency"],
            "kv": arm["kv"],
            "platform": "absent_from_seal",
            "model_spec": plan["openvino"]["model_spec"],
        },
    }

    # TTFT vs prompt tokens on local turns. n_ctx is prompt_tokens for local turns.
    scatter: list[dict[str, Any]] = []
    fits: dict[str, Any] = {}
    for policy in POLICIES:
        pts: list[dict[str, Any]] = []
        for led in ledgers[policy]:
            for t in led["turns"]:
                if t.get("placement") != "local":
                    continue
                if t.get("ttft_s") is None:
                    continue
                row = {
                    "run_id": RUN_ID,
                    "policy": policy,
                    "entry_id": str(led["entry_id"]),
                    "turn": int(t["turn"]),
                    "ttft_s": float(t["ttft_s"]),
                    "prompt_tokens": int(t["n_ctx"]),
                }
                pts.append(row)
                scatter.append(row)
        fit = _ols(
            np.asarray([p["prompt_tokens"] for p in pts], dtype=float),
            np.asarray([p["ttft_s"] for p in pts], dtype=float),
        )
        fit["run_id"] = RUN_ID
        fit["policy"] = policy
        fits[policy] = fit
    effect = _policy_effect_test(scatter)
    effect["run_id"] = RUN_ID
    effect["prompt_token_field"] = (
        "turn.n_ctx on placement=local (runner stores prompt_tokens there)"
    )

    # Census-D
    all_three = set.intersection(*(ism_ids[p] for p in POLICIES))
    census = {
        "run_id": RUN_ID,
        "failure_class": "instance_state_mismatch",
        "per_policy": {
            p: {
                "run_id": RUN_ID,
                "n_entries": 200,
                "n_instance_state_mismatch": len(ism_ids[p]),
                "rate": len(ism_ids[p]) / 200,
            }
            for p in POLICIES
        },
        "n_entries_ism_under_all_three": len(all_three),
        "entry_ids_ism_under_all_three": sorted(all_three),
    }

    # Measured quantities used by the prediction table.
    def _emission_ok_rate(policy: str) -> tuple[int, float]:
        n_ok = 0
        for led in ledgers[policy]:
            turns = led["turns"]
            if turns and all(t.get("emitted_parseable_tool_call") is True for t in turns):
                n_ok += 1
        return n_ok, n_ok / 200

    def _n_escalated_entries(policy: str) -> int:
        return sum(1 for r in per_entry if r["policy"] == policy and r["n_escalated_turns"] > 0)

    def _n_bounces(policy: str) -> int:
        return sum(len(led.get("bounces") or []) for led in ledgers[policy])

    slo_emit_n, slo_emit_rate = _emission_ok_rate("slo_escalate")
    em_esc_entries = _n_escalated_entries("emission_escalate")
    bb_esc_entries = _n_escalated_entries("full_signal_bounceback")
    n_bounces = _n_bounces("full_signal_bounceback")
    usd = {p: next(r["usd_total"] for r in frontier_rows if r["policy"] == p) for p in POLICIES}
    hyb_rate = {
        p: next(r["pass_rate"] for r in frontier_rows if r["policy"] == p) for p in POLICIES
    }
    loc_rate = {p: sum(1 for v in local[p].values() if v) / 200 for p in POLICIES}
    slo_frac = 1.0 - (n_either / len(slo_turns))

    r2a = preds["predictions"]["R2a"]
    r2b = preds["predictions"]["R2b"]
    r2c = preds["predictions"]["R2c"]
    comparison: list[dict[str, Any]] = []

    def add_line(
        *,
        source: str,
        arm: str,
        field: str,
        predicted: float,
        measured: float,
        verdict: str,
        lo: float | None = None,
        hi: float | None = None,
        note: str,
    ) -> None:
        comparison.append(
            {
                "run_id": RUN_ID,
                "source": source,
                "arm": arm,
                "field": field,
                "predicted": predicted,
                "lo": lo,
                "hi": hi,
                "measured": measured,
                "verdict": verdict,
                "note": note,
            }
        )

    src_3p = "derived/h1_hybrid/H1_3POLICY_PREDICTIONS.json"
    src_d1 = "derived/d1_replay/H1_PREDICTIONS.md"
    src_8b = "derived/h1_hybrid/R2B_8B_PREDICTIONS.json"

    add_line(
        source=src_3p,
        arm="R2a",
        field="completion",
        predicted=float(r2a["completion"]["value"]),
        lo=float(r2a["completion"]["range"][0]),
        hi=float(r2a["completion"]["range"][1]),
        measured=hyb_rate["slo_escalate"],
        verdict=_hit_interval(
            hyb_rate["slo_escalate"],
            float(r2a["completion"]["range"][0]),
            float(r2a["completion"]["range"][1]),
        ),
        note="hybrid_pass rate; slo local_pass equals hybrid_pass",
    )
    add_line(
        source=src_3p,
        arm="R2a",
        field="cloud_usd_total",
        predicted=0.0,
        measured=usd["slo_escalate"],
        verdict=_hit_point(usd["slo_escalate"], 0.0, atol=1e-9),
        note="sum of entry cloud_usd",
    )
    add_line(
        source=src_3p,
        arm="R2a",
        field="emission",
        predicted=float(r2a["emission"]["value"]),
        lo=float(r2a["emission"]["range"][0]),
        hi=float(r2a["emission"]["range"][1]),
        measured=slo_emit_rate,
        verdict=_hit_interval(
            slo_emit_rate,
            float(r2a["emission"]["range"][0]),
            float(r2a["emission"]["range"][1]),
        ),
        note=(
            f"fraction of slo entries with emitted_parseable_tool_call on every turn; "
            f"n_ok={slo_emit_n}/200. Prediction is 1 - emission_failure_mid/200."
        ),
    )
    add_line(
        source=src_3p,
        arm="R2a",
        field="slo_fraction_local_turns",
        predicted=1.0,
        measured=slo_frac,
        verdict=_hit_point(slo_frac, 1.0, atol=1e-12),
        note="1 - (turns violating either SLO clause) / n_turns",
    )
    add_line(
        source=src_3p,
        arm="R2b",
        field="n_escalated",
        predicted=float(r2b["n_escalated"]["value"]),
        lo=float(r2b["n_escalated"]["range"][0]),
        hi=float(r2b["n_escalated"]["range"][1]),
        measured=float(em_esc_entries),
        verdict=_hit_interval(
            float(em_esc_entries),
            float(r2b["n_escalated"]["range"][0]),
            float(r2b["n_escalated"]["range"][1]),
        ),
        note="entries with n_escalated_turns > 0",
    )
    add_line(
        source=src_3p,
        arm="R2b",
        field="cloud_usd_total",
        predicted=float(r2b["cloud_usd_total"]["value"]),
        lo=float(r2b["cloud_usd_total"]["lo"]),
        hi=float(r2b["cloud_usd_total"]["hi"]),
        measured=usd["emission_escalate"],
        verdict=_hit_interval(
            usd["emission_escalate"],
            float(r2b["cloud_usd_total"]["lo"]),
            float(r2b["cloud_usd_total"]["hi"]),
        ),
        note="sum of entry cloud_usd",
    )
    add_line(
        source=src_3p,
        arm="R2b",
        field="completion_floor",
        predicted=float(r2b["completion"]["floor"]),
        lo=0.05,
        hi=0.07,
        measured=loc_rate["emission_escalate"],
        verdict=_hit_interval(loc_rate["emission_escalate"], 0.05, 0.07),
        note="local_pass rate. Interval is the re-anchored completion band the floor cites (10-14/200).",
    )
    add_line(
        source=src_3p,
        arm="R2b",
        field="completion_indep",
        predicted=float(r2b["completion"]["indep"]),
        measured=hyb_rate["emission_escalate"],
        verdict=_hit_point(
            hyb_rate["emission_escalate"], float(r2b["completion"]["indep"]), atol=5e-5
        ),
        note="hybrid_pass rate vs point prediction; no interval was filed",
    )
    add_line(
        source=src_3p,
        arm="R2c",
        field="n_bounces",
        predicted=float(r2c["n_bounces"]["value"]),
        lo=float(r2c["n_bounces"]["range"][0]),
        hi=float(r2c["n_bounces"]["range"][1]),
        measured=float(n_bounces),
        verdict=_hit_interval(
            float(n_bounces),
            float(r2c["n_bounces"]["range"][0]),
            float(r2c["n_bounces"]["range"][1]),
        ),
        note="len(bounces) summed over entries; escalated entries=" + str(bb_esc_entries),
    )
    add_line(
        source=src_3p,
        arm="R2c",
        field="cloud_usd_total",
        predicted=float(r2c["cloud_usd_total"]["value"]),
        lo=float(r2c["cloud_usd_total"]["lo"]),
        hi=float(r2c["cloud_usd_total"]["hi"]),
        measured=usd["full_signal_bounceback"],
        verdict=_hit_interval(
            usd["full_signal_bounceback"],
            float(r2c["cloud_usd_total"]["lo"]),
            float(r2c["cloud_usd_total"]["hi"]),
        ),
        note="sum of entry cloud_usd",
    )
    add_line(
        source=src_3p,
        arm="R2c",
        field="completion",
        predicted=float(r2c["completion"]["value"]),
        lo=float(r2c["completion"]["range"][0]),
        hi=float(r2c["completion"]["range"][1]),
        measured=loc_rate["full_signal_bounceback"],
        verdict=_hit_interval(
            loc_rate["full_signal_bounceback"],
            float(r2c["completion"]["range"][0]),
            float(r2c["completion"]["range"][1]),
        ),
        note="filed completion is the local band; measured is local_pass rate",
    )

    # Superseded H-1 lines (d1_replay), same measured quantities.
    sup_b = r2b["superseded"]
    add_line(
        source=src_d1,
        arm="R2a",
        field="completion",
        predicted=0.1,
        measured=hyb_rate["slo_escalate"],
        verdict=_hit_point(hyb_rate["slo_escalate"], 0.1, atol=5e-5),
        note="point 0.1000 in H1_PREDICTIONS.md; file is derived/d1_replay/H1_PREDICTIONS.md",
    )
    add_line(
        source=src_d1,
        arm="R2a",
        field="cloud_usd",
        predicted=0.0,
        measured=usd["slo_escalate"],
        verdict=_hit_point(usd["slo_escalate"], 0.0, atol=1e-9),
        note="point 0.0000",
    )
    add_line(
        source=src_d1,
        arm="R2a",
        field="emission",
        predicted=0.775,
        measured=slo_emit_rate,
        verdict=_hit_point(slo_emit_rate, 0.775, atol=5e-5),
        note="point 0.7750; same emission_ok definition as the re-anchored line",
    )
    add_line(
        source=src_d1,
        arm="R2a",
        field="slo_frac_local",
        predicted=1.0,
        measured=slo_frac,
        verdict=_hit_point(slo_frac, 1.0, atol=1e-12),
        note="point 1.0000",
    )
    add_line(
        source=src_d1,
        arm="R2b",
        field="cloud_usd",
        predicted=float(sup_b["cloud_usd_total"]),
        lo=float(sup_b["cloud_usd_interval"][0]),
        hi=float(sup_b["cloud_usd_interval"][1]),
        measured=usd["emission_escalate"],
        verdict=_hit_interval(
            usd["emission_escalate"],
            float(sup_b["cloud_usd_interval"][0]),
            float(sup_b["cloud_usd_interval"][1]),
        ),
        note="interval from H1_3POLICY superseded block, matching H1_PREDICTIONS.md",
    )
    add_line(
        source=src_d1,
        arm="R2b",
        field="n_escalated",
        predicted=float(sup_b["n_escalated"]),
        measured=float(em_esc_entries),
        verdict=_hit_point(float(em_esc_entries), float(sup_b["n_escalated"]), atol=0.0),
        note="superseded point 45; H1_PREDICTIONS.md emission 0.775 implies 45/200",
    )
    add_line(
        source=src_d1,
        arm="R2b",
        field="completion_floor",
        predicted=float(sup_b["completion_floor"]),
        measured=loc_rate["emission_escalate"],
        verdict=_hit_point(
            loc_rate["emission_escalate"], float(sup_b["completion_floor"]), atol=5e-5
        ),
        note="local_pass rate vs point 0.1000",
    )
    add_line(
        source=src_d1,
        arm="R2b",
        field="completion_indep",
        predicted=float(sup_b["completion_indep"]),
        measured=hyb_rate["emission_escalate"],
        verdict=_hit_point(
            hyb_rate["emission_escalate"], float(sup_b["completion_indep"]), atol=5e-5
        ),
        note="hybrid_pass rate vs point 0.24625",
    )

    r2b8 = _load(R2B_8B)
    r2b8_note = (
        "R2B_8B_PREDICTIONS targets Qwen3-8B-int4-ov emission_escalate "
        f"({r2b8.get('model_spec')}). "
        f"This seal is {arm['model']} {arm['weight']} {arm['placement']}. "
        "Not scored HIT/MISS."
    )
    comparison.append(
        {
            "run_id": RUN_ID,
            "source": src_8b,
            "arm": "R2b-8B",
            "field": "not_scored",
            "predicted": None,
            "lo": None,
            "hi": None,
            "measured": None,
            "verdict": "NOT_THIS_EXPERIMENT",
            "note": r2b8_note,
            "registered_model_note": r2b8.get("registered_utc") or r2b8.get("status"),
        }
    )

    results = {
        "run_id": RUN_ID,
        "measurement_kind": "MEASURED",
        "seal_tree": f"derived/h1_hybrid/interleaved_{RUN_ID}",
        "tree_sha256": _load(SEAL / "summary.json")["tree_sha256"],
        "assertion": {
            "run_id": RUN_ID,
            "n_rows_per_policy_is_200": True,
            "pass_counts_equal_summary": summary_ok,
            "pass_counts_equal_summary_divided_by_3": div3_ok,
            "div3_verdict": "FAIL" if not div3_ok else "PASS",
            "per_policy": assertion_rows,
            "reading": (
                "Entry pass counts equal each policy summary. "
                "They do not equal those summary counts divided by 3."
            ),
        },
        "per_entry": per_entry,
        "mcnemar_hybrid_pass": mcnemar,
        "slo_audit": slo_audit,
        "ttft_vs_prompt_tokens": {
            "run_id": RUN_ID,
            "fits": fits,
            "policy_effect": effect,
            "scatter": scatter,
        },
        "census_d": census,
        "prediction_comparison": comparison,
        "prediction_files_read": [src_3p, src_d1, src_8b],
        "h1_predictions_md_at_requested_path": False,
        "requested_path_missing": "derived/h1_hybrid/H1_PREDICTIONS.md",
    }
    frontier = {
        "run_id": RUN_ID,
        "measurement_kind": "MEASURED",
        "tier": "4B",
        "outcome": "hybrid_pass",
        "recovered_definition": "hybrid_pass in policy and hybrid_pass false in slo_escalate",
        "rows": frontier_rows,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "H1_3POLICY_RESULTS.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "COST_FRONTIER_4B.json").write_text(
        json.dumps(frontier, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "H1_3POLICY_RESULTS.md").write_text(_markdown(results, frontier), encoding="utf-8")
    print(
        json.dumps(
            {
                "div3": results["assertion"]["div3_verdict"],
                "hybrid": {p: assertion_rows[p]["n_hybrid_pass"] for p in POLICIES},
                "local": {p: assertion_rows[p]["n_local_pass"] for p in POLICIES},
                "mcnemar": mcnemar,
                "slo_max_ttft": slo_audit["ttft_s_max"],
                "slo_violations": n_either,
                "ttft_flag": effect["flag"],
                "ism": {p: len(ism_ids[p]) for p in POLICIES},
                "ism_all_three": len(all_three),
                "n_bounces": n_bounces,
                "em_esc": em_esc_entries,
                "verdicts": [(c["arm"], c["field"], c["verdict"]) for c in comparison],
            },
            indent=2,
        )
    )


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def _markdown(results: dict[str, Any], frontier: dict[str, Any]) -> str:
    run = RUN_ID
    lines: list[str] = []
    lines.append(f"# H1 3-policy results ({run})")
    lines.append("")
    lines.append(f"Every number below is from run_id `{run}`.")
    lines.append("")
    lines.append("## Assertion")
    lines.append("")
    a = results["assertion"]
    lines.append(
        f"200 rows per policy: yes. Pass counts equal policy summaries: "
        f"{a['pass_counts_equal_summary']}. Pass counts equal summary/3: "
        f"**{a['div3_verdict']}**."
    )
    lines.append("")
    lines.append("| policy | rows | hybrid_pass | local_pass | summary hybrid | summary local |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for p, row in a["per_policy"].items():
        lines.append(
            f"| {p} | {row['n_rows']} | {row['n_hybrid_pass']} | {row['n_local_pass']} | "
            f"{row['summary_n_hybrid_pass']} | {row['summary_n_local_pass']} |"
        )
    lines.append("")
    lines.append("## McNemar on hybrid_pass")
    lines.append("")
    lines.append(
        "b = left pass and right fail. c = left fail and right pass. p is the two-sided exact binomial test on the discordant pairs."
    )
    lines.append("")
    lines.append("| left | right | b | c | p |")
    lines.append("|---|---|---:|---:|---:|")
    for m in results["mcnemar_hybrid_pass"]:
        lines.append(
            f"| {m['left']} | {m['right']} | {m['b_left_pass_right_fail']} | "
            f"{m['c_left_fail_right_pass']} | {m['p_exact_binomial']:.6g} |"
        )
    lines.append("")
    lines.append("## Cost frontier, 4B")
    lines.append("")
    lines.append(
        "| policy | pass rate | USD total | USD/entry | recovered vs slo | USD/recovered | "
        "escalated-turn fraction | cloud tokens / escalated turn |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in frontier["rows"]:
        lines.append(
            f"| {r['policy']} | {r['n_hybrid_pass']}/200 = {_fmt(r['pass_rate'])} | "
            f"{_fmt(r['usd_total'])} | {_fmt(r['usd_per_entry'])} | "
            f"{r['n_recovered_vs_slo']} | {_fmt(r['usd_per_recovered_entry'])} | "
            f"{r['n_escalated_turns']}/{r['n_turns']} = {_fmt(r['escalated_turn_fraction'])} | "
            f"{_fmt(r['cloud_tokens_per_escalated_turn'])} |"
        )
    lines.append("")
    lines.append("## SLO trigger audit")
    lines.append("")
    s = results["slo_audit"]
    cfg = s["config"]
    lines.append(f"**{s['label']}**")
    lines.append("")
    lines.append(
        f"Config: model `{cfg['model']}`, precision `{cfg['precision']}`, "
        f"placement `{cfg['placement']}`, residency `{cfg['residency']}`, "
        f"KV `{cfg['kv']}`, platform `{cfg['platform']}`."
    )
    lines.append("")
    lines.append(
        f"Turns {s['n_turns']}. TTFT max {_fmt(s['ttft_s_max'])} s, "
        f"median {_fmt(s['ttft_s_median'])} s, p99 {_fmt(s['ttft_s_p99'])} s. "
        f"Min decode {_fmt(s['decode_tok_s_min'])} tok/s. "
        f"Turns violating ttft>{s['slo_clauses']['ttft_s_gt']} or "
        f"decode<{s['slo_clauses']['decode_tok_s_lt']}: {s['n_turns_either_clause']}. "
        f"Escalations: {s['n_escalations']}."
    )
    lines.append("")
    lines.append("## TTFT vs prompt tokens (local turns)")
    lines.append("")
    lines.append(
        "| policy | n | slope (s/token) | intercept (s) | r2 | mean TTFT (s) | mean prompt tokens |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    fits = results["ttft_vs_prompt_tokens"]["fits"]
    for p, f in fits.items():
        lines.append(
            f"| {p} | {f['n']} | {_fmt(f['slope_ttft_s_per_prompt_token'])} | "
            f"{_fmt(f['intercept_ttft_s'])} | {_fmt(f['r2'])} | "
            f"{_fmt(f['mean_ttft_s'])} | {_fmt(f['mean_prompt_tokens'])} |"
        )
    eff = results["ttft_vs_prompt_tokens"]["policy_effect"]
    lines.append("")
    lines.append(f"Policy effect after prompt length, slo as reference: **{eff['flag']}**.")
    lines.append("")
    lines.append("| term | estimate | 95% CI | excludes 0 |")
    lines.append("|---|---:|---|---|")
    for name, c in eff["coefficients"].items():
        if name == "intercept":
            continue
        lo, hi = c["ci95"]
        lines.append(
            f"| {name} | {_fmt(c['estimate'])} | [{_fmt(lo)}, {_fmt(hi)}] | {c['excludes_0']} |"
        )
    lines.append("")
    lines.append(
        "Scatter points are in `H1_3POLICY_RESULTS.json` under `ttft_vs_prompt_tokens.scatter`."
    )
    lines.append("")
    lines.append("## Census-D instance_state_mismatch")
    lines.append("")
    lines.append("| policy | n | rate |")
    lines.append("|---|---:|---:|")
    cen = results["census_d"]
    for p, row in cen["per_policy"].items():
        lines.append(f"| {p} | {row['n_instance_state_mismatch']}/200 | {_fmt(row['rate'])} |")
    lines.append("")
    lines.append(
        f"Entries with instance_state_mismatch under all three policies: "
        f"{cen['n_entries_ism_under_all_three']}."
    )
    lines.append("")
    lines.append("## Predicted vs measured")
    lines.append("")
    lines.append(
        "`derived/h1_hybrid/H1_PREDICTIONS.md` is not in the tree. "
        "Re-anchored lines are `H1_3POLICY_PREDICTIONS.json`. "
        "Superseded H-1 lines are `derived/d1_replay/H1_PREDICTIONS.md`. "
        "R2B-8B is a different model and is not scored."
    )
    lines.append("")
    lines.append("| source | arm | field | predicted | measured | verdict |")
    lines.append("|---|---|---|---:|---:|---|")
    for c in results["prediction_comparison"]:
        lines.append(
            f"| {c['source']} | {c['arm']} | {c['field']} | {_fmt(c['predicted'])} | "
            f"{_fmt(c['measured'])} | {c['verdict']} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
