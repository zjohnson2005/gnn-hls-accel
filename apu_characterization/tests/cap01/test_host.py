from __future__ import annotations

from pathlib import Path

from apu_characterization.cap01.host import (
    HostObservation,
    answer_space_hash,
    evaluate_host_qualification,
)


def _observation(digest: str, **changes: object) -> HostObservation:
    values = {
        "system": "Linux",
        "virtualization": "none",
        "tracked_git_clean": True,
        "lock_acquired": True,
        "load_1m": 0.5,
        "cpu_count": 8,
        "answer_space_sha256": digest,
    }
    values.update(changes)
    return HostObservation(**values)  # type: ignore[arg-type]


def test_answer_space_hash_is_order_independent_and_content_bound(
    tmp_path: Path,
) -> None:
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    digest = answer_space_hash([first, second])
    assert digest == answer_space_hash([second, first])
    second.write_text("changed", encoding="utf-8")
    assert digest != answer_space_hash([first, second])


def test_native_bare_metal_clean_locked_low_load_host_passes() -> None:
    digest = "a" * 64
    result = evaluate_host_qualification(
        _observation(digest), expected_answer_space_sha256=digest
    )
    assert result.passed


def test_host_rigor_rejects_each_publication_hazard() -> None:
    digest = "a" * 64
    result = evaluate_host_qualification(
        _observation(
            "b" * 64,
            virtualization="kvm",
            tracked_git_clean=False,
            lock_acquired=False,
            load_1m=8.0,
        ),
        expected_answer_space_sha256=digest,
    )
    assert not result.passed
    text = "\n".join(result.errors)
    assert "systemd-detect-virt" in text
    assert "tracked git" in text
    assert "exclusive host lock" in text
    assert "load per CPU" in text
    assert "answer-space hash" in text
