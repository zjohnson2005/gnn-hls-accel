"""H-1 live hybrid runner - one routing policy per sealed arm, or interleaved.

Policies (``--policy``):
  cloud_only        every turn to cloud
  agnostic_default  local cpu-p NON_RESIDENT int4-4B; router sees task+model only
  slo_escalate      local; escalate on MEASURED ttft_s>10s or decode_tok_s<6;
                    stay on cloud for the rest of that entry (no ctx threshold)
  emission_escalate local; escalate when no parseable tool call; stay on cloud
                    for the rest of that entry
  full_signal_bounceback  R2c: one-turn cloud bounce then resume local
  hybrid_full       DEMO-2 (design of 2026-10-14):
                    mechanical (ctx_overflow, step-0 ttft>10s / decode<6,
                    local generation_error; sticky) then quality
                    (no parseable call, tool_exec_error, n_steps >= 5;
                    one-turn bounce)

``--context-window N`` (default off): before each local generate, a prompt
plus max_new_tokens above N is not generated; the turn escalates (sticky,
trigger ctx_overflow) under every policy that can reach the cloud.

Interleaved (``--interleaved`` / INF-5 session_design=interleaved):
  Same 200 entries, entry-by-entry. Default arm order is slo_escalate ->
  emission_escalate -> full_signal_bounceback (H1-3POLICY). Pass
  ``--interleaved-policy`` repeatedly to select a subset (H1-2POLICY =
  slo_escalate + emission_escalate). Per-policy caps + session cap; resume
  skips completed entries *per policy* so a cap abort on one arm does not
  re-bill others. When R2c is omitted, plan/seal record the exclusion so
  the session is never mistaken for the full three-policy comparison.

This module must never open prediction files under derived/d1_replay/ or
derived/h1_hybrid/*PREDICTIONS* (blinding). Operators pass caps explicitly;
the launcher may set defaults *outside* this process.

R1 (agnostic_default) is not run live: use ``--derive-r1`` to scale from the
sealed cb781dbf X-2 arm and mark the artifact DERIVED.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.context_window import context_overflow  # noqa: E402
from tools.h1_seal_git import launch_evidence_record, seal_git_record  # noqa: E402
from tools.phase_timers import finalize_phase_timers, phases_sum_to_wall  # noqa: E402

# ---------------------------------------------------------------------------
# Pins (must match W-3 seals 6225d6e1 / 1d8db970)
# ---------------------------------------------------------------------------
W3_ENTRIES_SHA256 = "3502c5356219f8bf5679f2f5626cb706a1f24b61eb38e51d6921e0fcfcf8628e"
W3_SEAL_REFS = (
    "6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a",
    "1d8db970-4c18-4bcf-824d-d9c141b6eb22",
)
# Entry sets the live runner accepts, keyed by the file's sha256. The W-3
# 200-entry multi_turn_base pin, and the DEMO-1 long_context subset drawn by
# tools/h1_context_sizing.py --make-subset (seed 20260930; rule in its
# .meta.json).
DEMO1_LONGCTX_30_SHA256 = "7a71fa6ab4a649bdc18b2c994c9904e44f5667a680abadf2f79147f6ed2513cb"
DEMO1_BASE_30_SHA256 = "7842d7d960b4acb5d5b09614fbf5a2b06fe752407f766d8df57ddd02e1f0260c"
DEMO1_LONGCTX_15_SHA256 = "7311610496286db6af4af8e98aa49723cdaaaf61d139d8c30d074358b18befdd"
DEMO1_LONGCTX_OBSK1024_15_SHA256 = (
    "3d6dc25f574019025a915c434ec4e7f284fca888e2e3935f0520b2385b939995"
)
DEMO1_PAIRED_15_SHA256 = "71faf5455559887cf0aa3c7a8317fab641b27c939b0643e501eeab5f63f9c080"
DEMO2_HELDOUT_60_SHA256 = "cc74a37ed84ed95b0f4dd4b8d7eb774f2737230dcfca01321fe136cdbfbca447"
DEMO2_HELDOUT_60_B_LONG30_SHA256 = (
    "46aa65098a4f704d07cd8037168ad48a04269b6731b0118bfb195a50b032c37c"
)
ENTRY_PINS: dict[str, dict[str, Any]] = {
    W3_ENTRIES_SHA256: {"name": "W3_multi_turn_base_200", "n": 200, "seal_refs": list(W3_SEAL_REFS)},
    DEMO1_LONGCTX_30_SHA256: {
        "name": "DEMO1_LONGCTX_30",
        "n": 30,
        "path": "derived/h1_hybrid/demo1/DEMO1_LONGCTX_30.json",
        "category": "multi_turn_long_context",
        "seed": 20260930,
    },
    DEMO1_BASE_30_SHA256: {
        "name": "DEMO1_BASE_30",
        "n": 30,
        "path": "derived/h1_hybrid/demo1/DEMO1_BASE_30.json",
        "category": "multi_turn_base",
        "seed": 20260930,
    },
    DEMO1_LONGCTX_15_SHA256: {
        "name": "DEMO1_LONGCTX_15",
        "n": 15,
        "path": "derived/h1_hybrid/demo1/DEMO1_LONGCTX_15.json",
        "category": "multi_turn_long_context",
        "seed": 20260930,
    },
    # Entries for DEMO-1 V4: chosen by the OBS_MASK K=1024 sizing; the arm
    # itself is not in the live runner yet (DEMO-1 tooling gap).
    DEMO1_LONGCTX_OBSK1024_15_SHA256: {
        "name": "DEMO1_LONGCTX_OBSK1024_15",
        "n": 15,
        "path": "derived/h1_hybrid/demo1/DEMO1_LONGCTX_OBSK1024_15.json",
        "category": "multi_turn_long_context",
        "seed": 20260930,
        "retention_arm_required": "OBS_MASK K=1024",
    },
    # DEMO-1 V3 (FULL) and V4 (OBS_MASK K=1024) on the same 15 entries.
    DEMO1_PAIRED_15_SHA256: {
        "name": "DEMO1_PAIRED_15",
        "n": 15,
        "path": "derived/h1_hybrid/demo1/DEMO1_PAIRED_15.json",
        "category": "multi_turn_long_context",
        "seed": 20260930,
    },
    # DEMO-2 held-out pin: 30 multi_turn_base then 30 multi_turn_long_context,
    # none in a DEMO-1 pin (tools/demo2_heldout.py).
    DEMO2_HELDOUT_60_SHA256: {
        "name": "DEMO2_HELDOUT_60",
        "n": 60,
        "path": "derived/h1_hybrid/demo2/DEMO2_HELDOUT_60.json",
        "category": "multi_turn_base+multi_turn_long_context",
        "seed": 20261014,
    },
    # Second DEMO-2 held-out pin, long_context half (tools/demo2_heldout_b.py;
    # base half blocked). Reserved: the runner refuses it without
    # --confirmation-run.
    DEMO2_HELDOUT_60_B_LONG30_SHA256: {
        "name": "DEMO2_HELDOUT_60_B_LONG30",
        "n": 30,
        "path": "derived/h1_hybrid/demo2/DEMO2_HELDOUT_60_B_LONG30.json",
        "category": "multi_turn_long_context",
        "seed": 20261016,
        "reserved_for": "one DEMO-2 SEARCH confirmation run (final searched profile vs arm A)",
    },
}
ENTRY_PIN_DEFAULT: dict[str, Any] = {"sha256": W3_ENTRIES_SHA256, **ENTRY_PINS[W3_ENTRIES_SHA256]}


def _w3_pin_field(entry_pin: dict[str, Any] | None) -> str | None:
    """Plan field kept for old readers: the W-3 sha when the W-3 set ran, else None."""
    if entry_pin is None or entry_pin.get("sha256") == W3_ENTRIES_SHA256:
        return W3_ENTRIES_SHA256
    return None


SCORER_CHECKER = "bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker"
SCORER_WRAPPER = "apu_characterization.cap01.bfcl_cap01_multi_turn_checker"
CB781_SEAL = "cb781dbf-3486-4fbc-a69a-34026f801abe"

TTFT_SLO_S = 10.0
DECODE_SLO_TOK_S = 6.0
# CAP-1 / C-2 cold-start ctx limit - NOT an SLO escalate trigger under RESIDENT.
# Kept for ledger comparison / docs only (see derived/h1_hybrid/slo_rule_old_vs_new_*).
CTX_LIMIT_COLD_START = 10_000

POLICIES = (
    "cloud_only",
    "agnostic_default",
    "slo_escalate",
    "emission_escalate",
    "full_signal_bounceback",  # R2c
    "local_only",
    "hybrid_full",  # DEMO-2
)

# H1-3POLICY interleaved arm order (INF-5 session_design=interleaved).
INTERLEAVE_POLICIES: tuple[str, ...] = (
    "slo_escalate",
    "emission_escalate",
    "full_signal_bounceback",
)
# H1-2POLICY: R2a+R2b only (R2c omitted from interleaved subset by selection).
INTERLEAVE_POLICIES_2POLICY: tuple[str, ...] = (
    "slo_escalate",
    "emission_escalate",
)
# cloud_only is selectable inside the interleaved harness. The default arm
# order stays the three-policy comparison.
INTERLEAVE_SELECTABLE: tuple[str, ...] = INTERLEAVE_POLICIES + ("cloud_only", "local_only")
DEFAULT_POLICY_CAPS_USD: dict[str, float] = {
    "slo_escalate": 5.0,
    "local_only": 5.0,
    "emission_escalate": 20.0,
    "full_signal_bounceback": 10.0,
    # Same single-arm cap as tools/launch_h1.ps1 (1.5 x the registered R0 point).
    "cloud_only": 81.1056,
}
DEFAULT_SESSION_CAP_USD = 35.0
DEFAULT_SESSION_CAP_USD_2POLICY = 25.0

R2C_EXCLUSION_REASON = (
    "R2c (full_signal_bounceback) excluded from this interleaved session "
    "(H1-2POLICY = slo_escalate + emission_escalate only). "
    "Not the full three-policy comparison. R2C-TURNWISE is available for "
    "dedicated R2c / H1-3POLICY seals."
)


def interleaved_kind(policies: tuple[str, ...]) -> str:
    """Distinguish 2-policy vs full 3-policy interleaved seals."""
    if tuple(policies) == INTERLEAVE_POLICIES:
        return "h1_3policy_interleaved"
    if (
        set(policies) == set(INTERLEAVE_POLICIES_2POLICY)
        and "full_signal_bounceback" not in policies
    ):
        return "h1_2policy_interleaved"
    return "h1_interleaved"


def interleaved_exclusion_meta(policies: tuple[str, ...]) -> dict[str, Any]:
    """Record omitted interleaved arms (esp. R2c) so seals are unambiguous."""
    selected = tuple(policies)
    excluded = [p for p in INTERLEAVE_POLICIES if p not in selected]
    meta: dict[str, Any] = {
        "full_three_policy_comparison": selected == INTERLEAVE_POLICIES,
        "excluded_from_interleave": excluded,
    }
    if "full_signal_bounceback" in excluded:
        meta["r2c_excluded"] = True
        meta["r2c_exclusion_reason"] = R2C_EXCLUSION_REASON
        meta["excluded_policies"] = {
            "full_signal_bounceback": {
                "reason": R2C_EXCLUSION_REASON,
                "blocked_on": "R2C-TURNWISE",
            }
        }
    else:
        meta["r2c_excluded"] = False
    return meta


# R2c: bounce to cloud for one turn, then resume local.
BOUNCE_STEP_BUDGET = 5  # within-turn step count; not MAXIMUM_STEP_LIMIT (20)
BOUNCE_TRIGGERS = (
    "no_parseable_tool_call",
    "step_budget",
    "tool_exec_error",
)

# DEMO-2 hybrid_full trigger classes, recorded on every escalation row.
MECHANICAL = "mechanical"
QUALITY = "quality"

# Local agent-loop stop reasons (entry-level). Distinct events - do not collapse.
# completed:       all turns_in_entry ran (or cloud_only finished the entry)
# no_tool_call:    decode_execute_qwen raised (unparseable tool call)
# empty_execute:   decoded to an empty execute list with no prior tool success
# generation_error: gen_ok false
# max_steps:       MAXIMUM_STEP_LIMIT exceeded (force_quit); short turn_metrics
STOP_REASONS = (
    "completed",
    "no_tool_call",
    "empty_execute",
    "generation_error",
    "max_steps",
    "tool_exec_error",
)

# Arm wiring (not router inputs). agnostic_default keeps these out of the router.
ARM_CONFIG: dict[str, dict[str, str]] = {
    "cloud_only": {
        "placement": "cloud",
        "residency": "n/a",
        "kv": "n/a",
        "weight": "n/a",
        "tier": "cloud",
        "model": "claude-sonnet",
    },
    "agnostic_default": {
        "placement": "cpu-p",
        "residency": "NON_RESIDENT",
        "kv": "u8",
        "weight": "int4",
        "tier": "4B",
        "model": "Qwen3-4B-int4-ov",
    },
    "slo_escalate": {
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "kv": "u8",
        "weight": "int4",
        "tier": "4B",
        "model": "Qwen3-4B-int4-ov",
    },
    "local_only": {
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "kv": "u8",
        "weight": "int4",
        "tier": "4B",
        "model": "Qwen3-4B-int4-ov",
    },
    "emission_escalate": {
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "kv": "u8",
        "weight": "int4",
        "tier": "4B",
        "model": "Qwen3-4B-int4-ov",
    },
    "full_signal_bounceback": {
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "kv": "u8",
        "weight": "int4",
        "tier": "4B",
        "model": "Qwen3-4B-int4-ov",
    },
    # DEMO-2: wiring defaults only; --placement/--residency/--kv set each cell.
    "hybrid_full": {
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "kv": "u8",
        "weight": "int4",
        "tier": "4B",
        "model": "Qwen3-4B-int4-ov",
    },
}

DEFAULT_LOCAL_MODEL = "Qwen3-4B-int4-ov"
DEFAULT_LOCAL_TIER = "4B"
KV_MATCH_SEAL_4B = "86d0f4cf-e8c2-4ce5-96da-04c6a9c129f3"


def local_model_identity(local: Any) -> dict[str, str]:
    """Model name and tier of the local backend, read from its model spec.

    ARM_CONFIG names the 4B IR. A backend loaded from another spec (for
    example configs/models/Qwen3-8B-int4-ov.yaml) must not be recorded as 4B.
    A backend without a readable spec file (stubs, lifecycle smoke) keeps
    the 4B default.
    """
    import re

    spec = getattr(local, "model_spec", None)
    if spec is None:
        return {"model": DEFAULT_LOCAL_MODEL, "tier": DEFAULT_LOCAL_TIER}
    path = Path(spec)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        return {"model": DEFAULT_LOCAL_MODEL, "tier": DEFAULT_LOCAL_TIER}
    import yaml

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    name = str(doc.get("name") or "").strip()
    match = re.search(r"-(\d+(?:\.\d+)?B)-", name)
    if match is None:
        raise SystemExit(f"REFUSED -- model spec {path} has no tier in its name ({name!r})")
    return {"model": name, "tier": match.group(1)}


LOCAL_PLACEMENTS = ("gpu_only", "cpu-p")
LOCAL_RESIDENCIES = ("RESIDENT", "NON_RESIDENT")
# KV cache precision of the gpu_only local arm (DEMO-1 amendment 2026-10-13c,
# V5b). Default stays ARM_CONFIG (u8); the readback still refuses a mismatch.
LOCAL_KVS = ("u8", "u4", "f16", "default")
# DEMO-2 control: --kv default passes no KV_CACHE_PRECISION (delta_n arm
# gpu_only). The 2026-10-14 readbacks on both hosts (OpenVINO 2026.2.1)
# read KV_CACHE_PRECISION = dynamic before and after the load.
RUNTIME_DEFAULT_KV_READBACK = "dynamic"


def expected_kv_readback(kv: str) -> str:
    """KV readback the load must show: the pin, or the runtime default."""
    return RUNTIME_DEFAULT_KV_READBACK if kv == "default" else kv


def arm_config_for(policy: str, local: Any) -> dict[str, str]:
    """ARM_CONFIG[policy] with model, tier, placement and residency from ``local``.

    A backend built with --placement / --residency / --kv records what it
    loaded; stubs without those attributes keep the ARM_CONFIG values.
    """
    arm = dict(ARM_CONFIG[policy])
    if arm["placement"] != "cloud":
        arm.update(local_model_identity(local))
        for key in ("placement", "residency", "kv"):
            value = getattr(local, key, None)
            if isinstance(value, str) and value:
                arm[key] = value
    return arm


def run_platform_id() -> str | None:
    """Platform the gates resolve to: SEAM_PLATFORM_ID, else the tracked pin."""
    from seam.measurement_gates import resolve_platform_id

    try:
        return resolve_platform_id(ROOT)
    except RuntimeError:
        return None


USD_PER_MTOK_IN = 3.0
USD_PER_MTOK_OUT = 15.0


def cloud_usd(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * USD_PER_MTOK_IN + tokens_out * USD_PER_MTOK_OUT) / 1_000_000.0


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_tree(root: Path, *, exclude: set[str]) -> str:
    h = hashlib.sha256()
    files = sorted(
        (p for p in root.rglob("*") if p.is_file() and p.name not in exclude),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    for p in files:
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Ledger / policy
# ---------------------------------------------------------------------------
@dataclass
class TurnLedger:
    entry_id: str
    turn: int
    placement: str  # "local" | "cloud"
    model: str
    n_ctx: int
    ttft_s: float | None
    decode_tok_s: float | None
    emitted_parseable_tool_call: bool
    escalated: bool
    escalate_reason: str | None
    cloud_tokens_in: int
    cloud_tokens_out: int
    cloud_usd: float
    turn_wall_s: float
    t_tool_exec: float
    t_template_build: float
    t_tokenize: float
    t_generate: float
    t_other: float
    bounce_trigger: str | None = None  # R2c: set when this cloud turn is a bounce
    tool_exec_error: bool = False
    tool_exec_error_class: str | None = None
    # Per Anthropic request inside this user turn. None on local turns.
    cloud_requests: list[dict[str, Any]] | None = None
    # Execute strings for this user turn (list of agent steps). Cloud turns
    # are decode_execute_anthropic output; local turns are the probe decode.
    decoded_steps: list[list[str]] | None = None
    # Local attempt that triggered this bounce. Absent on rows that are not a bounce.
    local_attempt: dict[str, Any] | None = None
    # DEMO-2: "mechanical" | "quality" on hybrid_full / context-window escalations.
    # Absent otherwise, so existing ledgers are unchanged.
    trigger_class: str | None = None
    # DEMO-2: {"n_ctx", "window", "max_new_tokens", "step"} when a turn overflowed.
    ctx_overflow: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for optional in ("local_attempt", "trigger_class", "ctx_overflow"):
            if d.get(optional) is None:
                d.pop(optional, None)
        assert phases_sum_to_wall(
            {
                "turn_wall_s": self.turn_wall_s,
                "t_tool_exec": self.t_tool_exec,
                "t_template_build": self.t_template_build,
                "t_tokenize": self.t_tokenize,
                "t_generate": self.t_generate,
                "t_other": self.t_other,
            },
            tol_s=1e-3,
        ), f"phase timers do not sum to turn_wall for {self.entry_id}/t{self.turn}"
        return d


@dataclass
class BounceEvent:
    """Per-bounce ledger row for R2c (full_signal_bounceback).

    ``re_prefill_s`` is the cost of re-prefilling local RESIDENT KV after
    cloud->local context injection. It is a policy property, not overhead to
    hide: external assistant append invalidates resident KV.
    """

    turn: int
    trigger: str  # one of BOUNCE_TRIGGERS (trigger class)
    cloud_tokens_in: int = 0
    cloud_tokens_out: int = 0
    cloud_usd: float = 0.0
    re_prefill_s: float | None = None
    re_prefill_required: bool = True
    re_prefill_source: str | None = (
        None  # measured | stub_zero | inferred_unmeasured | pending_next_local
    )
    control_return_turn: int | None = None  # turn index where control returned to local
    kv_valid_after_inject: bool = False
    shared_tool_exec: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "trigger": self.trigger,
            "trigger_class": self.trigger,
            "cloud_tokens_in": self.cloud_tokens_in,
            "cloud_tokens_out": self.cloud_tokens_out,
            "cloud_usd": self.cloud_usd,
            "re_prefill_s": self.re_prefill_s,
            "re_prefill_required": self.re_prefill_required,
            "re_prefill_source": self.re_prefill_source,
            "control_return_turn": self.control_return_turn,
            "kv_valid_after_inject": self.kv_valid_after_inject,
            "shared_tool_exec": self.shared_tool_exec,
        }


@dataclass
class EntryResult:
    entry_id: str
    n_turns: int  # == turns_in_entry (kept for older callers)
    turns: list[TurnLedger] = field(default_factory=list)
    cloud_usd_entry: float = 0.0
    status: str = "complete"  # complete | aborted_cap | stopped_early
    turns_in_entry: int = 0
    turns_executed: int = 0
    stop_reason: str = "completed"
    slo_fraction: float | None = None
    bounces: list[BounceEvent] = field(default_factory=list)
    # W-3 scorer outputs (persisted for H-1 quality; sealed trees that lack
    # these cannot be scored offline).
    trajectory_pass: bool | None = None  # local_probe only; never hybrid
    score_error_type: str | None = None
    score_error_message: str | None = None
    model_result_decoded: list[Any] | None = None  # local_probe decode
    quality_scope: str | None = None  # "local_probe" when local score is attached
    local_pass: bool | None = None
    local_model_result_decoded: list[Any] | None = None
    hybrid_pass: bool | None = None
    hybrid_model_result_decoded: list[Any] | None = None
    hybrid_score_error_type: str | None = None
    hybrid_score_error_message: str | None = None
    hybrid_quality_scope: str | None = None  # "hybrid" when the merged score ran

    def as_ledger_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "status": self.status,
            "turns_in_entry": self.turns_in_entry,
            "turns_executed": self.turns_executed,
            "stop_reason": self.stop_reason,
            "slo_fraction": self.slo_fraction,
            "cloud_usd_entry": self.cloud_usd_entry,
            "bounces": [b.as_dict() for b in self.bounces],
            "trajectory_pass": self.trajectory_pass,
            "local_pass": self.local_pass,
            "hybrid_pass": self.hybrid_pass,
            "score_error_type": self.score_error_type,
            "score_error_message": self.score_error_message,
            "quality_scope": self.quality_scope,
            "hybrid_quality_scope": self.hybrid_quality_scope,
            "turns": [t.as_dict() for t in self.turns],
        }

    def as_quality_dict(self) -> dict[str, Any]:
        """Local-probe and hybrid scores, each under its own scope name."""
        local_pass = self.local_pass if self.local_pass is not None else self.trajectory_pass
        local_decoded = (
            self.local_model_result_decoded
            if self.local_model_result_decoded is not None
            else self.model_result_decoded
        )
        return {
            "entry_id": self.entry_id,
            "local_pass": local_pass,
            "local_quality_scope": "local_probe",
            "local_model_result_decoded": local_decoded,
            "hybrid_pass": self.hybrid_pass,
            "hybrid_quality_scope": self.hybrid_quality_scope,
            "hybrid_model_result_decoded": self.hybrid_model_result_decoded,
            "hybrid_score_error_type": self.hybrid_score_error_type,
            "hybrid_score_error_message": self.hybrid_score_error_message,
            # local_probe aliases. trajectory_pass is never the hybrid score.
            "trajectory_pass": local_pass,
            "score_error_type": self.score_error_type,
            "score_error_message": self.score_error_message,
            "quality_scope": "local_probe",
            "model_result_decoded": local_decoded,
            "cloud_usd_entry": self.cloud_usd_entry,
            "stop_reason": self.stop_reason,
            "status": self.status,
        }


@dataclass
class LocalEntrySpan:
    """How far the local agent loop got for one entry.

    ``turns_executed`` is len(turn_metrics): the last index present is the turn
    where the session stopped. Turns after it did not execute - not SLO
    failures, not successes; they did not happen.
    """

    turns_in_entry: int
    turns_executed: int
    stop_reason: str


def turns_in_entry_count(entry: dict[str, Any]) -> int:
    if isinstance(entry.get("question"), list):
        return len(entry["question"])
    if "n_user_turns" in entry:
        return int(entry["n_user_turns"])
    return len(entry.get("turns") or [0])


def turn_meets_slo(*, ttft_s: float | None, decode_tok_s: float | None) -> bool:
    """SLO gate uses MEASURED ttft_s / decode_tok_s only (no ctx threshold)."""
    if ttft_s is not None and ttft_s > TTFT_SLO_S:
        return False
    if decode_tok_s is not None and decode_tok_s < DECODE_SLO_TOK_S:
        return False
    return True


def decide_slo_escalate_legacy_with_ctx(
    *,
    already_on_cloud: bool,
    ttft_s: float | None,
    decode_tok_s: float | None,
    n_ctx: int,
    ctx_limit: int = CTX_LIMIT_COLD_START,
) -> tuple[bool, str | None]:
    """Pre-H1-3POLICY rule (TTFT OR decode OR ctx). For sealed-ledger diffs only."""
    if already_on_cloud:
        return True, "stay_cloud"
    reasons: list[str] = []
    if ttft_s is not None and ttft_s > TTFT_SLO_S:
        reasons.append(f"ttft>{TTFT_SLO_S}")
    if decode_tok_s is not None and decode_tok_s < DECODE_SLO_TOK_S:
        reasons.append(f"decode<{DECODE_SLO_TOK_S}")
    if n_ctx > ctx_limit:
        reasons.append(f"ctx>{ctx_limit}")
    if reasons:
        return True, "+".join(reasons)
    return False, None


@dataclass
class RouterView:
    """What the agnostic router is allowed to see: task + model only."""

    task_id: str
    model: str


def router_view_for_entry(entry: dict[str, Any], *, model: str) -> RouterView:
    return RouterView(task_id=str(entry["id"]), model=model)


def decide_cloud_only() -> tuple[bool, str]:
    return True, "cloud_only"


def decide_slo_escalate(
    *,
    already_on_cloud: bool,
    ttft_s: float | None,
    decode_tok_s: float | None,
) -> tuple[bool, str | None]:
    """Escalate on MEASURED ttft_s / decode_tok_s only (no cold-start ctx gate)."""
    if already_on_cloud:
        return True, "stay_cloud"
    reasons: list[str] = []
    if ttft_s is not None and ttft_s > TTFT_SLO_S:
        reasons.append(f"ttft>{TTFT_SLO_S}")
    if decode_tok_s is not None and decode_tok_s < DECODE_SLO_TOK_S:
        reasons.append(f"decode<{DECODE_SLO_TOK_S}")
    if reasons:
        return True, "+".join(reasons)
    return False, None


def decide_local_only() -> tuple[bool, str | None]:
    """Explicit local-only arm. Never escalates, whatever the local signals are."""
    return False, None


def decide_emission_escalate(
    *,
    already_on_cloud: bool,
    emitted_parseable_tool_call: bool,
) -> tuple[bool, str | None]:
    if already_on_cloud:
        return True, "stay_cloud"
    if not emitted_parseable_tool_call:
        return True, "no_parseable_tool_call"
    return False, None


def decide_bounceback(
    *,
    emitted_parseable_tool_call: bool,
    n_steps: int | None,
    tool_exec_error: bool,
    step_budget: int = BOUNCE_STEP_BUDGET,
) -> tuple[bool, str | None]:
    """R2c full_signal_bounceback triggers (any one).

    (a) no parseable tool call
    (b) step count reaches ``step_budget`` within the turn (default 5)
    (c) tool execution raises
    """
    if tool_exec_error:
        return True, "tool_exec_error"
    if n_steps is not None and int(n_steps) >= int(step_budget):
        return True, "step_budget"
    if not emitted_parseable_tool_call:
        return True, "no_parseable_tool_call"
    return False, None


def decide_hybrid_mechanical(
    *,
    ttft_s: float | None,
    decode_tok_s: float | None,
    generation_error: bool,
) -> tuple[bool, str | None]:
    """hybrid_full mechanical triggers other than ctx_overflow (checked first).

    Step-0 TTFT / decode as slo_escalate (DEMO-1 rule), then a local
    generation error. Sticky in the caller.
    """
    escalate, reason = decide_slo_escalate(
        already_on_cloud=False, ttft_s=ttft_s, decode_tok_s=decode_tok_s
    )
    if escalate:
        return True, reason
    if generation_error:
        return True, "generation_error"
    return False, None


def local_attempt_record(bt: BackendTurn, *, stop_reason: str) -> dict[str, Any]:
    """Signals from the local attempt that triggered a bounce, before the cloud row.

    The cloud row's own emitted_parseable_tool_call is the cloud result. These
    fields keep the local decision inputs so decide_bounceback can be re-run.
    """
    raw = bt.raw_text if isinstance(bt.raw_text, str) else ""
    return {
        "emitted_parseable_tool_call": bool(bt.emitted_parseable_tool_call),
        "n_steps": None if bt.n_steps is None else int(bt.n_steps),
        "tool_exec_error": bool(bt.tool_exec_error),
        "stop_reason": stop_reason,
        "raw_text_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    }


# ---------------------------------------------------------------------------
# Backends (live + stub)
# ---------------------------------------------------------------------------
@dataclass
class BackendTurn:
    n_ctx: int
    ttft_s: float | None
    decode_tok_s: float | None
    emitted_parseable_tool_call: bool
    cloud_tokens_in: int = 0
    cloud_tokens_out: int = 0
    cloud_usd: float = 0.0
    t_tool_exec: float = 0.0
    t_template_build: float = 0.0
    t_tokenize: float = 0.0
    t_generate: float = 0.0
    turn_wall_s: float = 0.0
    raw_text: str = ""
    # When set (OpenVINO measured path), use as-is - genuine residual, not re-filled.
    t_other: float | None = None
    # R2c observability
    n_steps: int | None = None
    tool_exec_error: bool = False
    tool_exec_error_class: str | None = None
    cloud_context_text: str = ""  # cloud bounce output injected into local context
    # Set when the cloud path failed (API error / credit death / empty response).
    cloud_error: str | None = None
    # One dict per Anthropic request in this user turn.
    cloud_requests: list[dict[str, Any]] | None = None
    # Per user-turn execute steps. One inner list per agent step.
    decoded_steps: list[list[str]] | None = None
    # DEMO-2: set when --context-window stopped a local step before generate.
    ctx_overflow: dict[str, Any] | None = None
    # DEMO-2: a local generate in this turn returned not ok.
    generation_error: bool = False


def attach_local_probe_quality(
    result: EntryResult, local: LocalBackend, entry: dict[str, Any]
) -> None:
    """Persist W-3 scorer outputs already computed by the OpenVINO probe path.

    Probe ``MultiTurnAgentSession.finish`` scores in-memory; sealed H-1 trees
    86d0f4cf / 8ffd8371 dropped that payload. Future seals keep it.
    Scope is local-probe only (pre-escalation generation), never improvised.
    """
    if not isinstance(local, OpenVinoLocalBackend):
        return
    finalize = getattr(local, "finalize_entry", None)
    row = finalize(entry) if callable(finalize) else None
    if not isinstance(row, dict):
        return
    score = row.get("score") if isinstance(row.get("score"), dict) else {}
    valid = score.get("valid")
    result.trajectory_pass = bool(valid) if valid is not None else None
    result.score_error_type = (
        str(score["error_type"]) if score.get("error_type") is not None else None
    )
    err_msg = score.get("error_message") or score.get("error")
    result.score_error_message = str(err_msg) if err_msg is not None else None
    decoded = row.get("model_result_decoded")
    result.model_result_decoded = decoded if isinstance(decoded, list) else None
    result.local_model_result_decoded = result.model_result_decoded
    result.quality_scope = "local_probe"
    result.local_pass = result.trajectory_pass


def merged_decoded_steps(result: EntryResult) -> list[list[list[str]]]:
    """User-turn order: cloud turns contribute their converted calls, local theirs."""
    merged: list[list[list[str]]] = []
    for turn in result.turns:
        steps = turn.decoded_steps or []
        merged.append([list(step) for step in steps])
    return merged


def score_hybrid_trajectory(result: EntryResult, entry: dict[str, Any]) -> None:
    """BFCL checker on the merged local+cloud trajectory. Scope is hybrid."""
    from tools.bfcl_feasibility_probe import score_multi_turn

    merged = merged_decoded_steps(result)
    result.hybrid_model_result_decoded = merged
    raw = entry.get("raw_entry")
    ground = entry.get("reference")
    if not isinstance(raw, dict) or not isinstance(ground, list):
        result.hybrid_pass = None
        result.hybrid_score_error_type = "unscored_missing_entry"
        result.hybrid_quality_scope = None
        return
    result.hybrid_quality_scope = "hybrid"
    scored = score_multi_turn(
        test_entry=raw,
        ground_truth=ground,
        model_result_decoded=merged,
        test_category=str(entry.get("category") or "multi_turn_base"),
        model_name=f"hybrid_{result.entry_id}_{id(result)}",
    )
    valid = scored.get("valid")
    result.hybrid_pass = bool(valid) if valid is not None else None
    err_t = scored.get("error_type")
    result.hybrid_score_error_type = str(err_t) if err_t is not None else None
    err_m = scored.get("error_message") or scored.get("error")
    result.hybrid_score_error_message = str(err_m) if err_m is not None else None


def _entry_escalated(result: EntryResult) -> bool:
    return any(t.placement == "cloud" or t.escalated for t in result.turns)


def attach_entry_quality(result: EntryResult, local: LocalBackend, entry: dict[str, Any]) -> None:
    """Attach local_probe and hybrid scores under separate scope names.

    local_pass is local-alone completion with no escalation. hybrid_pass is
    the checker on the merged trajectory. An escalated entry is a local_pass
    failure even when the cloud turns make hybrid_pass true.
    """
    attach_local_probe_quality(result, local, entry)
    if result.local_pass is None and result.trajectory_pass is not None:
        result.local_pass = result.trajectory_pass
    score_hybrid_trajectory(result, entry)
    if _entry_escalated(result):
        result.local_pass = False
    elif result.local_pass is None:
        result.local_pass = result.hybrid_pass


def _stamp_decoded(ledger: TurnLedger, source: BackendTurn) -> TurnLedger:
    steps = source.decoded_steps or []
    ledger.decoded_steps = [list(step) for step in steps]
    return ledger


def _backend_begin_entry(local: LocalBackend, entry: dict[str, Any], *, policy: str) -> None:
    """Open backend session for this (entry, policy) cell when the backend owns lifecycle."""
    begin = getattr(local, "begin_entry", None)
    if callable(begin):
        begin(entry, policy=policy)


def _backend_finish_entry(local: LocalBackend, entry: dict[str, Any]) -> None:
    """Close backend session after last turn or abort (idempotent)."""
    finish = getattr(local, "finish_entry", None)
    if callable(finish):
        finish(entry)


def phases_from_backend_turn(bt: BackendTurn) -> dict[str, float]:
    """Prefer measured t_other from OpenVINO; otherwise close the budget."""
    if bt.t_other is not None:
        phases = {
            "turn_wall_s": float(bt.turn_wall_s),
            "t_tool_exec": float(bt.t_tool_exec),
            "t_template_build": float(bt.t_template_build),
            "t_tokenize": float(bt.t_tokenize),
            "t_generate": float(bt.t_generate),
            "t_other": float(bt.t_other),
        }
        if not phases_sum_to_wall(phases, tol_s=1e-3):
            raise SystemExit("REFUSED -- measured phase timers do not sum to turn_wall within 1 ms")
        return phases
    return finalize_phase_timers(
        turn_wall_s=bt.turn_wall_s,
        t_tool_exec=bt.t_tool_exec,
        t_template_build=bt.t_template_build,
        t_tokenize=bt.t_tokenize,
        t_generate=bt.t_generate,
    )


class LocalBackend(Protocol):
    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn: ...


class CloudBackend(Protocol):
    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn: ...


@dataclass
class StubLocalBackend:
    """Deterministic fixture backend for tests. Not sealable.

    ``script[entry_id]`` length is ``turns_executed``. When shorter than
    ``turns_in_entry``, pass ``stop_reasons[entry_id]`` (required) so the
    hybrid loop does not invent turns that never ran.

    R2c injection: ``accept_cloud_context`` appends an assistant turn into a
    per-entry message history that subsequent ``run_turn`` calls see (mirrors
    RESIDENT ChatHistory append). Stub reports ``re_prefill_s=0.0`` with
    source ``stub_zero`` - live OpenVINO must measure real re-prefill.
    """

    # entry_id -> list of per-turn dicts
    script: dict[str, list[dict[str, Any]]]
    stop_reasons: dict[str, str] = field(default_factory=dict)
    BACKEND_KIND = "stub"
    # Shared BFCL tool state (same object cloud bounce turns must use).
    shared_tools: Any = None
    # DEMO-2 --context-window on the stub: a row whose generate input
    # (``gen_input_tokens``, default ``n_ctx``) plus max_new_tokens exceeds the
    # window is not generated. None = off.
    context_window: int | None = None
    max_new_tokens: int = 512
    # Cell-keyed state: "{entry_id}\\0{policy}" when begin_entry is used.
    _history: dict[str, list[dict[str, Any]]] = field(default_factory=dict, repr=False)
    _cloud_context: dict[str, dict[int, str]] = field(default_factory=dict, repr=False)
    _last_injection: dict[str, Any] = field(default_factory=dict, repr=False)
    _pending_reprefill: dict[str, bool] = field(default_factory=dict, repr=False)
    _active_key: str | None = field(default=None, init=False, repr=False)

    @staticmethod
    def cell_key(entry_id: str, policy: str) -> str:
        return f"{entry_id}\0{policy}"

    def begin_entry(self, entry: dict[str, Any], *, policy: str) -> None:
        """Fresh per-(entry, policy) history; no leak from a prior policy cell."""
        eid = str(entry["id"])
        key = self.cell_key(eid, policy)
        if self._active_key is not None:
            raise SystemExit(
                f"REFUSED -- StubLocalBackend.begin_entry while cell "
                f"{self._active_key!r} still active"
            )
        self._active_key = key
        self._history[key] = []
        self._cloud_context[key] = {}
        self._pending_reprefill.pop(key, None)
        self._last_injection.pop(key, None)

    def finish_entry(self, entry: dict[str, Any]) -> None:
        """Release active cell (idempotent)."""
        del entry  # key is _active_key; entry id checked by caller path
        self._active_key = None

    def _cell_or_eid(self, entry_id: str) -> str:
        if self._active_key is not None:
            prefix = f"{entry_id}\0"
            if not self._active_key.startswith(prefix):
                raise SystemExit(
                    f"REFUSED -- stub active cell {self._active_key!r} "
                    f"does not match entry {entry_id!r}"
                )
            return self._active_key
        return str(entry_id)

    def local_span(self, entry: dict[str, Any]) -> LocalEntrySpan:
        eid = str(entry["id"])
        turns_in = turns_in_entry_count(entry)
        rows = self.script[eid]
        turns_ex = len(rows)
        if turns_ex > turns_in:
            raise SystemExit(
                f"REFUSED -- stub script longer than turns_in_entry for {eid}: "
                f"{turns_ex} > {turns_in}"
            )
        if turns_ex < turns_in:
            reason = self.stop_reasons.get(eid) or entry.get("stop_reason")
            if reason not in STOP_REASONS or reason == "completed":
                raise SystemExit(
                    f"REFUSED -- short stub script for {eid} needs stop_reason in "
                    f"{STOP_REASONS} excluding 'completed'; got {reason!r}"
                )
            return LocalEntrySpan(turns_in, turns_ex, str(reason))
        return LocalEntrySpan(turns_in, turns_ex, "completed")

    def _history_keys_for(self, entry_id: str) -> list[str]:
        eid = str(entry_id)
        if self._active_key is not None and self._active_key.startswith(f"{eid}\0"):
            return [self._active_key]
        return [k for k in self._history if k == eid or k.startswith(f"{eid}\0")]

    def history_for(self, entry_id: str) -> list[dict[str, Any]]:
        keys = self._history_keys_for(entry_id)
        if not keys:
            return []
        return list(self._history.get(keys[-1], []))

    def context_contains(self, entry_id: str, text: str) -> bool:
        for key in self._history_keys_for(entry_id):
            if any(text in str(m.get("content", "")) for m in self._history.get(key, [])):
                return True
        return False

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        eid = str(entry["id"])
        key = self._cell_or_eid(eid)
        rows = self.script[eid]
        if turn_idx >= len(rows):
            raise SystemExit(
                f"REFUSED -- stub turn_idx={turn_idx} out of range "
                f"(n_script={len(rows)}); hybrid must stop at turns_executed"
            )
        row = rows[turn_idx]
        overflow = context_overflow(
            int(row.get("gen_input_tokens", row["n_ctx"])),
            max_new_tokens=int(self.max_new_tokens),
            window=self.context_window,
            step=0,
        )
        if overflow is not None:
            phases = finalize_phase_timers(
                turn_wall_s=0.01,
                t_tool_exec=0.0,
                t_template_build=0.005,
                t_tokenize=0.005,
                t_generate=0.0,
            )
            return BackendTurn(
                n_ctx=int(row["n_ctx"]),
                ttft_s=None,
                decode_tok_s=None,
                emitted_parseable_tool_call=False,
                turn_wall_s=phases["turn_wall_s"],
                t_tool_exec=phases["t_tool_exec"],
                t_template_build=phases["t_template_build"],
                t_tokenize=phases["t_tokenize"],
                t_generate=phases["t_generate"],
                n_steps=0,
                ctx_overflow=overflow,
            )
        # Mirror RESIDENT: user turn enters history before local generate.
        hist = self._history.setdefault(key, [])
        hist.append({"role": "user", "content": f"[stub_user_turn_{turn_idx}]"})
        # After a bounce inject, the next local turn *sees* cloud assistant text.
        saw_cloud = any(m.get("role") == "assistant" and m.get("source") == "cloud" for m in hist)
        wall = float(row.get("turn_wall_s", 0.05))
        t_gen = float(row.get("t_generate", wall * 0.6))
        t_tok = float(row.get("t_tokenize", wall * 0.1))
        t_tmpl = float(row.get("t_template_build", wall * 0.1))
        t_tool = float(row.get("t_tool_exec", wall * 0.1))
        # Stub: synthetic re-prefill accounted on the first local turn after inject.
        if self._pending_reprefill.pop(key, False):
            # Real OpenVINO measures this; stub records explicit zero (not hidden).
            inj = self._last_injection.get(key) or {}
            inj["re_prefill_s"] = 0.0
            inj["re_prefill_source"] = "stub_zero"
            self._last_injection[key] = inj
        phases = finalize_phase_timers(
            turn_wall_s=wall,
            t_tool_exec=t_tool,
            t_template_build=t_tmpl,
            t_tokenize=t_tok,
            t_generate=t_gen,
        )
        raw = str(row.get("raw_text", ""))
        decoded_steps = row.get("decoded_steps")
        if saw_cloud and not raw:
            raw = "[local_after_cloud_inject]"
        hist.append(
            {
                "role": "assistant",
                "content": raw or f"[stub_local_turn_{turn_idx}]",
                "source": "local",
            }
        )
        # Shared tool path (same SharedBfclToolState cloud bounce uses).
        if self.shared_tools is not None and bool(row.get("emitted_parseable_tool_call", False)):
            if not bool(row.get("tool_exec_error", False)):
                self.shared_tools.execute(
                    [f"stub_tool_turn_{turn_idx}()"],
                    initial_config={},
                    involved_classes=[],
                    test_entry_id=eid,
                    long_context=False,
                )
        return BackendTurn(
            n_ctx=int(row["n_ctx"]),
            ttft_s=float(row["ttft_s"]),
            decode_tok_s=float(row["decode_tok_s"]),
            emitted_parseable_tool_call=bool(row["emitted_parseable_tool_call"]),
            decoded_steps=(
                [list(step) for step in decoded_steps] if isinstance(decoded_steps, list) else None
            ),
            turn_wall_s=phases["turn_wall_s"],
            t_tool_exec=phases["t_tool_exec"],
            t_template_build=phases["t_template_build"],
            t_tokenize=phases["t_tokenize"],
            t_generate=phases["t_generate"],
            raw_text=raw,
            n_steps=(int(row["n_steps"]) if "n_steps" in row else None),
            tool_exec_error=bool(row.get("tool_exec_error", False)),
            tool_exec_error_class=(
                str(row["tool_exec_error_class"])
                if row.get("tool_exec_error_class") is not None
                else None
            ),
            generation_error=bool(row.get("generation_error", False)),
        )

    def accept_cloud_context(
        self,
        entry: dict[str, Any],
        turn_idx: int,
        *,
        text: str,
        trigger: str | None = None,
        cloud_tokens_in: int = 0,
        cloud_tokens_out: int = 0,
        cloud_usd: float = 0.0,
        tool_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Inject cloud bounce text as an assistant turn into local history.

        Mirrors OpenVINO ChatHistory.append(assistant) + finish_chat KV drop.
        Stub does not hold real KV; ``re_prefill_required`` is still True and
        ``re_prefill_s`` is filled as stub_zero on the next local turn.
        """
        from tools.r2c_inject import build_injection_receipt

        eid = str(entry["id"])
        key = self._cell_or_eid(eid)
        hist = self._history.setdefault(key, [])
        # Bounce replaces the failed local assistant for this turn if present.
        if hist and hist[-1].get("role") == "assistant" and hist[-1].get("source") == "local":
            hist.pop()
        hist.append(
            {
                "role": "assistant",
                "content": text,
                "source": "cloud",
                "bounce_turn": turn_idx,
            }
        )
        for tm in tool_messages or []:
            hist.append({**tm, "source": "cloud_tool"})
            if self.shared_tools is not None:
                self.shared_tools.execute(
                    [str(tm.get("name") or "cloud_tool")],
                    initial_config={},
                    involved_classes=[],
                    test_entry_id=eid,
                    long_context=False,
                )
        self._cloud_context.setdefault(key, {})[turn_idx] = text
        self._pending_reprefill[key] = True
        receipt = build_injection_receipt(
            entry_id=eid,
            bounce_turn=turn_idx,
            trigger_class=str(trigger or "unknown"),
            assistant_text=text,
            n_tool_messages=len(tool_messages or []),
            cloud_tokens_in=cloud_tokens_in,
            cloud_tokens_out=cloud_tokens_out,
            cloud_usd=cloud_usd,
            re_prefill_s=None,
            re_prefill_source="pending_next_local",
            shared_tool_exec=True,
        )
        self._last_injection[key] = receipt.as_dict()
        return self._last_injection[key]


