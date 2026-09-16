"""Native bare-metal Linux qualification for CAP-01 publication runs."""

from __future__ import annotations

import contextlib
import hashlib
import os
import platform
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


class HostQualificationError(RuntimeError):
    pass


class HostLockError(HostQualificationError):
    pass


@dataclass(frozen=True)
class HostObservation:
    system: str
    virtualization: str
    tracked_git_clean: bool
    lock_acquired: bool
    load_1m: float
    cpu_count: int
    answer_space_sha256: str


@dataclass(frozen=True)
class HostQualification:
    passed: bool
    errors: tuple[str, ...]
    observation: HostObservation
    max_load_per_cpu: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "pass": self.passed,
            "errors": list(self.errors),
            "observation": asdict(self.observation),
            "max_load_per_cpu": self.max_load_per_cpu,
        }


def answer_space_hash(paths: Sequence[str | os.PathLike[str]]) -> str:
    """Hash names and bytes in a stable order to bind host inputs to the lock."""
    digest = hashlib.sha256()
    normalized = [Path(path) for path in paths]
    if not normalized:
        raise ValueError("answer space must contain at least one file")
    common = Path(os.path.commonpath([str(path.absolute()) for path in normalized]))
    if len(normalized) == 1 or common.is_file():
        common = common.parent
    named = sorted(
        ((path, path.absolute().relative_to(common).as_posix()) for path in normalized),
        key=lambda item: item[1],
    )
    for path, relative_name in named:
        if not path.is_file():
            raise FileNotFoundError(path)
        name = relative_name.encode("utf-8")
        content = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def evaluate_host_qualification(
    observation: HostObservation | Mapping[str, Any],
    *,
    expected_answer_space_sha256: str,
    max_load_per_cpu: float = 0.10,
) -> HostQualification:
    """Pure policy evaluation used by both preflight and fixture tests."""
    item = _observation(observation)
    errors: list[str] = []
    if item.system != "Linux":
        errors.append(f"host system is {item.system}, not native Linux")
    if item.virtualization != "none":
        errors.append(
            "systemd-detect-virt must report none; "
            f"reported {item.virtualization or '<unavailable>'}"
        )
    if not item.tracked_git_clean:
        errors.append("tracked git files are dirty")
    if not item.lock_acquired:
        errors.append("CAP-01 exclusive host lock is not held")
    if item.cpu_count <= 0:
        errors.append("host CPU count is not positive")
    elif item.load_1m / item.cpu_count > max_load_per_cpu:
        errors.append(
            f"1-minute load per CPU {item.load_1m / item.cpu_count:.3f} "
            f"exceeds hygiene limit {max_load_per_cpu:.3f}"
        )
    if not _is_sha256(expected_answer_space_sha256):
        errors.append("expected answer-space hash is not a sha256 digest")
    if item.answer_space_sha256 != expected_answer_space_sha256:
        errors.append("answer-space hash does not match the frozen protocol lock")
    return HostQualification(
        passed=not errors,
        errors=tuple(errors),
        observation=item,
        max_load_per_cpu=max_load_per_cpu,
    )


def detect_virtualization(
    *,
    command: Sequence[str] = ("systemd-detect-virt",),
    timeout_s: float = 2.0,
) -> str:
    """Return the detector's token. Bare metal is exactly ``none``."""
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    value = completed.stdout.strip()
    # systemd-detect-virt normally exits 1 when it prints "none".
    if value == "none" and completed.returncode in (0, 1):
        return "none"
    return value or "unavailable"


def tracked_git_is_clean(repo_root: str | os.PathLike[str]) -> bool:
    """Ignore untracked output, but reject modifications to tracked files."""
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=Path(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and not completed.stdout.strip()


def observe_host(
    *,
    repo_root: str | os.PathLike[str],
    answer_space_paths: Sequence[str | os.PathLike[str]],
    lock_acquired: bool,
) -> HostObservation:
    load_1m = os.getloadavg()[0] if hasattr(os, "getloadavg") else float("inf")
    return HostObservation(
        system=platform.system(),
        virtualization=detect_virtualization(),
        tracked_git_clean=tracked_git_is_clean(repo_root),
        lock_acquired=lock_acquired,
        load_1m=load_1m,
        cpu_count=os.cpu_count() or 0,
        answer_space_sha256=answer_space_hash(answer_space_paths),
    )


def qualify_host(
    *,
    repo_root: str | os.PathLike[str],
    answer_space_paths: Sequence[str | os.PathLike[str]],
    expected_answer_space_sha256: str,
    lock_acquired: bool,
    max_load_per_cpu: float = 0.10,
) -> HostQualification:
    return evaluate_host_qualification(
        observe_host(
            repo_root=repo_root,
            answer_space_paths=answer_space_paths,
            lock_acquired=lock_acquired,
        ),
        expected_answer_space_sha256=expected_answer_space_sha256,
        max_load_per_cpu=max_load_per_cpu,
    )


@contextlib.contextmanager
def exclusive_host_lock(path: str | os.PathLike[str]) -> Iterator[Path]:
    """Hold a non-blocking advisory lock across the complete measurement."""
    if platform.system() != "Linux":
        raise HostLockError("CAP-01 publication lock requires Linux")
    import fcntl

    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="ascii")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise HostLockError(f"exclusive host lock is already held: {lock_path}") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        yield lock_path
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _observation(value: HostObservation | Mapping[str, Any]) -> HostObservation:
    if isinstance(value, HostObservation):
        return value
    return HostObservation(
        system=str(value.get("system", "")),
        virtualization=str(value.get("virtualization", "unavailable")),
        tracked_git_clean=bool(value.get("tracked_git_clean", False)),
        lock_acquired=bool(value.get("lock_acquired", False)),
        load_1m=float(value.get("load_1m", float("inf"))),
        cpu_count=int(value.get("cpu_count", 0)),
        answer_space_sha256=str(value.get("answer_space_sha256", "")),
    )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
