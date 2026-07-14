"""Strictly serial, resumable runner for MCP-01 measurements."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import socket
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .contracts import CellCoordinates, CellPlan
from .run_context import reset_run_tls_fixture, set_run_tls_fixture
from .tls_fixture import TlsFixture

DEFAULT_RUN_ROOT = Path("apu_characterization/out/mcp_tax/runs")
COMPLETE_MARKER = "COMPLETE.json"
CHECKPOINT_FILE = "checkpoint.json"

ExecutionCallback = Callable[..., Mapping[str, Any] | None]


def run_directory(
    root: Path, coordinates: CellCoordinates, seed: int
) -> Path:
    return root / coordinates.transport / coordinates.cell_id / str(seed)


def is_complete(run_dir: Path) -> bool:
    marker = run_dir / COMPLETE_MARKER
    if not marker.is_file():
        return False
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not data.get("complete") or data.get("layout_version") != 1:
        return False
    files = data.get("files")
    if not isinstance(files, Mapping) or not files:
        return False
    for relative, expected_hash in files.items():
        path = run_dir / str(relative)
        if not path.is_file() or _sha256_file(path) != expected_hash:
            return False
    return True


class HostLock(AbstractContextManager["HostLock"]):
    """Cross-process exclusive lock; held across every measurement."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: Any = None

    def __enter__(self) -> "HostLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a+b")
        self._file.seek(0)
        try:
            import fcntl

            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            import msvcrt

            try:
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                self._file.close()
                self._file = None
                raise RuntimeError(f"MCP-tax host lock is already held: {self.path}") from exc
        except BlockingIOError as exc:
            self._file.close()
            self._file = None
            raise RuntimeError(f"MCP-tax host lock is already held: {self.path}") from exc
        self._file.seek(0)
        self._file.truncate()
        self._file.write(
            f"pid={os.getpid()} host={socket.gethostname()}\n".encode("utf-8")
        )
        self._file.flush()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        if self._file is None:
            return
        try:
            try:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            except ImportError:
                import msvcrt

                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self._file.close()
            self._file = None


@dataclass
class RunOutcome:
    run_dir: Path
    status: str
    cell_id: str
    seed: int


