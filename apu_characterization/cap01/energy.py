"""RAPL package energy accounting and CAP-01 joule deadlines."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


class EnergyUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RaplCounter:
    package: str
    energy_uj_path: Path
    max_energy_range_uj: int

    def read_uj(self) -> int:
        value = int(self.energy_uj_path.read_text(encoding="ascii").strip())
        if value < 0:
            raise EnergyUnavailable(f"{self.package} RAPL energy is negative")
        return value


@dataclass(frozen=True)
class EnergyReading:
    package_uj: Mapping[str, int]

    @property
    def total_joules(self) -> float:
        return sum(self.package_uj.values()) / 1_000_000.0


class RaplPackageReader:
    """Read top-level package domains, excluding nested core/DRAM domains."""

    def __init__(self, counters: Sequence[RaplCounter]) -> None:
        if not counters:
            raise EnergyUnavailable("no readable RAPL package domains")
        packages = [counter.package for counter in counters]
        if len(packages) != len(set(packages)):
            raise ValueError("duplicate RAPL package names")
        self.counters = tuple(counters)

    @classmethod
    def discover(
        cls, powercap_root: str | Path = "/sys/class/powercap"
    ) -> "RaplPackageReader":
        root = Path(powercap_root)
        counters: list[RaplCounter] = []
        candidates = sorted(
            {
                *root.glob("intel-rapl:[0-9]*"),
                *root.glob("amd-rapl:[0-9]*"),
            }
        )
        for domain in candidates:
            # A colon after the package index denotes a nested sub-domain.
            suffix = domain.name.split(":", 1)[1] if ":" in domain.name else ""
            if ":" in suffix:
                continue
            energy_path = domain / "energy_uj"
            range_path = domain / "max_energy_range_uj"
            name_path = domain / "name"
            try:
                name = name_path.read_text(encoding="ascii").strip()
                maximum = int(range_path.read_text(encoding="ascii").strip())
                int(energy_path.read_text(encoding="ascii").strip())
            except (OSError, ValueError):
                continue
            if maximum <= 0:
                continue
            counters.append(RaplCounter(name, energy_path, maximum))
        return cls(counters)

    def read(self) -> EnergyReading:
        try:
            return EnergyReading(
                {counter.package: counter.read_uj() for counter in self.counters}
            )
        except (OSError, ValueError) as exc:
            raise EnergyUnavailable(f"cannot read RAPL package energy: {exc}") from exc

    def delta_joules(self, start: EnergyReading, end: EnergyReading) -> float:
        total_uj = 0
        for counter in self.counters:
            if counter.package not in start.package_uj or counter.package not in end.package_uj:
                raise ValueError(f"missing RAPL reading for {counter.package}")
            delta = end.package_uj[counter.package] - start.package_uj[counter.package]
            if delta < 0:
                delta += counter.max_energy_range_uj
            if delta < 0 or delta > counter.max_energy_range_uj:
                raise ValueError(f"invalid wrapped RAPL delta for {counter.package}")
            total_uj += delta
        return total_uj / 1_000_000.0


@dataclass(frozen=True)
class JouleDeadlineStatus:
    budget_joules: float
    consumed_joules: float
    exhausted: bool


class JouleDeadline:
    """A deadline whose monotonic progress is package joules, not wall time."""

    def __init__(self, reader: RaplPackageReader, budget_joules: float) -> None:
        if not math.isfinite(budget_joules) or budget_joules <= 0:
            raise ValueError("joule budget must be finite and positive")
        self.reader = reader
        self.budget_joules = float(budget_joules)
        self.start = reader.read()

    def status(self) -> JouleDeadlineStatus:
        consumed = self.reader.delta_joules(self.start, self.reader.read())
        return JouleDeadlineStatus(
            budget_joules=self.budget_joules,
            consumed_joules=consumed,
            exhausted=consumed >= self.budget_joules,
        )

    def exhausted(self) -> bool:
        return self.status().exhausted


@dataclass(frozen=True)
class ObserverValidation:
    passed: bool
    rapl_joules: float
    observer_joules: float | None
    relative_error: float | None
    tolerance: float
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self) | {"errors": list(self.errors)}


def validate_energy_observer(
    rapl_joules: float,
    observer_joules: float | None,
    *,
    relative_tolerance: float = 0.15,
) -> ObserverValidation:
    """Require an independent observer and bound disagreement with package RAPL."""
    errors: list[str] = []
    relative_error: float | None = None
    if not math.isfinite(rapl_joules) or rapl_joules <= 0:
        errors.append("RAPL joules must be finite and positive")
    if observer_joules is None:
        errors.append("independent energy observer reading is missing")
    elif not math.isfinite(observer_joules) or observer_joules <= 0:
        errors.append("observer joules must be finite and positive")
    elif not errors:
        relative_error = abs(observer_joules - rapl_joules) / rapl_joules
        if relative_error > relative_tolerance:
            errors.append(
                f"energy observer relative error {relative_error:.3f} exceeds "
                f"{relative_tolerance:.3f}"
            )
    return ObserverValidation(
        passed=not errors,
        rapl_joules=rapl_joules,
        observer_joules=observer_joules,
        relative_error=relative_error,
        tolerance=relative_tolerance,
        errors=tuple(errors),
    )


def energy_variant_manifest(
    reader: RaplPackageReader | None,
    *,
    unavailable_reason: str | None = None,
) -> dict[str, Any]:
    """Describe energy-arm availability without affecting wall-primary eligibility."""
    if reader is None:
        reason = unavailable_reason or "RAPL package energy unavailable"
        return {
            "status": "dropped",
            "reason": reason,
            "note": f"energy variant dropped: {reason}",
            "wall_primary_eligible": True,
            "primary_budget_kind": "wall",
        }
    return {
        "status": "available",
        "packages": [counter.package for counter in reader.counters],
        "observer_validation_required": True,
        "wall_primary_eligible": True,
        "primary_budget_kind": "wall",
    }


def open_rapl_or_manifest(
    powercap_root: str | Path = "/sys/class/powercap",
    *,
    factory: Callable[[str | Path], RaplPackageReader] = RaplPackageReader.discover,
) -> tuple[RaplPackageReader | None, dict[str, Any]]:
    try:
        reader = factory(powercap_root)
    except (EnergyUnavailable, OSError, ValueError) as exc:
        return None, energy_variant_manifest(None, unavailable_reason=str(exc))
    return reader, energy_variant_manifest(reader)