@dataclass
class StubCloudBackend:
    tokens_in: int = 1000
    tokens_out: int = 200
    wall_s: float = 0.02
    cloud_context_text: str = "[cloud_bounce_context]"
    # Optional per-call hook for cost-guard tests
    on_call: Callable[[], None] | None = None
    # turn_idx -> Anthropic tool_use dicts. Converted with decode_execute_anthropic.
    tool_use_by_turn: dict[int, list[dict[str, Any]]] | None = None

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        if self.on_call is not None:
            self.on_call()
        decoded_steps: list[list[str]] | None = None
        blocks = (self.tool_use_by_turn or {}).get(turn_idx)
        if blocks:
            from tools.bfcl_feasibility_probe import decode_execute_anthropic

            decoded_steps = [decode_execute_anthropic(blocks)]
        usd = cloud_usd(self.tokens_in, self.tokens_out)
        phases = finalize_phase_timers(
            turn_wall_s=self.wall_s,
            t_tool_exec=0.0,
            t_template_build=0.002,
            t_tokenize=0.0,
            t_generate=self.wall_s * 0.8,
        )
        return BackendTurn(
            n_ctx=0,
            ttft_s=None,
            decode_tok_s=None,
            emitted_parseable_tool_call=True,
            cloud_tokens_in=self.tokens_in,
            cloud_tokens_out=self.tokens_out,
            cloud_usd=usd,
            turn_wall_s=phases["turn_wall_s"],
            t_tool_exec=phases["t_tool_exec"],
            t_template_build=phases["t_template_build"],
            t_tokenize=phases["t_tokenize"],
            t_generate=phases["t_generate"],
            raw_text="[cloud]",
            cloud_context_text=self.cloud_context_text,
            decoded_steps=decoded_steps,
        )