class McpTaxRunner:
    """Execute one callback at a time and checkpoint after every seed."""

    def __init__(
        self,
        *,
        run_root: Path = DEFAULT_RUN_ROOT,
        execute: ExecutionCallback,
        lock_path: Path | None = None,
    ) -> None:
        self.run_root = Path(run_root)
        self.execute = execute
        self.lock_path = lock_path or self.run_root.parent / ".measurement.lock"
        self._lock_held = False

    def run(
        self,
        plans: Iterable[CellPlan],
        *,
        resume: bool = True,
    ) -> list[RunOutcome]:
        plans = list(plans)
        self.run_root.mkdir(parents=True, exist_ok=True)
        outcomes: list[RunOutcome] = []
        run_tls_id = hashlib.sha256(self.run_root.as_posix().encode("utf-8")).hexdigest()[:16]
        with TlsFixture.create(matrix_id=run_tls_id) as tls_fixture:
            tls_token = set_run_tls_fixture(tls_fixture)
            try:
                with HostLock(self.lock_path):
                    self._lock_held = True
                    try:
                        for plan in plans:
                            outcomes.append(self._run_one_unlocked(plan, resume=resume))
                            self._write_checkpoint(plans, outcomes)
                    finally:
                        self._lock_held = False
            finally:
                reset_run_tls_fixture(tls_token)
        return outcomes

    def run_one(self, plan: CellPlan, *, resume: bool = True) -> RunOutcome:
        """Run one plan while still honoring the global host lock."""
        if self._lock_held:
            return self._run_one_unlocked(plan, resume=resume)
        run_tls_id = hashlib.sha256(self.run_root.as_posix().encode("utf-8")).hexdigest()[
            :16
        ]
        with TlsFixture.create(matrix_id=run_tls_id) as tls_fixture:
            tls_token = set_run_tls_fixture(tls_fixture)
            try:
                with HostLock(self.lock_path):
                    self._lock_held = True
                    try:
                        return self._run_one_unlocked(plan, resume=resume)
                    finally:
                        self._lock_held = False
            finally:
                reset_run_tls_fixture(tls_token)

    def _run_one_unlocked(self, plan: CellPlan, *, resume: bool) -> RunOutcome:
        run_dir = run_directory(self.run_root, plan.coordinates, plan.seed)
        if is_complete(run_dir):
            if resume:
                return RunOutcome(run_dir, "skipped_complete", plan.coordinates.cell_id, plan.seed)
            raise FileExistsError(f"immutable completed run exists: {run_dir}")
        if (run_dir / COMPLETE_MARKER).exists():
            raise RuntimeError(f"completion marker or completed files are corrupt: {run_dir}")
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "client").mkdir(exist_ok=True)
        (run_dir / "server").mkdir(exist_ok=True)
        plan_json = plan.as_dict()
        plan_json["request_hashes"] = plan.request_hashes()
        _atomic_json(run_dir / "plan.json", plan_json)

        result = self._invoke(plan, run_dir)
        if result is not None:
            for role in ("client", "server"):
                endpoint = result.get(role)
                if isinstance(endpoint, Mapping):
                    _atomic_json(run_dir / role / "result.json", endpoint)
            manifest = result.get("manifest")
            if isinstance(manifest, Mapping):
                _atomic_json(run_dir / "manifest.json", manifest)
        self._assert_required_outputs(run_dir)
        self._complete(run_dir, plan)
        return RunOutcome(run_dir, "completed", plan.coordinates.cell_id, plan.seed)

    def _invoke(self, plan: CellPlan, run_dir: Path) -> Mapping[str, Any] | None:
        parameters = inspect.signature(self.execute).parameters
        if len(parameters) == 1:
            return self.execute(
                {
                    "plan": plan,
                    "run_dir": run_dir,
                    "client_dir": run_dir / "client",
                    "server_dir": run_dir / "server",
                }
            )
        return self.execute(plan, run_dir)

    def _assert_required_outputs(self, run_dir: Path) -> None:
        required = (
            run_dir / "manifest.json",
            run_dir / "client" / "result.json",
            run_dir / "server" / "result.json",
        )
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(f"execution callback omitted required outputs: {missing}")

    def _complete(self, run_dir: Path, plan: CellPlan) -> None:
        files = sorted(
            path
            for path in run_dir.rglob("*")
            if path.is_file() and path.name != COMPLETE_MARKER
        )
        marker = {
            "complete": True,
            "layout_version": 1,
            "protocol_version": plan.protocol_version,
            "cell_id": plan.coordinates.cell_id,
            "seed": plan.seed,
            "cell_plan_sha256": plan.digest(),
            "files": {
                path.relative_to(run_dir).as_posix(): _sha256_file(path)
                for path in files
            },
        }
        payload = json.dumps(marker, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        try:
            descriptor = os.open(
                run_dir / COMPLETE_MARKER,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o444,
            )
        except FileExistsError as exc:
            raise FileExistsError(f"completion marker is immutable: {run_dir}") from exc
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(payload)

    def _write_checkpoint(
        self, plans: list[CellPlan], outcomes: list[RunOutcome]
    ) -> None:
        completed = [
            {
                "cell_id": outcome.cell_id,
                "seed": outcome.seed,
                "status": outcome.status,
            }
            for outcome in outcomes
        ]
        _atomic_json(
            self.run_root.parent / CHECKPOINT_FILE,
            {
                "protocol_version": plans[0].protocol_version if plans else None,
                "planned_runs": len(plans),
                "visited_runs": len(outcomes),
                "runs": completed,
            },
        )


def _atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
