"""Step 4 — full C1/C2 collection under budget_lock with 10% hand-monitor + replay sample."""

from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

from apu_characterization.turntrace_v2.collect_cloud import (
    DEFAULT_BUDGET_LOCK,
    HARNESS_IDS,
    collect_cell,
)
from apu_characterization.turntrace_v2.mock_engine import MockEngine
from apu_characterization.turntrace_v2.replay import load_bundle, swapped_step_replay
from apu_characterization.turntrace_v2.spend_guard import BudgetLock
from apu_characterization.turntrace_v2.workload.swebench_lite import write_fixture_subset


def _flag_rate(corpus_dir: Path) -> dict:
    path = corpus_dir / "call_records.jsonl"
    if not path.is_file():
        return {"n": 0, "flag_rate": 0.0, "flags": {}}
    n = 0
    flagged = 0
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        n += 1
        fl = row.get("audit_flags") or []
        if fl:
            flagged += 1
        for f in fl:
            counts[f] = counts.get(f, 0) + 1
    return {"n": n, "flag_rate": (flagged / n if n else 0.0), "flags": counts}


def _replay_sample(bundle_dir: Path, *, k: int = 5) -> list[dict]:
    bundles = sorted(bundle_dir.glob("*.ttbundle"))
    if not bundles:
        return []
    pick = bundles if len(bundles) <= k else random.sample(bundles, k)
    mock = MockEngine()
    out = []
    for bp in pick:
        archived = load_bundle(bp)
        if not archived.turns:
            out.append({"bundle": str(bp), "success": False, "error": "empty"})
            continue
        result = swapped_step_replay(
            archived,
            swap_turn=max(1, archived.turns[-1].turn_index // 2),
            model_fn=mock.as_model_fn(fixed_output="full-swap"),
            model_id="swap-mock",
            reasoning_mode="on",
            tool_executor=lambda name, args, turn: turn.tool_results[0]
            if turn.tool_results
            else {"ok": True},
        )
        out.append(
            {
                "bundle": str(bp),
                "success": result.success,
                "swap_turn": result.swap_turn,
            }
        )
    return out


def collect_cell_phased(
    *,
    cell_id: str,
    out_root: Path,
    api_key: str,
    lock: BudgetLock,
    spent_usd: float,
    max_flag_rate: float = 0.5,
) -> tuple[dict, float]:
    cell = lock.cell(cell_id)
    n_full = int(cell["n_trajectories"])
    out_dir = out_root / f"cell_{cell_id}"
    subset = out_dir / "subset.json"
    write_fixture_subset(subset, n=max(3, n_full))

    # Phase A: first ~10% (1 traj × both harnesses)
    phase_a = collect_cell(
        out_dir=out_dir / "phase_a",
        cell_id=cell_id,
        model_id=str(cell["model_id"]),
        n_trajectories=1,
        subset_path=subset,
        live=True,
        base_url=str(cell.get("base_url") or "https://api.openai.com/v1"),
        api_key=api_key,
        network_baseline_ms=40.0,
        n_turns=6,
        harnesses=HARNESS_IDS,
        budget_lock_path=lock.path,
        spent_usd=spent_usd,
    )
    spent_usd += float((phase_a.get("spend") or {}).get("planned_usd") or 0.0)
    rates = _flag_rate(out_dir / "phase_a" / "corpus")
    if rates["flag_rate"] > max_flag_rate:
        raise SystemExit(
            f"{cell_id} phase_a flag_rate={rates['flag_rate']:.2f} > {max_flag_rate}; "
            f"flags={rates['flags']}. Pause — do not continue unattended."
        )

    # Phase B: remaining trajectories
    remain = n_full - 1
    phase_b = None
    if remain > 0:
        phase_b = collect_cell(
            out_dir=out_dir / "phase_b",
            cell_id=cell_id,
            model_id=str(cell["model_id"]),
            n_trajectories=remain,
            subset_path=subset,
            live=True,
            base_url=str(cell.get("base_url") or "https://api.openai.com/v1"),
            api_key=api_key,
            network_baseline_ms=40.0,
            n_turns=6,
            harnesses=HARNESS_IDS,
            budget_lock_path=lock.path,
            spent_usd=spent_usd,
        )
        spent_usd += float((phase_b.get("spend") or {}).get("planned_usd") or 0.0)

    # Merge bundle paths for replay sample
    bundle_dir = out_dir / "bundles_all"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for phase in ("phase_a", "phase_b"):
        src = out_dir / phase / "bundles"
        if src.is_dir():
            for bp in src.glob("*.ttbundle"):
                dest = bundle_dir / bp.name
                if not dest.exists():
                    dest.write_bytes(bp.read_bytes())

    replay = _replay_sample(bundle_dir, k=5)
    summary = {
        "cell_id": cell_id,
        "model_id": cell["model_id"],
        "phase_a": phase_a,
        "phase_a_flag_rates": rates,
        "phase_b": phase_b,
        "replay_sample": replay,
        "replay_all_ok": all(r.get("success") for r in replay) and len(replay) >= min(5, n_full * 2),
        "spent_usd_after": spent_usd,
    }
    (out_dir / "full_cell_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    if not summary["replay_all_ok"]:
        raise SystemExit(f"{cell_id} replay sample failed: {replay}")
    return summary, spent_usd


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--budget-lock", type=Path, default=DEFAULT_BUDGET_LOCK)
    p.add_argument("--api-key", type=str, default=None)
    p.add_argument("--cells", nargs="+", default=["C1", "C2"])
    p.add_argument("--spent-usd", type=float, default=0.0, help="Prior spend (e.g. smoke+survey)")
    args = p.parse_args(argv)
    key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY required")

    lock = BudgetLock.load(args.budget_lock)
    spent = float(args.spent_usd)
    cells = []
    for cell_id in args.cells:
        summary, spent = collect_cell_phased(
            cell_id=cell_id,
            out_root=args.out,
            api_key=key,
            lock=lock,
            spent_usd=spent,
        )
        cells.append(summary)

    report = {
        "cells": cells,
        "spent_usd_estimated": spent,
        "hard_ceiling_usd": lock.hard_ceiling_usd,
        "under_ceiling": spent <= lock.hard_ceiling_usd,
        "all_replay_ok": all(c["replay_all_ok"] for c in cells),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "full_collect_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["all_replay_ok"] and report["under_ceiling"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
