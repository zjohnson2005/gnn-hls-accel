"""S2: live multi-tool collection with Tier-0 dep_refs (append-only traces)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from apu_characterization.tlp01.contracts import load_protocol, sha256_json
from apu_characterization.tlp01.labels import find_rung_labels
from apu_characterization.tlp01.s2_harness import (
    run_s2_session,
    session_record_to_events,
)
from apu_characterization.tlp01.schema import write_frozen_trace
from apu_characterization.tlp01.t0_audit import audit_trace_events

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "apu_characterization/tlp01/s2_task_manifest.json"
DEFAULT_OUT = REPO / "apu_characterization/out/tlp01/traces"
DISCARD_LOG = REPO / "apu_characterization/out/tlp01/traces/S2_discard_log.jsonl"


def _ensure_schema_frozen_before_s2() -> str:
    protocol = load_protocol()
    schema = protocol["trace_schema"]
    if schema.get("version") != "tlp01_trace_v2":
        raise SystemExit("refuse S2: protocol trace schema is not tlp01_trace_v2")
    if "dep_refs" not in schema.get("required_fields", []):
        raise SystemExit("refuse S2: dep_refs not frozen in protocol schema")
    if "Tier_0" not in protocol.get("dependence_oracles", {}):
        raise SystemExit("refuse S2: Tier_0 oracle missing from protocol")
    digest = sha256_json(schema)
    stamp = REPO / "apu_characterization/out/tlp01/traces/SCHEMA_FREEZE.json"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    if stamp.exists():
        prior = json.loads(stamp.read_text(encoding="utf-8"))
        if prior.get("trace_schema_sha256") != digest:
            raise SystemExit(
                "refuse S2: SCHEMA_FREEZE.json drift vs current protocol schema"
            )
    else:
        stamp.write_text(
            json.dumps(
                {
                    "trace_schema_sha256": digest,
                    "schema_version": schema["version"],
                    "frozen_before_s2": True,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return digest


def _append_discard(entry: dict) -> None:
    DISCARD_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DISCARD_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-sessions", type=int, default=50)
    parser.add_argument("--attempt-budget", type=int, default=80)
    parser.add_argument("--sleep-s", type=float, default=0.75)
    args = parser.parse_args()

    import os

    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if len(key) < 20:
        raise SystemExit(
            "refuse S2: OPENAI_API_KEY missing or invalid "
            f"(observed len={len(key)}; need a live OpenAI key in the env)"
        )

    schema_sha = _ensure_schema_frozen_before_s2()
    print(f"SCHEMA_FREEZE ok sha={schema_sha[:16]}…")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    templates = list(manifest["templates"])
    seeds = list(manifest["seeds"])
    out_s2 = args.out / "S2"
    out_s2.mkdir(parents=True, exist_ok=True)

    # Resume: count already-frozen passing traces.
    existing = list(out_s2.glob("S2-*.jsonl"))
    passed = len(existing)
    print(f"resume: {passed} frozen S2 traces already present")

    attempts = 0
    plan = [(t, s) for t in templates for s in seeds]
    # Skip cells that already have a frozen file.
    pending = []
    for tmpl, seed in plan:
        sid = f"S2-{tmpl['task_id']}-s{seed}"
        if (out_s2 / f"{sid}.jsonl").exists():
            continue
        pending.append((tmpl, seed, sid))

    while passed < args.max_sessions and attempts < args.attempt_budget and pending:
        tmpl, seed, canonical_sid = pending.pop(0)
        attempts += 1
        # Discarded attempts get a distinct attempt_id; the frozen file uses
        # the canonical cell id so resume stays deterministic.
        attempt_id = f"{canonical_sid}-a{attempts}"
        print(f"[{passed}/{args.max_sessions}] attempt={attempts} {attempt_id}")
        record = run_s2_session(
            task_id=tmpl["task_id"], goal=tmpl["goal"], seed=seed
        )
        path = out_s2 / f"{canonical_sid}.jsonl"
        if path.exists():
            passed = len(list(out_s2.glob("S2-*.jsonl")))
            continue

        if not record.get("ok"):
            _append_discard(
                {
                    "session_id": attempt_id,
                    "canonical_session_id": canonical_sid,
                    "reason": "runtime_error",
                    "error": record.get("error"),
                    "attempt": attempts,
                }
            )
            pending.append((tmpl, seed, canonical_sid))
            time.sleep(args.sleep_s)
            continue

        events = session_record_to_events(record, attempt_id)
        try:
            audit = audit_trace_events(
                events, source="S2", task_id=tmpl["task_id"]
            )
        except Exception as exc:  # noqa: BLE001
            _append_discard(
                {
                    "session_id": attempt_id,
                    "canonical_session_id": canonical_sid,
                    "reason": "audit_exception",
                    "error": str(exc),
                }
            )
            pending.append((tmpl, seed, canonical_sid))
            continue

        if not audit["pass"]:
            _append_discard(
                {
                    "session_id": attempt_id,
                    "canonical_session_id": canonical_sid,
                    "reason": "audit_fail",
                    "errors": audit["errors"],
                    "tool_call_count": audit.get("tool_call_count"),
                }
            )
            pending.append((tmpl, seed, canonical_sid))
            time.sleep(args.sleep_s)
            continue

        # Freeze under canonical id; rewrite session_id on events for the store.
        for event in events:
            event["session_id"] = canonical_sid
        meta = write_frozen_trace(events, path)
        meta.update(
            {
                "source": "S2",
                "task_id": tmpl["task_id"],
                "seed": seed,
                "negative_control": bool(tmpl.get("negative_control")),
                "shape": tmpl.get("shape"),
                "model": record.get("model"),
                "prompt_sha256": record.get("prompt_sha256"),
                "system_prompt_sha256": record.get("system_prompt_sha256"),
                "schema_freeze_sha256": schema_sha,
                "tier0_edge_count": audit.get("tier0_edge_count"),
                "tool_call_count": audit.get("tool_call_count"),
                "attempt_id": attempt_id,
            }
        )
        path.with_suffix(".jsonl.meta.json").write_text(
            json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        # Persist raw session record (append-only) for determinism notes.
        raw_path = out_s2 / f"{canonical_sid}.raw.json"
        if not raw_path.exists():
            raw_path.write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        passed += 1
        time.sleep(args.sleep_s)

    summary = {
        "source": "S2",
        "passed": passed,
        "target": args.max_sessions,
        "attempts": attempts,
        "schema_freeze_sha256": schema_sha,
        "pending_remaining": len(pending),
        "complete": passed >= args.max_sessions,
    }
    blob = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if find_rung_labels(blob):
        raise SystemExit("S2 summary must not contain rung labels")
    (args.out / "S2_collection_summary.json").write_text(blob, encoding="utf-8")
    print(json.dumps(summary))
    if passed < args.max_sessions:
        raise SystemExit(
            f"S2 incomplete: {passed}/{args.max_sessions} "
            f"(attempts={attempts}, pending={len(pending)})"
        )


if __name__ == "__main__":
    main()
