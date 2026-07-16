"""Frozen protocol contracts for TurnTrace v2 (rev. B)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

PROTOCOL_VERSION = "turntrace_v2.0"
PROTOCOL_PATH = Path(__file__).with_name("protocol_turntrace_v2.json")
TOOL_MANIFEST_PATH = Path(__file__).with_name("tool_manifest.json")

CacheState = str  # cold | warm-hit | warm-partial | disabled
ReasoningMode = str  # on | off | n/a
ToolClass = str  # read_only | state_mutating | none
NetworkMethod = str  # measured | estimated:<method>
PrefillMethod = str  # direct | ttft_derived

DEPLOYMENT_IDS = ("L1a", "L1b", "L2", "L3", "C1", "C2")
CACHE_MODES = ("engine-default", "cache-disabled", "ideal-cache-simulated")
CACHE_STATES = ("cold", "warm-hit", "warm-partial", "disabled")
REASONING_MODES = ("on", "off", "n/a")
TOOL_CLASSES = ("read_only", "state_mutating", "none")
AUDIT_FLAGS = (
    "residual_exceeds_budget",
    "profile_drift",
    "cache_state_unverified",
    "token_count_mismatch",
    "power_mode_changed",
    "negative_prefill_residual",
    "missing_replay_bundle",
    "attribution_out_of_domain",
    "token_accounting_anomaly",
    "implausible_cold_sample",
)

FORBIDDEN_CLAIM_FRAGMENTS = (
    "v2 implements routing",
    "v2 runs layer 1 swap sweeps at scale",
    "mechanism layer is validated across domains",
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != PROTOCOL_VERSION:
        raise ValueError("TurnTrace v2 protocol version mismatch")
    return protocol


def protocol_sha256(path: Path = PROTOCOL_PATH) -> str:
    return sha256_json(load_protocol(path))


def load_tool_manifest(path: Path = TOOL_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_protocol(protocol: Mapping[str, Any] | None = None) -> list[str]:
    protocol = dict(protocol or load_protocol())
    errors: list[str] = []
    if protocol.get("protocol_version") != PROTOCOL_VERSION:
        errors.append("protocol_version mismatch")
    if protocol.get("validity_class") != "turn_decomposition_and_layer1_handoff":
        errors.append("validity_class mismatch")
    if protocol.get("revision") != "B":
        errors.append("revision must be B")
    locked = protocol.get("locked_decisions") or {}
    if locked.get("step_unit") != "one_model_call_equals_one_step":
        errors.append("step_unit must be one_model_call_equals_one_step")
    required_call = set(protocol.get("call_record_required_fields") or [])
    for field in (
        "retemplated_tokens",
        "step_features",
        "pred_t_prefill_ms",
        "reasoning_mode",
    ):
        if field not in required_call:
            errors.append(f"CallRecord missing required field {field}")
    traj = set(protocol.get("trajectory_record_required_fields") or [])
    if "replay_bundle_path" not in traj:
        errors.append("TrajectoryRecord must require replay_bundle_path")
    replay = protocol.get("replay_bundle") or {}
    if not replay.get("mandatory_for_headline"):
        errors.append("replay_bundle.mandatory_for_headline must be true")
    cal = protocol.get("calibration") or {}
    if float(cal.get("r2_gate") or 0) < 0.99:
        errors.append("calibration.r2_gate must be >= 0.99")
    affirmative = " ".join(
        [
            str(protocol.get("claim_under_test") or ""),
            str(protocol.get("status") or ""),
        ]
    ).lower()
    for fragment in FORBIDDEN_CLAIM_FRAGMENTS:
        if fragment in affirmative:
            errors.append(f"forbidden claim fragment in affirmative text: {fragment}")
    for dep in DEPLOYMENT_IDS:
        if dep not in (protocol.get("deployments") or {}):
            errors.append(f"missing deployment {dep}")
    return errors
