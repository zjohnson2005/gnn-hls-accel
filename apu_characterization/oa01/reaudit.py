"""Recompute OA-01 audits from retained raw boundary artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apu_characterization.oa01.audit import audit_trajectory
from apu_characterization.oa01.derive import (
    derive_turn_records,
    load_api_records,
    load_exec_spans,
    write_jsonl,
)


def reaudit_run(run_dir: Path) -> dict:
    run_meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    api_records = load_api_records(run_dir / "raw" / "api_boundary.jsonl")
    exec_spans = load_exec_spans(run_dir / "raw" / "exec_events.jsonl")
    turns = derive_turn_records(
        api_records=api_records,
        exec_spans=exec_spans,
        task_id=str(run_meta["task_id"]),
        trajectory_start_unix_ns=int(run_meta["trajectory_start_unix_ns"]),
        trajectory_end_unix_ns=int(run_meta["trajectory_end_unix_ns"]),
    )
    write_jsonl(run_dir / "derived" / "turn_records.jsonl", (t.to_dict() for t in turns))
    write_jsonl(run_dir / "derived" / "exec_spans.jsonl", (s.to_dict() for s in exec_spans))
    bundle_path = run_dir / "replay" / f"{run_meta['trajectory_id']}.oa01bundle"
    audit = audit_trajectory(
        turns=turns,
        api_records=api_records,
        exec_spans=exec_spans,
        run_meta=run_meta,
        bundle_path=bundle_path,
    )
    (run_dir / "audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    traj_path = run_dir / "trajectory_record.json"
    if traj_path.is_file():
        traj = json.loads(traj_path.read_text(encoding="utf-8"))
        flags = [
            flag
            for flag in traj.get("flags", [])
            if not str(flag).startswith("audit:")
        ]
        if not audit["pass"]:
            flags.extend(f"audit:{flag}" for flag in audit["flags"])
        traj["flags"] = flags
        traj_path.write_text(json.dumps(traj, indent=2) + "\n", encoding="utf-8")
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/oa01"),
    )
    parser.add_argument(
        "--trajectory-id",
        action="append",
        default=[],
        help="Reaudit one trajectory (repeatable). Default: all runs under out/runs.",
    )
    args = parser.parse_args(argv)
    runs_root = args.out / "runs"
    if args.trajectory_id:
        run_dirs = [runs_root / tid for tid in args.trajectory_id]
    else:
        run_dirs = sorted(path for path in runs_root.iterdir() if path.is_dir())
    for run_dir in run_dirs:
        if not (run_dir / "run.json").is_file():
            continue
        audit = reaudit_run(run_dir)
        print(
            json.dumps(
                {
                    "trajectory_id": audit.get("trajectory_id"),
                    "pass": audit.get("pass"),
                    "flags": audit.get("flags"),
                }
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
