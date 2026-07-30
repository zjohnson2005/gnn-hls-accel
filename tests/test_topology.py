"""Topology tests (spec §4, §7/M1).

Windows calls are mocked, so the suite runs anywhere. Two areas get the most attention:

* **Buffer parsing** — ``SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX`` is parsed by explicit byte
  offset, which is exactly the kind of code that silently produces plausible-but-wrong answers.
  Tested against synthetic buffers with known contents.
* **The unverified state** — that ``affinity_for`` refuses rather than guessing. Spec §4 warns
  against trusting ``EfficiencyClass`` ordering, and open question 4 asks whether it can be
  trusted, so a guessed mapping would answer an open research question by assumption.
"""

from __future__ import annotations

import struct
from typing import Any

import pytest

from seam.config import ResolvedConfig, resolve_config
from seam.errors import ConfigError, TopologyNotVerifiedError, TopologyVerificationError
from seam.topology import (
    CoreInfo,
    _evaluate_efficiency_class_agreement,
    _parse_processor_core_records,
    _split_into_two_clusters,
    affinity_for,
    build_kernel,
    load_verified_topology,
    measure_topology,
    verify_topology,
)

_RELATION_PROCESSOR_CORE = 0
_SIZEOF_GROUP_AFFINITY = 16


def make_core_record(*, efficiency_class: int, logical_cpus: list[int], group: int = 0, smt: bool = False) -> bytes:
    """Build one synthetic ``SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX`` processor-core record."""
    size = 32 + _SIZEOF_GROUP_AFFINITY
    record = bytearray(size)

    struct.pack_into("<I", record, 0, _RELATION_PROCESSOR_CORE)
    struct.pack_into("<I", record, 4, size)
    record[8] = 0x1 if smt else 0x0
    record[9] = efficiency_class
    struct.pack_into("<H", record, 30, 1)  # GroupCount

    mask = 0
    for cpu in logical_cpus:
        mask |= 1 << cpu
    struct.pack_into("<Q", record, 32, mask)
    struct.pack_into("<H", record, 40, group)

    return bytes(record)


def make_platform_a_buffer(*, p_class: int = 1, lpe_class: int = 0) -> bytes:
    """A 4 P + 4 LP-E, 8C/8T buffer: CPUs 0-3 P, CPUs 4-7 LP-E."""
    records = [make_core_record(efficiency_class=p_class, logical_cpus=[cpu]) for cpu in range(4)]
    records += [make_core_record(efficiency_class=lpe_class, logical_cpus=[cpu]) for cpu in range(4, 8)]
    return b"".join(records)


# ==================================================================================================
# Buffer parsing
# ==================================================================================================


def test_parses_platform_a_topology() -> None:
    cores = _parse_processor_core_records(make_platform_a_buffer())

    assert len(cores) == 8, "8 physical cores, one logical CPU each (no SMT)"
    assert [core.logical_cpus for core in cores] == [(cpu,) for cpu in range(8)]
    assert [core.efficiency_class for core in cores] == [1, 1, 1, 1, 0, 0, 0, 0]
    assert all(core.smt is False for core in cores)


def test_parses_multi_cpu_core_masks() -> None:
    """An SMT core reports several bits in one mask; the parser must expand all of them."""
    cores = _parse_processor_core_records(
        make_core_record(efficiency_class=1, logical_cpus=[0, 1], smt=True)
    )
    assert cores[0].logical_cpus == (0, 1)
    assert cores[0].smt is True


def test_parses_high_cpu_indices() -> None:
    """The affinity mask is 64-bit; a bit above 31 must not be lost to a 32-bit read."""
    cores = _parse_processor_core_records(
        make_core_record(efficiency_class=0, logical_cpus=[40, 63])
    )
    assert cores[0].logical_cpus == (40, 63)


def test_parses_group_id() -> None:
    cores = _parse_processor_core_records(
        make_core_record(efficiency_class=0, logical_cpus=[3], group=2)
    )
    assert cores[0].group == 2


def test_rejects_empty_buffer() -> None:
    with pytest.raises(TopologyVerificationError, match="no processor-core records"):
        _parse_processor_core_records(b"")


def test_rejects_zero_size_record() -> None:
    """A Size of 0 would loop forever; it must raise instead."""
    record = bytearray(make_core_record(efficiency_class=1, logical_cpus=[0]))
    struct.pack_into("<I", record, 4, 0)
    with pytest.raises(TopologyVerificationError, match="Size=0"):
        _parse_processor_core_records(bytes(record))


def test_rejects_record_overrunning_the_buffer() -> None:
    record = bytearray(make_core_record(efficiency_class=1, logical_cpus=[0]))
    struct.pack_into("<I", record, 4, 4096)
    with pytest.raises(TopologyVerificationError, match="overruns"):
        _parse_processor_core_records(bytes(record))


