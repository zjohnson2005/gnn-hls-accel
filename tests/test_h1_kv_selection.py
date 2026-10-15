"""DEMO-1 amendment 2026-10-13c (3c): selectable KV precision for the H1 local arm.

Default stays u8; u4 and f16 go through the existing arm table and the
pipeline KV readback refuses a mismatch. Hardware-free.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.run_h1_hybrid as rh  # noqa: E402

LAUNCHER = ROOT / "tools" / "launch_h1.ps1"


def _meta(normalized: str) -> dict:
    return {
        "loads": [
            {
                "device": "GPU",
                "kv_cache_precision": {
                    "requested": normalized,
                    "readback": {
                        "property": "KV_CACHE_PRECISION",
                        "device": "GPU",
                        "raw": "x",
                        "to_string": normalized,
                        "normalized": normalized,
                        "ok": True,
                        "error": None,
                    },
                    "match": True,
                    "enforced": True,
                    "failure_mode": None,
                },
            }
        ]
    }


def test_default_kv_is_unchanged_u8() -> None:
    for policy in ("slo_escalate", "emission_escalate", "full_signal_bounceback", "local_only"):
        assert rh.local_arm_settings(policy)["kv"] == "u8"
    assert rh.arm_id_for_h1(rh.local_arm_settings("slo_escalate")) == "gpu_only_u8"


@pytest.mark.parametrize(
    ("kv", "arm"), [("u8", "gpu_only_u8"), ("u4", "gpu_only_u4"), ("f16", "gpu_only_f16")]
)
def test_kv_selects_the_arm(kv: str, arm: str) -> None:
    settings = rh.local_arm_settings("slo_escalate", kv=kv)
    assert settings["kv"] == kv
    assert rh.arm_id_for_h1(settings) == arm


def test_kv_refusals() -> None:
    with pytest.raises(SystemExit, match="kv"):
        rh.local_arm_settings("slo_escalate", kv="i8")
    with pytest.raises(SystemExit, match="gpu_only"):
        rh.local_arm_settings("slo_escalate", placement="cpu-p", kv="u4")


def test_cli_kv_option() -> None:
    args = rh.build_argparser().parse_args(["--policy", "slo_escalate"])
    assert args.kv is None
    args = rh.build_argparser().parse_args(["--policy", "slo_escalate", "--kv", "u4"])
    assert args.kv == "u4"
    with pytest.raises(SystemExit):
        rh.build_argparser().parse_args(["--policy", "slo_escalate", "--kv", "i4"])


def test_make_openvino_local_passes_kv(monkeypatch) -> None:
    seen: dict = {}

    def fake_backend(**kwargs):
        seen.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    monkeypatch.setattr(rh, "OpenVinoLocalBackend", fake_backend)
    rh._make_openvino_local("slo_escalate", None, residency="RESIDENT", kv="u4")
    assert seen["kv"] == "u4" and seen["residency"] == "RESIDENT"
    assert seen["placement"] == "gpu_only"
    rh._make_openvino_local("slo_escalate", None)
    assert seen["kv"] == "u8"


def test_plan_arm_config_records_the_loaded_kv() -> None:
    local = types.SimpleNamespace(placement="gpu_only", residency="RESIDENT", kv="u4")
    arm = rh.arm_config_for("slo_escalate", local)
    assert arm["kv"] == "u4" and arm["residency"] == "RESIDENT"
    stub = types.SimpleNamespace()
    assert rh.arm_config_for("slo_escalate", stub)["kv"] == "u8"


def test_readback_refusal_is_kept() -> None:
    rh.OpenVinoLocalBackend._assert_kv_readback(_meta("u4"), expected="u4")
    with pytest.raises(SystemExit, match="KV_PRECISION_MISMATCH"):
        rh.OpenVinoLocalBackend._assert_kv_readback(_meta("u8"), expected="u4")


def test_launcher_kv_parameter() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    # DEMO-2 added "default" (no KV property; readback must be dynamic).
    assert '[ValidateSet("", "u8", "u4", "f16", "default")]\n    [string]$Kv = ""' in text
    assert "$resolvedCmd = $resolvedCmd + ' --kv ' + $Kv" in text
    assert "if (-not [string]::IsNullOrWhiteSpace($Kv)) {" in text
    assert 'Refuse "-Kv applies to the gpu_only arm' in text
