from __future__ import annotations

from apu_characterization.validity import (
    TURN_LEVEL_PARALLELISM,
    artifact_stem,
    validity_banner,
)


def test_turn_level_parallelism_has_narrow_banner() -> None:
    banner = validity_banner(TURN_LEVEL_PARALLELISM)
    assert "Turn-level parallelism" in banner
    assert "S/C" in banner or "Tier-S" in banner
    assert "Tier D" in banner


def test_tlp_artifact_has_no_debug_suffix() -> None:
    assert artifact_stem("tlp01", TURN_LEVEL_PARALLELISM) == "tlp01"
