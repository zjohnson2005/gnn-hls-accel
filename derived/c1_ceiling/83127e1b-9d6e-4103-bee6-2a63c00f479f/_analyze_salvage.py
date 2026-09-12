"""C-1 salvage analysis for session 83127e1b. Analysis-only; no runs."""
from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

SESSION = Path(__file__).resolve().parent
ROOT = SESSION.parents[2]  # session -> c1_ceiling -> derived -> repo
WORK = SESSION / "work"
REF_W = 2_290_768_181
REF_KW = 234_827
LOCK = 12_884_901_888  # SetProcessWorkingSetSizeEx maximum_bytes
SEALED_41 = (
    ROOT
    / "derived"
    / "delta_prefill"
    / "sealed_41e419bd-f3e9-43b1-8364-0ebd89fa086b"
)


def extract_probes() -> list[dict]:
    rows: list[dict] = []
    for p in sorted(WORK.glob("*.result.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        g = d.get("generation") or {}
        parts = p.name.split(".")
        n = int(next(x[1:] for x in parts if x.startswith("n") and x[1:].isdigit()))
        r = int(next(x[1:] for x in parts if x.startswith("r") and x[1:].isdigit()))
        a = int(next(x[1:] for x in parts if x.startswith("a") and x[1:].isdigit()))
        rows.append(
            {
                "file": p.name,
                "n": n,
                "repeat": r,
                "attempt": a,
                "completed": bool(d.get("completed")),
                "peak_rss_bytes": g.get("peak_rss_bytes"),
                "peak_commit_bytes": g.get("peak_commit_bytes"),
                "available_mb_min": g.get("available_mb_min"),
                "free_physical_mb_min": g.get("free_physical_mb_min"),
                "prefill_s": g.get("prefill_s"),
                "decode_tok_s": g.get("decode_tok_s"),
                "r_prefill_tok_s": g.get("r_prefill_tok_s"),
                "wall_s": g.get("wall_s"),
                "exception": d.get("exception"),
            }
        )
    return rows


def ols(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    den = n * sxx - sx * sx
    slope = (n * sxy - sx * sy) / den
    intercept = (sy - slope * sx) / n
    return intercept, slope


def fit_commit(rows: list[dict]) -> dict:
    usable = [r for r in rows if r["peak_commit_bytes"] is not None]
    xs = [float(r["n"]) for r in usable]
    ys = [float(r["peak_commit_bytes"]) for r in usable]
    W, kw = ols(xs, ys)
    residuals = []
    for r in usable:
        pred = W + kw * r["n"]
        meas = r["peak_commit_bytes"]
        resid = meas - pred
        residuals.append(
            {
                "n": r["n"],
                "repeat": r["repeat"],
                "attempt": r["attempt"],
                "meas_bytes": meas,
                "pred_bytes": pred,
                "resid_bytes": resid,
                "resid_pct": 100.0 * resid / meas,
                "meas_GB": meas / 1e9,
                "pred_GB": pred / 1e9,
            }
        )
    by_n: dict[int, list[float]] = defaultdict(list)
    for r in usable:
        by_n[r["n"]].append(float(r["peak_commit_bytes"]))
    ns = sorted(by_n)
    med_ys = [statistics.median(by_n[n]) for n in ns]
    W_med, kw_med = ols([float(n) for n in ns], med_ys)

    hand_n = 44742
    hand_meas = next(
        r["peak_commit_bytes"]
        for r in usable
        if r["n"] == hand_n and r["repeat"] == 0 and r["attempt"] == 0
    )
    hand_pred_ref = REF_W + REF_KW * hand_n
    hand_pred_fit = W + kw * hand_n
    return {
        "n_points": len(usable),
        "fit_all_probes": {
            "W_bytes": W,
            "W_bytes_rounded": int(round(W)),
            "k_plus_w_B_per_token": kw,
            "k_plus_w_rounded": int(round(kw)),
            "vs_41e419bd": {
                "ref_W": REF_W,
                "ref_k_plus_w": REF_KW,
                "delta_W": W - REF_W,
                "delta_W_pct": 100.0 * (W - REF_W) / REF_W,
                "delta_k_plus_w": kw - REF_KW,
                "delta_k_plus_w_pct": 100.0 * (kw - REF_KW) / REF_KW,
            },
        },
        "fit_median_per_n": {
            "n_levels": len(ns),
            "W_bytes": W_med,
            "W_bytes_rounded": int(round(W_med)),
            "k_plus_w_B_per_token": kw_med,
            "k_plus_w_rounded": int(round(kw_med)),
        },
        "residuals": residuals,
        "residual_summary": {
            "max_abs_resid_bytes": max(abs(x["resid_bytes"]) for x in residuals),
            "max_abs_resid_pct": max(abs(x["resid_pct"]) for x in residuals),
            "rmse_bytes": (
                sum(x["resid_bytes"] ** 2 for x in residuals) / len(residuals)
            )
            ** 0.5,
            "mean_abs_pct": statistics.mean(abs(x["resid_pct"]) for x in residuals),
        },
        "hand_check_n44742": {
            "meas_commit_bytes": hand_meas,
            "meas_GB": hand_meas / 1e9,
            "pred_41e419bd_bytes": hand_pred_ref,
            "pred_41e419bd_GB": hand_pred_ref / 1e9,
            "underpredict_pct_vs_41e419bd": 100.0
            * (hand_meas - hand_pred_ref)
            / hand_meas,
            "pred_refit_bytes": hand_pred_fit,
            "pred_refit_GB": hand_pred_fit / 1e9,
            "resid_pct_vs_refit": 100.0 * (hand_meas - hand_pred_fit) / hand_meas,
        },
        "rss_lock_bytes": LOCK,
        "rss_note": (
            "peak_rss_bytes is capped by SetProcessWorkingSetSizeEx "
            f"maximum_bytes={LOCK}; not a consumption measure above ~n=42000."
        ),
    }


def _n_cached_from_name(name: str) -> int | None:
    m = re.search(r"_nc(\d+)_", name)
    return int(m.group(1)) if m else None


def sealed_f16_turn1_points() -> list[dict]:
    points: list[dict] = []
    cells = SEALED_41 / "cells"
    if not cells.is_dir():
        return points
    for p in sorted(cells.glob("dispatch_*armgpu_only_f16*.json")):
        n = _n_cached_from_name(p.name)
        if n is None:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        t1 = d.get("turn1") or {}
        if not t1.get("ok"):
            continue
        pre = t1.get("prefill_s")
        dec = t1.get("decode_tok_s")
        if pre is None:
            continue
        # repeat from filename _r2 or similar
        rm = re.search(r"_r(\d+)\.json$", p.name)
        points.append(
            {
                "source": "sealed_41e419bd",
                "arm": "gpu_only_f16",
                "n": n,
                "repeat": int(rm.group(1)) if rm else None,
                "file": p.name,
                "prefill_s": float(pre),
                "decode_tok_s": float(dec) if dec is not None else None,
            }
        )
    return points


def c1_points(probes: list[dict]) -> list[dict]:
    out = []
    for r in probes:
        if r["prefill_s"] is None:
            continue
        out.append(
            {
                "source": "83127e1b",
                "arm": "gpu_only_f16",
                "n": r["n"],
                "repeat": r["repeat"],
                "attempt": r["attempt"],
                "file": r["file"],
                "prefill_s": r["prefill_s"],
                "decode_tok_s": r["decode_tok_s"],
            }
        )
    return out


def find_crossing(
    points: list[dict], *, metric: str, threshold: float, above_is_fail: bool
) -> dict:
    by_n: dict[int, list[float]] = defaultdict(list)
    by_n_src: dict[int, set[str]] = defaultdict(set)
    for p in points:
        v = p.get(metric)
        if v is None:
            continue
        by_n[int(p["n"])].append(float(v))
        by_n_src[int(p["n"])].add(str(p.get("source")))
    levels = []
    for n in sorted(by_n):
        med = statistics.median(by_n[n])
        ok = (med <= threshold) if above_is_fail else (med >= threshold)
        levels.append(
            {
                "n": n,
                "median": med,
                "min": min(by_n[n]),
                "max": max(by_n[n]),
                "n_obs": len(by_n[n]),
                "sources": sorted(by_n_src[n]),
                "ok": ok,
            }
        )

    last_ok = None
    first_fail = None
    for L in levels:
        if L["ok"]:
            last_ok = L
            first_fail = None  # reset if non-monotonic recovery
        elif last_ok is not None and first_fail is None:
            first_fail = L

    if last_ok and first_fail:
        status = "bracketed"
    elif not any(L["ok"] for L in levels):
        status = "already_failed_at_lowest_observed"
    elif all(L["ok"] for L in levels):
        status = "never_crossed_in_observed_range"
    else:
        status = "ambiguous_nonmonotonic"

    return {
        "metric": metric,
        "threshold": threshold,
        "status": status,
        "n_ok_side": last_ok,
        "n_fail_side": first_fail,
        "levels": levels,
    }


def main() -> None:
    assert ROOT.joinpath("tools").is_dir(), f"ROOT mis-resolved: {ROOT}"
    probes = extract_probes()
    fit = fit_commit(probes)
    pts = sealed_f16_turn1_points() + c1_points(probes)
    prefill_x = find_crossing(pts, metric="prefill_s", threshold=10.0, above_is_fail=True)
    decode_x = find_crossing(
        pts, metric="decode_tok_s", threshold=6.0, above_is_fail=False
    )

    # Also report decode crossing using only C-1 (high-n) if sealed never fails decode
    decode_c1 = find_crossing(
        c1_points(probes), metric="decode_tok_s", threshold=6.0, above_is_fail=False
    )
    prefill_c1 = find_crossing(
        c1_points(probes), metric="prefill_s", threshold=10.0, above_is_fail=True
    )

    out = {
        "session_id": "83127e1b-9d6e-4103-bee6-2a63c00f479f",
        "n_result_files": len(probes),
        "n_completed": sum(1 for r in probes if r["completed"]),
        "probes": probes,
        "commit_model_refit": fit,
        "slo": {
            "definition": "TTFT/prefill_s <= 10 s AND decode_tok_s >= 6 tok/s",
            "corpus": "sealed_41e419bd gpu_only_f16 turn1 + 83127e1b probes",
            "prefill_cross_10s": prefill_x,
            "decode_cross_6_tok_s": decode_x,
            "c1_only_prefill_cross_10s": prefill_c1,
            "c1_only_decode_cross_6_tok_s": decode_c1,
        },
        "corrections": {
            "max_position_embeddings_not_enforced": {
                "config_claims": 40960,
                "highest_completed_n": max(
                    (r["n"] for r in probes if r["completed"]), default=None
                ),
                "evidence": (
                    "Completed probes at n=44742; incomplete attempt at n=44871. "
                    "max_position_embeddings=40960 is not enforced at inference."
                ),
            },
            "no_hard_memory_ceiling_on_16gb_host": {
                "probes_with_avail_0": [
                    r["file"]
                    for r in probes
                    if r.get("available_mb_min") == 0.0 and r["completed"]
                ],
                "evidence": (
                    "available_mb_min reached 0.0 with generate continuing to completion; "
                    "OS pages; commit keeps growing."
                ),
            },
        },
    }
    out_path = SESSION / "salvage_analysis.json"
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("WROTE", out_path)
    print("N_PROBES", len(probes), "COMPLETED", out["n_completed"])
    fa = fit["fit_all_probes"]
    print(
        "FIT_ALL W=",
        fa["W_bytes_rounded"],
        "kw=",
        fa["k_plus_w_rounded"],
        "vs_ref deltaW%=",
        round(fa["vs_41e419bd"]["delta_W_pct"], 2),
        "deltakw%=",
        round(fa["vs_41e419bd"]["delta_k_plus_w_pct"], 2),
    )
    print("HAND", fit["hand_check_n44742"])
    print("RESID", fit["residual_summary"])
    print("PREFILL", {k: prefill_x[k] for k in ("status", "n_ok_side", "n_fail_side")})
    for L in prefill_x["levels"]:
        print("  prefill", L)
    print("DECODE", {k: decode_x[k] for k in ("status", "n_ok_side", "n_fail_side")})
    for L in decode_x["levels"]:
        print("  decode", L)
    print("DECODE_C1", {k: decode_c1[k] for k in ("status", "n_ok_side", "n_fail_side")})


if __name__ == "__main__":
    main()
