from __future__ import annotations

from apu_characterization.validity import (
    CAPABILITY_SCALING,
    artifact_stem,
    validity_banner,
)


def test_capability_scaling_has_narrow_banner() -> None:
    banner = validity_banner(CAPABILITY_SCALING)
    assert "Capability-scaling experiment" in banner
    assert "fixed budget" in banner
    assert "Tier D is projection-only" in banner


def test_capability_scaling_artifact_has_no_debug_suffix() -> None:
    assert artifact_stem("cap01", CAPABILITY_SCALING) == "cap01"
