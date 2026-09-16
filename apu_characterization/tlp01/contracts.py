"""Frozen data contracts for TLP-01."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

PROTOCOL_VERSION = "tlp01_v2.1"
PROTOCOL_PATH = Path(__file__).with_name("protocol_tlp01_v2.json")
PROTOCOL_V1_PATH = Path(__file__).with_name("protocol_tlp01_v1.json")
EXPECTATIONS_PATH = Path(__file__).resolve().parents[1] / "PREDICTIONS_TLP01.md"
DIED_LEDGER_PATH = Path(__file__).with_name("died_ledger.json")
FORBIDDEN_CLAIM_FRAGMENTS = (
    "harvested by nobody",
    "universally unharvested",
    "nobody harvests",
    "first to parallelize",
    "field is single-issue",
)

EventType = Literal["turn", "tool_call", "delegation"]
DependenceTier = Literal["Tier_S", "Tier_C", "Tier_J"]
MachineModel = Literal["M0", "M1a", "M1b", "M2", "M3", "M4", "M5"]
TRACE_SCHEMA_VERSION = "tlp01_trace_v2"
REQUIRED_EVENT_FIELDS = (
    "session_id",
    "seq",
    "event_type",
    "t_issue_ns",
    "t_complete_ns",
    "inputs_hash",
    "output_hash",
    "output_text_ref",
    "tool_name",
    "args_ref",
    "result_ref",
    "stage_timings",
    "harness_order_index",
    "dep_refs",
)
GATE_NAMES = ("G_V", "G_D", "G_A", "G_R", "G_J")
MACHINE_MODELS = ("M0", "M1a", "M1b", "M2", "M3", "M4", "M5")
MULTI_TOOL_TASK_CLASSES = ("FO", "SH", "RH", "RE", "CH", "SO", "LH")


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
        raise ValueError("TLP-01 protocol version mismatch")
    return protocol


def protocol_sha256(path: Path = PROTOCOL_PATH) -> str:
    return sha256_json(load_protocol(path))


def expectations_sha256(path: Path = EXPECTATIONS_PATH) -> str:
    return sha256_bytes(path.read_bytes())


def validate_template(protocol: Mapping[str, Any] | None = None) -> list[str]:
    protocol = dict(protocol or load_protocol())
    errors: list[str] = []
    if protocol.get("status") != "template_requires_t0_lock":
        errors.append("source template status must be template_requires_t0_lock")
    if protocol.get("validity_class") != "turn_level_parallelism":
        errors.append("validity_class must be turn_level_parallelism")
    if protocol.get("study_form") != "trace_driven_limit_study":
        errors.append("study_form must be trace_driven_limit_study")
    schema = protocol.get("trace_schema") or {}
    if schema.get("version") != TRACE_SCHEMA_VERSION:
        errors.append("trace schema version mismatch")
    missing_fields = set(REQUIRED_EVENT_FIELDS) - set(schema.get("required_fields") or [])
    if missing_fields:
        errors.append(f"trace schema missing fields: {sorted(missing_fields)}")
    if "dep_refs" not in (schema.get("required_fields") or []):
        errors.append("trace schema must require dep_refs (Tier-0)")
    for gate in GATE_NAMES:
        if gate not in (protocol.get("gates") or {}):
            errors.append(f"missing gate {gate}")
    for model in MACHINE_MODELS:
        if model not in (protocol.get("machine_models") or {}):
            errors.append(f"missing machine model {model}")
    oracles = protocol.get("dependence_oracles") or {}
    for tier in ("Tier_0", "Tier_S", "Tier_C", "Tier_J"):
        if tier not in oracles:
            errors.append(f"missing dependence oracle {tier}")
    if oracles.get("Tier_J", {}).get("headline_load_bearing") is not False:
        errors.append("Tier_J must not be headline-load-bearing")
    if oracles.get("headline_form") != "S_C_bracket_never_point":
        errors.append("headline form must be S/C bracket")
    g_d = (protocol.get("gates") or {}).get("G_D") or {}
    if not (g_d.get("tier0_extension") or {}).get("rule"):
        errors.append("G_D must declare Tier-0 ⊆ Tier-C extension for T1")
    if not protocol.get("blocked_claims"):
        errors.append("blocked_claims must be non-empty")
    # Scan affirmative claim surfaces only — blocked_claims may name the bans.
    affirmative = " ".join(
        [
            str(protocol.get("claim_under_test") or ""),
            str(protocol.get("pre_registered_null_ceiling") or ""),
            str(protocol.get("pre_registered_null_frontier") or ""),
            str(protocol.get("pre_registered_null") or ""),
        ]
    )
    ladder = protocol.get("claim_ladder") or {}
    for track in ("ceiling_track", "frontier_track"):
        for entry in (ladder.get(track) or {}).values():
            if isinstance(entry, Mapping):
                affirmative += " " + str(entry.get("language") or "")
    lowered = affirmative.lower()
    for fragment in FORBIDDEN_CLAIM_FRAGMENTS:
        if fragment in lowered:
            errors.append(f"forbidden claim language in affirmative surface: {fragment}")
    if "ceiling_track" not in ladder or "frontier_track" not in ladder:
        errors.append("claim_ladder must expose ceiling_track and frontier_track")
    frontier = protocol.get("speculation_frontier") or {}
    if not frontier.get("penalty_axis_ns"):
        errors.append("speculation_frontier.penalty_axis_ns required")
    if not frontier.get("policies"):
        errors.append("speculation_frontier.policies required")
    timer = protocol.get("timer_resolution") or {}
    if int(timer.get("sub_ms_absolute_floor_ns") or 0) < 5000:
        errors.append("sub-ms absolute floor must be frozen at >= 5000 ns")
    projection = protocol.get("projection") or {}
    if projection.get("tier") != "D":
        errors.append("Praetor penalty projection must be Tier D")
    if projection.get("blocked_subject_claim") != "Praetor achieves":
        errors.append("blocked_subject_claim must quarantine Praetor achieves")
    if projection.get("boundary_location_tier") != "A_or_B_from_traces_never_D":
        errors.append("boundary location must be Tier A/B, never D")
    s3 = (protocol.get("trace_sources") or {}).get("S3") or {}
    if s3.get("required_for_v1") is not False:
        errors.append("S3 must remain optional for v1")
    g_v = (protocol.get("gates") or {}).get("G_V") or {}
    if float(g_v.get("relative_tolerance", -1)) != 0.05:
        errors.append("G_V relative tolerance must be 0.05")
    g_j = (protocol.get("gates") or {}).get("G_J") or {}
    if float(g_j.get("kappa_threshold", -1)) != 0.6:
        errors.append("G_J kappa threshold must be 0.6")
    g_r = (protocol.get("gates") or {}).get("G_R") or {}
    if int(g_r.get("required_seeds", 0)) != 5:
        errors.append("G_R required_seeds must be 5")
    citations = protocol.get("related_work_required_citations") or []
    required_keys = {
        "PASTE_B_PASTE",
        "SPORK",
        "LLMCompiler_GAP",
        "LLM_Tool_Compiler_oracle_ablation",
        "Governed_MCP",
    }
    got_keys = {item.get("key") for item in citations}
    if not required_keys.issubset(got_keys):
        errors.append(f"related_work missing keys: {sorted(required_keys - got_keys)}")
    return errors


def validate_lock(locked: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if locked.get("protocol_version") != PROTOCOL_VERSION:
        errors.append("locked protocol version mismatch")
    if locked.get("status") != "locked":
        errors.append("locked protocol status must be locked")
    fields = locked.get("lock_fields") or {}
    for key in (
        "trace_schema_sha256",
        "s2_task_manifest_sha256",
        "expectations_sha256",
        "dependence_oracle_config_sha256",
        "machine_model_ladder_sha256",
        "speculation_frontier_sha256",
    ):
        value = fields.get(key)
        if not isinstance(value, str) or len(value) != 64:
            errors.append(f"lock_fields.{key} must be a sha256 hex digest")
    errors.extend(
        err
        for err in validate_template({**locked, "status": "template_requires_t0_lock"})
        if "template status" not in err
    )
    return errors


@dataclass(frozen=True)
class TraceEvent:
    session_id: str
    seq: int
    event_type: EventType
    t_issue_ns: int
    t_complete_ns: int
    inputs_hash: str
    output_hash: str
    output_text_ref: str | None
    tool_name: str | None
    args_ref: str | None
    result_ref: str | None
    stage_timings: Mapping[str, Any]
    harness_order_index: int
    task_class: str = ""
    seed: int = 0
    control_parent_seq: int | None = None
    produced_paths: tuple[str, ...] = ()
    result_ids: tuple[str, ...] = ()
    input_text: str = ""
    output_text: str = ""
    dep_refs: tuple[int, ...] | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TraceEvent":
        missing = [field for field in REQUIRED_EVENT_FIELDS if field not in value]
        if missing:
            raise ValueError(f"trace event missing fields: {missing}")
        event_type = str(value["event_type"])
        if event_type not in ("turn", "tool_call", "delegation"):
            raise ValueError(f"unsupported event_type: {event_type}")
        issue = int(value["t_issue_ns"])
        complete = int(value["t_complete_ns"])
        if complete < issue:
            raise ValueError("t_complete_ns must be >= t_issue_ns")
        raw_deps = value.get("dep_refs")
        if raw_deps is None:
            dep_refs: tuple[int, ...] | None = None
        else:
            dep_refs = tuple(int(x) for x in raw_deps)
            if any(d < 0 for d in dep_refs):
                raise ValueError("dep_refs must be non-negative seq numbers")
        return cls(
            session_id=str(value["session_id"]),
            seq=int(value["seq"]),
            event_type=event_type,  # type: ignore[arg-type]
            t_issue_ns=issue,
            t_complete_ns=complete,
            inputs_hash=str(value["inputs_hash"]),
            output_hash=str(value["output_hash"]),
            output_text_ref=(
                None
                if value.get("output_text_ref") is None
                else str(value["output_text_ref"])
            ),
            tool_name=(
                None if value.get("tool_name") is None else str(value["tool_name"])
            ),
            args_ref=None if value.get("args_ref") is None else str(value["args_ref"]),
            result_ref=(
                None if value.get("result_ref") is None else str(value["result_ref"])
            ),
            stage_timings=dict(value.get("stage_timings") or {}),
            harness_order_index=int(value["harness_order_index"]),
            task_class=str(value.get("task_class") or ""),
            seed=int(value.get("seed") or 0),
            control_parent_seq=(
                None
                if value.get("control_parent_seq") is None
                else int(value["control_parent_seq"])
            ),
            produced_paths=tuple(str(p) for p in (value.get("produced_paths") or ())),
            result_ids=tuple(str(i) for i in (value.get("result_ids") or ())),
            input_text=str(value.get("input_text") or ""),
            output_text=str(value.get("output_text") or ""),
            dep_refs=dep_refs,
        )

    @property
    def duration_ns(self) -> int:
        return self.t_complete_ns - self.t_issue_ns

    @property
    def orch_ns(self) -> int:
        timings = self.stage_timings
        if "orch_ns" in timings:
            return int(timings["orch_ns"])
        total = 0
        for key, value in timings.items():
            if str(key).upper().startswith("ORCH") or str(key).endswith("_orch_ns"):
                total += int(value)
        return total

    def node_id(self) -> str:
        return f"{self.session_id}:{self.seq}"
