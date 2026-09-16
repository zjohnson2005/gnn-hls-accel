"""Budget-laddered OA-01 trajectory launcher.

Only routing is configured: the selected model and transparent proxy base URL.
Prompts, sampling parameters, tool behavior, and native stop conditions come
from the pinned mini-SWE-agent SWE-bench configuration unchanged. OA-01's
50-turn/60-minute observation windows are enforced by this parent process and
recorded as censoring rather than agent failure.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Sequence

from apu_characterization.oa01 import PROTOCOL_VERSION, SUBJECT_COMMIT
from apu_characterization.oa01.audit import audit_trajectory
from apu_characterization.oa01.bundle import save_bundle
from apu_characterization.oa01.derive import (
    derive_turn_records,
    load_api_records,
    load_exec_spans,
    write_jsonl,
)
from apu_characterization.oa01.manifest import validate_manifest
from apu_characterization.oa01.proxy import OA01ProxyServer
from apu_characterization.oa01.schema import ApiBoundaryRecord, TrajectoryRecord

ROOT = Path(__file__).resolve().parents[2]
OA_ROOT = ROOT / "apu_characterization" / "oa01"
DEFAULT_OUT = ROOT / "apu_characterization" / "out" / "oa01"
PROTOCOL_PATH = OA_ROOT / "protocol_oa01_v1.json"
MANIFEST_PATH = OA_ROOT / "task_manifest.json"

PHASES: dict[str, dict[str, Any]] = {
    "S": {
        "task_orders": [0],
        "model": "openai/gpt-4o-mini",
        "turn_cap": 15,
        "wall_cap_s": 3600,
        "phase_budget_usd": 1.0,
    },
    "P": {
        "task_orders": [0, 1, 2],
        "model": "openai/gpt-4.1",
        "turn_cap": 50,
        "wall_cap_s": 3600,
        "phase_budget_usd": 5.0,
    },
    "M": {
        "task_orders": list(range(3, 15)),
        "model": "openai/gpt-4.1",
        "turn_cap": 50,
        "wall_cap_s": 3600,
        "phase_budget_usd": 50.0,
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(value, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _subject_commit() -> str | None:
    try:
        import importlib.metadata

        direct_url = importlib.metadata.distribution("mini-swe-agent").read_text(
            "direct_url.json"
        )
        if direct_url:
            value = json.loads(direct_url)
            return (
                value.get("vcs_info", {}).get("commit_id")
                or value.get("archive_info", {}).get("hash")
            )
    except Exception:
        return None
    return None


def preflight(*, out_root: Path, phase: str, live: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    protocol = _load_json(PROTOCOL_PATH)
    if protocol.get("protocol_version") != PROTOCOL_VERSION:
        raise RuntimeError("OA-01 protocol version mismatch")
    if protocol.get("status") != "pre_registered_locked":
        raise RuntimeError("OA-01 protocol is not pre_registered_locked")
    manifest = _load_json(MANIFEST_PATH)
    errors = validate_manifest(manifest)
    if errors:
        raise RuntimeError("invalid OA-01 task manifest: " + "; ".join(errors))
    if protocol.get("task_manifest_sha256") != manifest.get("manifest_sha256"):
        raise RuntimeError("protocol/task manifest hash mismatch")
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase}")
    if live:
        if platform.system() != "Linux":
            raise RuntimeError("OA-01 live collection requires Linux/WSL2")
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set")
        if shutil.which("docker") is None:
            raise RuntimeError("docker executable not found")
        try:
            import minisweagent  # noqa: F401
            import tiktoken  # noqa: F401
        except ImportError as exc:
            raise RuntimeError("OA-01 subject/tiktoken environment is incomplete") from exc
        installed_commit = _subject_commit()
        if installed_commit and SUBJECT_COMMIT not in installed_commit:
            raise RuntimeError(
                f"mini-SWE-agent commit {installed_commit} != pinned {SUBJECT_COMMIT}"
            )
    out_root.mkdir(parents=True, exist_ok=True)
    return protocol, manifest


class ProxyCounter:
    def __init__(self, *, turn_cap: int, cost_anomaly_usd: float = 4.0) -> None:
        self.turn_cap = turn_cap
        self.cost_anomaly_usd = cost_anomaly_usd
        self.lock = threading.Lock()
        self.count = 0
        self.cost = 0.0
        self.cap_reached = threading.Event()
        self.anomaly_reported = False

    def on_record(self, record: ApiBoundaryRecord) -> None:
        with self.lock:
            self.cost += record.cost_usd
            # Provider retry attempts remain raw records and costs, but the
            # external turn cap tracks completed scaffold model calls.
            if record.response_status < 400:
                self.count += 1
            if self.cost > self.cost_anomaly_usd and not self.anomaly_reported:
                self.anomaly_reported = True
                print(
                    f"COST_ANOMALY trajectory={record.trajectory_id} "
                    f"running_cost=${self.cost:.4f}",
                    flush=True,
                )
            if self.count >= self.turn_cap:
                self.cap_reached.set()

    def snapshot(self) -> tuple[int, float]:
        with self.lock:
            return self.count, self.cost


class SnapshotSidecar(threading.Thread):
    """Asynchronously snapshot container/git state after observed exec calls."""

    def __init__(
        self,
        *,
        exec_log: Path,
        snapshot_log: Path,
        real_docker: str,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(name="oa01-snapshot-sidecar", daemon=True)
        self.exec_log = exec_log
        self.snapshot_log = snapshot_log
        self.real_docker = real_docker
        self.stop_event = stop_event
        self.seen: set[str] = set()

    def run(self) -> None:
        while not self.stop_event.wait(0.05):
            self._scan()
        self._scan()

    def _scan(self) -> None:
        if not self.exec_log.is_file():
            return
        try:
            events = _read_jsonl(self.exec_log)
        except (OSError, json.JSONDecodeError):
            return
        for event in events:
            if event.get("event") != "end" or event["span_id"] in self.seen:
                continue
            self.seen.add(event["span_id"])
            container = event.get("container_id")
            if not container:
                continue
            snapshot: dict[str, Any] = {
                "schema_version": "oa01_env_snapshot_v1",
                "trajectory_id": event.get("trajectory_id"),
                "after_span_id": event["span_id"],
                "exec_end_unix_ns": event.get("unix_ns"),
                "snapshot_start_unix_ns": time.time_ns(),
                "container_id": container,
                "observer_mode": "asynchronous_nonblocking_sidecar",
            }
            commands = {
                "image_id": [
                    self.real_docker,
                    "inspect",
                    "--format={{.Image}}",
                    container,
                ],
                "git_commit": [
                    self.real_docker,
                    "exec",
                    "-w",
                    "/testbed",
                    container,
                    "git",
                    "rev-parse",
                    "HEAD",
                ],
                "git_status": [
                    self.real_docker,
                    "exec",
                    "-w",
                    "/testbed",
                    container,
                    "git",
                    "status",
                    "--porcelain=v1",
                ],
                "git_diff": [
                    self.real_docker,
                    "exec",
                    "-w",
                    "/testbed",
                    container,
                    "git",
                    "diff",
                    "--binary",
                ],
            }
            for key, command in commands.items():
                try:
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        timeout=30,
                        check=False,
                    )
                    raw = result.stdout
                    truncated = len(raw) > 2_000_000
                    snapshot[key] = raw[:2_000_000].decode("utf-8", errors="replace")
                    snapshot[f"{key}_returncode"] = result.returncode
                    snapshot[f"{key}_truncated"] = truncated
                except Exception as exc:
                    snapshot[key] = None
                    snapshot[f"{key}_error"] = f"{type(exc).__name__}: {exc}"
            snapshot["snapshot_end_unix_ns"] = time.time_ns()
            _append_jsonl(self.snapshot_log, snapshot)


def _write_wrapper(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '#!/usr/bin/env bash\nexec "$OA01_PYTHON" -m '
        'apu_characterization.oa01.exec_wrapper "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    path.chmod(0o755)
    return path


def _subject_command(
    *,
    task_id: str,
    model: str,
    proxy_base_url: str,
    subject_out: Path,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "minisweagent.run.benchmarks.swebench",
        "--subset",
        "lite",
        "--split",
        "test",
        "--filter",
        f"^{re.escape(task_id)}$",
        "--output",
        str(subject_out),
        "--workers",
        "1",
        "--model",
        model,
        "--config",
        "swebench.yaml",
        "--config",
        f"model.model_kwargs.api_base={proxy_base_url}",
    ]


def _interrupt(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    try:
        process.send_signal(signal.SIGINT)
        process.wait(timeout=30)
        return
    except (subprocess.TimeoutExpired, OSError):
        pass
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _find_subject_trajectory(subject_out: Path, task_id: str) -> Path | None:
    expected = subject_out / task_id / f"{task_id}.traj.json"
    if expected.is_file():
        return expected
    matches = list(subject_out.rglob("*.traj.json"))
    return matches[0] if len(matches) == 1 else None


def _exit_status(subject_trajectory: Path | None) -> tuple[str, str, dict[str, Any] | None]:
    if subject_trajectory is None:
        return "missing_subject_trajectory", "", None
    value = _load_json(subject_trajectory)
    info = value.get("info") or {}
    return str(info.get("exit_status", "")), str(info.get("submission", "")), value


def _bundle_value(
    *,
    trajectory_id: str,
    task_id: str,
    run_meta: dict[str, Any],
    api_records: Sequence[ApiBoundaryRecord],
    exec_events_path: Path,
    snapshots_path: Path,
    tool_io_dir: Path,
    subject_value: dict[str, Any] | None,
) -> dict[str, Any]:
    tool_io = []
    if tool_io_dir.is_dir():
        for path in sorted(tool_io_dir.glob("*.bin")):
            raw = path.read_bytes()
            tool_io.append(
                {
                    "name": path.name,
                    "size": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "body_b64": base64.b64encode(raw).decode("ascii"),
                }
            )
    return {
        "schema_version": "oa01_replay_bundle_v1",
        "trajectory_id": trajectory_id,
        "task_id": task_id,
        "append_only": True,
        "run": run_meta,
        "api_boundary_records": [record.to_dict() for record in api_records],
        "tool_exec_events": _read_jsonl(exec_events_path),
        "tool_io_verbatim": tool_io,
        "env_snapshots": _read_jsonl(snapshots_path),
        "subject_trajectory": subject_value,
        "sampling_note": (
            "Sampling parameters are exactly those present in each archived request; "
            "OA-01 does not override provider/scaffold defaults."
        ),
    }


def run_one(
    *,
    out_root: Path,
    phase: str,
    task: dict[str, Any],
    smoke_attempt: int,
    live: bool,
) -> TrajectoryRecord | None:
    config = PHASES[phase]
    task_id = str(task["instance_id"])
    suffix = f"-attempt{smoke_attempt:02d}" if phase == "S" else ""
    trajectory_id = f"OA01-{phase}-{int(task['order']):02d}-{task_id}{suffix}"
    run_dir = out_root / "runs" / trajectory_id
    if run_dir.exists():
        raise FileExistsError(
            f"{run_dir} already exists; OA-01 never re-rolls launched trajectories"
        )
    if not live:
        command = _subject_command(
            task_id=task_id,
            model=config["model"],
            proxy_base_url="http://127.0.0.1:<dynamic>/v1",
            subject_out=run_dir / "subject",
        )
        print(json.dumps({"trajectory_id": trajectory_id, "command": command}, indent=2))
        return None

    run_dir.mkdir(parents=True)
    launch_record = {
        "schema_version": "oa01_launch_v1",
        "record_type": "trajectory_launched",
        "launched_unix_ns": time.time_ns(),
        "trajectory_id": trajectory_id,
        "task_id": task_id,
        "task_order": int(task["order"]),
        "phase": phase,
        "model_id": config["model"],
        "turn_cap": config["turn_cap"],
        "wall_cap_s": config["wall_cap_s"],
    }
    (run_dir / "launch.json").write_text(
        json.dumps(launch_record, indent=2) + "\n", encoding="utf-8"
    )
    _append_jsonl(
        out_root / "budget_ledger.jsonl",
        {
            "schema_version": "oa01_budget_ledger_v1",
            **launch_record,
        },
    )
    proxy_log = run_dir / "raw" / "api_boundary.jsonl"
    exec_log = run_dir / "raw" / "exec_events.jsonl"
    snapshots_log = run_dir / "raw" / "env_snapshots.jsonl"
    tool_io_dir = run_dir / "raw" / "tool_io"
    subject_out = run_dir / "subject"
    runtime = run_dir / "runtime"
    wrapper = _write_wrapper(runtime / "docker-observer")
    real_docker = shutil.which("docker")
    assert real_docker is not None
    counter = ProxyCounter(turn_cap=int(config["turn_cap"]))
    proxy = OA01ProxyServer(
        ("127.0.0.1", 0),
        upstream_base="https://api.openai.com",
        log_path=proxy_log,
        trajectory_id=trajectory_id,
        on_record=counter.on_record,
    )
    proxy_port = int(proxy.server_address[1])
    proxy_thread = threading.Thread(
        target=proxy.serve_forever,
        kwargs={"poll_interval": 0.05},
        name=f"oa01-proxy-{trajectory_id}",
        daemon=True,
    )
    proxy_thread.start()

    command = _subject_command(
        task_id=task_id,
        model=str(config["model"]),
        proxy_base_url=f"http://127.0.0.1:{proxy_port}/v1",
        subject_out=subject_out,
    )
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT),
            "MSWEA_DOCKER_EXECUTABLE": str(wrapper),
            "OA01_REAL_DOCKER": real_docker,
            "OA01_EXEC_LOG": str(exec_log),
            "OA01_TOOL_IO_DIR": str(tool_io_dir),
            "OA01_TRAJECTORY_ID": trajectory_id,
            "OA01_PYTHON": sys.executable,
        }
    )
    stop_sidecar = threading.Event()
    sidecar = SnapshotSidecar(
        exec_log=exec_log,
        snapshot_log=snapshots_log,
        real_docker=real_docker,
        stop_event=stop_sidecar,
    )
    sidecar.start()

    start_ns = time.time_ns()
    censored = False
    censor_reason: str | None = None
    with (run_dir / "subject_stdout.log").open("wb") as output:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=False,
        )
        while process.poll() is None:
            elapsed_s = (time.time_ns() - start_ns) / 1_000_000_000.0
            if counter.cap_reached.is_set():
                censored = True
                censor_reason = "turn_cap"
                _interrupt(process)
                break
            if elapsed_s >= float(config["wall_cap_s"]):
                censored = True
                censor_reason = "wall_clock_cap"
                _interrupt(process)
                break
            time.sleep(0.05)
        returncode = process.wait()
    end_ns = time.time_ns()

    proxy.shutdown()
    proxy.server_close()
    proxy_thread.join(timeout=5)
    stop_sidecar.set()
    sidecar.join(timeout=35)
    calls, cost = counter.snapshot()
    subject_path = _find_subject_trajectory(subject_out, task_id)
    exit_status, submission, subject_value = _exit_status(subject_path)
    flags: list[str] = []
    if cost > 4.0:
        flags.append("cost_anomaly")
    if returncode != 0 and not censored:
        flags.append("subject_process_nonzero")
    if subject_path is None:
        flags.append("missing_subject_trajectory")
    if any(not r.stream_requested for r in load_api_records(proxy_log)):
        flags.append("nonstreaming_subject_default")
    outcome = (
        "censored"
        if censored
        else "submitted"
        if bool(submission)
        else "agent_failure"
    )
    run_meta = {
        "schema_version": "oa01_run_v1",
        "protocol_version": PROTOCOL_VERSION,
        "trajectory_id": trajectory_id,
        "task_id": task_id,
        "task_order": int(task["order"]),
        "phase": phase,
        "model_id": config["model"],
        "subject_commit": SUBJECT_COMMIT,
        "subject_command": command,
        "subject_defaults_not_overridden": [
            "system_template",
            "instance_template",
            "sampling_parameters",
            "step_limit",
            "cost_limit",
            "format_error_limit",
            "environment_timeout",
        ],
        "routing_overrides_only": ["model_name", "model.model_kwargs.api_base"],
        "trajectory_start_unix_ns": start_ns,
        "trajectory_end_unix_ns": end_ns,
        "subject_returncode": returncode,
        "exit_status": exit_status,
        "censored": censored,
        "censor_reason": censor_reason,
        "turns_observed": calls,
        "cost_usd": cost,
        "flags": flags,
    }
    (run_dir / "run.json").write_text(
        json.dumps(run_meta, indent=2) + "\n", encoding="utf-8"
    )

    api_records = load_api_records(proxy_log)
    exec_spans = load_exec_spans(exec_log)
    turns = derive_turn_records(
        api_records=api_records,
        exec_spans=exec_spans,
        task_id=task_id,
        trajectory_start_unix_ns=start_ns,
        trajectory_end_unix_ns=end_ns,
    )
    write_jsonl(run_dir / "derived" / "turn_records.jsonl", (t.to_dict() for t in turns))
    write_jsonl(run_dir / "derived" / "exec_spans.jsonl", (s.to_dict() for s in exec_spans))
    bundle_path = run_dir / "replay" / f"{trajectory_id}.oa01bundle"
    save_bundle(
        _bundle_value(
            trajectory_id=trajectory_id,
            task_id=task_id,
            run_meta=run_meta,
            api_records=api_records,
            exec_events_path=exec_log,
            snapshots_path=snapshots_log,
            tool_io_dir=tool_io_dir,
            subject_value=subject_value,
        ),
        bundle_path,
    )
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
    if not audit["pass"]:
        flags.extend(f"audit:{flag}" for flag in audit["flags"])
    record = TrajectoryRecord(
        trajectory_id=trajectory_id,
        task_id=task_id,
        phase=phase,
        model_id=str(config["model"]),
        outcome=outcome,
        success=None,
        censored=censored,
        censor_reason=censor_reason,
        turns=calls,
        wall_clock_ms=(end_ns - start_ns) / 1_000_000.0,
        cost_usd=cost,
        cost_anomaly=cost > 4.0,
        exit_status=exit_status,
        subject_trajectory_path=str(subject_path) if subject_path else None,
        replay_bundle_path=str(bundle_path),
        flags=flags,
    )
    (run_dir / "trajectory_record.json").write_text(
        json.dumps(record.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return record


def _ledger_totals(rows: Sequence[dict[str, Any]], *, phase: str | None = None) -> float:
    return sum(
        float(row.get("cost_usd", 0.0))
        for row in rows
        if phase is None or row.get("phase") == phase
    )


def run_phase(
    *,
    out_root: Path,
    phase: str,
    live: bool,
    smoke_attempt: int,
) -> list[TrajectoryRecord]:
    _, manifest = preflight(out_root=out_root, phase=phase, live=live)
    ledger_path = out_root / "budget_ledger.jsonl"
    ledger = _read_jsonl(ledger_path)
    total_spend = _ledger_totals(ledger)
    phase_spend = _ledger_totals(ledger, phase=phase)
    if live and total_spend >= 50.0:
        raise RuntimeError("OA-01 $50 hard budget reached; no new trajectories launched")
    if live and phase_spend >= float(PHASES[phase]["phase_budget_usd"]):
        raise RuntimeError(f"OA-01 phase {phase} budget reached")
    if phase == "P" and live:
        smoke = [
            row
            for row in ledger
            if row.get("phase") == "S"
            and row.get("record_type") == "trajectory_complete"
        ]
        if not smoke:
            raise RuntimeError("Phase P requires a retained smoke trajectory")
        latest_smoke = smoke[-1]
        smoke_run = out_root / "runs" / latest_smoke["trajectory_id"]
        smoke_audit = _load_json(smoke_run / "audit.json")
        if not smoke_audit.get("pass"):
            raise RuntimeError(
                "latest smoke audit did not pass; fix instrumentation and launch "
                "a new explicitly numbered smoke attempt"
            )
        if not latest_smoke.get("subject_trajectory_path"):
            raise RuntimeError("latest smoke lacks the subject trajectory archive")
    if phase == "M" and live:
        pilot = [
            row
            for row in ledger
            if row.get("phase") == "P" and row.get("record_type") == "trajectory_complete"
        ]
        if len(pilot) != 3:
            raise RuntimeError("Phase M requires exactly three retained pilot trajectories")
        mean_pilot = sum(float(row["cost_usd"]) for row in pilot) / 3.0
        if mean_pilot > 3.0:
            raise RuntimeError(
                f"pilot mean ${mean_pilot:.4f} exceeds 2x upper estimate ($3.00); re-project first"
            )

    tasks = {int(task["order"]): task for task in manifest["tasks"]}
    completed: list[TrajectoryRecord] = []
    for order in PHASES[phase]["task_orders"]:
        ledger = _read_jsonl(ledger_path)
        if _ledger_totals(ledger) >= 50.0:
            print("OA01_BUDGET_STOP total spend reached $50; no new launch", flush=True)
            break
        if _ledger_totals(ledger, phase=phase) >= float(
            PHASES[phase]["phase_budget_usd"]
        ):
            print(f"OA01_PHASE_BUDGET_STOP phase={phase}", flush=True)
            break
        if phase != "S" and any(
            row.get("task_order") == order
            and row.get("phase") in {"P", "M"}
            and row.get("record_type") in {
                "trajectory_launched",
                "trajectory_complete",
            }
            for row in ledger
        ):
            raise RuntimeError(f"task order {order} was already launched; no re-rolls")
        record = run_one(
            out_root=out_root,
            phase=phase,
            task=tasks[order],
            smoke_attempt=smoke_attempt,
            live=live,
        )
        if record is None:
            continue
        completed.append(record)
        # Pace launches against provider TPM; does not alter in-trajectory subject
        # behavior. Override with OA01_INTER_TASK_SLEEP_S=0 to disable.
        if live and phase in {"P", "M"} and order != PHASES[phase]["task_orders"][-1]:
            sleep_s = float(os.environ.get("OA01_INTER_TASK_SLEEP_S", "60"))
            if sleep_s > 0:
                print(f"OA01_INTER_TASK_SLEEP_S={sleep_s}", flush=True)
                time.sleep(sleep_s)
        row = {
            "schema_version": "oa01_budget_ledger_v1",
            "record_type": "trajectory_complete",
            "completed_unix_ns": time.time_ns(),
            "task_order": order,
            **record.to_dict(),
        }
        _append_jsonl(ledger_path, row)
        running_total = _ledger_totals(_read_jsonl(ledger_path))
        print(
            f"OA01_LEDGER trajectory={record.trajectory_id} "
            f"trajectory_cost=${record.cost_usd:.4f} running_total=${running_total:.4f}",
            flush=True,
        )
    return completed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=sorted(PHASES), required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--smoke-attempt", type=int, default=1)
    args = parser.parse_args(argv)
    records = run_phase(
        out_root=args.out,
        phase=args.phase,
        live=args.live,
        smoke_attempt=args.smoke_attempt,
    )
    print(json.dumps([record.to_dict() for record in records], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

