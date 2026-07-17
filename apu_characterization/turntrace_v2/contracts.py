"""Frozen protocol contracts for TurnTrace v2 (rev. C)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

PROTOCOL_VERSION = "turntrace_v2.1"
PROTOCOL_PATH = Path(__file__).with_name("protocol_turntrace_v2.json")
PROTOCOL_LOCK_PATH = Path(__file__).with_name("protocol_turntrace_v2.lock.json")
PAYLOAD_MANIFEST_PATH = Path(__file__).with_name("rev_c_payload_manifest.json")
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
ARMS = ("baseline_naive", "orchestration_optimized")
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
    "pair_context_divergence",
    "append_discipline_violated",
    "quality_parity_failed",
    "provider_cache_reconciliation",
    "pair_missing",
    "cache_truth_unverified",
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
    protocol = load_protocol(path)
    lock = dict(protocol.get("protocol_lock") or {})
    lock.pop("sha256", None)
    protocol["protocol_lock"] = lock
    return sha256_json(protocol)


def validate_protocol_lock(
    protocol_path: Path = PROTOCOL_PATH,
    lock_path: Path = PROTOCOL_LOCK_PATH,
) -> list[str]:
    errors: list[str] = []
    if not Path(lock_path).is_file():
        return [f"missing protocol lock artifact: {lock_path}"]
    protocol = load_protocol(protocol_path)
    lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    observed = protocol_sha256(protocol_path)
    embedded = str((protocol.get("protocol_lock") or {}).get("sha256") or "")
    locked = str(lock.get("protocol_sha256") or "")
    if observed != embedded:
        errors.append(f"embedded protocol hash mismatch: {embedded} != {observed}")
    if observed != locked:
        errors.append(f"lock artifact hash mismatch: {locked} != {observed}")
    if lock.get("protocol_version") != PROTOCOL_VERSION:
        errors.append("lock artifact protocol_version mismatch")
    payload_path = Path(lock_path).with_name(
        str(lock.get("payload_manifest_path") or PAYLOAD_MANIFEST_PATH.name)
    )
    if not payload_path.is_file():
        errors.append(f"missing payload manifest: {payload_path}")
    else:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        embedded_payload_hash = str(payload.pop("manifest_sha256", ""))
        observed_payload_hash = sha256_json(payload)
        locked_payload_hash = str(lock.get("payload_manifest_sha256") or "")
        if observed_payload_hash != embedded_payload_hash:
            errors.append("payload manifest embedded hash mismatch")
        if observed_payload_hash != locked_payload_hash:
            errors.append("payload manifest lock hash mismatch")
        from apu_characterization.turntrace_v2.workload.rev_c_suite import (
            validate_frozen_payload_manifest,
        )

        errors.extend(validate_frozen_payload_manifest(payload_path))
    return errors


def load_tool_manifest(path: Path = TOOL_MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_protocol(protocol: Mapping[str, Any] | None = None) -> list[str]:
    protocol = dict(protocol or load_protocol())
    errors: list[str] = []
    if protocol.get("protocol_version") != PROTOCOL_VERSION:
        errors.append("protocol_version mismatch")
    if protocol.get("validity_class") != "orchestration_significance_characterization":
        errors.append("validity_class mismatch")
    if protocol.get("revision") != "C":
        errors.append("revision must be C")
    locked = protocol.get("locked_decisions") or {}
    if locked.get("step_unit") != "one_model_call_equals_one_step":
        errors.append("step_unit must be one_model_call_equals_one_step")
    required_call = set(protocol.get("call_record_required_fields") or [])
    for field in (
        "retemplated_tokens",
        "step_features",
        "pred_t_prefill_ms",
        "reasoning_mode",
        "arm",
        "interventions_active",
        "pair_id",
        "provider_cached_tokens",
        "structurally_redundant_tokens",
        "actually_recomputed_tokens",
    ):
        if field not in required_call:
            errors.append(f"CallRecord missing required field {field}")
    traj = set(protocol.get("trajectory_record_required_fields") or [])
    if "replay_bundle_path" not in traj:
        errors.append("TrajectoryRecord must require replay_bundle_path")
    for field in ("arm", "interventions_active", "pair_id", "usd_model_cost", "joules_total"):
        if field not in traj:
            errors.append(f"TrajectoryRecord missing required field {field}")
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
    errors.extend(validate_protocol_lock())
    return errors
