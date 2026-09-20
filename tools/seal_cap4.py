"""Seal a CAP-4 session (write-once derived_diagnostic + INF-5 fields).

Accepts status=complete or status=aborted. Aborted seals remain clearly marked
aborted - never silently promoted to complete. Copies session artifacts under
derived/cap4/<session_id>/ into sealed_<session_id>/, writes manifest.json +
summary.json + .sealed (tree_sha256). Requires plan/summary run_environment
(INF-5). Does not promote to raw/.

Also supports --reconstruct: rebuild summary.json from cells.json /
probes.ndjson / plan.json when a Force-kill skipped the worker ``finally``
(same gap as 2b3316b6). Cross-host reconstruct takes platform identity from the
session plan/probes - never from the sealing host.

Usage:
  .\\.venv-seam\\Scripts\\python.exe tools\\seal_cap4.py --session-id <uuid>
  .\\.venv-seam\\Scripts\\python.exe tools\\seal_cap4.py --session-id <uuid> --reconstruct \\
      --abort-reason \"Stop-Process -Force\" \\
      --abort-verbatim \"killed; finally skipped; no summary.json\"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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

#: Marker digest when a cross-host reconstruct cannot recover a host INF-5 field.
#: Equal to sha256(b"SEAM_UNAVAILABLE_CROSS_HOST_RECONSTRUCT") - not a pip freeze.
_UNAVAILABLE_CROSS_HOST_SHA256 = hashlib.sha256(
    b"SEAM_UNAVAILABLE_CROSS_HOST_RECONSTRUCT"
).hexdigest()
_UNAVAILABLE_CROSS_HOST_STR = "UNAVAILABLE_CROSS_HOST_RECONSTRUCT"

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

_HOST_ONLY_INF5 = (
    "gpu_driver_version",
    "windows_build",
    "pip_freeze_sha256",
    "tokenizers_version",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


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


def _seal_host_platform_id() -> str:
    pin = ROOT / "configs" / "platforms" / "active_platform_id.txt"
    if pin.is_file():
        return pin.read_text(encoding="utf-8").strip() or "aipc-c1"
    return "aipc-c1"


def infer_execution_platform_id(plan: dict[str, Any], probes: list[dict[str, Any]]) -> str:
    """Infer execution host from session artifacts - never from the sealing host."""
    explicit = plan.get("platform_id") or (plan.get("run_environment") or {}).get("platform_id")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    model_spec = str(plan.get("model_spec") or "")
    watchdog = str((plan.get("watchdog") or {}).get("kill_log") or "")
    blob = f"{model_spec}\n{watchdog}".lower()
    if "\\users\\zach\\" in blob or "/users/zach/" in blob:
        return "evo-t2"
    if "\\users\\zjohn\\" in blob or "/users/zjohn/" in blob:
        return "aipc-c1"

    avail = plan.get("available_mb_start")
    if isinstance(avail, dict):
        mb = avail.get("available_mb")
    else:
        mb = (plan.get("run_environment") or {}).get("available_mb_start")
    try:
        mb_f = float(mb) if mb is not None else None
    except (TypeError, ValueError):
        mb_f = None
    if mb_f is not None and mb_f >= 40000:
        return "evo-t2"

    if probes:
        host_mem = probes[0].get("host_memory_start") or {}
        total = host_mem.get("total_physical_bytes")
        try:
            total_f = float(total) if total is not None else None
        except (TypeError, ValueError):
            total_f = None
        if total_f is not None and total_f >= 50_000_000_000:
            return "evo-t2"
        if total_f is not None and total_f < 25_000_000_000:
            return "aipc-c1"

    raise SystemExit(
        "REFUSED -- cannot infer execution platform_id from plan/probes; "
        "set plan.platform_id or pass --execution-platform-id"
    )


def _fold_prompt_renders(probes: list[dict[str, Any]]) -> tuple[str, int, dict[str, Any]]:
    """Replay prompt hasher from probes; prefer local prompt files, else stored sha256."""
    hasher = hashlib.sha256()
    updates = 0
    missing_local: list[int] = []
    used_stored_digest: list[int] = []

    def _fold_text(text: str) -> None:
        nonlocal updates
        hasher.update(b"\0")
        hasher.update(text.encode("utf-8"))
        updates += 1

    for row in probes:
        n = row.get("n_tokens")
        local = ROOT / "derived" / "delta_n" / "prompts" / f"n{int(n)}.txt" if n is not None else None
        prompt_path = row.get("prompt_path")
        if local is not None and local.is_file():
            _fold_text(local.read_text(encoding="utf-8"))
            continue
        if isinstance(prompt_path, str) and Path(prompt_path).is_file():
            _fold_text(Path(prompt_path).read_text(encoding="utf-8"))
            continue
        digest = row.get("prompt_sha256")
        if isinstance(digest, str) and re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            hasher.update(b"\0prompt_sha256:")
            hasher.update(digest.lower().encode("ascii"))
            updates += 1
            if n is not None:
                used_stored_digest.append(int(n))
                missing_local.append(int(n))
            continue
        raise SystemExit(
            f"REFUSED -- reconstruct cannot fold prompt for probe "
            f"arm={row.get('arm_id')} n={n} (no local file, path, or prompt_sha256)"
        )

    if updates < 1:
        raise SystemExit("REFUSED -- reconstruct found no prompts to hash")

    meta = {
        "prompt_render_updates": updates,
        "missing_local_prompt_n": sorted(set(missing_local)),
        "folded_stored_prompt_sha256_n": sorted(set(used_stored_digest)),
        "note": (
            "When local derived/delta_n/prompts/nN.txt is absent on the seal host, "
            "the probe's recorded prompt_sha256 is folded under a typed prefix. "
            "This preserves a deterministic INF-5 digest without inventing prompt text."
        ),
    }
    return hasher.hexdigest(), updates, meta


def reconstruct_aborted_summary(
    *,
    session_dir: Path,
    abort_reason: str,
    abort_verbatim: str,
    execution_platform_id: str | None = None,
    abort_at: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild summary.json from on-disk cells/probes/plan for an aborted session.

    Reusable for same-host (2b3316b6) and cross-host (65e33de8 executed on evo-t2,
    sealed on aipc-c1). Never captures host INF-5 fields from the sealing machine
    when execution_platform_id differs from the seal host.
    """
    from tools.run_cap4_prefill_curve import analyze_session, _assert_predictions, _render_report

    plan = _read_json(session_dir / "plan.json")
    cells_doc = _read_json(session_dir / "cells.json")
    cells = list(cells_doc.get("cells") or [])
    probes = [
        json.loads(line)
        for line in (session_dir / "probes.ndjson").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    pred = _assert_predictions()
    arms = list(plan.get("arms") or ["gpu_only_f16", "gpu_only_u8", "gpu_only_u4"])
    session_id = str(plan.get("session_id") or session_dir.name)

    exec_id = execution_platform_id or infer_execution_platform_id(plan, probes)
    seal_id = _seal_host_platform_id()
    cross_host = exec_id != seal_id

    prompt_sha, prompt_updates, prompt_meta = _fold_prompt_renders(probes)

    last_mb_end = None
    if probes:
        last_mb_end = probes[-1].get("available_mb_end")
    avail_start = plan.get("available_mb_start")
    if isinstance(avail_start, dict):
        avail_start_mb = avail_start.get("available_mb")
    else:
        avail_start_mb = (plan.get("run_environment") or {}).get("available_mb_start")

    power = plan.get("power_state_at_start") or {}
    power_guid = power.get("power_plan_guid")

    run_environment: dict[str, Any] = {
        "available_mb_start": float(avail_start_mb),
        "available_mb_end": float(last_mb_end if last_mb_end is not None else avail_start_mb),
        "session_design": plan.get("session_design") or "interleaved",
        "arm_order": list(plan.get("arm_order") or arms),
        "prompt_render_sha256": prompt_sha,
        "reconstructed_from": "cells.json+probes.ndjson+plan.json",
        "prompt_render_updates": prompt_updates,
        "prompt_render_meta": prompt_meta,
        "platform_id": exec_id,
        "execution_platform_id": exec_id,
        "seal_platform_id": seal_id,
        "cross_host_reconstruct": cross_host,
    }
    if isinstance(power_guid, str) and power_guid.strip():
        run_environment["active_power_scheme_guid"] = power_guid.strip()

    # Host-only INF-5: never fill from the sealing host when platforms differ.
    unavailable: list[str] = []
    if cross_host:
        for key in _HOST_ONLY_INF5:
            if key == "pip_freeze_sha256":
                run_environment[key] = _UNAVAILABLE_CROSS_HOST_SHA256
            else:
                run_environment[key] = _UNAVAILABLE_CROSS_HOST_STR
            unavailable.append(key)
        if "active_power_scheme_guid" not in run_environment:
            run_environment["active_power_scheme_guid"] = _UNAVAILABLE_CROSS_HOST_STR
            unavailable.append("active_power_scheme_guid")
        # WSH bookend was never written (Force-kill skipped finally).
        run_environment["workloads_session_host_resident"] = False
        run_environment["workloads_session_host_note"] = (
            "Force-kill left no WSH bookend; recorded False as unknown-at-reconstruct, "
            "not a measured end-of-run probe on the seal host."
        )
        run_environment["cross_host_unavailable_fields"] = unavailable
        run_environment["cross_host_unavailable_pip_freeze_marker"] = (
            "pip_freeze_sha256 equals sha256(b'SEAM_UNAVAILABLE_CROSS_HOST_RECONSTRUCT'); "
            "not a measured freeze."
        )
    else:
        from seam.run_environment import capture_host_run_environment, merge_run_environment

        # Same-host retro-seal (2b3316b6 path): host capture fills missing INF-5.
        run_environment = merge_run_environment(run_environment, capture_host=True)

    ckpt: dict[str, Any] = {}
    ckpt_path = session_dir / "checkpoint.json"
    if ckpt_path.is_file():
        ckpt = _read_json(ckpt_path)

    executed = sorted({int(c["n_tokens"]) for c in cells})
    rungs_completed_per_arm = {
        a: sorted({int(c["n_tokens"]) for c in cells if c.get("arm_id") == a}) for a in arms
    }

    if abort_at is None:
        abort_at = {
            "n_probes_completed": len(probes),
            "n_cells_completed": len(cells),
            "active_arms_at_abort": ckpt.get("active_arms") or arms,
            "highest_n_completed": max(executed) if executed else None,
            "source": "seal_cap4.reconstruct",
        }
        if probes:
            last = probes[-1]
            abort_at["last_completed_probe"] = {
                "arm_id": last.get("arm_id"),
                "n_tokens": last.get("n_tokens"),
                "repeat_index": last.get("repeat_index"),
                "ended_utc": last.get("ended_utc"),
            }

    ended = _utc_now()
    summary: dict[str, Any] = {
        "kind": "cap4_prefill_curve_to_failure",
        "experiment": "CAP-4",
        "session_id": session_id,
        "status": "aborted",
        "ended_utc": ended,
        "arms": arms,
        "session_design": "interleaved",
        "arm_order": list(plan.get("arm_order") or arms),
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "cells": cells,
        "arm_dead": ckpt.get("arm_dead") or {},
        "n_probes": len(probes),
        "rungs_executed": executed,
        "rungs_completed_per_arm": rungs_completed_per_arm,
        "predictions_registered_utc": pred.get("registered_utc"),
        "available_mb_start": run_environment["available_mb_start"],
        "available_mb_end": run_environment["available_mb_end"],
        "prompt_render_sha256": run_environment["prompt_render_sha256"],
        "run_environment": run_environment,
        "abort_reason": abort_reason,
        "abort_verbatim": abort_verbatim,
        "abort_at": abort_at,
        "reconstructed": True,
        "reconstruction_note": (
            "summary.json rebuilt from session artifacts after Force-kill / "
            "Stop-Process -Force skipped worker finally (no summary write). "
            f"Executed on {exec_id}; sealed on {seal_id}."
        ),
        "execution_platform_id": exec_id,
        "seal_platform_id": seal_id,
        "cross_host_reconstruct": cross_host,
    }

    analysis = analyze_session(summary, pred)
    analysis["stop_classification"] = {
        "class": "force_killed_no_summary",
        "note": (
            "Worker was killed (Stop-Process -Force / equivalent); finally did not run, "
            "so summary.json was absent. Completed cells are retained as aborted data. "
            "Not an allocation ceiling and not a quiescence-refusal stop."
        ),
        "abort_reason": abort_reason,
        "abort_verbatim": abort_verbatim,
        "abort_at": abort_at,
        "execution_platform_id": exec_id,
        "seal_platform_id": seal_id,
    }
    summary["analysis"] = analysis

    plan["status"] = "aborted"
    plan["ended_utc"] = ended
    plan["abort_reason"] = abort_reason
    plan["abort_verbatim"] = abort_verbatim
    plan["abort_at"] = abort_at
    plan["run_environment"] = run_environment
    plan["prompt_render_sha256"] = run_environment["prompt_render_sha256"]
    plan["rungs_executed"] = executed
    plan["rungs_completed_per_arm"] = rungs_completed_per_arm
    plan["platform_id"] = exec_id
    plan["execution_platform_id"] = exec_id
    plan["seal_platform_id"] = seal_id
    plan["cross_host_reconstruct"] = cross_host
    _write_json(session_dir / "plan.json", plan)
    _write_json(session_dir / "summary.json", summary)
    _write_json(session_dir / "analysis.json", analysis)
    report = _render_report(summary, analysis, pred)
    # Session-local report only - never overwrite Platform A derived/cap4/CAP4_RESULTS.md.
    (session_dir / "CAP4_RESULTS.md").write_text(report, encoding="utf-8")
    print(report.encode("ascii", errors="replace").decode("ascii"))
    return summary


def seal_session(
    *,
    session_id: str,
    capture_host: bool | None = None,
) -> Path:
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

    exec_id = (
        summary.get("execution_platform_id")
        or plan.get("execution_platform_id")
        or plan.get("platform_id")
        or env.get("execution_platform_id")
        or env.get("platform_id")
    )
    seal_id = _seal_host_platform_id()
    cross_host = bool(
        summary.get("cross_host_reconstruct")
        or plan.get("cross_host_reconstruct")
        or env.get("cross_host_reconstruct")
        or (exec_id and exec_id != seal_id)
    )
    do_capture = (not cross_host) if capture_host is None else capture_host
    if cross_host and do_capture:
        raise SystemExit(
            "REFUSED -- cross-host CAP-4 seal must not capture_host from the sealing machine "
            f"(execution={exec_id!r} seal_host={seal_id!r})"
        )

    merged = merge_run_environment(env, capture_host=do_capture)
    # Preserve cross-host identity even if merge omitted it.
    if exec_id:
        merged["platform_id"] = exec_id
        merged["execution_platform_id"] = exec_id
    merged["seal_platform_id"] = seal_id
    merged["cross_host_reconstruct"] = cross_host
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
            "execution_platform_id": exec_id,
            "seal_platform_id": seal_id,
            "cross_host_reconstruct": cross_host,
            "note": (
                "ABORTED seal - completed cells are data; status is not complete. "
                "Do not treat this as a finished curve-to-failure."
                + (
                    f" Executed on {exec_id}; sealed on {seal_id}."
                    if cross_host
                    else ""
                )
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
        "execution_platform_id": exec_id,
        "seal_platform_id": seal_id,
        "cross_host_reconstruct": cross_host,
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
    sealed_summary["status"] = status  # never promote aborted -> complete
    sealed_summary["run_environment"] = merged
    sealed_summary["seal_style"] = "derived_diagnostic"
    sealed_summary["sealed_utc"] = sealed_utc
    sealed_summary["execution_platform_id"] = exec_id
    sealed_summary["seal_platform_id"] = seal_id
    sealed_summary["cross_host_reconstruct"] = cross_host
    if status == "aborted":
        sealed_summary["seal_note"] = (
            "Sealed as aborted. Completed cells retained; not a complete curve-to-failure."
            + (
                f" Executed on {exec_id}; sealed on {seal_id}."
                if cross_host
                else ""
            )
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
        "execution_platform_id": exec_id,
        "seal_platform_id": seal_id,
        "cross_host_reconstruct": cross_host,
        "note": (
            "Advisory marker for derived_diagnostic seals. Not "
            "seam.rawstore.verify_sealed; raw/ was not written. Do not mutate "
            "this directory after seal."
            + (" STATUS=aborted - not a complete run." if status == "aborted" else "")
            + (
                f" CROSS-HOST: executed on {exec_id}, sealed on {seal_id}; "
                "platform identity from session plan/probes, not seal-host capture."
                if cross_host
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
                "execution_platform_id": exec_id,
                "seal_platform_id": seal_id,
                "cross_host_reconstruct": cross_host,
            },
            indent=2,
        )
    )
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session-id", required=True)
    p.add_argument(
        "--reconstruct",
        action="store_true",
        help=(
            "Rebuild summary.json from cells/probes/plan (Force-kill gap), then seal. "
            "Platform identity from plan/probes; cross-host does not capture seal-host INF-5."
        ),
    )
    p.add_argument(
        "--abort-reason",
        default="Stop-Process -Force",
        help="abort_reason recorded on reconstructed summary (default: Stop-Process -Force)",
    )
    p.add_argument(
        "--abort-verbatim",
        default=(
            "Worker killed with Stop-Process -Force; finally skipped; "
            "no summary.json (same gap as 2b3316b6)."
        ),
        help="abort_verbatim recorded on reconstructed summary",
    )
    p.add_argument(
        "--execution-platform-id",
        default=None,
        help="Override inferred execution platform_id (evo-t2 / aipc-c1)",
    )
    args = p.parse_args(argv)

    if args.reconstruct:
        session_dir = SESSION_BASE / args.session_id
        reconstruct_aborted_summary(
            session_dir=session_dir,
            abort_reason=str(args.abort_reason),
            abort_verbatim=str(args.abort_verbatim),
            execution_platform_id=args.execution_platform_id,
        )

    seal_session(session_id=args.session_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
