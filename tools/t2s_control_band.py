"""T2S f16 control band at n=18687, from sealed run 5c714535.

Pass: the control cell's median prefill_s lies in [min, max] of that run's
three repeats, widened by their max relative spread.

    max_relative_spread = max(abs(x - median) / median)
    low = min * (1 - max_relative_spread)
    high = max * (1 + max_relative_spread)

The cell estimate is 3 * that median plus the c2246b1f canary overhead,
rounded up to the next whole second.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REFERENCE_RUN_ID = "5c714535-9f36-4614-a594-698b6cd09296"
CONTROL_N = 18687
CONTROL_REPEATS = 3
CANARY_OVERHEAD_S = 752.1359013
FORMULA = (
    "max_relative_spread = max(abs(x - median) / median); "
    "low = min * (1 - max_relative_spread); "
    "high = max * (1 + max_relative_spread); "
    "pass iff the control median prefill_s is inside [low, high]"
)


def _uncold_reason() -> str:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from seam.measurement_gates import UNCOLD_UPTIME_REASON

    return UNCOLD_UPTIME_REASON


def noreboot_deviation() -> dict[str, Any] | None:
    """Deviation stamped into plan and summary when the sequencer sets the env."""
    if os.environ.get("SEAM_NOREBOOT_DEVIATION") != "1":
        return None
    raw = os.environ.get("SEAM_NOREBOOT_UPTIME_S", "").strip()
    uptime: float | None = float(raw) if raw else None
    return {
        "kind": "UNCOLD_UPTIME",
        "uptime_s": uptime,
        "reason": _uncold_reason(),
    }


def _prefill_s(doc: dict[str, Any]) -> float | None:
    generation = doc.get("generation")
    if isinstance(generation, dict) and generation.get("prefill_s") is not None:
        return float(generation["prefill_s"])
    if doc.get("prefill_s") is not None:
        return float(doc["prefill_s"])
    return None


def _result_path(work: Path, repeat: int, n: int = CONTROL_N) -> Path | None:
    name = f"gpu_only_f16.n{n}.r{repeat}.a0.result.json"
    direct = work / name
    if direct.is_file():
        return direct
    matches = sorted(p for p in work.rglob(name) if p.is_file())
    if len(matches) == 1:
        return matches[0]
    return None


def load_prefills(work: Path, n: int = CONTROL_N) -> list[float]:
    """Repeat-order prefill_s. Short when a repeat file or value is missing."""
    values: list[float] = []
    for repeat in range(CONTROL_REPEATS):
        path = _result_path(work, repeat, n)
        if path is None:
            return values
        value = _prefill_s(json.loads(path.read_text(encoding="utf-8")))
        if value is None:
            return values
        values.append(value)
    return values


def reference_work(repo_root: Path) -> Path:
    return repo_root / "derived" / "c2_ttft" / REFERENCE_RUN_ID / "work"


def band_from_prefills(prefills: list[float]) -> dict[str, Any]:
    if len(prefills) != CONTROL_REPEATS:
        raise ValueError(f"expected {CONTROL_REPEATS} prefills, got {len(prefills)}")
    median = float(statistics.median(prefills))
    if median <= 0:
        raise ValueError("median prefill_s must be positive")
    low_raw = min(prefills)
    high_raw = max(prefills)
    spread = max(abs(value - median) / median for value in prefills)
    return {
        "reference_run_id": REFERENCE_RUN_ID,
        "n": CONTROL_N,
        "repeats_prefill_s": list(prefills),
        "min": low_raw,
        "max": high_raw,
        "median": median,
        "max_relative_spread": spread,
        "low": low_raw * (1.0 - spread),
        "high": high_raw * (1.0 + spread),
        "formula": FORMULA,
    }


def reference_band(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or ROOT
    prefills = load_prefills(reference_work(root))
    band = band_from_prefills(prefills)
    base_s = CONTROL_REPEATS * float(band["median"])
    raw_estimate = base_s + CANARY_OVERHEAD_S
    if raw_estimate == math.floor(raw_estimate):
        estimate_s = int(raw_estimate)
    else:
        estimate_s = math.ceil(raw_estimate)
    band["base_s"] = base_s
    band["noreboot_reason"] = _uncold_reason()
    band["canary_overhead_s"] = CANARY_OVERHEAD_S
    band["estimate_s"] = int(estimate_s)
    band["estimate_formula"] = (
        "estimate_s = next whole second of (3 * reference median prefill_s "
        "+ canary overhead 752.1359013 from c2246b1f)"
    )
    return band


def evaluate_control(prefills: list[float], band: dict[str, Any]) -> dict[str, Any]:
    verdict: dict[str, Any] = {
        "reference_run_id": band["reference_run_id"],
        "n": band["n"],
        "low": band["low"],
        "high": band["high"],
        "max_relative_spread": band["max_relative_spread"],
        "reference_min": band["min"],
        "reference_max": band["max"],
        "reference_median": band["median"],
        "control_prefills": list(prefills),
        "formula": band["formula"],
    }
    if len(prefills) != CONTROL_REPEATS:
        verdict["pass"] = False
        verdict["median"] = None
        verdict["reason"] = f"expected {CONTROL_REPEATS} control prefills, got {len(prefills)}"
        return verdict
    median = float(statistics.median(prefills))
    ok = float(band["low"]) <= median <= float(band["high"])
    verdict["pass"] = ok
    verdict["median"] = median
    verdict["reason"] = "inside_band" if ok else "median_outside_band"
    return verdict


def check_work(repo_root: Path, work: Path) -> dict[str, Any]:
    return evaluate_control(load_prefills(work), reference_band(repo_root))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-band", action="store_true")
    parser.add_argument("--check-work", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=None)
    args = parser.parse_args(argv)
    root = (args.repo_root or ROOT).resolve()
    if args.print_band:
        print(json.dumps(reference_band(root), sort_keys=True))
        return 0
    if args.check_work is not None:
        verdict = check_work(root, args.check_work)
        print(json.dumps(verdict, sort_keys=True))
        return 0 if verdict["pass"] else 1
    parser.error("pass --print-band or --check-work")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
