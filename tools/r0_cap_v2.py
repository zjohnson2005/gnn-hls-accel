"""Entry-level bootstrap cap for an H1 cloud budget. Does not read prereg files.

v1 (R0_CAP.json) stays untouched. This writes R0_CAP_V2.json.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "d482c621-4292-4281-b6a1-8635e5eeb6da"
POLICIES = ("slo_escalate", "emission_escalate", "full_signal_bounceback")
SEED = 20260925
N_DRAWS = 10_000
PERCENTILE = 0.995


def _load_entries(run_dir: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for policy in POLICIES:
        path = run_dir / "policies" / policy / "turn_ledger.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        out[policy] = list(doc.get("entries") or [])
    return out


def _cloud_pairs(entry: dict[str, Any]) -> list[tuple[int, float]]:
    pairs: list[tuple[int, float]] = []
    for turn in entry.get("turns") or []:
        if turn.get("placement") != "cloud":
            continue
        pairs.append((int(turn.get("turn")), float(turn.get("cloud_usd") or 0.0)))
    return pairs


def bootstrap_cap(
    ledgers: dict[str, list[dict[str, Any]]],
    *,
    n_draws: int = N_DRAWS,
    seed: int = SEED,
    percentile: float = PERCENTILE,
) -> dict[str, Any]:
    """Resample escalated entries. Apply each draw's per-depth mean to fixed N_slo(k)."""
    n_slo: dict[int, int] = defaultdict(int)
    for entry in ledgers["slo_escalate"]:
        for turn in entry.get("turns") or []:
            n_slo[int(turn.get("turn"))] += 1

    cloud_by_depth: dict[int, list[float]] = defaultdict(list)
    by_entry: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for policy in POLICIES:
        for entry in ledgers[policy]:
            eid = str(entry.get("entry_id"))
            pairs = _cloud_pairs(entry)
            by_entry[eid].extend(pairs)
            for depth, usd in pairs:
                cloud_by_depth[depth].append(usd)

    escalated = [pairs for pairs in by_entry.values() if pairs]
    full_mean = {
        depth: (sum(vals) / len(vals) if vals else 0.0) for depth, vals in cloud_by_depth.items()
    }
    depths = sorted(set(n_slo) | set(full_mean))
    rng = random.Random(seed)
    draws: list[float] = []
    n_fallback = 0
    n_units = len(escalated)
    for _ in range(int(n_draws)):
        picked = [escalated[rng.randrange(n_units)] for _ in range(n_units)] if n_units else []
        pooled: dict[int, list[float]] = defaultdict(list)
        for pairs in picked:
            for depth, usd in pairs:
                pooled[depth].append(usd)
        expected = 0.0
        for depth in depths:
            n = n_slo.get(depth, 0)
            if n == 0:
                continue
            sample = pooled.get(depth) or []
            if sample:
                mean = sum(sample) / len(sample)
            else:
                mean = full_mean.get(depth, 0.0)
                n_fallback += 1
            expected += n * mean
        draws.append(expected)

    ordered = sorted(draws)
    rank = (len(ordered) - 1) * float(percentile)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    cap = ordered[lo] * (1.0 - frac) + ordered[hi] * frac
    return {
        "n_escalated_entries": n_units,
        "n_draws": int(n_draws),
        "seed": int(seed),
        "percentile": float(percentile),
        "percentile_method": "linear rank (n-1)*p",
        "n_depth_fallbacks_to_full_sample_mean": n_fallback,
        "fallback": (
            "A draw with no cloud turn at depth k uses the full-sample mean at k. "
            "N_slo(k) is not dropped."
        ),
        "expected_usd_draw_mean": sum(draws) / len(draws),
        "cap_usd": cap,
        "N_slo": {str(k): n_slo[k] for k in sorted(n_slo)},
        "full_sample_mean_usd": {str(k): full_mean[k] for k in sorted(full_mean)},
    }


def write_v2(run_dir: Path, out_path: Path, v1_path: Path) -> dict[str, Any]:
    v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    stats = bootstrap_cap(_load_entries(run_dir))
    doc = {
        "run_id": RUN_ID,
        "formula": "cap = 99.5th percentile of entry-bootstrap expected cost",
        "expected_formula": "expected = sum_k N_slo(k) * mean_usd_draw(k)",
        "resample": (
            "Escalated entries (any policy has a cloud turn) drawn with replacement, "
            "10,000 draws. Each draw's per-depth mean cloud_usd is applied to the "
            "fixed full-sample N_slo(k)."
        ),
        "source": (
            "derived/h1_hybrid/interleaved_d482c621-4292-4281-b6a1-8635e5eeb6da/"
            "policies/*/turn_ledger.json"
        ),
        "v1_cap_usd": v1["cap_usd"],
        "v1_expected_usd": v1["expected_usd"],
        "v1_file": "derived/h1_hybrid/R0_CAP.json",
        "launch": False,
        **stats,
    }
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def main() -> None:
    run_dir = ROOT / "derived" / "h1_hybrid" / f"interleaved_{RUN_ID}"
    out = ROOT / "derived" / "h1_hybrid" / "R0_CAP_V2.json"
    v1 = ROOT / "derived" / "h1_hybrid" / "R0_CAP.json"
    doc = write_v2(run_dir, out, v1)
    print(f"v1_cap_usd={doc['v1_cap_usd']}")
    print(f"v2_cap_usd={doc['cap_usd']}")
    print(f"n_escalated_entries={doc['n_escalated_entries']}")
    print(f"fallbacks={doc['n_depth_fallbacks_to_full_sample_mean']}")


if __name__ == "__main__":
    main()
