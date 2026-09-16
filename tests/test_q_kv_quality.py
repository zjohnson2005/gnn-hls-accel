"""Unit tests for Q-KV helpers (no hardware)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_q_kv_quality import (  # noqa: E402
    ARMS,
    _arm_order_for_entry,
    _contingency,
    _entry_emission_ok,
    analyze_paired,
)


def test_arm_order_is_permutation_and_deterministic() -> None:
    a = _arm_order_for_entry("multi_turn_base_0", seed=20260915)
    b = _arm_order_for_entry("multi_turn_base_0", seed=20260915)
    assert a == b
    assert sorted(a) == sorted(ARMS)
    c = _arm_order_for_entry("multi_turn_base_1", seed=20260915)
    # Different entries should usually differ; at least both are perms.
    assert sorted(c) == sorted(ARMS)


def test_entry_emission_ok() -> None:
    assert _entry_emission_ok({"turn_metrics": [{"n_decoded_steps": 1}, {"n_decoded_steps": 2}]})
    assert not _entry_emission_ok(
        {"turn_metrics": [{"n_decoded_steps": 1}, {"n_decoded_steps": 0}]}
    )
    assert not _entry_emission_ok({"turn_metrics": []})


def test_mcnemar_contingency_and_analyze() -> None:
    # Construct paired rows where f16 beats u8 on emission.
    entry_ids = [f"e{i}" for i in range(10)]
    by_arm = {a: {} for a in ARMS}
    for i, eid in enumerate(entry_ids):
        # f16 always emits; u8 fails first 8; u4 fails all
        by_arm["gpu_only_f16"][eid] = {
            "emission_ok": True,
            "trajectory_pass": i < 2,
        }
        by_arm["gpu_only_u8"][eid] = {
            "emission_ok": i >= 8,
            "trajectory_pass": i < 1,
        }
        by_arm["gpu_only_u4"][eid] = {
            "emission_ok": False,
            "trajectory_pass": False,
        }
    paired = analyze_paired(by_arm, entry_ids)
    assert paired["per_arm"]["gpu_only_f16"]["emission_failures"] == 0
    assert paired["per_arm"]["gpu_only_u8"]["emission_failures"] == 8
    assert paired["per_arm"]["gpu_only_u4"]["emission_failures"] == 10
    blk = paired["emission"]["gpu_only_f16__vs__gpu_only_u8"]
    assert blk["table_2x2"]["first_only"] == 8  # f16 ok, u8 fail
    assert blk["mcnemar"]["discordant"] == 8
    assert blk["mcnemar"]["p_value"] < 0.05
    # Should not agree (KV axis not falsified).
    assert paired["falsification"]["emission_arms_agree"] is False


def test_contingency_zero_discordant() -> None:
    a = [True, False, True]
    b = [True, False, True]
    c = _contingency(a, b)
    assert c["mcnemar"]["discordant"] == 0
    assert c["mcnemar"]["p_value"] == 1.0


if __name__ == "__main__":
    test_arm_order_is_permutation_and_deterministic()
    test_entry_emission_ok()
    test_mcnemar_contingency_and_analyze()
    test_contingency_zero_discordant()
    print("PASS tests/test_q_kv_quality.py")
