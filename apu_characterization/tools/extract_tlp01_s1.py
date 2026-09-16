"""S1: extract frozen TLP-01 traces from existing replication artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from apu_characterization.tlp01.extract import extract_from_replication_session
from apu_characterization.tlp01.labels import find_rung_labels
from apu_characterization.tlp01.schema import write_frozen_trace
from apu_characterization.tlp01.t0_audit import audit_trace_events

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = (
    REPO / "apu_characterization/out/replication_remote_search_v3.json"
)
DEFAULT_OUT = REPO / "apu_characterization/out/tlp01/traces"


def iter_sessions(artifact: dict) -> list[dict]:
    sessions: list[dict] = []
    for art in artifact.get("per_seed_artifacts") or []:
        seed = int((art.get("config") or {}).get("seed") or 0)
        git = (art.get("env") or {}).get("git") or artifact.get("git") or {}
        for sess in (art.get("run") or {}).get("per_session") or []:
            row = dict(sess)
            row["seed"] = seed
            row["_source_seed"] = seed
            row["_source_git"] = git
            row["_host_class"] = (art.get("env") or {}).get("platform") or "unknown"
            sessions.append(row)
    return sessions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    artifact = json.loads(args.source.read_text(encoding="utf-8"))
    sessions = iter_sessions(artifact)
    out_s1 = args.out / "S1"
    out_s1.mkdir(parents=True, exist_ok=True)

    written = []
    discarded = []
    by_task: Counter[str] = Counter()

    for index, sess in enumerate(sessions):
        task_id = str(sess.get("task_id") or "UNK")
        seed = int(sess.get("seed") or 0)
        sid = f"S1-{task_id}-s{seed}-i{index}"
        events = extract_from_replication_session(sess, session_id=sid)
        # Attach provenance onto event dicts via rewrite.
        payload = []
        for event in events:
            payload.append(
                {
                    "session_id": event.session_id,
                    "seq": event.seq,
                    "event_type": event.event_type,
                    "t_issue_ns": event.t_issue_ns,
                    "t_complete_ns": event.t_complete_ns,
                    "inputs_hash": event.inputs_hash,
                    "output_hash": event.output_hash,
                    "output_text_ref": event.output_text_ref,
                    "tool_name": event.tool_name,
                    "args_ref": event.args_ref,
                    "result_ref": event.result_ref,
                    "stage_timings": dict(event.stage_timings),
                    "harness_order_index": event.harness_order_index,
                    "task_class": event.task_class,
                    "seed": event.seed,
                    "control_parent_seq": event.control_parent_seq,
                    "produced_paths": list(event.produced_paths),
                    "result_ids": list(event.result_ids),
                    "input_text": event.input_text,
                    "output_text": event.output_text,
                    "dep_refs": None,
                }
            )
        audit = audit_trace_events(payload, source="S1", task_id=task_id)
        path = out_s1 / f"{sid}.jsonl"
        meta_path = path.with_suffix(".jsonl.meta.json")
        if path.exists() and meta_path.exists():
            # Append-only resume: already-frozen traces count as usable.
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            written.append(meta)
            by_task[task_id] += 1
            continue
        if not audit["pass"]:
            discarded.append(
                {"session_id": sid, "reason": "audit_fail", "errors": audit["errors"]}
            )
            continue
        meta = write_frozen_trace(payload, path)
        meta.update(
            {
                "source": "S1",
                "source_artifact": str(args.source.relative_to(REPO)).replace("\\", "/"),
                "task_id": task_id,
                "seed": seed,
                "host_class": sess.get("_host_class"),
                "result_validity_inherited": artifact.get("result_validity"),
                "limitation": (
                    "S1 tasks were never designed for parallelism; "
                    "serial-spectrum anchor / oracle calibration only."
                ),
            }
        )
        meta_path.write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        written.append(meta)
        by_task[task_id] += 1

    inventory = {
        "source": "S1",
        "source_artifact": str(args.source),
        "usable_traces": len(written),
        "discarded": discarded,
        "by_task": dict(sorted(by_task.items())),
        "limitation": (
            "S1 anchors the SERIAL end of the task spectrum; not the basis "
            "for the ceiling claim (S2 is)."
        ),
    }
    blob = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    if find_rung_labels(blob):
        raise SystemExit("S1 inventory must not contain rung labels")
    (args.out / "S1_extract_inventory.json").write_text(blob, encoding="utf-8")
    print(
        f"S1 extraction: {len(written)} usable / {len(sessions)} source sessions; "
        f"discarded={len(discarded)}"
    )


if __name__ == "__main__":
    main()
