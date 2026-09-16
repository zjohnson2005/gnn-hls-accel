from apu_characterization.cap01.contracts import load_protocol
from apu_characterization.cap01.schedule import estimate_matrix_hours


def test_matrix_estimate_uses_full_five_domain_cross_product() -> None:
    protocol = load_protocol()
    estimate = estimate_matrix_hours(protocol, setup_ms=0.0, cooldown_ms=0.0)
    expected_hours = (
        250 * 6 * 5 * 3 * (2 + 10) / 3600
    )
    assert estimate["serial_hours_total"] == expected_hours
    assert estimate["serial_hours_by_tier"]["2000"] == 12.5
    assert estimate["serial_hours_by_tier"]["10000"] == 62.5


def test_descoping_drops_only_code_math_off_tiers() -> None:
    protocol = load_protocol()
    full = estimate_matrix_hours(protocol, setup_ms=1.0, cooldown_ms=2.0)
    descoped = estimate_matrix_hours(
        protocol,
        setup_ms=1.0,
        cooldown_ms=2.0,
        drop_off_tier_domains=("CODE", "MATH"),
    )
    assert descoped["serial_hours_total"] < full["serial_hours_total"]
    assert descoped["primary_cells_preserved"]
    assert descoped["positive_controls_preserved"]