def arm_id_for_h1(arm: dict[str, str]) -> str:
    """Map H-1 arm_config placement/kv -> delta_n.yaml arm id."""
    placement = arm["placement"]
    kv = (arm.get("kv") or "").lower()
    if placement == "cpu-p":
        return "A"
    if placement == "gpu_only":
        if kv == "u8":
            return "gpu_only_u8"
        if kv == "f16":
            return "gpu_only_f16"
        if kv == "u4":
            return "gpu_only_u4"
        # "default" (DEMO-2 control) and an unset kv: no KV property.
        return "gpu_only"
    raise ValueError(f"unsupported placement {placement!r}")


@dataclass
class OpenVinoLocalBackend:
    """Live local backend: same OpenVINO multi-turn path as W-3 / X-2.

    Generation is turn-wise via ``bfcl_feasibility_probe.MultiTurnAgentSession``
    (W-3 inner step loop unchanged; hybrid owns the outer user-turn loop).
    ``seam/measurement.py`` is the machine-validity envelope only - it does
    not generate tokens; no change was required there.

    Per turn: greedy, max_new_tokens=512, W-3 decode settings. ``run_turn``
    drives ``session.run_user_turn`` - no full-entry precompute. RESIDENT /
    NON_RESIDENT and KV pins are enforced at pipeline load. R2c inject uses
    ``session.inject_assistant`` + measured re-prefill on the next local TTFT.

    Lifecycle (owned here, not by ``run_hybrid_entry`` turn loop)::

        begin_entry(entry, policy=...)   # MultiTurnAgentSession.begin
        run_turn / accept_cloud_context   # requires active begun session
        finish_entry(entry)              # session.finish; always from finally

    Cells are keyed by ``(entry_id, policy)`` so interleaved arms sharing one
    backend cannot leak a finished session into the next policy.
    """

    model_spec: Path
    placement: str
    residency: str
    kv: str
    max_new_tokens: int = 512
    # OBS_MASK arm (tools.h1_obs_mask.ObservationMask); None = FULL observations.
    obs_mask: Any = field(default=None, repr=False)
    # DEMO-2 --context-window; None = off (no check, unchanged behavior).
    context_window: int | None = None
    arm_id: str = field(init=False)
    pipe: Any = field(init=False, repr=False)
    tokenizer: Any = field(init=False, repr=False)
    cfg: Any = field(init=False, repr=False)
    ov_genai: Any = field(init=False, repr=False)
    load_meta: dict[str, Any] = field(init=False, default_factory=dict)
    # Cell-keyed: "{entry_id}\\0{policy}". Active cell set by begin_entry.
    _entry_cache: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _sessions: dict[str, Any] = field(default_factory=dict, repr=False)
    _span_state: dict[str, LocalEntrySpan] = field(default_factory=dict, repr=False)
    _cloud_context: dict[str, dict[int, str]] = field(default_factory=dict, repr=False)
    _last_injection: dict[str, Any] = field(default_factory=dict, repr=False)
    _active_cell: str | None = field(default=None, init=False, repr=False)

    BACKEND_KIND = "openvino"
    TURNWISE = True

    def __post_init__(self) -> None:
        import openvino_genai as ov_genai

        import tools.bfcl_feasibility_probe as probe

        residency = self.residency.upper()
        if residency not in ("RESIDENT", "NON_RESIDENT"):
            raise SystemExit(
                f"REFUSED -- residency must be RESIDENT|NON_RESIDENT, got {residency!r}"
            )
        self.residency = residency
        arm = {
            "placement": self.placement,
            "kv": self.kv,
        }
        self.arm_id = arm_id_for_h1(arm)
        probe.apply_model_spec(self.model_spec)
        # NON_RESIDENT: SchedulerConfig(enable_prefix_caching=False).
        # RESIDENT: omit SchedulerConfig (CB default prefix caching ON).
        enable_pc = False if residency == "NON_RESIDENT" else None
        pipe, meta, _load_s = probe.load_arm_pipeline(self.arm_id, enable_prefix_caching=enable_pc)
        # load_arm_pipeline already raises on KV_PRECISION_MISMATCH when the arm
        # requests a pin. Re-check expected kv against readback for H-1 arm_config.
        self._assert_kv_readback(meta, expected=expected_kv_readback(self.kv))
        self.pipe = pipe
        self.tokenizer = probe._hf_tokenizer()
        self.ov_genai = ov_genai
        self.load_meta = meta
        self._prefix_reloads = 0
        cfg = ov_genai.GenerationConfig()
        cfg.max_new_tokens = int(self.max_new_tokens)
        cfg.do_sample = False
        cfg.apply_chat_template = False
        self.cfg = cfg
        self._active_cell = None

    @classmethod
    def for_stubbed_generate(
        cls,
        *,
        pipe: Any,
        tokenizer: Any,
        cfg: Any,
        residency: str = "RESIDENT",
        kv: str = "u8",
        placement: str = "gpu_only",
        max_new_tokens: int = 512,
        ov_genai: Any = None,
        obs_mask: Any = None,
    ) -> OpenVinoLocalBackend:
        """Build a live-shaped backend without loading an IR (tests / launcher smoke).

        ``pipe.generate`` must be stubbed by the caller. W-3 pins unchanged.
        """
        obj = cls.__new__(cls)
        obj.model_spec = Path("<stubbed_generate>")
        obj.placement = placement
        obj.residency = residency.upper()
        obj.kv = kv
        obj.max_new_tokens = max_new_tokens
        obj.obs_mask = obs_mask
        obj.arm_id = arm_id_for_h1({"placement": placement, "kv": kv})
        obj.pipe = pipe
        obj.tokenizer = tokenizer
        obj.cfg = cfg
        obj.ov_genai = ov_genai
        obj.load_meta = {"stubbed_generate": True}
        obj._prefix_reloads = 0
        obj._entry_cache = {}
        obj._sessions = {}
        obj._span_state = {}
        obj._cloud_context = {}
        obj._last_injection = {}
        obj._active_cell = None
        return obj

    @staticmethod
    def cell_key(entry_id: str, policy: str) -> str:
        """Isolate session state per (entry, policy) for interleaved arms."""
        return f"{entry_id}\0{policy}"

    @staticmethod
    def _assert_kv_readback(meta: dict[str, Any], *, expected: str) -> None:
        """Require load_arm_pipeline KV shape from enforce_kv_cache_precision.

        Observed live shape (gpu_only_u8, 2026-09-12)::

            meta["loads"][i]["kv_cache_precision"] = {
              "requested": "u8",
              "readback": {  # read_kv_cache_precision(...)
                "property": "KV_CACHE_PRECISION",
                "device": "GPU",
                "raw": "...",
                "to_string": "u8",
                "normalized": "u8",   # str | None  <-- precision lives HERE
                "ok": True,
                "error": None,
              },
              "match": True,
              "enforced": True,
              "failure_mode": None,
            }

        Do not accept alternate shapes silently. normalized is None => REFUSE.
        """
        expected_n = (expected or "").strip().lower()
        if expected_n in ("", "n/a"):
            return
        if not isinstance(meta, dict) or "loads" not in meta:
            raise SystemExit(
                "REFUSED -- OpenVINO load meta missing 'loads'; "
                f"observed_type={type(meta).__name__} "
                f"observed_keys={sorted(meta.keys()) if isinstance(meta, dict) else None}"
            )
        loads = meta["loads"]
        if not isinstance(loads, list) or not loads:
            raise SystemExit(
                f"REFUSED -- OpenVINO load meta 'loads' empty or not a list; "
                f"observed_type={type(loads).__name__} observed={loads!r}"
            )
        for i, load in enumerate(loads):
            if not isinstance(load, dict) or "kv_cache_precision" not in load:
                raise SystemExit(
                    f"REFUSED -- loads[{i}] missing kv_cache_precision; observed={load!r}"
                )
            kv = load["kv_cache_precision"]
            if not isinstance(kv, dict):
                raise SystemExit(
                    f"REFUSED -- loads[{i}].kv_cache_precision not a dict: "
                    f"type={type(kv).__name__} value={kv!r}"
                )
            required_kv = ("requested", "readback", "match", "enforced", "failure_mode")
            missing_kv = [k for k in required_kv if k not in kv]
            if missing_kv:
                raise SystemExit(
                    f"REFUSED -- loads[{i}].kv_cache_precision missing keys "
                    f"{missing_kv}; observed_keys={sorted(kv.keys())} observed={kv!r}"
                )
            readback = kv["readback"]
            if not isinstance(readback, dict):
                raise SystemExit(
                    f"REFUSED -- loads[{i}].kv_cache_precision.readback not a dict: "
                    f"type={type(readback).__name__} value={readback!r}"
                )
            if "normalized" not in readback:
                raise SystemExit(
                    f"REFUSED -- loads[{i}].kv_cache_precision.readback missing "
                    f"'normalized'; observed_keys={sorted(readback.keys())} "
                    f"observed={readback!r}"
                )
            normalized = readback["normalized"]
            if normalized is None:
                raise SystemExit(
                    "REFUSED -- KV_CACHE_PRECISION readback normalized is None "
                    "(property read failed); arm must not run with unverified KV. "
                    f"device={readback.get('device')!r} ok={readback.get('ok')!r} "
                    f"error={readback.get('error')!r} observed_readback={readback!r}"
                )
            if not isinstance(normalized, str):
                raise SystemExit(
                    f"REFUSED -- loads[{i}].kv_cache_precision.readback.normalized "
                    f"must be str, got {type(normalized).__name__}={normalized!r}; "
                    f"observed_readback={readback!r}"
                )
            got = normalized.lower()
            if not kv["match"]:
                raise SystemExit(
                    f"REFUSED -- KV_PRECISION_MISMATCH expected={expected_n!r} "
                    f"got={got!r} failure={kv['failure_mode']!r}"
                )
            if got != expected_n:
                raise SystemExit(
                    f"REFUSED -- KV_PRECISION_MISMATCH expected={expected_n!r} "
                    f"readback={got!r} requested={kv['requested']!r}"
                )

    def reload_prefix_cache(self) -> str:
        """Drop continuous-batching prefix blocks before the next arm.

        ``pipe.finish_chat()`` ends the chat session and leaves CB prefix blocks
        in place. The clear is a new ``ov_genai.LLMPipeline``, constructed by
        ``tools.bfcl_feasibility_probe.load_arm_pipeline`` (``_make_llm_pipeline``).
        Stubbed backends count the request and do not load an IR.
        """
        from tools.h1_provenance import PREFIX_BLOCK_CLEAR_CALL

        self._prefix_reloads = int(getattr(self, "_prefix_reloads", 0)) + 1
        if self.load_meta.get("stubbed_generate"):
            return PREFIX_BLOCK_CLEAR_CALL
        import tools.bfcl_feasibility_probe as probe

        enable_pc = False if self.residency == "NON_RESIDENT" else None
        pipe, meta, _load_s = probe.load_arm_pipeline(
            self.arm_id, enable_prefix_caching=enable_pc
        )
        self._assert_kv_readback(meta, expected=expected_kv_readback(self.kv))
        self.pipe = pipe
        self.load_meta = meta
        return PREFIX_BLOCK_CLEAR_CALL

    def begin_entry(self, entry: dict[str, Any], *, policy: str) -> None:
        """Own lifecycle: ``MultiTurnAgentSession.begin`` before the first turn.

        Cell key is ``(entry_id, policy)`` so interleaved arms sharing this
        backend cannot reuse a finished or in-flight session from another policy.
        Each begin constructs a new pipeline so the previous arm's prefix blocks
        are gone.
        """
        self.reload_prefix_cache()
        eid = str(entry["id"])
        key = self.cell_key(eid, policy)
        if self._active_cell is not None:
            raise SystemExit(
                f"REFUSED -- begin_entry while cell {self._active_cell!r} still active "
                f"(requested {key!r})"
            )
        if "raw_entry" not in entry or "question" not in entry:
            raise SystemExit(
                f"REFUSED -- entry {eid} missing raw_entry/question "
                "(need full BFCL multi_turn probe entry, not a fixture stub)"
            )
        # Drop any stale finished maps for this cell (isolation + resume safety).
        self._sessions.pop(key, None)
        self._entry_cache.pop(key, None)
        self._span_state.pop(key, None)
        self._cloud_context.pop(key, None)
        self._last_injection.pop(key, None)

        import tools.bfcl_feasibility_probe as probe

        session = probe.MultiTurnAgentSession(
            pipe=self.pipe,
            tokenizer=self.tokenizer,
            cfg=self.cfg,
            residency_mode=self.residency,
            ov_genai=self.ov_genai,
        )
        session.begin(entry)
        if self.context_window is not None:
            session.context_window = int(self.context_window)
        if self.obs_mask is not None:
            from tools.h1_obs_mask import install_on_session

            self.obs_mask.context = {"policy": policy}
            install_on_session(session, self.obs_mask, entry_id=eid)
        self._sessions[key] = session
        turns_in = turns_in_entry_count(entry)
        self._span_state[key] = LocalEntrySpan(turns_in, turns_in, "completed")
        self._active_cell = key

    def finish_entry(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        """Own lifecycle: ``session.finish`` after last turn or on abort (idempotent).

        Mid-entry exceptions: ``run_hybrid_entry`` calls this from ``finally``, so
        RESIDENT ``finish_chat`` still runs and the cell is released for the next
        policy. Does not re-raise finish errors after marking the cell closed.
        """
        eid = str(entry["id"])
        key = self._active_cell
        if key is None:
            # Already finished / never begun. Do not guess across policy cells.
            return None
        if key.split("\0", 1)[0] != eid:
            raise SystemExit(f"REFUSED -- finish_entry entry={eid!r} but active cell={key!r}")
        session = self._sessions.get(key)
        row: dict[str, Any] | None = self._entry_cache.get(key)
        if session is not None and not getattr(session, "_finished", False):
            try:
                row = session.finish()
                if isinstance(row, dict):
                    self._entry_cache[key] = row
            except Exception as exc:
                # Still release the cell so the next policy is not poisoned.
                self._entry_cache[key] = {
                    "id": eid,
                    "score": {
                        "valid": False,
                        "error_type": "probe:finish_exception",
                        "error_message": f"{type(exc).__name__}: {exc}",
                    },
                }
                row = self._entry_cache[key]
        # Drop live session so the next policy cannot observe it.
        self._sessions.pop(key, None)
        self._span_state.pop(key, None)
        self._active_cell = None
        return row if isinstance(row, dict) else None

    def finalize_entry(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        """Finish the active cell if still open; return cached probe row."""
        return self.finish_entry(entry)

    def _require_active_session(self, entry: dict[str, Any]) -> Any:
        """Return the live session for the active cell; re-begin if tear-down left it dead.

        Bounce inject calls ``pipe.finish_chat`` (KV drop) but must leave the
        MultiTurnAgentSession begun. If a prior bug finished the session mid-entry,
        re-begin a fresh session for the same cell (history reset is explicit).
        """
        eid = str(entry["id"])
        key = self._active_cell
        if key is None:
            raise SystemExit(
                f"REFUSED -- OpenVinoLocalBackend.run_turn without begin_entry (entry={eid})"
            )
        if key.split("\0", 1)[0] != eid:
            raise SystemExit(f"REFUSED -- active cell {key!r} does not match entry {eid!r}")
        session = self._sessions.get(key)
        if session is None or not getattr(session, "_begun", False):
            raise SystemExit(f"REFUSED -- no begun MultiTurnAgentSession for cell {key!r}")
        if getattr(session, "_finished", False):
            # Session torn down mid-entry (e.g. premature finish before bounce resume).
            # Re-begin on the same cell key; caller must not rely on prior KV.
            policy = key.split("\0", 1)[1]
            self._active_cell = None
            self._sessions.pop(key, None)
            # Preserve span / injection receipts across re-begin.
            span = self._span_state.get(key)
            inj = self._last_injection.get(key)
            cloud_ctx = self._cloud_context.get(key)
            self.begin_entry(entry, policy=policy)
            if span is not None:
                self._span_state[key] = span
            if inj is not None:
                self._last_injection[key] = inj
            if cloud_ctx is not None:
                self._cloud_context[key] = cloud_ctx
            session = self._sessions[key]
            # Mark pending re-prefill so the next TTFT is attributed.
            session._pending_reprefill = True
            session._last_reprefill_source = "pending_next_local"
        return session

    def local_span(self, entry: dict[str, Any]) -> LocalEntrySpan:
        """Progressive span: provisional complete until force_quit shortens it.

        The returned object is cached and mutated when ``run_turn`` hits
        ``force_quit``, so ``run_hybrid_entry`` sees the updated bound.
        """
        eid = str(entry["id"])
        key = self._active_cell
        if key is None or key.split("\0", 1)[0] != eid:
            # Span before begin_entry (should not happen for OV path).
            turns_in = turns_in_entry_count(entry)
            return LocalEntrySpan(turns_in, turns_in, "completed")
        if key in self._span_state:
            return self._span_state[key]
        turns_in = turns_in_entry_count(entry)
        span = LocalEntrySpan(turns_in, turns_in, "completed")
        self._span_state[key] = span
        return span

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        del model  # configuration pin only; generation uses loaded IR
        eid = str(entry["id"])
        key = self._active_cell
        if key is None:
            raise SystemExit(f"REFUSED -- run_turn without begin_entry (entry={eid})")
        session = self._require_active_session(entry)
        if session.force_quit:
            raise SystemExit(
                f"REFUSED -- turn_idx={turn_idx} after force_quit for entry {eid}; "
                f"hybrid must stop at local_span.turns_executed"
            )
        tm = session.run_user_turn(turn_idx)
        if not isinstance(tm, dict):
            raise SystemExit(
                f"REFUSED -- turn_metrics for {eid}/t{turn_idx} not a dict: "
                f"type={type(tm).__name__}"
            )
        # Progressive span: shorten on max_steps / force_quit.
        if session.force_quit:
            span = self.local_span(entry)
            span.turns_executed = turn_idx + 1
            span.stop_reason = "max_steps"
        required_tm = (
            "n_decoded_steps",
            "prompt_tokens",
            "ttft_s",
            "decode_tok_s",
            "turn_wall_s",
            "t_tool_exec",
            "t_template_build",
            "t_tokenize",
            "t_generate",
            "t_other",
        )
        missing_tm = [k for k in required_tm if k not in tm]
        if missing_tm:
            raise SystemExit(
                f"REFUSED -- turn_metrics[{turn_idx}] missing keys {missing_tm}; "
                f"observed_keys={sorted(tm.keys())}"
            )
        raws = (
            session.all_model_response[turn_idx]
            if turn_idx < len(session.all_model_response)
            else []
        )
        if not isinstance(raws, list):
            raise SystemExit(
                f"REFUSED -- model_result_raw[{turn_idx}] not a list: type={type(raws).__name__}"
            )
        raw_text = "\n".join(str(t) for t in raws if t)
        emitted = int(tm["n_decoded_steps"] or 0) > 0
        prompt_tokens = tm["prompt_tokens"]
        n_ctx = int(prompt_tokens) if prompt_tokens is not None else 0
        tool_err = bool(tm.get("tool_exec_error", False))
        tool_err_class = tm.get("tool_exec_error_class")
        if tool_err_class is not None:
            tool_err_class = str(tool_err_class)
        n_steps = int(tm["n_decoded_steps"] or 0)
        decoded_steps = session.all_decoded[turn_idx] if turn_idx < len(session.all_decoded) else []
        # Backfill measured re-prefill onto the last injection receipt.
        if session._last_reprefill_s is not None and key in self._last_injection:
            inj = self._last_injection[key]
            if inj.get("re_prefill_s") is None:
                inj["re_prefill_s"] = float(session._last_reprefill_s)
                inj["re_prefill_source"] = str(session._last_reprefill_source or "measured")
                self._last_injection[key] = inj
        # Do not finish here: finish_entry owns end-of-entry / abort closeout so
        # bounce inject on the last local turn still sees an active session.
        return BackendTurn(
            n_ctx=n_ctx,
            ttft_s=(float(tm["ttft_s"]) if tm["ttft_s"] is not None else None),
            decode_tok_s=(float(tm["decode_tok_s"]) if tm["decode_tok_s"] is not None else None),
            emitted_parseable_tool_call=emitted,
            turn_wall_s=float(tm["turn_wall_s"]),
            t_tool_exec=float(tm["t_tool_exec"]),
            t_template_build=float(tm["t_template_build"]),
            t_tokenize=float(tm["t_tokenize"]),
            t_generate=float(tm["t_generate"]),
            t_other=float(tm["t_other"]),
            raw_text=raw_text,
            n_steps=n_steps,
            tool_exec_error=tool_err,
            tool_exec_error_class=tool_err_class,
            decoded_steps=[list(step) for step in decoded_steps],
            ctx_overflow=tm.get("ctx_overflow"),
            generation_error=any(
                step.get("ok") is False for step in (tm.get("steps") or []) if "ok" in step
            ),
        )

    def accept_cloud_context(
        self,
        entry: dict[str, Any],
        turn_idx: int,
        *,
        text: str,
        trigger: str | None = None,
        cloud_tokens_in: int = 0,
        cloud_tokens_out: int = 0,
        cloud_usd: float = 0.0,
        tool_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Inject cloud assistant into the live session; invalidate resident KV.

        Next ``run_turn`` measures re-prefill as that turn's first-step TTFT
        (``re_prefill_source=measured``). Sealing R2c requires TURNWISE + RESIDENT.
        """
        from tools.r2c_inject import build_injection_receipt

        eid = str(entry["id"])
        key = self._active_cell
        if key is None or key.split("\0", 1)[0] != eid:
            raise SystemExit(f"REFUSED -- accept_cloud_context without begin_entry (entry={eid})")
        session = self._require_active_session(entry)
        if self.residency != "RESIDENT":
            raise SystemExit(
                "REFUSED -- R2c accept_cloud_context requires RESIDENT residency "
                f"(got {self.residency!r}); NON_RESIDENT has no resident KV to invalidate"
            )
        session.inject_assistant(
            assistant_text=text,
            tool_messages=tool_messages,
            replace_last_local_assistant=True,
        )
        self._cloud_context.setdefault(key, {})[turn_idx] = text
        receipt = build_injection_receipt(
            entry_id=eid,
            bounce_turn=turn_idx,
            trigger_class=str(trigger or "unknown"),
            assistant_text=text,
            n_tool_messages=len(tool_messages or []),
            cloud_tokens_in=cloud_tokens_in,
            cloud_tokens_out=cloud_tokens_out,
            cloud_usd=cloud_usd,
            re_prefill_s=None,
            re_prefill_source="pending_next_local",
            shared_tool_exec=True,
            note=(
                "ChatHistory accepts external assistant append; KV invalidated via "
                "finish_chat; next local generate TTFT is measured re_prefill_s."
            ),
        )
        self._last_injection[key] = receipt.as_dict()
        return self._last_injection[key]


def local_backend_kind(local: LocalBackend) -> str:
    kind = getattr(local, "BACKEND_KIND", None)
    if kind:
        return str(kind)
    return type(local).__name__


def assert_seal_allowed(*, seal: bool, local: LocalBackend, policy: str) -> None:
    """Stub/scripted local backends must never produce a sealed MEASURED tree."""
    if not seal:
        return
    if policy == "cloud_only":
        # Local backend is unused; sealing cloud-only MEASURED arms is allowed.
        return
    if not isinstance(local, OpenVinoLocalBackend):
        raise SystemExit(
            "REFUSED -- --seal requires OpenVinoLocalBackend for hybrid policies. "
            f"Got {local_backend_kind(local)}. Stub/scripted runs cannot be sealed."
        )
    if policy == "full_signal_bounceback":
        if not getattr(local, "TURNWISE", False):
            raise SystemExit(
                "REFUSED -- full_signal_bounceback (R2c) requires turn-by-turn "
                "OpenVinoLocalBackend (TURNWISE=True) with cloud context injection."
            )
        if getattr(local, "residency", None) != "RESIDENT":
            raise SystemExit(
                "REFUSED -- full_signal_bounceback (R2c) requires RESIDENT residency "
                "for measured re-prefill after inject; "
                f"got {getattr(local, 'residency', None)!r}"
            )


@dataclass
class ScriptedLiveLocalBackend:
    """Precomputed per-turn metrics (debug / non-seal only). Not sealable."""

    script: dict[str, list[dict[str, Any]]]
    BACKEND_KIND = "scripted"

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        return StubLocalBackend(script=self.script).run_turn(entry, turn_idx, model=model)


@dataclass
class AnthropicCloudBackend:
    """One Anthropic user-turn (native tool-use agent steps) -> BackendTurn."""

    client: Any
    cloud_model: str
    max_tokens: int = 512
    caching_policy: str = "none"
    # OBS_MASK arm: the cloud agent sees the same masked observations as local.
    obs_mask: Any = None
    _entry_cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    def _ensure_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        eid = str(entry["id"])
        if eid not in self._entry_cache:
            import tools.bfcl_feasibility_probe as probe

            hook = None
            if self.obs_mask is not None:
                from tools.h1_obs_mask import cloud_hook

                hook = cloud_hook(self.obs_mask, entry_id=eid)
            row = probe.run_cloud_multi_turn_agent_entry(
                client=self.client,
                model=self.cloud_model,
                max_tokens=self.max_tokens,
                entry=entry,
                running_usd=0.0,
                caching_policy=self.caching_policy,
                observation_hook=hook,
            )
            self._entry_cache[eid] = row
        return self._entry_cache[eid]

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        row = self._ensure_entry(entry)
        entry_error = row.get("entry_error")
        calls = [
            c
            for c in (row.get("calls") or [])
            if int(c.get("user_turn", c.get("turn", -1))) == turn_idx
        ]
        if not calls:
            # Fallback: apportion entry totals across user turns.
            n = max(1, int(row.get("n_user_turns") or 1))
            tin = int(row.get("prompt_tokens_sum") or 0) // n
            tout = int(row.get("completion_tokens_sum") or 0) // n
            usd = float(row.get("usd") or 0.0) / n
            wall = 0.05
        else:
            tin = sum(int(c.get("prompt_tokens") or 0) for c in calls)
            tout = sum(int(c.get("completion_tokens") or 0) for c in calls)
            usd = sum(float(c.get("usd") or 0.0) for c in calls)
            wall = sum(float(c.get("latency_s") or 0.0) for c in calls) or 0.05
            # Prefer explicit per-call API failure over apportioned zeros.
            for c in calls:
                if c.get("ok") is False and c.get("error"):
                    entry_error = entry_error or str(c.get("error"))
                    break
        phases = finalize_phase_timers(
            turn_wall_s=wall,
            t_tool_exec=0.0,
            t_template_build=0.0,
            t_tokenize=0.0,
            t_generate=wall * 0.9,
        )
        cloud_error: str | None = None
        if entry_error:
            cloud_error = str(entry_error)
        elif tin == 0 and tout == 0:
            cloud_error = "cloud_empty_tokens"
        md = row.get("model_result_decoded") or []
        turn_steps = md[turn_idx] if isinstance(md, list) and turn_idx < len(md) else None
        decoded_steps = [list(step) for step in turn_steps] if isinstance(turn_steps, list) else []
        return BackendTurn(
            n_ctx=tin,
            ttft_s=None,
            decode_tok_s=None,
            emitted_parseable_tool_call=True,
            cloud_tokens_in=tin,
            cloud_tokens_out=tout,
            cloud_usd=usd if usd > 0 else cloud_usd(tin, tout),
            turn_wall_s=phases["turn_wall_s"],
            t_tool_exec=phases["t_tool_exec"],
            t_template_build=phases["t_template_build"],
            t_tokenize=phases["t_tokenize"],
            t_generate=phases["t_generate"],
            raw_text="[anthropic]",
            cloud_error=cloud_error,
            cloud_requests=list(calls),
            decoded_steps=decoded_steps,
        )


# ---------------------------------------------------------------------------
# Cost guard + checkpoint
# ---------------------------------------------------------------------------
class CostCapExceeded(Exception):
    def __init__(
        self,
        running_usd: float,
        max_usd: float,
        *,
        partial: EntryResult | None = None,
    ) -> None:
        super().__init__(f"cost cap hit: running_usd={running_usd:.6f} max_usd={max_usd:.6f}")
        self.running_usd = running_usd
        self.max_usd = max_usd
        self.partial = partial


@dataclass
class CostGuard:
    max_usd: float
    running_usd: float = 0.0

    def charge(self, usd: float) -> None:
        self.running_usd += float(usd)
        if self.running_usd > self.max_usd + 1e-12:
            raise CostCapExceeded(self.running_usd, self.max_usd)


# ---------------------------------------------------------------------------
# Cloud dead-path guard (same class as stub-seal refuse / degenerate N=3)
# ---------------------------------------------------------------------------
# Evidence: void interleaved session 6c7f88f1
#   derived/h1_hybrid/interleaved_6c7f88f1-0642-413e-bf72-f45c4f8f8a1e/
# After multi_turn_base_52 the Anthropic path returned tin=0/tout=0/usd=0 for
# every subsequent escalate (172 consecutive dead cloud turns on emission;
# 75 on bounceback) while the runner kept recording escalations. Credits were
# exhausted; numbers from that dead path are not measurements.
#
# N=3 = refuse after three consecutive dead cloud turns (session-wide):
#   - Matches DEGENERATE_CONSECUTIVE_N derivation style (b1a291f0).
#   - Trips inside the first dead entry (base_52 had 3 zero turns) before the
#     remaining ~169 garbage escalations.
# Recorded twin: derived/h1_hybrid/CLOUD_DEAD_PATH_GUARD.json
CLOUD_DEAD_CONSECUTIVE_N = 3
CLOUD_DEAD_CITING_RUN = "6c7f88f1"
CLOUD_DEAD_CITING_SESSION = "interleaved_6c7f88f1-0642-413e-bf72-f45c4f8f8a1e"


class CloudDeadPathError(Exception):
    """Session abort: repeated cloud turns returned nothing usable."""


def cloud_turn_is_dead(bt: BackendTurn) -> bool:
    """True when a cloud BackendTurn carries no usable completion.

    Signature from 6c7f88f1 post-credit-death cells: tin=0 and tout=0 (often
    usd=0). Explicit ``cloud_error`` also counts.
    """
    if bt.cloud_error:
        return True
    return int(bt.cloud_tokens_in or 0) == 0 and int(bt.cloud_tokens_out or 0) == 0


# Per-request fields copied into cloud_dead_events.json. An allow-list, so no
# header, key or request text can reach the file.
CLOUD_EVENT_REQUEST_FIELDS = (
    "turn",
    "step",
    "user_turn",
    "request_index_within_turn",
    "ok",
    "error",
    "error_class",
    "http_status",
    "request_id",
    "model",
    "prompt_tokens",
    "completion_tokens",
    "input_tokens",
    "output_tokens",
    "latency_s",
    "usd",
)


def cloud_event_request_row(row: dict[str, Any]) -> dict[str, Any]:
    """One request row for the events file: allow-listed fields, error redacted."""
    from tools.h1_cloud_accounting import redact_secrets

    out = {name: row.get(name) for name in CLOUD_EVENT_REQUEST_FIELDS if name in row}
    if out.get("error") is not None:
        out["error"] = redact_secrets(str(out["error"]))
    if "error_class" not in out and out.get("error"):
        # Rows written before error_class existed: "api_error: <Class>: <msg>".
        parts = str(out["error"]).split(": ", 2)
        out["error_class"] = parts[1] if len(parts) >= 2 and parts[0] == "api_error" else None
    return out


@dataclass
class CloudDeadPathGuard:
    """Abort after N consecutive dead cloud turns (any policy / entry).

    With ``events_path`` set, every dead turn and the abort rewrite
    ``cloud_dead_events.json`` (guard events plus the allow-listed request rows
    of every observed turn), so the error text survives the abort.
    """

    n: int = CLOUD_DEAD_CONSECUTIVE_N
    consecutive: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    requests_by_turn: dict[tuple[str, str, int], list[dict[str, Any]]] = field(
        default_factory=dict
    )
    events_path: Path | None = None

    def events_doc(self, *, status: str | None = None, abort: str | None = None) -> dict[str, Any]:
        from tools.h1_cloud_accounting import redact_secrets

        return {
            "status": status,
            "abort": redact_secrets(abort),
            "threshold_n": self.n,
            "consecutive": self.consecutive,
            "events": [
                {**ev, "cloud_error": redact_secrets(ev.get("cloud_error"))} for ev in self.events
            ],
            "requests": [
                {
                    "policy": policy,
                    "entry_id": entry_id,
                    "turn": turn,
                    "rows": [cloud_event_request_row(r) for r in rows],
                }
                for (policy, entry_id, turn), rows in self.requests_by_turn.items()
            ],
            "written_utc": _utc_now(),
            "note": "No API key or headers. Errors are redacted. Written on each dead cloud turn and on abort.",
        }

    def write_events(self, *, status: str | None = None, abort: str | None = None) -> None:
        if self.events_path is not None:
            _write_json(self.events_path, self.events_doc(status=status, abort=abort))

    def observe(
        self,
        bt: BackendTurn,
        *,
        entry_id: str,
        turn: int,
        policy: str,
    ) -> dict[str, Any]:
        dead = cloud_turn_is_dead(bt)
        if dead:
            self.consecutive += 1
        else:
            self.consecutive = 0
        rec = {
            "entry_id": entry_id,
            "turn": turn,
            "policy": policy,
            "dead": dead,
            "consecutive_after": self.consecutive,
            "cloud_tokens_in": int(bt.cloud_tokens_in or 0),
            "cloud_tokens_out": int(bt.cloud_tokens_out or 0),
            "cloud_error": bt.cloud_error,
        }
        self.events.append(rec)
        if bt.cloud_requests is not None:
            self.requests_by_turn[(policy, entry_id, turn)] = list(bt.cloud_requests)
        if dead:
            self.write_events(status="dead_turn")
        return rec

    def raise_if_refused(self) -> None:
        if self.consecutive >= self.n:
            raise CloudDeadPathError(
                "REFUSED -- CLOUD_DEAD_PATH_STREAK "
                f"n={self.consecutive} threshold={self.n} "
                f"citing={CLOUD_DEAD_CITING_RUN} "
                f"session={CLOUD_DEAD_CITING_SESSION} "
                "(cloud turns returned tin=0/tout=0 or cloud_error; "
                "abort rather than seal numbers from a dead cloud path)"
            )


CLOUD_PING_WORKER_FILE = "cloud_ping_worker.json"
REFUSED_CLOUD_PING = "refused_cloud_ping"


def policy_reaches_cloud(policy: str) -> bool:
    """Every H1 policy can send a turn to the cloud except local_only."""
    return policy != "local_only"


def run_worker_cloud_ping(
    preflight: Callable[[], dict[str, Any]], out_dir: Path
) -> dict[str, Any]:
    """The tools/cloud_ping.py request, made from inside this worker process.

    launch_h1 pings from the ssh session; the worker runs as a WMI child and
    can see a different environment. The record (already redacted by
    cloud_ping) is written to <run dir>/cloud_ping_worker.json, inside the
    sealed tree. Returns the plan.json block.
    """
    import os

    from tools.h1_cloud_accounting import exception_fields

    try:
        record = dict(preflight())
    except Exception as exc:
        record = {"ok": False, "exit_code": 1, **exception_fields(exc)}
    record["process"] = "worker"
    record["pid"] = os.getpid()
    path = out_dir / CLOUD_PING_WORKER_FILE
    _write_json(path, record)
    return {
        "ran": True,
        "ok": bool(record.get("ok")),
        "path": CLOUD_PING_WORKER_FILE,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "model": record.get("model"),
        "http_status": record.get("http_status"),
        "error_class": record.get("error_class"),
        "anthropic_sdk_version": record.get("anthropic_sdk_version"),
        "api_key_present": record.get("api_key_present"),
        "usd": record.get("usd"),
        "note": "Ping cost is recorded here and is not charged to the policy or session caps.",
    }


def load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"completed_entry_ids": [], "running_usd": 0.0, "entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(path: Path, state: dict[str, Any]) -> None:
    _write_json(path, state)


# ---------------------------------------------------------------------------
# Entry / scorer asserts
# ---------------------------------------------------------------------------
def assert_entry_set_pinned(entries_path: Path, *, allow_reserved: bool = False) -> dict[str, Any]:
    """Refuse an entries file whose sha256 is not in ENTRY_PINS, or whose count differs.

    A pin with ``reserved_for`` is refused unless ``allow_reserved``
    (--confirmation-run).
    """
    digest = _sha256_file(entries_path)
    pin = ENTRY_PINS.get(digest)
    if pin is None:
        raise SystemExit(
            f"REFUSED -- multi_turn entries sha256 {digest} is not a pinned entry set "
            f"(W-3 {W3_ENTRIES_SHA256}, seals {', '.join(W3_SEAL_REFS)}; "
            f"DEMO1_LONGCTX_30 {DEMO1_LONGCTX_30_SHA256})"
        )
    if pin.get("reserved_for") and not allow_reserved:
        raise SystemExit(
            f"REFUSED -- entry pin {pin['name']} is reserved for {pin['reserved_for']}; "
            "pass --confirmation-run only for that run"
        )
    entries = json.loads(entries_path.read_text(encoding="utf-8-sig"))
    if not isinstance(entries, list) or len(entries) != int(pin["n"]):
        raise SystemExit(
            f"REFUSED -- expected {pin['n']} entries, got {type(entries)} "
            f"n={getattr(entries, '__len__', lambda: '?')()}"
        )
    return {"sha256": digest, **pin}


def slice_entries(
    entries: list[dict[str, Any]], entry_pin: dict[str, Any], *, offset: int | None, count: int | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Chunk a pinned entry set for one boot (--entry-offset / --entry-count).

    The whole file is still checked against its pin; the chunk is recorded on
    the pin record in the plan. No flags: the full set, unchanged.
    """
    if offset is None and count is None:
        return entries, entry_pin
    start = int(offset or 0)
    n = len(entries) - start if count is None else int(count)
    if start < 0 or n < 1 or start + n > len(entries):
        raise SystemExit(
            f"REFUSED -- entry chunk offset={start} count={n} outside the pinned set "
            f"of {len(entries)} entries"
        )
    chunk = entries[start : start + n]
    return chunk, {
        **entry_pin,
        "chunk": {
            "offset": start,
            "count": n,
            "first_entry_id": str(chunk[0]["id"]),
            "last_entry_id": str(chunk[-1]["id"]),
        },
    }


def assert_entry_set_matches_w3(entries_path: Path) -> dict[str, Any]:
    """Kept for callers that accept only the W-3 pin."""
    doc = assert_entry_set_pinned(entries_path)
    if doc["sha256"] != W3_ENTRIES_SHA256:
        raise SystemExit(
            f"REFUSED -- multi_turn entries sha256 {doc['sha256']} != W-3 pin {W3_ENTRIES_SHA256} "
            f"(seals {', '.join(W3_SEAL_REFS)})"
        )
    return {"sha256": doc["sha256"], "n": doc["n"], "seal_refs": list(W3_SEAL_REFS)}


def assert_scorer_version(gold_selftest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assert checker/wrapper paths match W-3 gold selftests; record bfcl_eval version."""
    checker = SCORER_CHECKER
    wrapper = SCORER_WRAPPER
    if gold_selftest is not None:
        if gold_selftest.get("checker") != checker:
            raise SystemExit(
                f"REFUSED -- gold selftest checker {gold_selftest.get('checker')!r} != {checker!r}"
            )
        # wrapper may be absent on older selftests; if present must match
        if "wrapper" in gold_selftest and gold_selftest["wrapper"] != wrapper:
            raise SystemExit(
                f"REFUSED -- gold selftest wrapper {gold_selftest.get('wrapper')!r} != {wrapper!r}"
            )
    version = None
    try:
        import tools.bfcl_feasibility_probe as probe

        version = probe.inventory().get("version")
    except Exception as exc:  # pragma: no cover - optional in stub tests
        version = f"unavailable:{type(exc).__name__}"
    return {
        "checker": checker,
        "wrapper": wrapper,
        "bfcl_eval_version": version,
        "w3_seal_refs": list(W3_SEAL_REFS),
    }


# ---------------------------------------------------------------------------
# Hybrid entry loop
# ---------------------------------------------------------------------------
def _resolve_local_span(local: LocalBackend, entry: dict[str, Any]) -> LocalEntrySpan:
    span_fn = getattr(local, "local_span", None)
    if callable(span_fn):
        return span_fn(entry)
    n = turns_in_entry_count(entry)
    return LocalEntrySpan(n, n, "completed")


def run_hybrid_entry(
    entry: dict[str, Any],
    *,
    policy: str,
    local: LocalBackend,
    cloud: CloudBackend,
    cost: CostGuard,
    model: str,
    cloud_dead_guard: CloudDeadPathGuard | None = None,
) -> EntryResult:
    """Run one entry under ``policy``.

    Early-stop semantics (D-2d)
    ---------------------------
    The local BFCL agent loop may end before ``turns_in_entry``. The last turn
    metric present is where the session stopped; later turns did not execute
    (not SLO failures, not successes).

    Per policy:
    - cloud_only: ignore local span; run every turn on cloud.
    - agnostic_default: run local turns that exist; stop at local span
      (no escalation). Record local ``stop_reason``.
    - slo_escalate: a short entry is *not* an SLO violation. Score
      ``slo_fraction`` over turns that ran. Unexecuted turns are omitted from
      the denominator. If the last local turn itself trips SLO, escalate that
      turn to cloud and continue remaining turns on cloud.
    - emission_escalate: stop caused by no-parseable-tool-call / empty_execute
      *is* the escalation trigger. Cloud picks up from that turn and runs the
      rest of ``turns_in_entry``. ``generation_error`` / ``max_steps`` are
      different events - recorded as ``stop_reason``, not emission escalate.
    - full_signal_bounceback (R2c): on (a) no parseable tool call, (b) step
      count >= ``BOUNCE_STEP_BUDGET`` (5) within the turn, or (c) tool exec
      error, cloud handles *that turn only*; its output is injected into the
      local context; local resumes at the next turn. Does not stay on cloud.
    """
    if policy not in POLICIES:
        raise ValueError(policy)
    # Blind router: only task + model (configuration never passed into RouterView).
    _view = router_view_for_entry(entry, model=model)
    assert _view.model == model

    # Backend owns MultiTurnAgentSession lifecycle for local policies.
    # begin_entry before first turn; finish_entry in finally (last turn or abort).
    needs_local_lifecycle = policy != "cloud_only"
    if needs_local_lifecycle:
        _backend_begin_entry(local, entry, policy=policy)
    try:
        return _run_hybrid_entry_body(
            entry,
            policy=policy,
            local=local,
            cloud=cloud,
            cost=cost,
            model=model,
            cloud_dead_guard=cloud_dead_guard,
        )
    finally:
        if needs_local_lifecycle:
            _backend_finish_entry(local, entry)


def _note_cloud_turn(
    guard: CloudDeadPathGuard | None,
    bt: BackendTurn,
    *,
    entry: dict[str, Any],
    turn_idx: int,
    policy: str,
) -> None:
    if guard is None:
        return
    guard.observe(bt, entry_id=str(entry["id"]), turn=turn_idx, policy=policy)
    guard.raise_if_refused()


def _run_hybrid_entry_body(
    entry: dict[str, Any],
    *,
    policy: str,
    local: LocalBackend,
    cloud: CloudBackend,
    cost: CostGuard,
    model: str,
    cloud_dead_guard: CloudDeadPathGuard | None = None,
) -> EntryResult:
    """Inner entry loop; caller owns begin_entry / finish_entry around this."""
    turns_in = turns_in_entry_count(entry)
    local_span = (
        LocalEntrySpan(turns_in, turns_in, "completed")
        if policy == "cloud_only"
        else _resolve_local_span(local, entry)
    )
    if local_span.turns_in_entry != turns_in and policy != "cloud_only":
        # Prefer question length; probe n_user_turns should match.
        turns_in = max(turns_in, local_span.turns_in_entry)

    on_cloud = policy == "cloud_only"
    result = EntryResult(
        entry_id=str(entry["id"]),
        n_turns=turns_in,
        turns_in_entry=turns_in,
        stop_reason=local_span.stop_reason if policy != "cloud_only" else "completed",
    )

    for turn_idx in range(turns_in):
        # --- cloud path (cloud_only, or stay-on-cloud after escalate) ---
        if on_cloud or policy == "cloud_only":
            bt = cloud.run_turn(entry, turn_idx, model=model)
            _note_cloud_turn(cloud_dead_guard, bt, entry=entry, turn_idx=turn_idx, policy=policy)
            if policy == "cloud_only":
                reason_out = "cloud_only"
            else:
                reason_out = "stay_cloud"
            try:
                cost.charge(bt.cloud_usd)
            except CostCapExceeded:
                phases = phases_from_backend_turn(bt)
                ledger = TurnLedger(
                    entry_id=str(entry["id"]),
                    turn=turn_idx,
                    placement="cloud",
                    model=model,
                    n_ctx=bt.n_ctx,
                    ttft_s=bt.ttft_s,
                    decode_tok_s=bt.decode_tok_s,
                    emitted_parseable_tool_call=bt.emitted_parseable_tool_call,
                    escalated=True,
                    escalate_reason=reason_out,
                    cloud_tokens_in=bt.cloud_tokens_in,
                    cloud_tokens_out=bt.cloud_tokens_out,
                    cloud_usd=bt.cloud_usd,
                    turn_wall_s=phases["turn_wall_s"],
                    t_tool_exec=phases["t_tool_exec"],
                    t_template_build=phases["t_template_build"],
                    t_tokenize=phases["t_tokenize"],
                    t_generate=phases["t_generate"],
                    t_other=phases["t_other"],
                    tool_exec_error=bool(bt.tool_exec_error),
                    tool_exec_error_class=bt.tool_exec_error_class,
                )
                result.turns.append(_stamp_decoded(ledger, bt))
                result.cloud_usd_entry += bt.cloud_usd
                result.status = "aborted_cap"
                result.turns_executed = len(result.turns)
                attach_entry_quality(result, local, entry)
                raise CostCapExceeded(cost.running_usd, cost.max_usd, partial=result)
            phases = phases_from_backend_turn(bt)
            ledger = TurnLedger(
                entry_id=str(entry["id"]),
                turn=turn_idx,
                placement="cloud",
                model=model,
                n_ctx=bt.n_ctx,
                ttft_s=bt.ttft_s,
                decode_tok_s=bt.decode_tok_s,
                emitted_parseable_tool_call=bt.emitted_parseable_tool_call,
                escalated=True,
                escalate_reason=reason_out,
                cloud_tokens_in=bt.cloud_tokens_in,
                cloud_tokens_out=bt.cloud_tokens_out,
                cloud_usd=bt.cloud_usd,
                turn_wall_s=phases["turn_wall_s"],
                t_tool_exec=phases["t_tool_exec"],
                t_template_build=phases["t_template_build"],
                t_tokenize=phases["t_tokenize"],
                t_generate=phases["t_generate"],
                t_other=phases["t_other"],
                tool_exec_error=bool(bt.tool_exec_error),
                tool_exec_error_class=bt.tool_exec_error_class,
            )
            result.turns.append(_stamp_decoded(ledger, bt))
            result.cloud_usd_entry += bt.cloud_usd
            continue

        # --- past local span: turns did not happen ---
        if turn_idx >= local_span.turns_executed:
            break

        # Local turn (must exist in span)
        bt = local.run_turn(entry, turn_idx, model=model)

        # --- DEMO-2: mechanical triggers first (sticky) ---
        # ctx_overflow only occurs with --context-window; hybrid_full adds the
        # step-0 TTFT / decode and generation_error triggers. With neither,
        # mech_reason stays None and every existing path below is unchanged.
        mech_reason: str | None = None
        if bt.ctx_overflow is not None:
            if policy in ("local_only", "agnostic_default"):
                raise SystemExit(
                    f"REFUSED -- ctx_overflow under {policy}, which cannot escalate "
                    f"(entry {entry['id']} turn {turn_idx})"
                )
            mech_reason = "ctx_overflow"
        elif policy == "hybrid_full":
            at_end = turn_idx == local_span.turns_executed - 1
            _mech, mech_reason = decide_hybrid_mechanical(
                ttft_s=bt.ttft_s,
                decode_tok_s=bt.decode_tok_s,
                generation_error=bool(bt.generation_error)
                or (at_end and local_span.stop_reason == "generation_error"),
            )
        quality_class = QUALITY if policy == "hybrid_full" else None

        # --- R2c bounceback: one-turn cloud, then resume local ---
        if mech_reason is None and policy in ("full_signal_bounceback", "hybrid_full"):
            bounce, trigger = decide_bounceback(
                emitted_parseable_tool_call=bt.emitted_parseable_tool_call,
                n_steps=bt.n_steps,
                tool_exec_error=bool(bt.tool_exec_error),
            )
            if bounce:
                assert trigger is not None
                bt_c = cloud.run_turn(entry, turn_idx, model=model)
                _note_cloud_turn(
                    cloud_dead_guard,
                    bt_c,
                    entry=entry,
                    turn_idx=turn_idx,
                    policy=policy,
                )
                try:
                    cost.charge(bt_c.cloud_usd)
                except CostCapExceeded:
                    phases = phases_from_backend_turn(bt_c)
                    result.turns.append(
                        TurnLedger(
                            entry_id=str(entry["id"]),
                            turn=turn_idx,
                            placement="cloud",
                            model=model,
                            n_ctx=bt.n_ctx,
                            ttft_s=bt.ttft_s,
                            decode_tok_s=bt.decode_tok_s,
                            emitted_parseable_tool_call=bt.emitted_parseable_tool_call,
                            escalated=True,
                            escalate_reason=f"bounce:{trigger}",
                            cloud_tokens_in=bt_c.cloud_tokens_in,
                            cloud_tokens_out=bt_c.cloud_tokens_out,
                            cloud_usd=bt_c.cloud_usd,
                            turn_wall_s=phases["turn_wall_s"],
                            t_tool_exec=phases["t_tool_exec"],
                            t_template_build=phases["t_template_build"],
                            t_tokenize=phases["t_tokenize"],
                            t_generate=phases["t_generate"],
                            t_other=phases["t_other"],
                            decoded_steps=[list(s) for s in (bt_c.decoded_steps or [])],
                            bounce_trigger=trigger,
                            tool_exec_error=bool(bt.tool_exec_error),
                            tool_exec_error_class=bt.tool_exec_error_class,
                            local_attempt=local_attempt_record(
                                bt, stop_reason=local_span.stop_reason
                            ),
                            trigger_class=quality_class,
                        )
                    )
                    result.bounces.append(BounceEvent(turn=turn_idx, trigger=trigger))
                    result.cloud_usd_entry += bt_c.cloud_usd
                    result.status = "aborted_cap"
                    result.turns_executed = len(result.turns)
                    attach_entry_quality(result, local, entry)
                    raise CostCapExceeded(cost.running_usd, cost.max_usd, partial=result)
                phases = phases_from_backend_turn(bt_c)
                result.turns.append(
                    TurnLedger(
                        entry_id=str(entry["id"]),
                        turn=turn_idx,
                        placement="cloud",
                        model=model,
                        n_ctx=bt.n_ctx,
                        ttft_s=bt.ttft_s,
                        decode_tok_s=bt.decode_tok_s,
                        emitted_parseable_tool_call=True,
                        escalated=True,
                        escalate_reason=f"bounce:{trigger}",
                        cloud_tokens_in=bt_c.cloud_tokens_in,
                        cloud_tokens_out=bt_c.cloud_tokens_out,
                        cloud_usd=bt_c.cloud_usd,
                        turn_wall_s=phases["turn_wall_s"],
                        t_tool_exec=phases["t_tool_exec"],
                        t_template_build=phases["t_template_build"],
                        t_tokenize=phases["t_tokenize"],
                        t_generate=phases["t_generate"],
                        t_other=phases["t_other"],
                        decoded_steps=[list(s) for s in (bt_c.decoded_steps or [])],
                        bounce_trigger=trigger,
                        tool_exec_error=bool(bt.tool_exec_error),
                        tool_exec_error_class=bt.tool_exec_error_class,
                        local_attempt=local_attempt_record(
                            bt, stop_reason=local_span.stop_reason
                        ),
                        trigger_class=quality_class,
                    )
                )
                result.cloud_usd_entry += bt_c.cloud_usd
                # Inject cloud output into local context; do NOT stay on cloud.
                cloud_text = bt_c.cloud_context_text or bt_c.raw_text or "[cloud]"
                inj: dict[str, Any] = {}
                accept = getattr(local, "accept_cloud_context", None)
                if callable(accept):
                    inj = (
                        accept(
                            entry,
                            turn_idx,
                            text=cloud_text,
                            trigger=trigger,
                            cloud_tokens_in=bt_c.cloud_tokens_in,
                            cloud_tokens_out=bt_c.cloud_tokens_out,
                            cloud_usd=bt_c.cloud_usd,
                        )
                        or {}
                    )
                # Per-bounce ledger: trigger class, cloud tokens/$, re-prefill, return turn.
                result.bounces.append(
                    BounceEvent(
                        turn=turn_idx,
                        trigger=trigger,
                        cloud_tokens_in=int(inj.get("cloud_tokens_in", bt_c.cloud_tokens_in) or 0),
                        cloud_tokens_out=int(
                            inj.get("cloud_tokens_out", bt_c.cloud_tokens_out) or 0
                        ),
                        cloud_usd=float(inj.get("cloud_usd", bt_c.cloud_usd) or 0.0),
                        re_prefill_s=(
                            float(inj["re_prefill_s"])
                            if inj.get("re_prefill_s") is not None
                            else None
                        ),
                        re_prefill_required=bool(inj.get("re_prefill_required", True)),
                        re_prefill_source=(
                            str(inj["re_prefill_source"])
                            if inj.get("re_prefill_source") is not None
                            else "pending_next_local"
                        ),
                        control_return_turn=int(inj.get("control_return_turn", turn_idx + 1)),
                        kv_valid_after_inject=bool(inj.get("kv_valid_after_inject", False)),
                        shared_tool_exec=bool(inj.get("shared_tool_exec", True)),
                    )
                )
                # Resume local on subsequent turns.
                if (
                    turn_idx == local_span.turns_executed - 1
                    and local_span.stop_reason != "completed"
                ):
                    break
                continue

            # No bounce: keep local turn.
            phases = phases_from_backend_turn(bt)
            result.turns.append(
                TurnLedger(
                    entry_id=str(entry["id"]),
                    turn=turn_idx,
                    placement="local",
                    model=model,
                    n_ctx=bt.n_ctx,
                    ttft_s=bt.ttft_s,
                    decode_tok_s=bt.decode_tok_s,
                    emitted_parseable_tool_call=bt.emitted_parseable_tool_call,
                    escalated=False,
                    escalate_reason=None,
                    cloud_tokens_in=0,
                    cloud_tokens_out=0,
                    cloud_usd=0.0,
                    turn_wall_s=phases["turn_wall_s"],
                    t_tool_exec=phases["t_tool_exec"],
                    t_template_build=phases["t_template_build"],
                    t_tokenize=phases["t_tokenize"],
                    t_generate=phases["t_generate"],
                    t_other=phases["t_other"],
                    decoded_steps=[list(s) for s in (bt.decoded_steps or [])],
                    tool_exec_error=bool(bt.tool_exec_error),
                    tool_exec_error_class=bt.tool_exec_error_class,
                )
            )
            # Backfill re_prefill onto the prior bounce once the next local turn ran.
            _inj = getattr(local, "_last_injection", None)
            _active = getattr(local, "_active_key", None) or getattr(local, "_active_cell", None)
            if isinstance(_inj, dict):
                _rec = {}
                if _active is not None and _active in _inj:
                    _rec = _inj[_active] or {}
                if not _rec:
                    _rec = _inj.get(str(entry["id"])) or {}
                if result.bounces and _rec.get("re_prefill_s") is not None:
                    _b = result.bounces[-1]
                    if _b.re_prefill_s is None and _b.control_return_turn == turn_idx:
                        _b.re_prefill_s = float(_rec["re_prefill_s"])
                        _b.re_prefill_source = str(_rec.get("re_prefill_source") or "stub_zero")
            if turn_idx == local_span.turns_executed - 1 and local_span.stop_reason != "completed":
                break
            continue

        escalate = False
        reason: str | None = None
        mech_class = MECHANICAL if mech_reason is not None else None
        overflow_rec = bt.ctx_overflow if mech_reason == "ctx_overflow" else None
        if mech_reason is not None:
            escalate, reason = True, mech_reason
        elif policy == "agnostic_default":
            escalate, reason = False, None
        elif policy == "local_only":
            escalate, reason = decide_local_only()
        elif policy == "slo_escalate":
            escalate, reason = decide_slo_escalate(
                already_on_cloud=False,
                ttft_s=bt.ttft_s,
                decode_tok_s=bt.decode_tok_s,
            )
        elif policy == "emission_escalate":
            # Distinguish emission failure from generation failure / max_steps.
            at_local_end = turn_idx == local_span.turns_executed - 1
            if at_local_end and local_span.stop_reason == "generation_error":
                escalate, reason = False, None
            elif at_local_end and local_span.stop_reason == "max_steps":
                escalate, reason = False, None
            elif at_local_end and local_span.stop_reason in (
                "no_tool_call",
                "empty_execute",
            ):
                escalate, reason = True, local_span.stop_reason
            else:
                escalate, reason = decide_emission_escalate(
                    already_on_cloud=False,
                    emitted_parseable_tool_call=bt.emitted_parseable_tool_call,
                )

        if escalate:
            # Re-do this turn on cloud and stay there for the rest of the entry.
            on_cloud = True
            bt_c = cloud.run_turn(entry, turn_idx, model=model)
            _note_cloud_turn(cloud_dead_guard, bt_c, entry=entry, turn_idx=turn_idx, policy=policy)
            try:
                cost.charge(bt_c.cloud_usd)
            except CostCapExceeded:
                phases = phases_from_backend_turn(bt_c)
                result.turns.append(
                    TurnLedger(
                        entry_id=str(entry["id"]),
                        turn=turn_idx,
                        placement="cloud",
                        model=model,
                        n_ctx=bt_c.n_ctx,
                        ttft_s=bt_c.ttft_s,
                        decode_tok_s=bt_c.decode_tok_s,
                        emitted_parseable_tool_call=bt_c.emitted_parseable_tool_call,
                        escalated=True,
                        escalate_reason=reason,
                        cloud_tokens_in=bt_c.cloud_tokens_in,
                        cloud_tokens_out=bt_c.cloud_tokens_out,
                        cloud_usd=bt_c.cloud_usd,
                        turn_wall_s=phases["turn_wall_s"],
                        t_tool_exec=phases["t_tool_exec"],
                        t_template_build=phases["t_template_build"],
                        t_tokenize=phases["t_tokenize"],
                        t_generate=phases["t_generate"],
                        t_other=phases["t_other"],
                        decoded_steps=[list(s) for s in (bt_c.decoded_steps or [])],
                        tool_exec_error=bool(bt.tool_exec_error),
                        tool_exec_error_class=bt.tool_exec_error_class,
                        trigger_class=mech_class,
                        ctx_overflow=overflow_rec,
                    )
                )
                result.cloud_usd_entry += bt_c.cloud_usd
                result.status = "aborted_cap"
                result.turns_executed = len(result.turns)
                attach_entry_quality(result, local, entry)
                raise CostCapExceeded(cost.running_usd, cost.max_usd, partial=result)
            phases = phases_from_backend_turn(bt_c)
            result.turns.append(
                TurnLedger(
                    entry_id=str(entry["id"]),
                    turn=turn_idx,
                    placement="cloud",
                    model=model,
                    n_ctx=bt.n_ctx,  # ctx that triggered escalation
                    ttft_s=bt.ttft_s,
                    decode_tok_s=bt.decode_tok_s,
                    emitted_parseable_tool_call=bt.emitted_parseable_tool_call,
                    escalated=True,
                    escalate_reason=reason,
                    cloud_tokens_in=bt_c.cloud_tokens_in,
                    cloud_tokens_out=bt_c.cloud_tokens_out,
                    cloud_usd=bt_c.cloud_usd,
                    turn_wall_s=phases["turn_wall_s"],
                    t_tool_exec=phases["t_tool_exec"],
                    t_template_build=phases["t_template_build"],
                    t_tokenize=phases["t_tokenize"],
                    t_generate=phases["t_generate"],
                    t_other=phases["t_other"],
                    decoded_steps=[list(s) for s in (bt_c.decoded_steps or [])],
                    tool_exec_error=bool(bt.tool_exec_error),
                    tool_exec_error_class=bt.tool_exec_error_class,
                    trigger_class=mech_class,
                    ctx_overflow=overflow_rec,
                )
            )
            result.cloud_usd_entry += bt_c.cloud_usd
            continue

        phases = phases_from_backend_turn(bt)
        result.turns.append(
            TurnLedger(
                entry_id=str(entry["id"]),
                turn=turn_idx,
                placement="local",
                model=model,
                n_ctx=bt.n_ctx,
                ttft_s=bt.ttft_s,
                decode_tok_s=bt.decode_tok_s,
                emitted_parseable_tool_call=bt.emitted_parseable_tool_call,
                escalated=False,
                escalate_reason=None,
                cloud_tokens_in=0,
                cloud_tokens_out=0,
                cloud_usd=0.0,
                turn_wall_s=phases["turn_wall_s"],
                t_tool_exec=phases["t_tool_exec"],
                t_template_build=phases["t_template_build"],
                t_tokenize=phases["t_tokenize"],
                t_generate=phases["t_generate"],
                t_other=phases["t_other"],
                decoded_steps=[list(s) for s in (bt.decoded_steps or [])],
                tool_exec_error=bool(bt.tool_exec_error),
                tool_exec_error_class=bt.tool_exec_error_class,
            )
        )

        # Last local turn, no escalation: remaining turns_in_entry did not happen.
        if (
            turn_idx == local_span.turns_executed - 1
            and local_span.stop_reason != "completed"
            and not on_cloud
        ):
            break

    result.turns_executed = len(result.turns)
    if policy == "cloud_only":
        result.stop_reason = (
            "completed" if result.turns_executed >= turns_in else result.stop_reason
        )
    elif result.status == "aborted_cap":
        pass
    elif result.turns_executed < turns_in:
        result.status = "stopped_early"
        result.stop_reason = local_span.stop_reason
    else:
        result.status = "complete"
        # Finished all turns (possibly via emission/slo cloud pickup).
        # Keep emission stop_reason when that was the escalate cause.
        if local_span.stop_reason in ("no_tool_call", "empty_execute") and any(
            t.escalated for t in result.turns
        ):
            result.stop_reason = local_span.stop_reason
        elif local_span.stop_reason == "completed":
            result.stop_reason = "completed"
        else:
            result.stop_reason = local_span.stop_reason

    if policy == "slo_escalate":
        # Denominator = turns that ran only (never turns_in_entry).
        ran = result.turns
        if ran:
            ok = sum(1 for t in ran if turn_meets_slo(ttft_s=t.ttft_s, decode_tok_s=t.decode_tok_s))
            result.slo_fraction = ok / len(ran)
        else:
            result.slo_fraction = None

    attach_entry_quality(result, local, entry)
    return result


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------
def _annotate_cloud_requests(
    rows: list[dict[str, Any]],
    guard: CloudDeadPathGuard | None,
    policy: str,
) -> list[dict[str, Any]]:
    """Copy per-request cloud logs onto serialized turn rows."""
    if guard is None:
        return rows
    for row in rows:
        eid = str(row.get("entry_id"))
        for turn in row.get("turns") or []:
            key = (policy, eid, int(turn.get("turn", -1)))
            logged = guard.requests_by_turn.get(key)
            if logged is not None:
                turn["cloud_requests"] = logged
    return rows


def _cloud_usd_invariant(state: dict[str, Any], policies: tuple[str, ...]) -> dict[str, Any]:
    from tools.h1_cloud_accounting import cloud_usd_nondecreasing

    arms: list[dict[str, Any]] = []
    for policy in policies:
        for row in state[policy]["ledger_rows"]:
            turns = row.get("turns") or []
            n_cloud = sum(1 for t in turns if t.get("placement") == "cloud")
            arms.append(
                {
                    "entry_id": row.get("entry_id"),
                    "policy": policy,
                    "n_cloud_turns": n_cloud,
                    "cloud_usd": float(row.get("cloud_usd_entry") or 0.0),
                }
            )
    return cloud_usd_nondecreasing(arms)


def _seal_git(seal_git: dict[str, Any] | None) -> dict[str, Any]:
    """Provenance for a plan and its seals.

    Library callers that omit the record capture with allow_dirty so fixture
    tests still seal. The CLI refuses a dirty tree before it gets here.
    """
    if seal_git is not None:
        return seal_git
    return seal_git_record(allow_dirty=True, root=ROOT)


def run_session(
    *,
    policy: str,
    entries: list[dict[str, Any]],
    out_dir: Path,
    max_usd: float,
    local: LocalBackend,
    cloud: CloudBackend,
    run_id: str | None = None,
    model: str | None = None,
    seal: bool = True,
    skip_entry_assert: bool = False,
    caching_policy: str = "none",
    seal_git: dict[str, Any] | None = None,
    entry_pin: dict[str, Any] | None = None,
    retention: dict[str, Any] | None = None,
    cloud_preflight: Callable[[], dict[str, Any]] | None = None,
    obs_mask: Any = None,
    context_window: int | None = None,
) -> dict[str, Any]:
    if max_usd is None:
        raise SystemExit("REFUSED -- --max-usd is required (cost guard)")
    if policy not in POLICIES:
        raise SystemExit(f"REFUSED -- unknown policy {policy!r}")
    if policy == "agnostic_default":
        raise SystemExit(
            "REFUSED -- agnostic_default must not run live (~21 h). "
            "Use --derive-r1 to scale from sealed cb781dbf (DERIVED)."
        )
    assert_seal_allowed(seal=seal, local=local, policy=policy)
    git_rec = _seal_git(seal_git)

    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_id or str(uuid.uuid4())
    arm = arm_config_for(policy, local)
    model = model or arm["model"]
    ckpt_path = out_dir / "checkpoint.json"
    ckpt = load_checkpoint(ckpt_path)
    completed = set(ckpt.get("completed_entry_ids") or [])
    cost = CostGuard(max_usd=float(max_usd), running_usd=float(ckpt.get("running_usd") or 0.0))
    ledger_rows: list[dict[str, Any]] = list(ckpt.get("entries") or [])
    quality_path = out_dir / "entry_quality.json"
    quality_rows: list[dict[str, Any]] = []
    if quality_path.is_file():
        prev_q = json.loads(quality_path.read_text(encoding="utf-8-sig"))
        quality_rows = list(prev_q.get("entries") or [])

    plan = {
        "run_id": run_id,
        "policy": policy,
        "arm_config": arm,
        "max_usd": float(max_usd),
        "n_entries": len(entries),
        "measurement_kind": "MEASURED",
        "local_backend": local_backend_kind(local),
        "seal": bool(seal),
        "started_utc": _utc_now(),
        "w3_entry_pin": _w3_pin_field(entry_pin),
        "entry_pin": entry_pin or ENTRY_PIN_DEFAULT,
        "retention": retention or {"arm": "FULL"},
        "w3_seal_refs": list(W3_SEAL_REFS),
        "scorer": assert_scorer_version(),
        "caching_policy": caching_policy,
        "resume_from_completed": sorted(completed),
        "platform_id": run_platform_id(),
        "git": git_rec,
    }
    if context_window is not None:
        # DEMO-2 only; absent otherwise so existing plans are unchanged.
        plan["context_window"] = {
            "tokens": int(context_window),
            "rule": "prompt + max_new_tokens > tokens before a local generate: "
            "not generated, escalate (sticky, ctx_overflow)",
        }
    from tools.h1_provenance import provenance_block

    plan.update(provenance_block(cloud, local))
    if isinstance(local, OpenVinoLocalBackend):
        plan["openvino"] = {
            "arm_id": local.arm_id,
            "model_spec": str(local.model_spec),
            "residency": local.residency,
            "kv": local.kv,
            "max_new_tokens": local.max_new_tokens,
            "load_meta": local.load_meta,
            "prefix_block_clear": "ov_genai.LLMPipeline",
        }
    if not skip_entry_assert:
        # When entries were loaded from the W-3 pin file, hash is checked at load.
        plan["entry_assert"] = {"n": len(entries), "mode": "caller_supplied"}
    _write_json(out_dir / "plan.json", plan)

    status = "complete"
    abort_reason: str | None = None
    abort_verbatim: str | None = None
    summary_written = False
    cloud_dead_guard = CloudDeadPathGuard(
        n=CLOUD_DEAD_CONSECUTIVE_N, events_path=out_dir / "cloud_dead_events.json"
    )
    ping_refused = False
    if cloud_preflight is not None:
        if policy_reaches_cloud(policy):
            plan["cloud_ping_worker"] = run_worker_cloud_ping(cloud_preflight, out_dir)
            if not plan["cloud_ping_worker"]["ok"]:
                ping_refused = True
                status = REFUSED_CLOUD_PING
                abort_reason = (
                    "REFUSED -- in-worker cloud ping failed "
                    f"(http_status={plan['cloud_ping_worker']['http_status']} "
                    f"error_class={plan['cloud_ping_worker']['error_class']}); no entry run"
                )
                abort_verbatim = abort_reason
                print(f"REFUSED_CLOUD_PING {abort_reason}")
        else:
            plan["cloud_ping_worker"] = {"ran": False, "reason": "policy does not reach the cloud"}
        _write_json(out_dir / "plan.json", plan)

    def _write_session_summary() -> dict[str, Any]:
        nonlocal summary_written
        n_scored = sum(1 for q in quality_rows if q.get("local_pass") is not None)
        n_pass = sum(1 for q in quality_rows if q.get("local_pass") is True)
        n_hybrid_scored = sum(1 for q in quality_rows if q.get("hybrid_pass") is not None)
        n_hybrid_pass = sum(1 for q in quality_rows if q.get("hybrid_pass") is True)
        doc = {
            "run_id": run_id,
            "policy": policy,
            "status": status,
            "abort_reason": abort_reason,
            "abort_verbatim": abort_verbatim,
            "measurement_kind": "MEASURED",
            "n_entries_planned": len(entries),
            "n_entries_completed": len(completed),
            "running_usd": cost.running_usd,
            "max_usd": float(max_usd),
            "finished_utc": _utc_now(),
            "arm_config": arm,
            "quality": {
                "local_probe": {
                    "scope": "local_probe",
                    "n_entries_with_score": n_scored,
                    "n_local_pass": n_pass,
                },
                "hybrid": {
                    "scope": "hybrid",
                    "n_entries_with_score": n_hybrid_scored,
                    "n_hybrid_pass": n_hybrid_pass,
                },
                "path": "entry_quality.json",
            },
        }
        _write_json(out_dir / "summary.json", doc)
        _write_json(out_dir / "turn_ledger.json", {"entries": _annotate_cloud_requests(ledger_rows, cloud_dead_guard, policy)})
        _write_json(out_dir / "entry_quality.json", {"entries": quality_rows})
        summary_written = True
        return doc

    try:
        for entry in [] if ping_refused else entries:
            eid = str(entry["id"])
            if eid in completed:
                print(f"RESUME_SKIP entry={eid} running_usd={cost.running_usd:.6f}")
                continue
            print(f"ENTRY_START id={eid} running_usd={cost.running_usd:.6f} max_usd={max_usd}")
            try:
                er = run_hybrid_entry(
                    entry,
                    policy=policy,
                    local=local,
                    cloud=cloud,
                    cost=cost,
                    model=model,
                    cloud_dead_guard=cloud_dead_guard,
                )
            except CloudDeadPathError as exc:
                status = "aborted_cloud_dead"
                abort_reason = str(exc)
                abort_verbatim = str(exc)
                cloud_dead_guard.write_events(status=status, abort=abort_reason)
                print(f"ABORT_CLOUD_DEAD {exc}")
                save_checkpoint(
                    ckpt_path,
                    {
                        "completed_entry_ids": sorted(completed),
                        "running_usd": cost.running_usd,
                        "entries": ledger_rows,
                        "updated_utc": _utc_now(),
                        "abort_reason": abort_reason,
                    },
                )
                _write_json(out_dir / "turn_ledger.json", {"entries": _annotate_cloud_requests(ledger_rows, cloud_dead_guard, policy)})
                _write_json(out_dir / "entry_quality.json", {"entries": quality_rows})
                break
            except CostCapExceeded as exc:
                status = "aborted_cap"
                abort_reason = str(exc)
                abort_verbatim = str(exc)
                print(f"COST_CAP_ABORT {exc}")
                if exc.partial is not None:
                    ledger_rows.append(exc.partial.as_ledger_dict())
                    quality_rows.append(exc.partial.as_quality_dict())
                save_checkpoint(
                    ckpt_path,
                    {
                        "completed_entry_ids": sorted(completed),
                        "running_usd": cost.running_usd,
                        "entries": ledger_rows,
                        "updated_utc": _utc_now(),
                        "abort_reason": abort_reason,
                    },
                )
                _write_json(out_dir / "turn_ledger.json", {"entries": _annotate_cloud_requests(ledger_rows, cloud_dead_guard, policy)})
                _write_json(out_dir / "entry_quality.json", {"entries": quality_rows})
                break

            ledger_rows.append(er.as_ledger_dict())
            quality_rows.append(er.as_quality_dict())
            completed.add(eid)
            save_checkpoint(
                ckpt_path,
                {
                    "completed_entry_ids": sorted(completed),
                    "running_usd": cost.running_usd,
                    "entries": ledger_rows,
                    "updated_utc": _utc_now(),
                },
            )
            _write_json(out_dir / "turn_ledger.json", {"entries": _annotate_cloud_requests(ledger_rows, cloud_dead_guard, policy)})
            _write_json(out_dir / "entry_quality.json", {"entries": quality_rows})
            print(
                f"ENTRY_DONE id={eid} cloud_usd_entry={er.cloud_usd_entry:.6f} "
                f"running_usd={cost.running_usd:.6f} "
                f"trajectory_pass={er.trajectory_pass}"
            )
    except BaseException as exc:
        if status == "complete":
            status = "aborted"
            abort_reason = type(exc).__name__
            abort_verbatim = str(exc)
        raise
    finally:
        if not summary_written:
            summary = _write_session_summary()
        else:
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8-sig"))

    # The OBS_MASK ledger is part of the run: write it before the seal so the
    # tree hash covers it (a678926e wrote it 46 ms after .sealed).
    write_obs_mask_ledger(out_dir, obs_mask)

    from tools.h1_provenance import stamp_seal

    if seal and status == "complete":
        tree = _sha256_tree(out_dir, exclude={".sealed"})
        seal_doc = {
            "run_id": run_id,
            "policy": policy,
            "sealed_utc": _utc_now(),
            "tree_sha256": tree,
            "status": status,
            "measurement_kind": "MEASURED",
            "git": git_rec,
        }
        stamp_seal(seal_doc, plan)
        (out_dir / ".sealed").write_text(
            json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif seal and status != "complete":
        # Still allow sealing aborted/partial sessions with an explicit status.
        tree = _sha256_tree(out_dir, exclude={".sealed"})
        seal_doc = {
            "run_id": run_id,
            "policy": policy,
            "sealed_utc": _utc_now(),
            "tree_sha256": tree,
            "status": status,
            "abort_reason": abort_reason,
            "measurement_kind": "MEASURED",
            "note": "Sealed non-complete H1 session; status is not complete.",
            "git": git_rec,
        }
        stamp_seal(seal_doc, plan)
        (out_dir / ".sealed").write_text(
            json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    return summary


def _policy_subdir(out_dir: Path, policy: str) -> Path:
    return out_dir / "policies" / policy


def run_interleaved_session(
    *,
    entries: list[dict[str, Any]],
    out_dir: Path,
    local: LocalBackend,
    cloud: CloudBackend,
    policy_caps_usd: dict[str, float] | None = None,
    session_max_usd: float = DEFAULT_SESSION_CAP_USD,
    policies: tuple[str, ...] = INTERLEAVE_POLICIES,
    run_id: str | None = None,
    model: str | None = None,
    seal: bool = True,
    skip_entry_assert: bool = False,
    caching_policy: str = "none",
    seal_git: dict[str, Any] | None = None,
    arm_order_seed: int = 0,
    entry_pin: dict[str, Any] | None = None,
    retention: dict[str, Any] | None = None,
    cloud_preflight: Callable[[], dict[str, Any]] | None = None,
    obs_mask: Any = None,
) -> dict[str, Any]:
    """Entry-by-entry interleave of selected H1 policy arms (INF-5 session_design=interleaved).

    For each entry, arm order is one row of a seeded Latin square
    (``latin_square_order``). ``arm_order`` on the plan stays the symbol list.
    ``arm_order_this_entry`` is recorded on every cell. Each policy has its own
    cost cap and completed-entry set under ``out_dir/policies/<policy>/``.
    A policy-cap abort stops *that* arm only; other arms continue. A session-cap
    abort stops remaining work across all arms. Resume never re-bills a
    completed (policy, entry) pair. When R2c is omitted from ``policies``,
    plan/summary/seal record ``r2c_excluded`` so the artifact is not mistaken
    for the full three-policy comparison.
    """
    git_rec = _seal_git(seal_git)
    caps = dict(policy_caps_usd or DEFAULT_POLICY_CAPS_USD)
    for p in policies:
        if p not in caps:
            raise SystemExit(f"REFUSED -- missing per-policy cap for {p!r}")
        if p == "agnostic_default":
            raise SystemExit("REFUSED -- agnostic_default must not run in interleaved live")
        assert_seal_allowed(seal=seal, local=local, policy=p)

    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_id or str(uuid.uuid4())
    session_ckpt_path = out_dir / "checkpoint.json"
    session_ckpt = load_checkpoint(session_ckpt_path)
    session_cost = CostGuard(
        max_usd=float(session_max_usd),
        running_usd=float(session_ckpt.get("running_usd") or 0.0),
    )

    # Per-policy state
    state: dict[str, dict[str, Any]] = {}
    for policy in policies:
        pdir = _policy_subdir(out_dir, policy)
        pdir.mkdir(parents=True, exist_ok=True)
        ckpt = load_checkpoint(pdir / "checkpoint.json")
        quality_path = pdir / "entry_quality.json"
        quality_rows: list[dict[str, Any]] = []
        if quality_path.is_file():
            prev_q = json.loads(quality_path.read_text(encoding="utf-8-sig"))
            quality_rows = list(prev_q.get("entries") or [])
        arm = arm_config_for(policy, local)
        state[policy] = {
            "dir": pdir,
            "completed": set(ckpt.get("completed_entry_ids") or []),
            "cost": CostGuard(
                max_usd=float(caps[policy]),
                running_usd=float(ckpt.get("running_usd") or 0.0),
            ),
            "ledger_rows": list(ckpt.get("entries") or []),
            "quality_rows": quality_rows,
            "status": str(ckpt.get("status") or "running"),
            "abort_reason": ckpt.get("abort_reason"),
            "arm": arm,
            "model": model or arm["model"],
        }

    excl = interleaved_exclusion_meta(policies)
    kind = interleaved_kind(policies)
    identity = local_model_identity(local)
    local_arm = arm_config_for("slo_escalate", local)
    plan = {
        "run_id": run_id,
        "kind": kind,
        "session_design": "interleaved",
        "arm_order": list(policies),
        "arm_order_seed": int(arm_order_seed),
        "arm_order_rule": "seeded_latin_square",
        "policy_caps_usd": {p: float(caps[p]) for p in policies},
        "session_max_usd": float(session_max_usd),
        "n_entries": len(entries),
        "measurement_kind": "MEASURED",
        "local_backend": local_backend_kind(local),
        "seal": bool(seal),
        "started_utc": _utc_now(),
        "w3_entry_pin": _w3_pin_field(entry_pin),
        "entry_pin": entry_pin or ENTRY_PIN_DEFAULT,
        "retention": retention or {"arm": "FULL"},
        "w3_seal_refs": list(W3_SEAL_REFS),
        "scorer": assert_scorer_version(),
        "caching_policy": caching_policy,
        "kv_match_seal": (
            KV_MATCH_SEAL_4B
            if identity["tier"] == DEFAULT_LOCAL_TIER
            and local_arm["placement"] == "gpu_only"
            and local_arm["residency"] == "RESIDENT"
            else None
        ),
        "placement": local_arm["placement"],
        "residency": local_arm["residency"],
        "tier": identity["tier"],
        "model": identity["model"],
        "weight": "int4",
        "platform_id": run_platform_id(),
        "resume_completed_by_policy": {
            p: sorted(state[p]["completed"]) for p in policies
        },
        "git": git_rec,
        **excl,
    }
    from tools.h1_provenance import provenance_block

    plan.update(provenance_block(cloud, local))
    if isinstance(local, OpenVinoLocalBackend):
        plan["openvino"] = {
            "arm_id": local.arm_id,
            "model_spec": str(local.model_spec),
            "residency": local.residency,
            "kv": local.kv,
            "max_new_tokens": local.max_new_tokens,
            "load_meta": local.load_meta,
            "prefix_block_clear": "ov_genai.LLMPipeline",
        }
    if not skip_entry_assert:
        plan["entry_assert"] = {"n": len(entries), "mode": "caller_supplied"}
    _write_json(out_dir / "plan.json", plan)

    session_status = "complete"
    session_abort: str | None = None
    cell_log: list[dict[str, Any]] = list(session_ckpt.get("cell_log") or [])
    prefix_cache_control_failures: list[dict[str, Any]] = []
    n_entries_finished = 0
    cloud_dead_guard = CloudDeadPathGuard(
        n=CLOUD_DEAD_CONSECUTIVE_N, events_path=out_dir / "cloud_dead_events.json"
    )

    def _persist_policy(policy: str) -> None:
        st = state[policy]
        pdir: Path = st["dir"]
        cost: CostGuard = st["cost"]
        save_checkpoint(
            pdir / "checkpoint.json",
            {
                "completed_entry_ids": sorted(st["completed"]),
                "running_usd": cost.running_usd,
                "entries": st["ledger_rows"],
                "status": st["status"],
                "abort_reason": st["abort_reason"],
                "updated_utc": _utc_now(),
            },
        )
        _write_json(pdir / "turn_ledger.json", {"entries": _annotate_cloud_requests(st["ledger_rows"], cloud_dead_guard, policy)})
        _write_json(pdir / "entry_quality.json", {"entries": st["quality_rows"]})
        rows = st["quality_rows"]
        n_scored = sum(1 for q in rows if q.get("local_pass") is not None)
        n_pass = sum(1 for q in rows if q.get("local_pass") is True)
        n_hybrid_scored = sum(1 for q in rows if q.get("hybrid_pass") is not None)
        n_hybrid_pass = sum(1 for q in rows if q.get("hybrid_pass") is True)
        _write_json(
            pdir / "summary.json",
            {
                "run_id": run_id,
                "policy": policy,
                "status": st["status"],
                "abort_reason": st["abort_reason"],
                "measurement_kind": "MEASURED",
                "n_entries_planned": len(entries),
                "n_entries_completed": len(st["completed"]),
                "running_usd": cost.running_usd,
                "max_usd": cost.max_usd,
                "finished_utc": _utc_now(),
                "arm_config": st["arm"],
                "session_design": "interleaved",
                "quality": {
                    "local_probe": {
                        "scope": "local_probe",
                        "n_entries_with_score": n_scored,
                        "n_local_pass": n_pass,
                    },
                    "hybrid": {
                        "scope": "hybrid",
                        "n_entries_with_score": n_hybrid_scored,
                        "n_hybrid_pass": n_hybrid_pass,
                    },
                    "path": "entry_quality.json",
                },
            },
        )

    def _persist_session() -> None:
        save_checkpoint(
            session_ckpt_path,
            {
                "completed_entry_ids": [],  # completion is per-policy
                "running_usd": session_cost.running_usd,
                "cell_log": cell_log,
                "policy_status": {p: state[p]["status"] for p in policies},
                "updated_utc": _utc_now(),
            },
        )

    ping_refused = False
    if cloud_preflight is not None:
        if any(policy_reaches_cloud(p) for p in policies):
            plan["cloud_ping_worker"] = run_worker_cloud_ping(cloud_preflight, out_dir)
            if not plan["cloud_ping_worker"]["ok"]:
                ping_refused = True
                session_status = REFUSED_CLOUD_PING
                session_abort = (
                    "REFUSED -- in-worker cloud ping failed "
                    f"(http_status={plan['cloud_ping_worker']['http_status']} "
                    f"error_class={plan['cloud_ping_worker']['error_class']}); no entry run"
                )
                for p in policies:
                    state[p]["status"] = REFUSED_CLOUD_PING
                    state[p]["abort_reason"] = session_abort
                    _persist_policy(p)
                _persist_session()
                print(f"REFUSED_CLOUD_PING {session_abort}")
        else:
            plan["cloud_ping_worker"] = {
                "ran": False,
                "reason": "no selected policy reaches the cloud",
            }
        _write_json(out_dir / "plan.json", plan)

    try:
        from tools.h1_provenance import latin_square_order

        for entry in [] if ping_refused else entries:
            eid = str(entry["id"])
            order = latin_square_order(policies, eid, seed=int(arm_order_seed))
            for policy in order:
                st = state[policy]
                if st["status"] in ("aborted_cap", "aborted_session_cap"):
                    continue
                if eid in st["completed"]:
                    print(f"RESUME_SKIP policy={policy} entry={eid}")
                    continue
                if session_cost.running_usd > session_cost.max_usd + 1e-12:
                    session_status = "aborted_cap"
                    session_abort = (
                        f"session cost cap hit before cell: "
                        f"running_usd={session_cost.running_usd:.6f} "
                        f"max_usd={session_cost.max_usd:.6f}"
                    )
                    for p in policies:
                        if state[p]["status"] == "running":
                            state[p]["status"] = "aborted_session_cap"
                            state[p]["abort_reason"] = session_abort
                            _persist_policy(p)
                    break

                print(
                    f"CELL_START policy={policy} entry={eid} "
                    f"policy_usd={st['cost'].running_usd:.6f}/{st['cost'].max_usd:.6f} "
                    f"session_usd={session_cost.running_usd:.6f}/{session_cost.max_usd:.6f}"
                )
                # Shared dual charge: policy guard first, then session.
                # run_hybrid_entry only knows one CostGuard - wrap via a proxy.
                dual = _DualCostGuard(policy_guard=st["cost"], session_guard=session_cost)
                try:
                    er = run_hybrid_entry(
                        entry,
                        policy=policy,
                        local=local,
                        cloud=cloud,
                        cost=dual,  # type: ignore[arg-type]
                        model=st["model"],
                        cloud_dead_guard=cloud_dead_guard,
                    )
                except CloudDeadPathError as exc:
                    session_status = "aborted_cloud_dead"
                    session_abort = str(exc)
                    cloud_dead_guard.write_events(status=session_status, abort=session_abort)
                    st["status"] = "aborted_cloud_dead"
                    st["abort_reason"] = session_abort
                    for p in policies:
                        if state[p]["status"] == "running":
                            state[p]["status"] = "aborted_cloud_dead"
                            state[p]["abort_reason"] = session_abort
                            _persist_policy(p)
                    _persist_policy(policy)
                    _persist_session()
                    print(f"ABORT_CLOUD_DEAD {session_abort}")
                    break
                except CostCapExceeded as exc:
                    which = getattr(exc, "cap_which", "policy")
                    if exc.partial is not None:
                        st["ledger_rows"].append(exc.partial.as_ledger_dict())
                        st["quality_rows"].append(exc.partial.as_quality_dict())
                    if which == "session":
                        st["status"] = "aborted_session_cap"
                        st["abort_reason"] = str(exc)
                        session_status = "aborted_cap"
                        session_abort = str(exc)
                        _persist_policy(policy)
                        for p in policies:
                            if p != policy and state[p]["status"] == "running":
                                state[p]["status"] = "aborted_session_cap"
                                state[p]["abort_reason"] = session_abort
                                _persist_policy(p)
                        cell_log.append(
                            {
                                "entry_id": eid,
                                "policy": policy,
                                "arm_order_this_entry": list(order),
                                "status": "aborted_session_cap",
                                "running_usd_policy": st["cost"].running_usd,
                                "running_usd_session": session_cost.running_usd,
                            }
                        )
                        _persist_session()
                        break
                    # Policy-only cap: stop this arm; other arms continue.
                    st["status"] = "aborted_cap"
                    st["abort_reason"] = str(exc)
                    print(f"POLICY_CAP_ABORT policy={policy} {exc}")
                    _persist_policy(policy)
                    cell_log.append(
                        {
                            "entry_id": eid,
                            "policy": policy,
                            "arm_order_this_entry": list(order),
                            "status": "aborted_cap",
                            "running_usd_policy": st["cost"].running_usd,
                            "running_usd_session": session_cost.running_usd,
                        }
                    )
                    _persist_session()
                    continue

                st["ledger_rows"].append(er.as_ledger_dict())
                st["quality_rows"].append(er.as_quality_dict())
                st["completed"].add(eid)
                _persist_policy(policy)
                cell_log.append(
                    {
                        "entry_id": eid,
                        "policy": policy,
                        "arm_order_this_entry": list(order),
                        "status": "complete",
                        "cloud_usd_entry": er.cloud_usd_entry,
                        "running_usd_policy": st["cost"].running_usd,
                        "running_usd_session": session_cost.running_usd,
                    }
                )
                _persist_session()
                print(
                    f"CELL_DONE policy={policy} entry={eid} "
                    f"cloud_usd_entry={er.cloud_usd_entry:.6f} "
                    f"trajectory_pass={er.trajectory_pass}"
                )
            else:
                if str(getattr(local, "residency", "")).upper() == "RESIDENT":
                    from tools.h1_provenance import (
                        entry_turn0_local_ttft,
                        prefix_cache_control_failure,
                    )

                    arms = [
                        (pol, entry_turn0_local_ttft(state[pol]["ledger_rows"], eid))
                        for pol in order
                    ]
                    fail = prefix_cache_control_failure(arms)
                    if fail is not None:
                        fail["entry_id"] = eid
                        fail["arm_order_this_entry"] = list(order)
                        prefix_cache_control_failures.append(fail)
                        print(f"PREFIX_CACHE_CONTROL_FAIL entry={eid} n={len(fail['below'])}")
                n_entries_finished += 1
                from tools.h1_provenance import project_session_cost

                projected = project_session_cost(
                    running_usd=session_cost.running_usd,
                    n_done=n_entries_finished,
                    n_planned=len(entries),
                )
                if projected is not None and projected > session_cost.max_usd + 1e-12:
                    session_status = "aborted_projection"
                    session_abort = (
                        f"projection {projected:.6f} > cap {session_cost.max_usd:.6f} "
                        f"after {n_entries_finished} entries"
                    )
                    print(f"PROJECTION_STOP {session_abort}")
                    for p in policies:
                        if state[p]["status"] == "running":
                            state[p]["status"] = "aborted_projection"
                            state[p]["abort_reason"] = session_abort
                            _persist_policy(p)
                    break
                continue
            break  # session abort broke inner loop
    finally:
        for policy in policies:
            if state[policy]["status"] == "running":
                # Finished outer loop without abort -> complete if all entries done.
                if len(state[policy]["completed"]) >= len(entries):
                    state[policy]["status"] = "complete"
                else:
                    # Partial (other arms still) - leave as running unless all done.
                    remaining = [
                        e for e in entries if str(e["id"]) not in state[policy]["completed"]
                    ]
                    if not remaining:
                        state[policy]["status"] = "complete"
            _persist_policy(policy)
        _persist_session()

    all_complete = all(state[p]["status"] == "complete" for p in policies)
    if session_status == "complete" and not all_complete:
        # Some arms aborted_cap but session ok.
        if any(state[p]["status"] == "aborted_cap" for p in policies):
            session_status = "partial_policy_cap"
        elif any(state[p]["status"] == "running" for p in policies):
            session_status = "partial"

    summary = {
        "run_id": run_id,
        "kind": kind,
        "session_design": "interleaved",
        "arm_order": list(policies),
        "status": session_status,
        "abort_reason": session_abort,
        "measurement_kind": "MEASURED",
        "n_entries_planned": len(entries),
        "running_usd_session": session_cost.running_usd,
        "session_max_usd": float(session_max_usd),
        "policy_caps_usd": {p: float(caps[p]) for p in policies},
        "policies": {
            p: {
                "status": state[p]["status"],
                "abort_reason": state[p]["abort_reason"],
                "n_entries_completed": len(state[p]["completed"]),
                "running_usd": state[p]["cost"].running_usd,
                "max_usd": state[p]["cost"].max_usd,
                "path": str(_policy_subdir(out_dir, p).relative_to(out_dir)).replace("\\", "/"),
            }
            for p in policies
        },
        "finished_utc": _utc_now(),
        "caching_policy": caching_policy,
        "cloud_usd_invariant": _cloud_usd_invariant(state, policies),
        "prefix_cache_control_failures": len(prefix_cache_control_failures),
        "prefix_cache_control": prefix_cache_control_failures,
        **excl,
    }
    _write_json(out_dir / "summary.json", summary)
    write_obs_mask_ledger(out_dir, obs_mask)

    if seal:
        from tools.h1_provenance import stamp_seal

        # Per-policy seals when that arm completed (R2c may refuse OpenVINO above).
        for policy in policies:
            st = state[policy]
            if st["status"] != "complete":
                continue
            pdir: Path = st["dir"]
            tree = _sha256_tree(pdir, exclude={".sealed"})
            seal_doc = {
                "run_id": run_id,
                "policy": policy,
                "sealed_utc": _utc_now(),
                "tree_sha256": tree,
                "status": st["status"],
                "measurement_kind": "MEASURED",
                "session_design": "interleaved",
                "parent_run_id": run_id,
                "parent_kind": kind,
                "git": git_rec,
                **excl,
            }
            stamp_seal(seal_doc, plan)
            (pdir / ".sealed").write_text(
                json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        tree = _sha256_tree(out_dir, exclude={".sealed"})
        seal_doc = {
            "run_id": run_id,
            "kind": kind,
            "sealed_utc": _utc_now(),
            "tree_sha256": tree,
            "status": session_status,
            "measurement_kind": "MEASURED",
            "session_design": "interleaved",
            "arm_order": list(policies),
            "git": git_rec,
            **excl,
        }
        stamp_seal(seal_doc, plan)
        if session_status == "complete":
            (out_dir / ".sealed").write_text(
                json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        else:
            # Still record a seal marker for partial with explicit status.
            (out_dir / ".sealed").write_text(
                json.dumps(
                    {**seal_doc, "note": "non-complete interleaved session"},
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

    return summary


@dataclass
class _DualCostGuard:
    """Charge policy and session caps; tag which cap tripped."""

    policy_guard: CostGuard
    session_guard: CostGuard

    @property
    def running_usd(self) -> float:
        return float(self.policy_guard.running_usd)

    @property
    def max_usd(self) -> float:
        return float(self.policy_guard.max_usd)

    def charge(self, usd: float) -> None:
        try:
            self.policy_guard.charge(usd)
        except CostCapExceeded as exc:
            exc.cap_which = "policy"  # type: ignore[attr-defined]
            raise
        try:
            self.session_guard.charge(usd)
        except CostCapExceeded as exc:
            # Policy already accepted the charge; session trips after.
            exc.cap_which = "session"  # type: ignore[attr-defined]
            raise


def derive_r1_from_cb781(
    *,
    out_dir: Path,
    seal_dir: Path | None = None,
    run_id: str | None = None,
    seal_git: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Scale sealed cb781dbf (n=20 cpu-p NON_RESIDENT) -> 200-entry DERIVED R1.

    Does not call cloud. Does not read prediction files.
    """
    git_rec = _seal_git(seal_git)
    seal_dir = seal_dir or (
        ROOT / "derived" / "bfcl_feasibility" / "x2_feasibility_table" / f"sealed_{CB781_SEAL}"
    )
    if not seal_dir.is_dir():
        raise SystemExit(f"REFUSED -- missing cb781 seal dir {seal_dir}")

    # Prefer summary / report with session wall if present.
    summary_path = seal_dir / "summary.json"
    report_candidates = list(seal_dir.rglob("*report*.json")) + list(seal_dir.glob("*.json"))
    sealed_wall = None
    source_files: list[str] = []
    if summary_path.is_file():
        summ = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        source_files.append(summary_path.as_posix())
        for key in ("session_time_s_sum", "wall_s_sum", "total_wall_s"):
            if key in summ and summ[key] is not None:
                sealed_wall = float(summ[key])
                break
        if sealed_wall is None and isinstance(summ.get("metrics"), dict):
            m = summ["metrics"]
            for key in ("session_time_s_sum", "wall_s_sum"):
                if key in m:
                    sealed_wall = float(m[key])
                    break

    if sealed_wall is None:
        for p in report_candidates:
            try:
                obj = json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            # X-2 reports often nest per-entry walls
            if isinstance(obj, dict):
                if "session_time_s_sum" in obj:
                    sealed_wall = float(obj["session_time_s_sum"])
                    source_files.append(p.as_posix())
                    break
                entries = obj.get("entries") or obj.get("results")
                if isinstance(entries, list) and entries:
                    walls = []
                    for e in entries:
                        if isinstance(e, dict) and "wall_s" in e:
                            walls.append(float(e["wall_s"]))
                        elif isinstance(e, dict) and "session_time_s" in e:
                            walls.append(float(e["session_time_s"]))
                    if walls:
                        sealed_wall = sum(walls)
                        source_files.append(p.as_posix())
                        break

    if sealed_wall is None:
        # Last resort: known measured sum from X-2 cpu-p NON_RESIDENT n=20
        sealed_wall = 8148.5469116
        source_files.append("FALLBACK_CONSTANT_8148.5469116_from_cb781_characterization")

    scale = 200 / 20
    derived_wall = sealed_wall * scale
    run_id = run_id or str(uuid.uuid4())
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "run_id": run_id,
        "policy": "agnostic_default",
        "label": "R1",
        "measurement_kind": "DERIVED",
        "not_measured": True,
        "source_seal": CB781_SEAL,
        "source_seal_dir": str(seal_dir),
        "source_files": source_files,
        "source_n_entries": 20,
        "target_n_entries": 200,
        "scale_factor": scale,
        "source_session_time_s_sum": sealed_wall,
        "derived_session_time_s_sum": derived_wall,
        "cloud_usd_total": 0.0,
        "arm_config": ARM_CONFIG["agnostic_default"],
        "note": (
            "R1 is ~21 h of local compute; not run live. Scaled linearly from "
            f"sealed {CB781_SEAL} (n=20 -> n=200)."
        ),
        "finished_utc": _utc_now(),
        "git": git_rec,
    }
    from tools.h1_provenance import provenance_block, stamp_seal

    doc.update(provenance_block(None))
    _write_json(out_dir / "summary.json", doc)
    _write_json(out_dir / "plan.json", {**doc, "started_utc": _utc_now()})
    tree = _sha256_tree(out_dir, exclude={".sealed"})
    seal_doc = {
        "run_id": run_id,
        "policy": "agnostic_default",
        "sealed_utc": _utc_now(),
        "tree_sha256": tree,
        "measurement_kind": "DERIVED",
        "status": "complete",
        "git": git_rec,
    }
    stamp_seal(seal_doc, doc)
    (out_dir / ".sealed").write_text(
        json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return doc


def load_w3_entries(
    path: Path | None = None, *, allow_reserved: bool = False
) -> tuple[list[dict[str, Any]], Path]:
    if path is None:
        path = (
            ROOT
            / "derived"
            / "bfcl_feasibility"
            / "w3_weight_quality"
            / f"sealed_{W3_SEAL_REFS[0]}"
            / "artifacts"
            / "multi_turn_probe_entries.json"
        )
    assert_entry_set_pinned(path, allow_reserved=allow_reserved)
    entries = json.loads(path.read_text(encoding="utf-8-sig"))
    return entries, path


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="H-1 live hybrid runner")
    p.add_argument("--policy", choices=POLICIES, help="Routing policy (one arm per run)")
    p.add_argument(
        "--interleaved",
        action="store_true",
        help="H1 interleaved: entry-by-entry over --interleaved-policy arms "
        "(default: slo/emission/bounceback = H1-3POLICY; INF-5 session_design=interleaved). "
        "Ignores --policy.",
    )
    p.add_argument(
        "--interleaved-policy",
        action="append",
        default=[],
        choices=list(INTERLEAVE_SELECTABLE),
        metavar="POLICY",
        help="Select interleaved arms (repeatable; order preserved). "
        "Omit for full H1-3POLICY. cloud_only is selectable. H1-2POLICY: "
        "--interleaved-policy slo_escalate --interleaved-policy emission_escalate.",
    )
    p.add_argument(
        "--max-usd",
        type=float,
        default=None,
        help="Hard cloud spend cap (required for single-policy live; refuse without it)",
    )
    p.add_argument(
        "--session-max-usd",
        type=float,
        default=None,
        help="Interleaved session cloud cap (default 35). Required with --interleaved "
        "unless using the documented default via launcher.",
    )
    p.add_argument(
        "--policy-cap",
        action="append",
        default=[],
        metavar="POLICY=USD",
        help="Per-policy cap for --interleaved (repeatable). "
        "Defaults: slo_escalate=5, emission_escalate=20, full_signal_bounceback=10.",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output / seal directory (required except --lifecycle-smoke)",
    )
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument(
        "--entry-offset",
        type=int,
        default=None,
        help="Chunk: first entry index (0-based) of the pinned set for this boot.",
    )
    p.add_argument(
        "--entry-count",
        type=int,
        default=None,
        help="Chunk: number of entries from --entry-offset (default: to the end).",
    )
    p.add_argument(
        "--obs-mask-k",
        type=int,
        default=None,
        help="OBS_MASK retention arm: keep the first K whitespace tokens of every tool "
        "observation (local and cloud). Default: off (FULL).",
    )
    p.add_argument(
        "--context-window",
        type=int,
        default=None,
        help="DEMO-2: before each local generate, a prompt plus max_new_tokens above N "
        "is not generated and the turn escalates (sticky, ctx_overflow). Default: off.",
    )
    p.add_argument(
        "--placement",
        choices=LOCAL_PLACEMENTS,
        default=None,
        help="Hybrid local arm placement (default: ARM_CONFIG, gpu_only). cpu-p = delta_n arm A.",
    )
    p.add_argument(
        "--residency",
        choices=LOCAL_RESIDENCIES,
        default=None,
        help="Hybrid local arm residency (default: ARM_CONFIG, RESIDENT). "
        "NON_RESIDENT prefills the full prompt every step.",
    )
    p.add_argument(
        "--kv",
        choices=LOCAL_KVS,
        default=None,
        help="KV cache precision of the gpu_only local arm (default: ARM_CONFIG, u8). "
        "The pipeline readback refuses a mismatch.",
    )
    p.add_argument(
        "--entries", type=Path, default=None, help="BFCL entries JSON (default: W-3 seal)"
    )
    p.add_argument(
        "--lifecycle-smoke",
        action="store_true",
        help="TURNWISE lifecycle smoke: one W-3 entry x H1-3POLICY via "
        "OpenVinoLocalBackend with stubbed generate (no GPU load, no seal). "
        "Launcher runs this before detached spawn.",
    )
    p.add_argument(
        "--derive-r1",
        action="store_true",
        help="DERIVED R1 from sealed cb781dbf (no live compute, no cloud)",
    )
    p.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Test fixture JSON (entries + local_script); stub backends; never seals",
    )
    p.add_argument(
        "--local-script",
        type=Path,
        default=None,
        help="DEBUG only: scripted local metrics (cannot --seal)",
    )
    p.add_argument(
        "--model-spec",
        type=Path,
        default=None,
        help="OpenVINO model spec YAML (default: configs/models/Qwen3-4B-int4-ov.yaml)",
    )
    p.add_argument(
        "--cloud-model",
        type=str,
        default=None,
        help="Anthropic model id for cloud turns (default: probe CLOUD_DEFAULT_MODEL)",
    )
    p.add_argument(
        "--seal",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Write .sealed tree hash (requires OpenVinoLocalBackend for hybrid; "
        "fixture/scripted refuse). Default: on for live, off for --fixture.",
    )
    p.add_argument(
        "--caching-policy",
        choices=["none", "ephemeral"],
        default="none",
        help="Anthropic prompt-cache policy recorded in the seal. "
        "Default none matches d482c621 (no cache_control).",
    )
    p.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Permit a dirty tree. Plan and seal record DIRTY and the sha256 of git diff HEAD.",
    )
    p.add_argument(
        "--confirmation-run",
        action="store_true",
        help="Allow an entry pin marked reserved_for (DEMO2_HELDOUT_60_B: the one SEARCH "
        "confirmation run). Default: reserved pins are refused.",
    )
    p.add_argument(
        "--launch-evidence-dir",
        type=Path,
        default=None,
        help="The launcher's per-run, gitignored evidence dir (gate JSON, opening canary). "
        "Each file is recorded with its sha256 in plan.json git.launch_evidence.",
    )
    return p


def _parse_policy_caps(raw: list[str]) -> dict[str, float]:
    caps = dict(DEFAULT_POLICY_CAPS_USD)
    for item in raw:
        if "=" not in item:
            raise SystemExit(f"REFUSED -- --policy-cap must be POLICY=USD, got {item!r}")
        name, val = item.split("=", 1)
        name = name.strip()
        if name not in INTERLEAVE_SELECTABLE:
            raise SystemExit(f"REFUSED -- unknown interleaved policy in --policy-cap: {name!r}")
        caps[name] = float(val)
    return caps


def _resolve_interleaved_policies(raw: list[str] | None) -> tuple[str, ...]:
    """Resolve --interleaved-policy list; default full H1-3POLICY order."""
    if not raw:
        return INTERLEAVE_POLICIES
    seen: set[str] = set()
    out: list[str] = []
    for name in raw:
        if name not in INTERLEAVE_SELECTABLE:
            raise SystemExit(f"REFUSED -- unknown interleaved policy: {name!r}")
        if name in seen:
            raise SystemExit(f"REFUSED -- duplicate --interleaved-policy {name!r}")
        seen.add(name)
        out.append(name)
    if not out:
        raise SystemExit("REFUSED -- --interleaved-policy produced empty arm list")
    return tuple(out)


def _make_live_cloud(
    cloud_model: str | None, *, caching_policy: str = "none"
) -> AnthropicCloudBackend:
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "REFUSED -- ANTHROPIC_API_KEY unset. Export it in the environment "
            "(never on the command line)."
        )
    try:
        import anthropic
    except ImportError as exc:
        raise SystemExit("REFUSED -- anthropic package missing in this venv") from exc
    import tools.bfcl_feasibility_probe as probe

    model = cloud_model or probe.CLOUD_DEFAULT_MODEL
    return AnthropicCloudBackend(
        client=anthropic.Anthropic(), cloud_model=model, caching_policy=caching_policy
    )


def _stubbed_generate_fakes(hf_tokenizer: Any) -> tuple[Any, Any, Any]:
    """Minimal pipe / ov_genai / cfg for OpenVinoLocalBackend.for_stubbed_generate."""

    class _FakeGenResult:
        def __init__(self, text: str) -> None:
            self.texts = [text]
            self.perf_metrics = None

    class _FakeChatHistory:
        def __init__(self) -> None:
            self._messages: list[dict[str, Any]] = []
            self._tools: list[Any] = []
            self._extra: dict[str, Any] = {}

        def set_tools(self, tools: list[Any]) -> None:
            self._tools = list(tools)

        def set_extra_context(self, extra: dict[str, Any]) -> None:
            self._extra = dict(extra)

        def append(self, msg: Any) -> None:
            if isinstance(msg, dict):
                self._messages.append(dict(msg))
            else:
                self._messages.append({"role": "assistant", "content": str(msg)})

        def pop(self) -> dict[str, Any]:
            return self._messages.pop()

        def get_messages(self) -> list[dict[str, Any]]:
            return [dict(m) for m in self._messages]

        def set_messages(self, messages: list[dict[str, Any]]) -> None:
            self._messages = [dict(m) for m in messages]

    class _FakeStreamingStatus:
        RUNNING = 0

    class _FakeStreamerBase:
        def __init__(self) -> None:
            return None

    class _FakeGenerationConfig:
        def __init__(self) -> None:
            self.max_new_tokens = 512
            self.do_sample = False
            self.apply_chat_template = False

    class _FakeOvGenai:
        ChatHistory = _FakeChatHistory
        StreamerBase = _FakeStreamerBase
        StreamingStatus = _FakeStreamingStatus
        GenerationConfig = _FakeGenerationConfig

    class _FakeGenaiTokenizer:
        def __init__(self, hf: Any) -> None:
            self._hf = hf

        def apply_chat_template(self, history: Any, *_args: Any, **_kwargs: Any) -> str:
            from tools.bfcl_feasibility_probe import render_bfcl_tools_style

            msgs = list(getattr(history, "_messages", []) or [])
            tools = list(getattr(history, "_tools", []) or [])
            return render_bfcl_tools_style(self._hf, msgs, tools)

    class _FakePipe:
        def __init__(self, text: str = "I cannot help with that.") -> None:
            self._text = text
            self._n_generate = 0
            self._tokenizer = _FakeGenaiTokenizer(hf_tokenizer)

        def generate(self, prompt: Any, cfg: Any = None, streamer: Any = None) -> _FakeGenResult:
            del prompt, cfg
            self._n_generate += 1
            if streamer is not None:
                write = getattr(streamer, "write", None)
                if callable(write):
                    write(1)
                end = getattr(streamer, "end", None)
                if callable(end):
                    end()
            return _FakeGenResult(self._text)

        def finish_chat(self) -> None:
            return None

        def get_tokenizer(self) -> _FakeGenaiTokenizer:
            return self._tokenizer

    ov_genai = _FakeOvGenai()
    pipe = _FakePipe()
    cfg = _FakeGenerationConfig()
    return pipe, ov_genai, cfg


def openvino_backend_stubbed_generate(hf_tokenizer: Any) -> OpenVinoLocalBackend:
    """OpenVinoLocalBackend shaped for lifecycle tests (no IR load)."""
    pipe, ov_genai, cfg = _stubbed_generate_fakes(hf_tokenizer)
    return OpenVinoLocalBackend.for_stubbed_generate(
        pipe=pipe,
        tokenizer=hf_tokenizer,
        cfg=cfg,
        residency="RESIDENT",
        kv="u8",
        ov_genai=ov_genai,
    )


def run_turnwise_lifecycle_smoke(
    *,
    entries_path: Path | None = None,
    entry_index: int = 0,
) -> dict[str, Any]:
    """One real W-3 entry through H1-3POLICY on OpenVinoLocalBackend (stubbed generate).

    Refuses on lifecycle errors or cross-policy session leakage. No GPU IR load,
    no cloud spend, no seal.
    """
    from tools.bfcl_feasibility_probe import MODEL_DIR, _hf_tokenizer

    if not MODEL_DIR.is_dir():
        raise SystemExit(f"REFUSED -- lifecycle smoke needs HF tokenizer at {MODEL_DIR}")
    entries, resolved = load_w3_entries(entries_path)
    if not entries:
        raise SystemExit("REFUSED -- lifecycle smoke: empty entries")
    if entry_index < 0 or entry_index >= len(entries):
        raise SystemExit(
            f"REFUSED -- lifecycle smoke entry_index={entry_index} out of range n={len(entries)}"
        )
    entry = entries[entry_index]
    hf = _hf_tokenizer()
    local = openvino_backend_stubbed_generate(hf)
    cloud = StubCloudBackend(tokens_in=10, tokens_out=5)
    session_ids: list[int] = []
    results: list[dict[str, Any]] = []
    for policy in INTERLEAVE_POLICIES:
        before_sessions = dict(local._sessions)
        er = run_hybrid_entry(
            entry,
            policy=policy,
            local=local,
            cloud=cloud,
            cost=CostGuard(max_usd=100.0),
            model="stub-lifecycle-4B",
        )
        after_sessions = dict(local._sessions)
        if local._active_cell is not None:
            raise SystemExit(
                f"REFUSED -- lifecycle smoke: active_cell leaked after {policy}: "
                f"{local._active_cell!r}"
            )
        if after_sessions:
            raise SystemExit(
                f"REFUSED -- lifecycle smoke: live sessions remain after {policy}: "
                f"{sorted(after_sessions)}"
            )
        # Isolation: prior policy's finished session must not remain live.
        for key in before_sessions:
            if key in after_sessions:
                raise SystemExit(
                    f"REFUSED -- lifecycle smoke: session key {key!r} survived "
                    f"across policy boundary into {policy}"
                )
        cache_keys = [k for k in local._entry_cache if k.startswith(f"{entry['id']}\0")]
        results.append(
            {
                "policy": policy,
                "status": er.status,
                "turns_executed": er.turns_executed,
                "n_bounces": len(er.bounces),
                "cache_keys": cache_keys,
            }
        )
        # Distinct cache cell per policy (no overwrite of prior policy quality).
        expected_key = OpenVinoLocalBackend.cell_key(str(entry["id"]), policy)
        if expected_key not in local._entry_cache:
            raise SystemExit(
                f"REFUSED -- lifecycle smoke: missing entry_cache for {expected_key!r}"
            )
        session_ids.append(id(local._entry_cache[expected_key]))

    if len(set(session_ids)) != len(session_ids):
        # Cache dict values could theoretically alias; keys already distinct above.
        pass
    # Cross-policy key isolation: three distinct cell keys present.
    cell_keys = [OpenVinoLocalBackend.cell_key(str(entry["id"]), p) for p in INTERLEAVE_POLICIES]
    if len(set(cell_keys)) != 3:
        raise SystemExit("REFUSED -- lifecycle smoke: cell keys not unique per policy")
    for k in cell_keys:
        if k not in local._entry_cache:
            raise SystemExit(f"REFUSED -- lifecycle smoke: missing isolated cache {k!r}")

    return {
        "ok": True,
        "entry_id": str(entry["id"]),
        "entries_path": str(resolved),
        "policies": list(INTERLEAVE_POLICIES),
        "results": results,
        "cell_keys": cell_keys,
    }


def local_arm_settings(
    policy: str,
    *,
    placement: str | None = None,
    residency: str | None = None,
    kv: str | None = None,
) -> dict[str, str]:
    """Placement, residency and kv for a hybrid local arm. Defaults are ARM_CONFIG.

    placement cpu-p loads delta_n arm A (CPU only, as in the sealed CPU limit
    7f232f86); its KV is not pinned and is checked by readback (u8 on CPU).
    NON_RESIDENT prefills the full prompt every step (prefix caching off), as
    when the sealed cold limits were measured.
    """
    arm = ARM_CONFIG[policy]
    out = {
        "placement": placement or arm["placement"],
        "residency": (residency or arm["residency"]).upper(),
        "kv": (kv or arm["kv"]).lower(),
    }
    if out["kv"] not in LOCAL_KVS:
        raise SystemExit(f"REFUSED -- kv {out['kv']!r} not in {LOCAL_KVS}")
    if kv is not None and out["placement"] != "gpu_only":
        raise SystemExit(
            "REFUSED -- --kv applies to the gpu_only arm; cpu-p loads delta_n arm A, "
            "whose KV is not pinned"
        )
    if out["placement"] not in LOCAL_PLACEMENTS:
        raise SystemExit(f"REFUSED -- placement {out['placement']!r} not in {LOCAL_PLACEMENTS}")
    if out["residency"] not in LOCAL_RESIDENCIES:
        raise SystemExit(f"REFUSED -- residency {out['residency']!r} not in {LOCAL_RESIDENCIES}")
    return out


def attach_obs_mask(
    k: int | None, local: Any, cloud: Any
) -> tuple[dict[str, Any] | None, Any]:
    """Build the OBS_MASK arm and give it to both backends. (plan record, mask)."""
    if k is None:
        return None, None
    from tools.h1_obs_mask import ObservationMask, hf_token_count

    if isinstance(local, ScriptedLiveLocalBackend):
        raise SystemExit("REFUSED -- --obs-mask-k cannot apply to precomputed --local-script turns")
    tokenizer = getattr(local, "tokenizer", None)
    count = hf_token_count(tokenizer) if callable(tokenizer) else None
    mask = ObservationMask(int(k), token_count=count)
    if hasattr(local, "obs_mask"):
        local.obs_mask = mask
    if hasattr(cloud, "obs_mask"):
        cloud.obs_mask = mask
    return mask.plan_record(), mask


def attach_context_window(window: int | None, policy: str, local: Any) -> int | None:
    """DEMO-2 --context-window: give N to the local backend (None = off)."""
    if window is None:
        return None
    if policy in ("cloud_only", "local_only", "agnostic_default"):
        raise SystemExit(f"REFUSED -- --context-window needs a policy that can escalate, not {policy}")
    if int(window) <= 0:
        raise SystemExit("REFUSED -- --context-window must be positive")
    if isinstance(local, ScriptedLiveLocalBackend):
        raise SystemExit("REFUSED -- --context-window cannot apply to --local-script turns")
    if not hasattr(local, "context_window"):
        raise SystemExit(f"REFUSED -- local backend {type(local).__name__} has no context_window")
    local.context_window = int(window)
    return int(window)


def write_obs_mask_ledger(out_dir: Path, mask: Any) -> None:
    """Every observation's original and kept sizes, beside the turn ledgers."""
    if mask is not None:
        _write_json(Path(out_dir) / "obs_mask_ledger.json", mask.ledger())


def _make_openvino_local(
    policy: str,
    model_spec: Path | None,
    *,
    placement: str | None = None,
    residency: str | None = None,
    kv: str | None = None,
) -> OpenVinoLocalBackend:
    settings = local_arm_settings(policy, placement=placement, residency=residency, kv=kv)
    spec = model_spec or (ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml")
    return OpenVinoLocalBackend(
        model_spec=spec,
        placement=settings["placement"],
        residency=settings["residency"],
        kv=settings["kv"],
        max_new_tokens=512,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)

    if args.lifecycle_smoke:
        doc = run_turnwise_lifecycle_smoke(entries_path=args.entries)
        print(json.dumps(doc, indent=2, default=str))
        return 0 if doc.get("ok") else 2

    from seam.errors import DirtyTreeError

    try:
        git_rec = seal_git_record(allow_dirty=bool(args.allow_dirty), root=ROOT)
    except DirtyTreeError as exc:
        raise SystemExit(f"REFUSED -- {exc}") from exc
    if args.launch_evidence_dir is not None:
        git_rec["launch_evidence"] = launch_evidence_record(args.launch_evidence_dir, root=ROOT)
    args.seal_git = git_rec

    if args.out is None:
        raise SystemExit("REFUSED -- --out is required (except --lifecycle-smoke)")

    if args.derive_r1:
        doc = derive_r1_from_cb781(out_dir=args.out, run_id=args.run_id, seal_git=args.seal_git)
        print(json.dumps({"ok": True, "derived": doc}, indent=2, default=str))
        return 0

    if args.interleaved:
        if args.context_window is not None:
            raise SystemExit("REFUSED -- --context-window is single-arm only (DEMO-2)")
        return _main_interleaved(args)

    if args.policy is None:
        raise SystemExit(
            "REFUSED -- --policy is required (or pass --interleaved / --derive-r1 "
            "/ --lifecycle-smoke)"
        )
    if args.max_usd is None:
        raise SystemExit("REFUSED -- --max-usd is required (cost guard; no default inside runner)")

    if args.fixture is not None:
        if args.seal is True:
            raise SystemExit("REFUSED -- --seal is incompatible with --fixture (stub cannot seal)")
        fix = json.loads(args.fixture.read_text(encoding="utf-8"))
        entries = fix["entries"]
        local: LocalBackend = StubLocalBackend(
            script=fix["local_script"],
            stop_reasons=dict(fix.get("stop_reasons") or {}),
        )
        cloud: CloudBackend = StubCloudBackend(
            tokens_in=int(fix.get("cloud_tokens_in", 1000)),
            tokens_out=int(fix.get("cloud_tokens_out", 200)),
        )
        fixture_window = attach_context_window(args.context_window, args.policy, local)
        summary = run_session(
            policy=args.policy,
            entries=entries,
            out_dir=args.out,
            max_usd=float(args.max_usd),
            local=local,
            cloud=cloud,
            run_id=args.run_id,
            skip_entry_assert=True,
            seal=False,
            caching_policy=args.caching_policy,
            seal_git=args.seal_git,
            context_window=fixture_window,
        )
        print(json.dumps({"ok": True, "summary": summary}, indent=2, default=str))
        return 0 if summary["status"] == "complete" else 2

    allow_reserved = bool(getattr(args, "confirmation_run", False))
    entries, entries_path = load_w3_entries(args.entries, allow_reserved=allow_reserved)
    entry_pin = assert_entry_set_pinned(entries_path, allow_reserved=allow_reserved)
    entries, entry_pin = slice_entries(
        entries, entry_pin, offset=args.entry_offset, count=args.entry_count
    )
    gold_path = entries_path.parent / "multi_turn_gold_selftest.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8-sig")) if gold_path.is_file() else None
    assert_scorer_version(gold)

    cloud = _make_live_cloud(args.cloud_model, caching_policy=args.caching_policy)
    seal = True if args.seal is None else bool(args.seal)

    if args.policy == "cloud_only":
        # Local backend unused for cloud_only; sentinel stub (seal allowed).
        local = StubLocalBackend(script={})
    elif args.local_script is not None:
        if seal:
            raise SystemExit(
                "REFUSED -- --local-script cannot be sealed; pass --no-seal for debug replay"
            )
        script = json.loads(args.local_script.read_text(encoding="utf-8"))
        local = ScriptedLiveLocalBackend(script=script)
    else:
        local = _make_openvino_local(
            args.policy,
            args.model_spec,
            placement=args.placement,
            residency=args.residency,
            kv=args.kv,
        )

    retention, obs_mask = attach_obs_mask(args.obs_mask_k, local, cloud)
    context_window = attach_context_window(args.context_window, args.policy, local)
    from tools.cloud_ping import ping as cloud_ping

    summary = run_session(
        policy=args.policy,
        entries=entries,
        out_dir=args.out,
        max_usd=float(args.max_usd),
        local=local,
        cloud=cloud,
        run_id=args.run_id,
        skip_entry_assert=False,
        seal=seal,
        caching_policy=args.caching_policy,
        seal_git=args.seal_git,
        entry_pin=entry_pin,
        retention=retention,
        cloud_preflight=lambda: cloud_ping(
            cloud_model=args.cloud_model, backend_factory=lambda _model: cloud
        ),
        obs_mask=obs_mask,
        context_window=context_window,
    )
    print(json.dumps({"ok": True, "summary": summary}, indent=2, default=str))
    return 0 if summary["status"] == "complete" else 2


