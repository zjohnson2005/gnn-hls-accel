"""FLEET-FRONTIER (Task BO): empirical per-step context CDF from the pinned TraceLab trace.

Reads derived/fleet/raw/syfi_coding_trace.jsonl.gz (UW-SyFI/TraceLab v0.0.2, revision 7256bbf7,
sha256 11ce51ec..., CC BY 4.0) as a stream with the standard library. Per round, the step's
context is input_tokens_total (the whole prompt the model reads). It writes quantiles and
fit fractions for a list of capacities.

Registration rule (docs/registrations/FLEET_FRONTIER_2026-10-23.md): results are computed only
after the Nov 6 gate. Before then only --check-schema runs on the real file.
"""

from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

RAW = (
    Path(__file__).resolve().parents[1] / "derived" / "fleet" / "raw" / "syfi_coding_trace.jsonl.gz"
)
PINNED_SHA256 = "11ce51ec0a25e3d1d95b025bca2f7d1647e47571eb7cc968acd5fc64d4b4fb65"
REQUIRED = ("provider", "session_id", "round_index", "input_tokens_total", "prefix_tokens")
QUANTILES = (0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rounds(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def check_schema(path: Path, n: int = 100) -> dict[str, Any]:
    missing: set[str] = set()
    seen = 0
    for rec in rounds(path):
        missing |= {k for k in REQUIRED if k not in rec}
        seen += 1
        if seen >= n:
            break
    return {"records_checked": seen, "missing_fields": sorted(missing)}


def quantile(sorted_vals: list[int], q: float) -> float:
    if not sorted_vals:
        raise ValueError("empty")
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def summarise(values: Iterable[int], capacities: dict[str, int]) -> dict[str, Any]:
    vals = sorted(int(v) for v in values if v is not None and int(v) >= 0)
    n = len(vals)
    return {
        "n_steps": n,
        "quantiles": {f"p{int(q * 100)}": quantile(vals, q) for q in QUANTILES} if n else {},
        "fit_fraction": {
            name: (bisect.bisect_right(vals, cap) / n if n else None)
            for name, cap in capacities.items()
        },
    }


def by_provider(recs: Iterable[dict[str, Any]], capacities: dict[str, int]) -> dict[str, Any]:
    groups: dict[str, list[int]] = {}
    for r in recs:
        groups.setdefault(str(r.get("provider")), []).append(int(r.get("input_tokens_total") or 0))
    allv = [v for vs in groups.values() for v in vs]
    out = {p: summarise(v, capacities) for p, v in sorted(groups.items())}
    out["all"] = summarise(allv, capacities)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raw", type=Path, default=RAW)
    ap.add_argument("--check-schema", action="store_true")
    ap.add_argument("--capacities-json", type=Path, default=None, help="{name: tokens}")
    ap.add_argument("--after-nov6-gate", action="store_true", help="Required to compute results.")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    digest = sha256(a.raw)
    if digest != PINNED_SHA256:
        raise SystemExit(f"REFUSED -- {a.raw} sha256 {digest} is not the pinned {PINNED_SHA256}")
    if a.check_schema:
        print(json.dumps({"sha256_ok": True, **check_schema(a.raw)}))
        return 0
    if not a.after_nov6_gate:
        raise SystemExit("REFUSED -- FLEET-FRONTIER results are computed only after the Nov 6 gate")
    if a.capacities_json is None or a.out is None:
        raise SystemExit("REFUSED -- results need --capacities-json and --out")
    caps = {str(k): int(v) for k, v in json.loads(a.capacities_json.read_text()).items()}
    a.out.write_text(
        json.dumps(by_provider(rounds(a.raw), caps), indent=1) + "\n", encoding="ascii"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
