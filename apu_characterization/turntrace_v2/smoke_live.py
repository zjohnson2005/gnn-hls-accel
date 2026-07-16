"""Step 3 — live-fire smoke: 1× raw_python traj per cell, hand-inspect flags + replay CI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from apu_characterization.turntrace_v2.collect_cloud import collect_cell, DEFAULT_BUDGET_LOCK
from apu_characterization.turntrace_v2.mock_engine import MockEngine
from apu_characterization.turntrace_v2.replay import load_bundle, swapped_step_replay
from apu_characterization.turntrace_v2.spend_guard import BudgetLock
from apu_characterization.turntrace_v2.workload.swebench_lite import write_fixture_subset


EXPLAINED_FLAGS: set[str] = set()  # ttft_derived skips profile_drift; unexplained = any flag


def _inspect_events(events_path: Path) -> dict:
    rows = json.loads(events_path.read_text(encoding="utf-8"))
    # derive again for flags if corpus call_records exist
    return {
        "n_turns": len(rows),
        "prefill_methods": sorted({r.get("prefill_method") for r in rows}),
        "network_methods": sorted({r.get("network_method") for r in rows}),
        "engine_tokens": [r.get("engine_tokens_in") for r in rows],
        "tokens_out": [r.get("tokens_out") for r in rows],
        "deltas": [
            (r.get("engine_tokens_in") or 0) - (r.get("requested_tokens_in") or 0) for r in rows
        ],
        "t_prefill_ms": [r.get("t_prefill_ms") for r in rows],
    }


def _inspect_calls(corpus_dir: Path) -> dict:
    path = corpus_dir / "call_records.jsonl"
    if not path.is_file():
        return {"call_records": None}
    flags = []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows.append(row)
        flags.extend(row.get("audit_flags") or [])
    unexplained = sorted({f for f in flags if f not in EXPLAINED_FLAGS})
    return {
        "n_calls": len(rows),
        "all_flags": sorted(set(flags)),
        "unexplained_flags": unexplained,
        "per_call_flags": [(r.get("turn_index"), r.get("audit_flags")) for r in rows],
        "task_success_fields": "see trajectory records",
    }


def smoke_one(
    *,
    cell_id: str,
    out_root: Path,
    api_key: str,
    budget_lock: Path,
    spent_usd: float,
) -> dict:
    lock = BudgetLock.load(budget_lock)
    cell = lock.cell(cell_id)
    out_dir = out_root / f"smoke_{cell_id}"
    subset = out_dir / "subset.json"
    write_fixture_subset(subset, n=1)
    report = collect_cell(
        out_dir=out_dir,
        cell_id=cell_id,
        model_id=str(cell["smoke_model_id"]),
        n_trajectories=1,
        subset_path=subset,
        live=True,
        base_url=str(cell.get("base_url") or "https://api.openai.com/v1"),
        api_key=api_key,
        network_baseline_ms=40.0,
        n_turns=4,
        harnesses=("raw_python",),
        budget_lock_path=budget_lock,
        spent_usd=spent_usd,
        allow_spend_override=False,
    )
    traj_id = f"{cell_id}-raw_python-000"
    events_path = out_dir / "trajectories" / f"{traj_id}.events.json"
    bundle_path = out_dir / "bundles" / f"{traj_id}.ttbundle"
    event_insp = _inspect_events(events_path)
    call_insp = _inspect_calls(out_dir / "corpus")

    archived = load_bundle(bundle_path)
    mock = MockEngine()
    replay = swapped_step_replay(
        archived,
        swap_turn=max(1, archived.turns[-1].turn_index // 2) if archived.turns else 0,
        model_fn=mock.as_model_fn(fixed_output="smoke-swap"),
        model_id="swap-mock",
        reasoning_mode="on",
        tool_executor=lambda name, args, turn: turn.tool_results[0]
        if turn.tool_results
        else {"ok": True},
    )
    traj_meta = json.loads((out_dir / "collect_report.json").read_text(encoding="utf-8"))
    ok = (
        replay.success
        and "ttft_derived" in event_insp["prefill_methods"]
        and not call_insp.get("unexplained_flags")
    )
    return {
        "cell_id": cell_id,
        "model_id": cell["smoke_model_id"],
        "collect": report,
        "events": event_insp,
        "calls": call_insp,
        "replay": {
            "success": replay.success,
            "swap_turn": replay.swap_turn,
            "tool_replay_modes": replay.tool_replay_modes,
        },
        "spend": traj_meta.get("spend"),
        "ok": ok,
        "hand_inspection_notes": [
            "Read per_call_flags before trusting aggregate gate.",
            "profile_drift expected under placeholder f(n) in collect_cloud — explained.",
            "Confirm ttft_derived + usage tokens in events.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--budget-lock", type=Path, default=DEFAULT_BUDGET_LOCK)
    p.add_argument("--api-key", type=str, default=None)
    p.add_argument("--cells", nargs="+", default=["C1", "C2"])
    args = p.parse_args(argv)
    key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY required")

    results = []
    spent = 0.0
    for cell_id in args.cells:
        r = smoke_one(
            cell_id=cell_id,
            out_root=args.out,
            api_key=key,
            budget_lock=args.budget_lock,
            spent_usd=spent,
        )
        results.append(r)
        planned = (r.get("spend") or {}).get("planned_usd") or 0.0
        spent += float(planned)

    summary = {
        "results": results,
        "all_ok": all(r["ok"] for r in results),
        "spent_usd_estimated": spent,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "smoke_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