def test_rejects_truncated_record() -> None:
    with pytest.raises(TopologyVerificationError, match="truncated"):
        _parse_processor_core_records(make_core_record(efficiency_class=1, logical_cpus=[0])[:20])


# ==================================================================================================
# Clustering
# ==================================================================================================


def test_splits_a_clean_bimodal_distribution() -> None:
    scores = {0: 100.0, 1: 102.0, 2: 101.0, 3: 99.0, 4: 60.0, 5: 61.0, 6: 59.0, 7: 60.5}
    fast, slow = _split_into_two_clusters(scores)
    assert fast == [0, 1, 2, 3]
    assert slow == [4, 5, 6, 7]


def test_split_is_independent_of_cpu_ordering() -> None:
    """The fast cluster need not be the low-numbered CPUs — that is the point of measuring."""
    scores = {0: 60.0, 1: 100.0, 2: 61.0, 3: 101.0, 4: 59.0, 5: 99.0, 6: 60.5, 7: 102.0}
    fast, slow = _split_into_two_clusters(scores)
    assert fast == [1, 3, 5, 7]
    assert slow == [0, 2, 4, 6]


def test_split_is_deterministic() -> None:
    """A value committed to config must not depend on k-means seeding."""
    scores = {i: float(100 - i * 7) for i in range(8)}
    assert all(
        _split_into_two_clusters(scores) == _split_into_two_clusters(scores) for _ in range(5)
    )


def test_split_requires_at_least_two_cpus() -> None:
    with pytest.raises(TopologyVerificationError, match="at least 2"):
        _split_into_two_clusters({0: 100.0})


# ==================================================================================================
# Open question 4 — EfficiencyClass agreement
# ==================================================================================================


def _cores(classes: list[int]) -> list[CoreInfo]:
    return [
        CoreInfo(core_index=i, efficiency_class=cls, logical_cpus=(i,), group=0, smt=False)
        for i, cls in enumerate(classes)
    ]


def test_documented_ordering_is_reported_as_matched() -> None:
    """Higher EfficiencyClass on the measured-fast cores is the documented Windows behaviour."""
    cores = _cores([1, 1, 1, 1, 0, 0, 0, 0])
    matched, partition, direction = _evaluate_efficiency_class_agreement(
        cores, [0, 1, 2, 3], [4, 5, 6, 7]
    )
    assert matched is True
    assert partition is True
    assert direction == "higher_is_faster"


def test_inverted_ordering_is_distinguished_from_a_wrong_partition() -> None:
    """A correct grouping with an inverted sense must not be reported as a flat failure.

    This is the case spec §4 warns about, and reporting it precisely is what answers open
    question 4 rather than merely failing it.
    """
    cores = _cores([0, 0, 0, 0, 1, 1, 1, 1])
    matched, partition, direction = _evaluate_efficiency_class_agreement(
        cores, [0, 1, 2, 3], [4, 5, 6, 7]
    )
    assert matched is False, "documented interpretation did not hold"
    assert partition is True, "but the partition itself was correct"
    assert direction == "lower_is_faster"


def test_disagreeing_partition_is_reported_as_undetermined() -> None:
    cores = _cores([1, 0, 1, 0, 1, 0, 1, 0])
    matched, partition, direction = _evaluate_efficiency_class_agreement(
        cores, [0, 1, 2, 3], [4, 5, 6, 7]
    )
    assert matched is False
    assert partition is False
    assert direction == "undetermined"


def test_single_efficiency_class_cannot_answer_the_question() -> None:
    """If Windows reports one class for every core it carries no information about the split."""
    cores = _cores([0] * 8)
    matched, partition, direction = _evaluate_efficiency_class_agreement(
        cores, [0, 1, 2, 3], [4, 5, 6, 7]
    )
    assert (matched, partition, direction) == (False, False, "undetermined")


# ==================================================================================================
# Kernel selection (spec §8: the instrument is config, not a constant in code)
# ==================================================================================================


def test_build_kernel_refuses_an_unregistered_name() -> None:
    """Substituting a different instrument than config names would make every score untraceable."""
    with pytest.raises(ConfigError, match="unknown topology kernel"):
        build_kernel("kernel_that_does_not_exist", {})


def test_build_kernel_names_the_missing_parameter() -> None:
    with pytest.raises(ConfigError, match="float_iterations"):
        build_kernel("python_intfp_v1", {"integer_iterations": 10})


def test_committed_config_names_a_registered_kernel(real_platform_config: ResolvedConfig) -> None:
    params = real_platform_config.get("topology.verification")
    kernel = build_kernel(params["kernel"], params)
    assert kernel.name == params["kernel"]
    assert kernel.work_units_per_trial > 0


