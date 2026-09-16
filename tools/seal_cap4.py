"""Seal a CAP-4 session (write-once derived_diagnostic + INF-5 fields).

Accepts status=complete or status=aborted. Aborted seals remain clearly marked
aborted — never silently promoted to complete. Copies session artifacts under
derived/cap4/<session_id>/ into sealed_<session_id>/, writes manifest.json +
summary.json + .sealed (tree_sha256). Requires plan/summary run_environment
(INF-5). Does not promote to raw/.

Usage:
  .\\.venv-seam\\Scripts\\python.exe tools\\seal_cap4.py --session-id <uuid>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.run_environment import REQUIRED_RUN_ENVIRONMENT_FIELDS, require_run_environment

SESSION_BASE = ROOT / "derived" / "cap4"
WORKLOAD_KIND = "cap4_prefill_curve_to_failure"
IR_PIN = "c1821f29332faa48871c7f16426a21443fbc701fa4e4c8a581a8c51ab7bf2cb2"
SEALABLE_STATUSES = frozenset({"complete", "aborted"})

COPY_FILES = (
    "plan.json",
    "summary.json",
    "analysis.json",
    "cells.json",
    "probes.ndjson",
    "checkpoint.json",
    "realized_orders.json",
    "CAP4_RESULTS.md",
    "watchdog_kills.jsonl",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256_tree(root: Path, *, exclude: set[str]) -> str:
    h = hashlib.sha256()
    files = sorted(
        (p for p in root.rglob("*") if p.is_file() and p.name not in exclude),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    for p in files:
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def seal_session(*, session_id: str) -> Path:
    session_dir = SESSION_BASE / session_id
    if not session_dir.is_dir():
        raise SystemExit(f"REFUSED -- session dir missing: {session_dir}")
    plan = _read_json(session_dir / "plan.json")
    summary = _read_json(session_dir / "summary.json")
    status = summary.get("status")
    if status not in SEALABLE_STATUSES:
        raise SystemExit(
            f"REFUSED -- summary status={status!r} (need one of {sorted(SEALABLE_STATUSES)})"
        )

    env = summary.get("run_environment") or plan.get("run_environment")
    if not isinstance(env, dict):
        raise SystemExit("REFUSED -- INF-5 run_environment missing from summary/plan")
    from seam.run_environment import merge_run_environment

    merged = merge_run_environment(env, capture_host=True)
    require_run_environment(merged)

    if plan.get("ir_sha256") and plan["ir_sha256"] != IR_PIN:
        raise SystemExit(
            f"REFUSED -- ir_sha256 mismatch: plan={plan.get('ir_sha256')} pin={IR_PIN}"
        )

    out = SESSION_BASE / f"sealed_{session_id}"
    if out.exists():
        raise SystemExit(f"REFUSED -- seal already exists (write-once): {out}")
    out.mkdir(parents=True)

    for name in COPY_FILES:
        src = session_dir / name
        if src.is_file():
            shutil.copy2(src, out / name)

    work_src = session_dir / "work"
    if work_src.is_dir():
        shutil.copytree(work_src, out / "work", dirs_exist_ok=False)

    pred_src = SESSION_BASE / "CAP4_PREDICTIONS.json"
    if pred_src.is_file():
        shutil.copy2(pred_src, out / "CAP4_PREDICTIONS.json")
    pred_md = SESSION_BASE / "CAP4_PREDICTIONS.md"
    if pred_md.is_file():
        shutil.copy2(pred_md, out / "CAP4_PREDICTIONS.md")

    sealed_utc = _utc_now()
    abort_block: dict[str, Any] | None = None
    if status == "aborted":
        abort_block = {
            "status": "aborted",
            "abort_reason": summary.get("abort_reason"),
            "abort_verbatim": summary.get("abort_verbatim"),
            "abort_at": summary.get("abort_at"),
            "rungs_completed_per_arm": summary.get("rungs_completed_per_arm"),
            "note": (
                "ABORTED seal — completed cells are data; status is not complete. "
                "Do not treat this as a finished curve-to-failure."
            ),
        }

    manifest = {
        "kind": WORKLOAD_KIND,
        "experiment": "CAP-4",
        "session_id": session_id,
        "run_id": session_id,
        "status": status,
        "seal_style": "derived_diagnostic",
        "sealed_utc": sealed_utc,
        "spec_version_note": "INF-5 run_environment required; not a raw/ 1.1 emit",
        "ir_sha256": plan.get("ir_sha256") or IR_PIN,
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "session_design": "interleaved",
        "arm_order": plan.get("arm_order"),
        "run_environment": merged,
        "analysis": summary.get("analysis"),
        "arm_dead": summary.get("arm_dead"),
        "rungs_executed": summary.get("rungs_executed"),
        "predictions_registered_utc": summary.get("predictions_registered_utc"),
        "abort": abort_block,
        "source_session": _rel(session_dir),
        "raw_promote": {
            "attempted": False,
            "reason": "derived_diagnostic seal only; raw/ promote not requested for CAP-4.",
        },
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    sealed_summary = dict(summary)
    sealed_summary["status"] = status  # never promote aborted → complete
    sealed_summary["run_environment"] = merged
    sealed_summary["seal_style"] = "derived_diagnostic"
    sealed_summary["sealed_utc"] = sealed_utc
    if status == "aborted":
        sealed_summary["seal_note"] = (
            "Sealed as aborted. Completed cells retained; not a complete curve-to-failure."
        )
    (out / "summary.json").write_text(
        json.dumps(sealed_summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    tree_hash = _sha256_tree(out, exclude={".sealed"})
    seal_marker = {
        "session_id": session_id,
        "sealed_at_utc": sealed_utc,
        "seal_style": "derived_diagnostic",
        "status": status,
        "tree_sha256": tree_hash,
        "run_environment_fields": list(REQUIRED_RUN_ENVIRONMENT_FIELDS),
        "abort": abort_block,
        "note": (
            "Advisory marker for derived_diagnostic seals. Not "
            "seam.rawstore.verify_sealed; raw/ was not written. Do not mutate "
            "this directory after seal."
            + (
                " STATUS=aborted — not a complete run."
                if status == "aborted"
                else ""
            )
        ),
    }
    (out / ".sealed").write_text(
        json.dumps(seal_marker, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "ok": True,
                "seal_dir": str(out),
                "seal_id": f"sealed_{session_id}",
                "status": status,
                "tree_sha256": tree_hash,
                "aborted": status == "aborted",
            },
            indent=2,
        )
    )
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session-id", required=True)
    args = p.parse_args(argv)
    seal_session(session_id=args.session_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
