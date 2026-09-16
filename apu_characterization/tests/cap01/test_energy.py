from __future__ import annotations

from pathlib import Path

from apu_characterization.cap01.energy import (
    EnergyReading,
    JouleDeadline,
    RaplCounter,
    RaplPackageReader,
    energy_variant_manifest,
    open_rapl_or_manifest,
    validate_energy_observer,
)


def _reader(tmp_path: Path, value_uj: int = 100) -> tuple[RaplPackageReader, Path]:
    energy = tmp_path / "energy_uj"
    energy.write_text(str(value_uj), encoding="ascii")
    return RaplPackageReader([RaplCounter("package-0", energy, 1_000_000)]), energy


def test_rapl_package_delta_handles_counter_wrap(tmp_path: Path) -> None:
    reader, _ = _reader(tmp_path)
    start = EnergyReading({"package-0": 900_000})
    end = EnergyReading({"package-0": 100_000})
    assert reader.delta_joules(start, end) == 0.2


def test_joule_deadline_uses_rapl_not_wall(tmp_path: Path) -> None:
    reader, energy = _reader(tmp_path)
    deadline = JouleDeadline(reader, 0.0002)
    energy.write_text("250", encoding="ascii")
    assert not deadline.exhausted()
    energy.write_text("300", encoding="ascii")
    assert deadline.exhausted()


def test_observer_validation_is_required() -> None:
    assert validate_energy_observer(10.0, 10.5).passed
    assert not validate_energy_observer(10.0, None).passed
    assert not validate_energy_observer(10.0, 20.0).passed


def test_unavailable_energy_is_dropped_without_wall_primary_failure() -> None:
    reader, manifest = open_rapl_or_manifest(
        "/missing",
        factory=lambda _: (_ for _ in ()).throw(OSError("no powercap")),
    )
    assert reader is None
    assert manifest["status"] == "dropped"
    assert manifest["wall_primary_eligible"]
    assert energy_variant_manifest(None)["primary_budget_kind"] == "wall"
