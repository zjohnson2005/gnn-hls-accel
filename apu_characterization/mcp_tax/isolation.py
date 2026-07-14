"""Linux CPU-topology isolation and publication preflight for MCP-01."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping, Sequence

PreflightMode = Literal["publication", "smoke"]


class IsolationError(RuntimeError):
    pass


def parse_cpu_list(specification: str) -> frozenset[int]:
    """Parse Linux CPU-list syntax such as ``0-3,8,10-11``."""
    cpus: set[int] = set()
    text = specification.strip()
    if not text:
        return frozenset()
    for item in text.split(","):
        item = item.strip()
        if not item:
            raise ValueError(f"invalid CPU list {specification!r}")
        if "-" in item:
            start_text, separator, end_text = item.partition("-")
            if not separator or not start_text.isdigit() or not end_text.isdigit():
                raise ValueError(f"invalid CPU range {item!r}")
            start, end = int(start_text), int(end_text)
            if end < start:
                raise ValueError(f"descending CPU range {item!r}")
            cpus.update(range(start, end + 1))
        elif item.isdigit():
            cpus.add(int(item))
        else:
            raise ValueError(f"invalid CPU number {item!r}")
    return frozenset(cpus)


def format_cpu_list(cpus: Sequence[int] | set[int] | frozenset[int]) -> str:
    ordered = sorted(set(cpus))
    if not ordered:
        raise ValueError("CPU set must not be empty")
    ranges: list[str] = []
    start = previous = ordered[0]
    for cpu in ordered[1:]:
        if cpu == previous + 1:
            previous = cpu
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = cpu
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


@dataclass(frozen=True)
class CpuThread:
    cpu: int
    package_id: int
    core_id: int
    siblings: frozenset[int]
    governor: str | None

    @property
    def physical_core(self) -> tuple[int, int]:
        return self.package_id, self.core_id


@dataclass(frozen=True)
class CpuTopology:
    online_cpus: frozenset[int]
    threads: Mapping[int, CpuThread]

    @property
    def physical_cores(self) -> dict[tuple[int, int], frozenset[int]]:
        groups: dict[tuple[int, int], set[int]] = {}
        for thread in self.threads.values():
            groups.setdefault(thread.physical_core, set()).add(thread.cpu)
        return {key: frozenset(value) for key, value in groups.items()}


@dataclass(frozen=True)
class CorePartitions:
    os_cpus: frozenset[int]
    client_cpus: frozenset[int]
    server_cpus: frozenset[int]

    def roles(self) -> dict[str, frozenset[int]]:
        return {
            "os": self.os_cpus,
            "client": self.client_cpus,
            "server": self.server_cpus,
        }


@dataclass(frozen=True)
class HostEnvironment:
    system: str
    release: str
    is_wsl: bool
    is_virtualized: bool
    virtualization: str | None


@dataclass(frozen=True)
class PreflightResult:
    mode: PreflightMode
    passed: bool
    errors: tuple[str, ...]
    caveats: tuple[str, ...]
    environment: HostEnvironment
    governors: Mapping[int, str | None] = field(default_factory=dict)


def _read_int(path: Path) -> int:
    return int(path.read_text(encoding="ascii").strip())


def discover_topology(
    *,
    sys_root: str | os.PathLike[str] = "/sys",
) -> CpuTopology:
    """Discover online logical CPUs, physical cores, SMT siblings, and governors."""
    cpu_root = Path(sys_root) / "devices" / "system" / "cpu"
    online_path = cpu_root / "online"
    if online_path.exists():
        online = parse_cpu_list(online_path.read_text(encoding="ascii"))
    else:
        online = frozenset(
            int(path.name[3:])
            for path in cpu_root.glob("cpu[0-9]*")
            if path.name[3:].isdigit()
        )
    if not online:
        raise IsolationError("no online CPUs discovered in sysfs")

    threads: dict[int, CpuThread] = {}
    for cpu in sorted(online):
        root = cpu_root / f"cpu{cpu}"
        topology = root / "topology"
        try:
            package_id = _read_int(topology / "physical_package_id")
            core_id = _read_int(topology / "core_id")
            siblings = parse_cpu_list(
                (topology / "thread_siblings_list").read_text(encoding="ascii")
            )
        except (FileNotFoundError, OSError, ValueError) as exc:
            raise IsolationError(f"incomplete topology for CPU {cpu}: {exc}") from exc
        if cpu not in siblings:
            raise IsolationError(f"CPU {cpu} is missing from its SMT sibling list")
        governor_path = root / "cpufreq" / "scaling_governor"
        try:
            governor = governor_path.read_text(encoding="ascii").strip()
        except (FileNotFoundError, OSError):
            governor = None
        threads[cpu] = CpuThread(
            cpu=cpu,
            package_id=package_id,
            core_id=core_id,
            siblings=frozenset(siblings & online),
            governor=governor,
        )
    return CpuTopology(online_cpus=online, threads=threads)


def detect_host_environment(
    *,
    proc_root: str | os.PathLike[str] = "/proc",
    sys_root: str | os.PathLike[str] = "/sys",
) -> HostEnvironment:
    system = platform.system()
    release = platform.release()
    version_parts = [release]
    try:
        version_parts.append(
            (Path(proc_root) / "version").read_text(
                encoding="utf-8", errors="replace"
            )
        )
    except OSError:
        pass
    is_wsl = any(
        marker in " ".join(version_parts).lower()
        for marker in ("microsoft", "wsl")
    )

    virtualization: str | None = None
    detector = shutil.which("systemd-detect-virt")
    if detector:
        try:
            result = subprocess.run(
                [detector],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            detected = result.stdout.strip()
            if result.returncode == 0 and detected and detected != "none":
                virtualization = detected
        except (OSError, subprocess.TimeoutExpired):
            pass
    if virtualization is None:
        dmi_files = (
            Path(sys_root) / "class" / "dmi" / "id" / "product_name",
            Path(sys_root) / "class" / "dmi" / "id" / "sys_vendor",
        )
        dmi = " ".join(
            path.read_text(encoding="utf-8", errors="replace").strip()
            for path in dmi_files
            if path.exists()
        ).lower()
        markers = (
            "virtualbox",
            "vmware",
            "kvm",
            "qemu",
            "hyper-v",
            "xen",
            "parallels",
        )
        virtualization = next((marker for marker in markers if marker in dmi), None)
    if is_wsl:
        virtualization = virtualization or "wsl"
    return HostEnvironment(
        system=system,
        release=release,
        is_wsl=is_wsl,
        is_virtualized=virtualization is not None,
        virtualization=virtualization,
    )


def validate_partitions(
    topology: CpuTopology,
    partitions: CorePartitions,
    *,
    require_complete: bool = True,
) -> list[str]:
    """Return partition violations, including SMT siblings split across roles."""
    errors: list[str] = []
    roles = partitions.roles()
    for role, cpus in roles.items():
        if not cpus:
            errors.append(f"{role} CPU set is empty")
        unknown = cpus - topology.online_cpus
        if unknown:
            errors.append(f"{role} CPU set contains offline CPUs: {format_cpu_list(unknown)}")
    role_names = tuple(roles)
    for index, left in enumerate(role_names):
        for right in role_names[index + 1 :]:
            overlap = roles[left] & roles[right]
            if overlap:
                errors.append(
                    f"{left}/{right} CPU sets overlap: {format_cpu_list(overlap)}"
                )
    assigned = frozenset().union(*roles.values())
    if require_complete:
        missing = topology.online_cpus - assigned
        if missing:
            errors.append(
                f"online CPUs are not assigned to a role: {format_cpu_list(missing)}"
            )

    for physical_core, siblings in sorted(topology.physical_cores.items()):
        owners = [role for role, cpus in roles.items() if siblings & cpus]
        if len(owners) > 1:
            errors.append(
                "SMT siblings split across roles on physical core "
                f"{physical_core[0]}:{physical_core[1]} "
                f"({format_cpu_list(siblings)}): {','.join(owners)}"
            )
    return errors


def publication_preflight(
    topology: CpuTopology,
    partitions: CorePartitions,
    *,
    mode: PreflightMode = "publication",
    environment: HostEnvironment | None = None,
    require_complete: bool = True,
) -> PreflightResult:
    """Validate isolation; smoke mode downgrades host/governor limits to caveats."""
    if mode not in ("publication", "smoke"):
        raise ValueError(f"unknown preflight mode {mode!r}")
    host = environment or detect_host_environment()
    errors = validate_partitions(
        topology, partitions, require_complete=require_complete
    )
    caveats: list[str] = []

    host_issues: list[str] = []
    if host.system != "Linux":
        host_issues.append(f"host system is {host.system}, not Linux")
    if host.is_wsl:
        host_issues.append("WSL is smoke/debug only")
    elif host.is_virtualized:
        host_issues.append(
            f"virtualized host ({host.virtualization or 'unknown'}) is not publishable"
        )
    governors = {
        cpu: topology.threads[cpu].governor for cpu in sorted(topology.online_cpus)
    }
    bad_governors = {
        cpu: governor
        for cpu, governor in governors.items()
        if governor != "performance"
    }
    if bad_governors:
        rendered = ", ".join(
            f"{cpu}={governor or 'unverified'}"
            for cpu, governor in bad_governors.items()
        )
        host_issues.append(f"non-performance or unverified CPU governors: {rendered}")

    if mode == "publication":
        errors.extend(host_issues)
    else:
        caveats.extend(host_issues)
    return PreflightResult(
        mode=mode,
        passed=not errors,
        errors=tuple(errors),
        caveats=tuple(caveats),
        environment=host,
        governors=governors,
    )


def observed_affinity(pid: int) -> frozenset[int]:
    if hasattr(os, "sched_getaffinity"):
        try:
            return frozenset(os.sched_getaffinity(pid))
        except OSError:
            pass
    status = Path("/proc") / str(pid) / "status"
    try:
        for line in status.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Cpus_allowed_list:"):
                return parse_cpu_list(line.split(":", 1)[1])
    except OSError as exc:
        raise IsolationError(f"cannot read affinity for PID {pid}: {exc}") from exc
    raise IsolationError(f"cannot determine affinity for PID {pid}")


def verify_pid_affinity(pid: int, expected_cpus: Sequence[int] | set[int]) -> frozenset[int]:
    expected = frozenset(expected_cpus)
    if not expected:
        raise ValueError("expected CPU set must not be empty")
    observed = observed_affinity(pid)
    if observed != expected:
        raise IsolationError(
            f"PID {pid} affinity is {format_cpu_list(observed)}, "
            f"expected {format_cpu_list(expected)}"
        )
    return observed


def set_current_affinity(cpus: Sequence[int] | set[int]) -> frozenset[int]:
    requested = frozenset(cpus)
    if not requested:
        raise ValueError("CPU set must not be empty")
    if not hasattr(os, "sched_setaffinity"):
        raise IsolationError("sched_setaffinity is unavailable on this platform")
    os.sched_setaffinity(0, requested)
    return verify_pid_affinity(0, requested)


def taskset_command(
    command: Sequence[str], cpus: Sequence[int] | set[int]
) -> list[str]:
    if not command:
        raise ValueError("launch command must not be empty")
    executable = shutil.which("taskset")
    if not executable:
        raise IsolationError("taskset executable is unavailable")
    return [executable, "--cpu-list", format_cpu_list(cpus), *command]


@dataclass
class PinnedProcess:
    process: subprocess.Popen[bytes]
    requested_cpus: frozenset[int]
    observed_cpus: frozenset[int]
    launcher: str


def launch_pinned(
    command: Sequence[str],
    cpus: Sequence[int] | set[int],
    *,
    verify: bool = True,
    **popen_kwargs: object,
) -> PinnedProcess:
    """Launch through taskset and verify the kernel's applied CPU mask."""
    requested = frozenset(cpus)
    launch_command = taskset_command(command, requested)
    process = subprocess.Popen(launch_command, **popen_kwargs)
    observed = requested
    if verify:
        last_error: IsolationError | None = None
        for _ in range(20):
            try:
                observed = verify_pid_affinity(process.pid, requested)
                last_error = None
                break
            except IsolationError as exc:
                last_error = exc
                if process.poll() is not None:
                    break
                time.sleep(0.005)
        if last_error is not None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
            raise last_error
    return PinnedProcess(
        process=process,
        requested_cpus=requested,
        observed_cpus=observed,
        launcher="taskset",
    )