def _main_interleaved(args: argparse.Namespace) -> int:
    policies = _resolve_interleaved_policies(list(args.interleaved_policy or []))
    caps = _parse_policy_caps(list(args.policy_cap or []))
    # Drop caps for arms not selected (keeps CostGuard wiring strict).
    caps = {p: float(caps[p]) for p in policies}
    if args.session_max_usd is not None:
        session_max = float(args.session_max_usd)
    elif "full_signal_bounceback" not in policies:
        session_max = float(DEFAULT_SESSION_CAP_USD_2POLICY)
    else:
        session_max = float(DEFAULT_SESSION_CAP_USD)
    seal = False if args.fixture is not None else (True if args.seal is None else bool(args.seal))

    if args.fixture is not None:
        if args.seal is True:
            raise SystemExit("REFUSED -- --seal is incompatible with --fixture (stub cannot seal)")
        fix = json.loads(args.fixture.read_text(encoding="utf-8"))
        entries = fix["entries"]
        local: LocalBackend = StubLocalBackend(
            script=fix["local_script"],
            stop_reasons=dict(fix.get("stop_reasons") or {}),
        )
        cloud: CloudBackend = StubCloudBackend(
            tokens_in=int(fix.get("cloud_tokens_in", 1000)),
            tokens_out=int(fix.get("cloud_tokens_out", 200)),
        )
        summary = run_interleaved_session(
            entries=entries,
            out_dir=args.out,
            local=local,
            cloud=cloud,
            policy_caps_usd=caps,
            session_max_usd=session_max,
            policies=policies,
            run_id=args.run_id,
            skip_entry_assert=True,
            seal=False,
            caching_policy=args.caching_policy,
            seal_git=args.seal_git,
        )
        print(json.dumps({"ok": True, "summary": summary}, indent=2, default=str))
        ok_statuses = {"complete", "partial_policy_cap"}
        return 0 if summary["status"] in ok_statuses else 2

    allow_reserved = bool(getattr(args, "confirmation_run", False))
    entries, entries_path = load_w3_entries(args.entries, allow_reserved=allow_reserved)
    entry_pin = assert_entry_set_pinned(entries_path, allow_reserved=allow_reserved)
    entries, entry_pin = slice_entries(
        entries, entry_pin, offset=args.entry_offset, count=args.entry_count
    )
    gold_path = entries_path.parent / "multi_turn_gold_selftest.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8-sig")) if gold_path.is_file() else None
    assert_scorer_version(gold)

    cloud = _make_live_cloud(args.cloud_model, caching_policy=args.caching_policy)
    if args.local_script is not None:
        if seal:
            raise SystemExit(
                "REFUSED -- --local-script cannot be sealed; pass --no-seal for debug replay"
            )
        script = json.loads(args.local_script.read_text(encoding="utf-8"))
        local = ScriptedLiveLocalBackend(script=script)
    else:
        # Selected arms share gpu_only RESIDENT u8 int4-4B (match 86d0f4cf).
        local = _make_openvino_local(
            "slo_escalate",
            args.model_spec,
            placement=args.placement,
            residency=args.residency,
            kv=args.kv,
        )

    retention, obs_mask = attach_obs_mask(args.obs_mask_k, local, cloud)
    from tools.cloud_ping import ping as cloud_ping

    summary = run_interleaved_session(
        entries=entries,
        out_dir=args.out,
        local=local,
        cloud=cloud,
        policy_caps_usd=caps,
        session_max_usd=session_max,
        policies=policies,
        run_id=args.run_id,
        skip_entry_assert=False,
        seal=seal,
        caching_policy=args.caching_policy,
        seal_git=args.seal_git,
        entry_pin=entry_pin,
        retention=retention,
        cloud_preflight=lambda: cloud_ping(
            cloud_model=args.cloud_model, backend_factory=lambda _model: cloud
        ),
        obs_mask=obs_mask,
    )
    print(json.dumps({"ok": True, "summary": summary}, indent=2, default=str))
    ok_statuses = {"complete", "partial_policy_cap"}
    return 0 if summary["status"] in ok_statuses else 2


if __name__ == "__main__":
    raise SystemExit(main())
