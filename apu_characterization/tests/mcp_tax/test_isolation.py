from __future__ import annotations

import os
import shutil
import sys

import pytest

from apu_characterization.mcp_tax.isolation import (
    CorePartitions,
    CpuThread,
    CpuTopology,
    HostEnvironment,
    format_cpu_list,
    launch_pinned,
    observed_affinity,
    parse_cpu_list,
    publication_preflight,
    taskset_command,
    validate_partitions,
)


def _topology(*, governor: str | None = "performance") -> CpuTopology:
    threads = {
        cpu: CpuThread(
            cpu=cpu,
            package_id=0,
            core_id=cpu // 2,
            siblings=frozenset({cpu - cpu % 2, cpu - cpu % 2 + 1}),
            governor=governor,
        )
        for cpu in range(6)
    }
    return CpuTopology(online_cpus=frozenset(range(6)), threads=threads)


def _host(*, wsl: bool = False, virtualized: bool = False) -> HostEnvironment:
    return HostEnvironment(
        system="Linux",
        release="test",
        is_wsl=wsl,
        is_virtualized=virtualized or wsl,
        virtualization="wsl" if wsl else ("kvm" if virtualized else None),
    )


def test_cpu_list_round_trip() -> None:
    cpus = parse_cpu_list("0-3,8,10-12")
    assert cpus == frozenset({0, 1, 2, 3, 8, 10, 11, 12})
    assert format_cpu_list(cpus) == "0-3,8,10-12"


def test_partition_validation_rejects_overlap_and_split_smt() -> None:
    partitions = CorePartitions(
        os_cpus=frozenset({0, 1}),
        client_cpus=frozenset({2, 3}),
        server_cpus=frozenset({3, 4, 5}),
    )
    errors = validate_partitions(_topology(), partitions)
    assert any("overlap" in error for error in errors)
    assert any("SMT siblings split" in error for error in errors)


def test_publication_rejects_wsl_but_smoke_records_caveat() -> None:
    partitions = CorePartitions(
        os_cpus=frozenset({0, 1}),
        client_cpus=frozenset({2, 3}),
        server_cpus=frozenset({4, 5}),
    )
    publication = publication_preflight(
        _topology(), partitions, environment=_host(wsl=True)
    )
    smoke = publication_preflight(
        _topology(), partitions, mode="smoke", environment=_host(wsl=True)
    )
    assert not publication.passed
    assert any("WSL" in error for error in publication.errors)
    assert smoke.passed
    assert any("WSL" in caveat for caveat in smoke.caveats)


def test_publication_rejects_unverified_governor() -> None:
    partitions = CorePartitions(
        os_cpus=frozenset({0, 1}),
        client_cpus=frozenset({2, 3}),
        server_cpus=frozenset({4, 5}),
    )
    result = publication_preflight(
        _topology(governor=None), partitions, environment=_host()
    )
    assert not result.passed
    assert any("governors" in error for error in result.errors)


@pytest.mark.skipif(shutil.which("taskset") is None, reason="Linux taskset unavailable")
def test_taskset_command_is_explicit() -> None:
    command = taskset_command(["python3", "-V"], {2, 3})
    assert command[1:3] == ["--cpu-list", "2-3"]
    assert command[-2:] == ["python3", "-V"]


@pytest.mark.skipif(
    shutil.which("taskset") is None or not hasattr(os, "sched_getaffinity"),
    reason="Linux taskset and affinity APIs unavailable",
)
def test_taskset_launch_is_verified() -> None:
    cpu = min(observed_affinity(0))
    pinned = launch_pinned(
        [sys.executable, "-c", "import time; time.sleep(2)"], {cpu}
    )
    try:
        assert pinned.requested_cpus == frozenset({cpu})
        assert pinned.observed_cpus == frozenset({cpu})
        assert observed_affinity(pinned.process.pid) == frozenset({cpu})
    finally:
        pinned.process.terminate()
        pinned.process.wait(timeout=3)