# ==================================================================================================
# Verdict recording (AUDIT_LOG.md AF-006)
# ==================================================================================================


def _patch_measurement(
    monkeypatch: pytest.MonkeyPatch, scores: dict[int, float], *, efficiency_classes: list[int]
) -> None:
    """Run ``measure_topology`` against fixed scores and a fixed Windows core enumeration."""
    monkeypatch.setattr("seam.topology.enumerate_cores", lambda: _cores(efficiency_classes))
    monkeypatch.setattr(
        "seam.topology._bench_one_cpu", lambda cpu, **_kwargs: scores[cpu]
    )


_PLATFORM_A_CLASSES = [1, 1, 1, 1, 0, 0, 0, 0]


def test_measure_topology_passes_on_a_clean_split(
    fake_config: ResolvedConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    scores = {cpu: (5.0 if cpu < 4 else 4.0) for cpu in range(8)}
    _patch_measurement(monkeypatch, scores, efficiency_classes=_PLATFORM_A_CLASSES)

    result = measure_topology(fake_config)

    assert result.verdict == "pass"
    assert result.refusal_reasons == []
    assert result.p_cpus == [0, 1, 2, 3]
    assert result.lpe_cpus == [4, 5, 6, 7]
    assert result.cluster_separation_ratio == pytest.approx(1.25)
    assert result.efficiency_class_ordering_matched is True


def test_measure_topology_records_a_refusal_instead_of_raising(
    fake_config: ResolvedConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AF-006: a refusal must still yield the full measurement, not just an exception message.

    The earlier refused runs reported no CV at all, because the separation check raised before the
    CV was computed. Every criterion is now evaluated and recorded.
    """
    scores = {cpu: (5.0 if cpu < 4 else 4.8) for cpu in range(8)}
    _patch_measurement(monkeypatch, scores, efficiency_classes=_PLATFORM_A_CLASSES)

    result = measure_topology(fake_config)

    assert result.verdict == "refused"
    assert any("separate cleanly" in reason for reason in result.refusal_reasons)
    assert result.cluster_separation_ratio == pytest.approx(5.0 / 4.8)
    assert result.p_cluster_cv == pytest.approx(0.0)
    assert result.lpe_cluster_cv == pytest.approx(0.0)
    assert result.scores == scores
    # Open question 4 is answered for a refused run too — it is a separate question from whether
    # the separation was large enough.
    assert result.efficiency_class_direction == "higher_is_faster"


def test_measure_topology_reports_every_failing_criterion_not_just_the_first(
    fake_config: ResolvedConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 7/1 split that also fails separation must report both, so the diagnosis is complete."""
    scores = {0: 5.0, 1: 4.99, 2: 4.98, 3: 4.97, 4: 4.96, 5: 4.95, 6: 4.94, 7: 4.6}
    _patch_measurement(monkeypatch, scores, efficiency_classes=_PLATFORM_A_CLASSES)

    result = measure_topology(fake_config)

    assert result.verdict == "refused"
    assert any("separate cleanly" in reason for reason in result.refusal_reasons)
    assert any("does not match the expected" in reason for reason in result.refusal_reasons)


def test_verify_topology_still_raises_on_a_refusal(
    fake_config: ResolvedConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Callers that need a mapping must not be handed an unestablished one."""
    scores = {cpu: (5.0 if cpu < 4 else 4.8) for cpu in range(8)}
    _patch_measurement(monkeypatch, scores, efficiency_classes=_PLATFORM_A_CLASSES)

    with pytest.raises(TopologyVerificationError, match="REFUSED"):
        verify_topology(fake_config)


def test_measure_topology_refuses_a_platform_that_is_not_the_declared_part(
    fake_config: ResolvedConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A wrong CPU count is a broken instrument, not a verdict, so it still raises."""
    scores = dict.fromkeys(range(4), 5.0)
    _patch_measurement(monkeypatch, scores, efficiency_classes=[1, 1, 0, 0])

    with pytest.raises(TopologyVerificationError, match="expected 8 logical CPUs"):
        measure_topology(fake_config)


# ==================================================================================================
# The unverified state
# ==================================================================================================


def test_committed_config_ships_unverified(real_platform_config: ResolvedConfig) -> None:
    """AMENDMENTS.md AM-008: the committed config must NOT claim a verified mapping.

    This test is the tripwire against a future agent writing a plausible ``[0,1,2,3]`` into the
    config to make M1 look green. When verification genuinely runs, this test is updated in the
    same commit that records the measurement's run_id — which makes the change visible in review.
    """
    assert real_platform_config.get("topology.verified") is False
    assert real_platform_config.get("topology.p_cpus") is None
    assert real_platform_config.get("topology.lpe_cpus") is None
    assert real_platform_config.get("topology.measured.run_id") is None


def test_expected_split_is_stored_separately_from_measured(
    real_platform_config: ResolvedConfig,
) -> None:
    """An expectation must never be readable as a measurement."""
    expected = real_platform_config.get("topology.expected")
    assert expected["n_logical_cpus"] == 8
    assert expected["n_p_cores"] == 4
    assert expected["n_lpe_cores"] == 4
    assert expected["smt"] is False
    assert real_platform_config.get("topology.measured.scores") is None


def test_load_verified_topology_refuses_unverified_config(fake_config: ResolvedConfig) -> None:
    with pytest.raises(TopologyNotVerifiedError, match="no verified"):
        load_verified_topology(fake_config)


def test_affinity_for_refuses_unverified_config(fake_config: ResolvedConfig) -> None:
    for target in ("cpu-p", "cpu-lpe"):
        with pytest.raises(TopologyNotVerifiedError):
            affinity_for(target, fake_config)  # type: ignore[arg-type]


def test_affinity_for_refuses_even_with_allow_unverified(fake_config: ResolvedConfig) -> None:
    """There is no defensible default ordering, so the waiver still cannot produce a mapping.

    The waiver exists to make the *attempt* auditable, not to hand back a guess.
    """
    with pytest.raises(TopologyNotVerifiedError, match="no fallback mapping"):
        affinity_for("cpu-p", fake_config, allow_unverified=True)


# ==================================================================================================
# The verified state
# ==================================================================================================


def test_affinity_for_returns_four_cpus_per_cpu_target(verified_config: ResolvedConfig) -> None:
    """Spec §4: ``cpu-p`` and ``cpu-lpe`` each cover 4 logical CPUs on this 8-CPU part."""
    p_cpus = affinity_for("cpu-p", verified_config)
    lpe_cpus = affinity_for("cpu-lpe", verified_config)

    assert p_cpus == [0, 1, 2, 3]
    assert lpe_cpus == [4, 5, 6, 7]
    assert len(p_cpus) == 4
    assert len(lpe_cpus) == 4
    assert set(p_cpus).isdisjoint(lpe_cpus)
    assert len(p_cpus) + len(lpe_cpus) == 8, "8 logical CPUs, no SMT"


@pytest.mark.parametrize("bad_target", ["igpu", "npu", "cloud", "dgpu"])
def test_affinity_for_rejects_non_cpu_targets(
    verified_config: ResolvedConfig, bad_target: str
) -> None:
    with pytest.raises(ValueError, match="cpu-p"):
        affinity_for(bad_target, verified_config)  # type: ignore[arg-type]


def test_load_verified_topology_rejects_overlapping_clusters(fake_repo: Any) -> None:
    config = resolve_config(
        [fake_repo / "configs" / "platforms" / "aipc-c1.yaml"],
        overrides={"topology": {"verified": True, "p_cpus": [0, 1, 2, 3], "lpe_cpus": [3, 4, 5, 6]}},
        repo_root=fake_repo,
    )
    with pytest.raises(ConfigError, match="overlap"):
        load_verified_topology(config)


def test_load_verified_topology_rejects_incomplete_coverage(fake_repo: Any) -> None:
    """A mapping covering 6 of 8 logical CPUs means two cores were never classified."""
    config = resolve_config(
        [fake_repo / "configs" / "platforms" / "aipc-c1.yaml"],
        overrides={"topology": {"verified": True, "p_cpus": [0, 1, 2], "lpe_cpus": [4, 5, 6]}},
        repo_root=fake_repo,
    )
    with pytest.raises(ConfigError, match="declares 8"):
        load_verified_topology(config)


def test_load_verified_topology_rejects_duplicates(fake_repo: Any) -> None:
    config = resolve_config(
        [fake_repo / "configs" / "platforms" / "aipc-c1.yaml"],
        overrides={
            "topology": {"verified": True, "p_cpus": [0, 0, 1, 2], "lpe_cpus": [4, 5, 6, 7]}
        },
        repo_root=fake_repo,
    )
    with pytest.raises(ConfigError, match="duplicate"):
        load_verified_topology(config)


# ==================================================================================================
# Worker-pool sizing (spec §9.8)
# ==================================================================================================


def test_config_never_implies_more_than_eight_logical_cpus(
    real_platform_config: ResolvedConfig,
) -> None:
    """Spec §9.8: never tune pools assuming more than 8 logical CPUs, and never via cpu_count()."""
    assert real_platform_config.get("concurrency.n_logical_cpus") == 8
    assert real_platform_config.get("concurrency.smt") is False
    assert real_platform_config.get("concurrency.default_workers") <= 8
    assert real_platform_config.get("concurrency.sampler_workers") == 1
