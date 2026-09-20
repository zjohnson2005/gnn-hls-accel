"""H-1 live hybrid runner - one routing policy per sealed arm, or interleaved.

Policies (``--policy``):
  cloud_only        every turn to cloud
  agnostic_default  local cpu-p NON_RESIDENT int4-4B; router sees task+model only
  slo_escalate      local; escalate on MEASURED ttft_s>10s or decode_tok_s<6;
                    stay on cloud for the rest of that entry (no ctx threshold)
  emission_escalate local; escalate when no parseable tool call; stay on cloud
                    for the rest of that entry
  full_signal_bounceback  R2c: one-turn cloud bounce then resume local

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

from tools.phase_timers import finalize_phase_timers, phases_sum_to_wall  # noqa: E402

# ---------------------------------------------------------------------------
# Pins (must match W-3 seals 6225d6e1 / 1d8db970)
# ---------------------------------------------------------------------------
W3_ENTRIES_SHA256 = "3502c5356219f8bf5679f2f5626cb706a1f24b61eb38e51d6921e0fcfcf8628e"
W3_SEAL_REFS = (
    "6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a",
    "1d8db970-4c18-4bcf-824d-d9c141b6eb22",
)
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
DEFAULT_POLICY_CAPS_USD: dict[str, float] = {
    "slo_escalate": 5.0,
    "emission_escalate": 20.0,
    "full_signal_bounceback": 10.0,
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
    if set(policies) == set(INTERLEAVE_POLICIES_2POLICY) and "full_signal_bounceback" not in policies:
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
}

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

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
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
    re_prefill_source: str | None = None  # measured | stub_zero | inferred_unmeasured | pending_next_local
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
    trajectory_pass: bool | None = None
    score_error_type: str | None = None
    score_error_message: str | None = None
    model_result_decoded: list[Any] | None = None
    quality_scope: str | None = None  # "local_probe" | None

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
            "score_error_type": self.score_error_type,
            "score_error_message": self.score_error_message,
            "quality_scope": self.quality_scope,
            "turns": [t.as_dict() for t in self.turns],
        }

    def as_quality_dict(self) -> dict[str, Any]:
        """Full quality payload including decoded tool calls for offline re-score."""
        return {
            "entry_id": self.entry_id,
            "trajectory_pass": self.trajectory_pass,
            "score_error_type": self.score_error_type,
            "score_error_message": self.score_error_message,
            "quality_scope": self.quality_scope,
            "model_result_decoded": self.model_result_decoded,
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
    eid = str(entry["id"])
    row = local._entry_cache.get(eid)
    if not isinstance(row, dict):
        finalize = getattr(local, "finalize_entry", None)
        if callable(finalize):
            row = finalize(entry)
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
    result.quality_scope = "local_probe"


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
            raise SystemExit(
                "REFUSED -- measured phase timers do not sum to turn_wall within 1 ms"
            )
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
    _history: dict[str, list[dict[str, Any]]] = field(default_factory=dict, repr=False)
    _cloud_context: dict[str, dict[int, str]] = field(default_factory=dict, repr=False)
    _last_injection: dict[str, Any] = field(default_factory=dict, repr=False)
    _pending_reprefill: dict[str, bool] = field(default_factory=dict, repr=False)

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

    def history_for(self, entry_id: str) -> list[dict[str, Any]]:
        return list(self._history.get(str(entry_id), []))

    def context_contains(self, entry_id: str, text: str) -> bool:
        return any(
            text in str(m.get("content", "")) for m in self._history.get(str(entry_id), [])
        )

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        eid = str(entry["id"])
        rows = self.script[eid]
        if turn_idx >= len(rows):
            raise SystemExit(
                f"REFUSED -- stub turn_idx={turn_idx} out of range "
                f"(n_script={len(rows)}); hybrid must stop at turns_executed"
            )
        row = rows[turn_idx]
        # Mirror RESIDENT: user turn enters history before local generate.
        hist = self._history.setdefault(eid, [])
        hist.append({"role": "user", "content": f"[stub_user_turn_{turn_idx}]"})
        # After a bounce inject, the next local turn *sees* cloud assistant text.
        saw_cloud = any(m.get("role") == "assistant" and m.get("source") == "cloud" for m in hist)
        wall = float(row.get("turn_wall_s", 0.05))
        t_gen = float(row.get("t_generate", wall * 0.6))
        t_tok = float(row.get("t_tokenize", wall * 0.1))
        t_tmpl = float(row.get("t_template_build", wall * 0.1))
        t_tool = float(row.get("t_tool_exec", wall * 0.1))
        # Stub: synthetic re-prefill accounted on the first local turn after inject.
        if self._pending_reprefill.pop(eid, False):
            # Real OpenVINO measures this; stub records explicit zero (not hidden).
            inj = self._last_injection.get(eid) or {}
            inj["re_prefill_s"] = 0.0
            inj["re_prefill_source"] = "stub_zero"
            self._last_injection[eid] = inj
        phases = finalize_phase_timers(
            turn_wall_s=wall,
            t_tool_exec=t_tool,
            t_template_build=t_tmpl,
            t_tokenize=t_tok,
            t_generate=t_gen,
        )
        raw = str(row.get("raw_text", ""))
        if saw_cloud and not raw:
            raw = "[local_after_cloud_inject]"
        hist.append({"role": "assistant", "content": raw or f"[stub_local_turn_{turn_idx}]", "source": "local"})
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
        hist = self._history.setdefault(eid, [])
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
        self._cloud_context.setdefault(eid, {})[turn_idx] = text
        self._pending_reprefill[eid] = True
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
        self._last_injection[eid] = receipt.as_dict()
        return self._last_injection[eid]


@dataclass
class StubCloudBackend:
    tokens_in: int = 1000
    tokens_out: int = 200
    wall_s: float = 0.02
    cloud_context_text: str = "[cloud_bounce_context]"
    # Optional per-call hook for cost-guard tests
    on_call: Callable[[], None] | None = None

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        if self.on_call is not None:
            self.on_call()
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
    """

    model_spec: Path
    placement: str
    residency: str
    kv: str
    max_new_tokens: int = 512
    arm_id: str = field(init=False)
    pipe: Any = field(init=False, repr=False)
    tokenizer: Any = field(init=False, repr=False)
    cfg: Any = field(init=False, repr=False)
    ov_genai: Any = field(init=False, repr=False)
    load_meta: dict[str, Any] = field(init=False, default_factory=dict)
    _entry_cache: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _sessions: dict[str, Any] = field(default_factory=dict, repr=False)
    _span_state: dict[str, LocalEntrySpan] = field(default_factory=dict, repr=False)
    _cloud_context: dict[str, dict[int, str]] = field(default_factory=dict, repr=False)
    _last_injection: dict[str, Any] = field(default_factory=dict, repr=False)

    BACKEND_KIND = "openvino"
    TURNWISE = True

    def __post_init__(self) -> None:
        import openvino_genai as ov_genai

        import tools.bfcl_feasibility_probe as probe

        residency = self.residency.upper()
        if residency not in ("RESIDENT", "NON_RESIDENT"):
            raise SystemExit(f"REFUSED -- residency must be RESIDENT|NON_RESIDENT, got {residency!r}")
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
        pipe, meta, _load_s = probe.load_arm_pipeline(
            self.arm_id, enable_prefix_caching=enable_pc
        )
        # load_arm_pipeline already raises on KV_PRECISION_MISMATCH when the arm
        # requests a pin. Re-check expected kv against readback for H-1 arm_config.
        self._assert_kv_readback(meta, expected=self.kv)
        self.pipe = pipe
        self.tokenizer = probe._hf_tokenizer()
        self.ov_genai = ov_genai
        self.load_meta = meta
        cfg = ov_genai.GenerationConfig()
        cfg.max_new_tokens = int(self.max_new_tokens)
        cfg.do_sample = False
        cfg.apply_chat_template = False
        self.cfg = cfg

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
                    f"REFUSED -- loads[{i}] missing kv_cache_precision; "
                    f"observed={load!r}"
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

    def _ensure_session(self, entry: dict[str, Any]) -> Any:
        """Return the live MultiTurnAgentSession for this entry (begin once)."""
        eid = str(entry["id"])
        if eid in self._sessions:
            return self._sessions[eid]
        import tools.bfcl_feasibility_probe as probe

        if "raw_entry" not in entry or "question" not in entry:
            raise SystemExit(
                f"REFUSED -- entry {eid} missing raw_entry/question "
                "(need full BFCL multi_turn probe entry, not a fixture stub)"
            )
        session = probe.MultiTurnAgentSession(
            pipe=self.pipe,
            tokenizer=self.tokenizer,
            cfg=self.cfg,
            residency_mode=self.residency,
            ov_genai=self.ov_genai,
        )
        session.begin(entry)
        self._sessions[eid] = session
        return session

    def finalize_entry(self, entry: dict[str, Any]) -> dict[str, Any] | None:
        """Finish the session and cache the probe row (idempotent)."""
        eid = str(entry["id"])
        if eid in self._entry_cache:
            return self._entry_cache[eid]
        session = self._sessions.get(eid)
        if session is None:
            return None
        if not getattr(session, "_finished", False):
            row = session.finish()
            self._entry_cache[eid] = row
            return row
        return self._entry_cache.get(eid)

    def local_span(self, entry: dict[str, Any]) -> LocalEntrySpan:
        """Progressive span: provisional complete until force_quit shortens it.

        The returned object is cached and mutated when ``run_turn`` hits
        ``force_quit``, so ``run_hybrid_entry`` sees the updated bound.
        """
        eid = str(entry["id"])
        if eid in self._span_state:
            return self._span_state[eid]
        turns_in = turns_in_entry_count(entry)
        span = LocalEntrySpan(turns_in, turns_in, "completed")
        self._span_state[eid] = span
        return span

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        del model  # configuration pin only; generation uses loaded IR
        eid = str(entry["id"])
        session = self._ensure_session(entry)
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
        raws = session.all_model_response[turn_idx] if turn_idx < len(session.all_model_response) else []
        if not isinstance(raws, list):
            raise SystemExit(
                f"REFUSED -- model_result_raw[{turn_idx}] not a list: "
                f"type={type(raws).__name__}"
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
        # Backfill measured re-prefill onto the last injection receipt.
        if session._last_reprefill_s is not None and eid in self._last_injection:
            inj = self._last_injection[eid]
            if inj.get("re_prefill_s") is None:
                inj["re_prefill_s"] = float(session._last_reprefill_s)
                inj["re_prefill_source"] = str(
                    session._last_reprefill_source or "measured"
                )
                self._last_injection[eid] = inj
        # Finalize probe row when entry completes or force-quits.
        turns_in = turns_in_entry_count(entry)
        if session.force_quit or turn_idx >= turns_in - 1:
            self.finalize_entry(entry)
        return BackendTurn(
            n_ctx=n_ctx,
            ttft_s=(float(tm["ttft_s"]) if tm["ttft_s"] is not None else None),
            decode_tok_s=(
                float(tm["decode_tok_s"]) if tm["decode_tok_s"] is not None else None
            ),
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
        session = self._ensure_session(entry)
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
        self._cloud_context.setdefault(eid, {})[turn_idx] = text
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
        self._last_injection[eid] = receipt.as_dict()
        return self._last_injection[eid]


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
    _entry_cache: dict[str, dict[str, Any]] = field(default_factory=dict)

    def _ensure_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        eid = str(entry["id"])
        if eid not in self._entry_cache:
            import tools.bfcl_feasibility_probe as probe

            row = probe.run_cloud_multi_turn_agent_entry(
                client=self.client,
                model=self.cloud_model,
                max_tokens=self.max_tokens,
                entry=entry,
                running_usd=0.0,
            )
            self._entry_cache[eid] = row
        return self._entry_cache[eid]

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        row = self._ensure_entry(entry)
        calls = [c for c in (row.get("calls") or []) if int(c.get("user_turn", c.get("turn", -1))) == turn_idx]
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
        phases = finalize_phase_timers(
            turn_wall_s=wall,
            t_tool_exec=0.0,
            t_template_build=0.0,
            t_tokenize=0.0,
            t_generate=wall * 0.9,
        )
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


def load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"completed_entry_ids": [], "running_usd": 0.0, "entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(path: Path, state: dict[str, Any]) -> None:
    _write_json(path, state)


# ---------------------------------------------------------------------------
# Entry / scorer asserts
# ---------------------------------------------------------------------------
def assert_entry_set_matches_w3(entries_path: Path) -> dict[str, Any]:
    digest = _sha256_file(entries_path)
    if digest != W3_ENTRIES_SHA256:
        raise SystemExit(
            f"REFUSED -- multi_turn entries sha256 {digest} != W-3 pin {W3_ENTRIES_SHA256} "
            f"(seals {', '.join(W3_SEAL_REFS)})"
        )
    entries = json.loads(entries_path.read_text(encoding="utf-8-sig"))
    if not isinstance(entries, list) or len(entries) != 200:
        raise SystemExit(f"REFUSED -- expected 200 entries, got {type(entries)} n={getattr(entries, '__len__', lambda: '?')()}")
    return {"sha256": digest, "n": len(entries), "seal_refs": list(W3_SEAL_REFS)}


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
                result.turns.append(ledger)
                result.cloud_usd_entry += bt.cloud_usd
                result.status = "aborted_cap"
                result.turns_executed = len(result.turns)
                attach_local_probe_quality(result, local, entry)
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
            result.turns.append(ledger)
            result.cloud_usd_entry += bt.cloud_usd
            continue

        # --- past local span: turns did not happen ---
        if turn_idx >= local_span.turns_executed:
            break

        # Local turn (must exist in span)
        bt = local.run_turn(entry, turn_idx, model=model)

        # --- R2c bounceback: one-turn cloud, then resume local ---
        if policy == "full_signal_bounceback":
            bounce, trigger = decide_bounceback(
                emitted_parseable_tool_call=bt.emitted_parseable_tool_call,
                n_steps=bt.n_steps,
                tool_exec_error=bool(bt.tool_exec_error),
            )
            if bounce:
                assert trigger is not None
                bt_c = cloud.run_turn(entry, turn_idx, model=model)
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
                            bounce_trigger=trigger,
                            tool_exec_error=bool(bt.tool_exec_error),
                            tool_exec_error_class=bt.tool_exec_error_class,
                        )
                    )
                    result.bounces.append(BounceEvent(turn=turn_idx, trigger=trigger))
                    result.cloud_usd_entry += bt_c.cloud_usd
                    result.status = "aborted_cap"
                    result.turns_executed = len(result.turns)
                    attach_local_probe_quality(result, local, entry)
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
                        bounce_trigger=trigger,
                        tool_exec_error=bool(bt.tool_exec_error),
                        tool_exec_error_class=bt.tool_exec_error_class,
                    )
                )
                result.cloud_usd_entry += bt_c.cloud_usd
                # Inject cloud output into local context; do NOT stay on cloud.
                cloud_text = (
                    bt_c.cloud_context_text or bt_c.raw_text or "[cloud]"
                )
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
                        cloud_tokens_in=int(
                            inj.get("cloud_tokens_in", bt_c.cloud_tokens_in) or 0
                        ),
                        cloud_tokens_out=int(
                            inj.get("cloud_tokens_out", bt_c.cloud_tokens_out) or 0
                        ),
                        cloud_usd=float(inj.get("cloud_usd", bt_c.cloud_usd) or 0.0),
                        re_prefill_s=(
                            float(inj["re_prefill_s"])
                            if inj.get("re_prefill_s") is not None
                            else None
                        ),
                        re_prefill_required=bool(
                            inj.get("re_prefill_required", True)
                        ),
                        re_prefill_source=(
                            str(inj["re_prefill_source"])
                            if inj.get("re_prefill_source") is not None
                            else "pending_next_local"
                        ),
                        control_return_turn=int(
                            inj.get("control_return_turn", turn_idx + 1)
                        ),
                        kv_valid_after_inject=bool(
                            inj.get("kv_valid_after_inject", False)
                        ),
                        shared_tool_exec=bool(inj.get("shared_tool_exec", True)),
                    )
                )
                # Resume local on subsequent turns.
                if turn_idx == local_span.turns_executed - 1 and local_span.stop_reason != "completed":
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
                    tool_exec_error=bool(bt.tool_exec_error),
                    tool_exec_error_class=bt.tool_exec_error_class,
                )
            )
            # Backfill re_prefill onto the prior bounce once the next local turn ran.
            _inj = getattr(local, "_last_injection", None)
            if isinstance(_inj, dict):
                _rec = _inj.get(str(entry["id"])) or {}
                if result.bounces and _rec.get("re_prefill_s") is not None:
                    _b = result.bounces[-1]
                    if _b.re_prefill_s is None and _b.control_return_turn == turn_idx:
                        _b.re_prefill_s = float(_rec["re_prefill_s"])
                        _b.re_prefill_source = str(
                            _rec.get("re_prefill_source") or "stub_zero"
                        )
            if (
                turn_idx == local_span.turns_executed - 1
                and local_span.stop_reason != "completed"
            ):
                break
            continue

        escalate = False
        reason: str | None = None
        if policy == "agnostic_default":
            escalate, reason = False, None
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
                        tool_exec_error=bool(bt.tool_exec_error),
                        tool_exec_error_class=bt.tool_exec_error_class,
                    )
                )
                result.cloud_usd_entry += bt_c.cloud_usd
                result.status = "aborted_cap"
                result.turns_executed = len(result.turns)
                attach_local_probe_quality(result, local, entry)
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
                    tool_exec_error=bool(bt.tool_exec_error),
                    tool_exec_error_class=bt.tool_exec_error_class,
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
            ok = sum(
                1
                for t in ran
                if turn_meets_slo(ttft_s=t.ttft_s, decode_tok_s=t.decode_tok_s)
            )
            result.slo_fraction = ok / len(ran)
        else:
            result.slo_fraction = None

    attach_local_probe_quality(result, local, entry)
    return result


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------
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

    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_id or str(uuid.uuid4())
    arm = ARM_CONFIG[policy]
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
        "w3_entry_pin": W3_ENTRIES_SHA256,
        "w3_seal_refs": list(W3_SEAL_REFS),
        "scorer": assert_scorer_version(),
        "resume_from_completed": sorted(completed),
    }
    if isinstance(local, OpenVinoLocalBackend):
        plan["openvino"] = {
            "arm_id": local.arm_id,
            "model_spec": str(local.model_spec),
            "residency": local.residency,
            "kv": local.kv,
            "max_new_tokens": local.max_new_tokens,
            "load_meta": local.load_meta,
        }
    if not skip_entry_assert:
        # When entries were loaded from the W-3 pin file, hash is checked at load.
        plan["entry_assert"] = {"n": len(entries), "mode": "caller_supplied"}
    _write_json(out_dir / "plan.json", plan)

    status = "complete"
    abort_reason: str | None = None
    abort_verbatim: str | None = None
    summary_written = False

    def _write_session_summary() -> dict[str, Any]:
        nonlocal summary_written
        n_scored = sum(1 for q in quality_rows if q.get("trajectory_pass") is not None)
        n_pass = sum(1 for q in quality_rows if q.get("trajectory_pass") is True)
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
                "scope": "local_probe",
                "n_entries_with_score": n_scored,
                "n_trajectory_pass": n_pass,
                "path": "entry_quality.json",
            },
        }
        _write_json(out_dir / "summary.json", doc)
        _write_json(out_dir / "turn_ledger.json", {"entries": ledger_rows})
        _write_json(out_dir / "entry_quality.json", {"entries": quality_rows})
        summary_written = True
        return doc

    try:
        for entry in entries:
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
                )
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
                _write_json(out_dir / "turn_ledger.json", {"entries": ledger_rows})
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
            _write_json(out_dir / "turn_ledger.json", {"entries": ledger_rows})
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

    if seal and status == "complete":
        tree = _sha256_tree(out_dir, exclude={".sealed"})
        seal_doc = {
            "run_id": run_id,
            "policy": policy,
            "sealed_utc": _utc_now(),
            "tree_sha256": tree,
            "status": status,
            "measurement_kind": "MEASURED",
        }
        (out_dir / ".sealed").write_text(
            json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        summary["tree_sha256"] = tree
        _write_json(out_dir / "summary.json", summary)
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
        }
        (out_dir / ".sealed").write_text(
            json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        summary["tree_sha256"] = tree
        _write_json(out_dir / "summary.json", summary)

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
) -> dict[str, Any]:
    """Entry-by-entry interleave of selected H1 policy arms (INF-5 session_design=interleaved).

    For each entry, run policies in ``policies`` order. Each policy has its own
    cost cap and completed-entry set under ``out_dir/policies/<policy>/``.
    A policy-cap abort stops *that* arm only; other arms continue. A session-cap
    abort stops remaining work across all arms. Resume never re-bills a
    completed (policy, entry) pair. When R2c is omitted from ``policies``,
    plan/summary/seal record ``r2c_excluded`` so the artifact is not mistaken
    for the full three-policy comparison.
    """
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
        arm = ARM_CONFIG[policy]
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
    plan = {
        "run_id": run_id,
        "kind": kind,
        "session_design": "interleaved",
        "arm_order": list(policies),
        "policy_caps_usd": {p: float(caps[p]) for p in policies},
        "session_max_usd": float(session_max_usd),
        "n_entries": len(entries),
        "measurement_kind": "MEASURED",
        "local_backend": local_backend_kind(local),
        "seal": bool(seal),
        "started_utc": _utc_now(),
        "w3_entry_pin": W3_ENTRIES_SHA256,
        "w3_seal_refs": list(W3_SEAL_REFS),
        "scorer": assert_scorer_version(),
        "kv_match_seal": "86d0f4cf-e8c2-4ce5-96da-04c6a9c129f3",
        "placement": "gpu_only",
        "residency": "RESIDENT",
        "tier": "4B",
        "weight": "int4",
        "resume_completed_by_policy": {
            p: sorted(state[p]["completed"]) for p in policies
        },
        **excl,
    }
    if isinstance(local, OpenVinoLocalBackend):
        plan["openvino"] = {
            "arm_id": local.arm_id,
            "model_spec": str(local.model_spec),
            "residency": local.residency,
            "kv": local.kv,
            "max_new_tokens": local.max_new_tokens,
            "load_meta": local.load_meta,
        }
    if not skip_entry_assert:
        plan["entry_assert"] = {"n": len(entries), "mode": "caller_supplied"}
    _write_json(out_dir / "plan.json", plan)

    session_status = "complete"
    session_abort: str | None = None
    cell_log: list[dict[str, Any]] = list(session_ckpt.get("cell_log") or [])

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
        _write_json(pdir / "turn_ledger.json", {"entries": st["ledger_rows"]})
        _write_json(pdir / "entry_quality.json", {"entries": st["quality_rows"]})
        n_scored = sum(1 for q in st["quality_rows"] if q.get("trajectory_pass") is not None)
        n_pass = sum(1 for q in st["quality_rows"] if q.get("trajectory_pass") is True)
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
                    "scope": "local_probe",
                    "n_entries_with_score": n_scored,
                    "n_trajectory_pass": n_pass,
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

    try:
        for entry in entries:
            eid = str(entry["id"])
            for policy in policies:
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
                    )
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
                        e
                        for e in entries
                        if str(e["id"]) not in state[policy]["completed"]
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
                "path": str(_policy_subdir(out_dir, p).relative_to(out_dir)).replace(
                    "\\", "/"
                ),
            }
            for p in policies
        },
        "finished_utc": _utc_now(),
        **excl,
    }
    _write_json(out_dir / "summary.json", summary)

    if seal:
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
                **excl,
            }
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
            **excl,
        }
        if session_status == "complete":
            (out_dir / ".sealed").write_text(
                json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            summary["tree_sha256"] = tree
            _write_json(out_dir / "summary.json", summary)
        else:
            # Still record a seal marker for partial with explicit status.
            (out_dir / ".sealed").write_text(
                json.dumps({**seal_doc, "note": "non-complete interleaved session"}, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            summary["tree_sha256"] = tree
            _write_json(out_dir / "summary.json", summary)

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
) -> dict[str, Any]:
    """Scale sealed cb781dbf (n=20 cpu-p NON_RESIDENT) -> 200-entry DERIVED R1.

    Does not call cloud. Does not read prediction files.
    """
    seal_dir = seal_dir or (
        ROOT
        / "derived"
        / "bfcl_feasibility"
        / "x2_feasibility_table"
        / f"sealed_{CB781_SEAL}"
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
    }
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
    }
    (out_dir / ".sealed").write_text(
        json.dumps(seal_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    doc["tree_sha256"] = tree
    _write_json(out_dir / "summary.json", doc)
    return doc


def load_w3_entries(path: Path | None = None) -> tuple[list[dict[str, Any]], Path]:
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
    assert_entry_set_matches_w3(path)
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
        choices=list(INTERLEAVE_POLICIES),
        metavar="POLICY",
        help="Select interleaved arms (repeatable; order preserved). "
        "Omit for full H1-3POLICY. H1-2POLICY: "
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
    p.add_argument("--out", type=Path, required=True, help="Output / seal directory")
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--entries", type=Path, default=None, help="BFCL entries JSON (default: W-3 seal)")
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
    return p


def _parse_policy_caps(raw: list[str]) -> dict[str, float]:
    caps = dict(DEFAULT_POLICY_CAPS_USD)
    for item in raw:
        if "=" not in item:
            raise SystemExit(f"REFUSED -- --policy-cap must be POLICY=USD, got {item!r}")
        name, val = item.split("=", 1)
        name = name.strip()
        if name not in INTERLEAVE_POLICIES:
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
        if name not in INTERLEAVE_POLICIES:
            raise SystemExit(f"REFUSED -- unknown interleaved policy: {name!r}")
        if name in seen:
            raise SystemExit(f"REFUSED -- duplicate --interleaved-policy {name!r}")
        seen.add(name)
        out.append(name)
    if not out:
        raise SystemExit("REFUSED -- --interleaved-policy produced empty arm list")
    return tuple(out)


def _make_live_cloud(cloud_model: str | None) -> AnthropicCloudBackend:
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
    return AnthropicCloudBackend(client=anthropic.Anthropic(), cloud_model=model)


def _make_openvino_local(policy: str, model_spec: Path | None) -> OpenVinoLocalBackend:
    arm = ARM_CONFIG[policy]
    spec = model_spec or (ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml")
    return OpenVinoLocalBackend(
        model_spec=spec,
        placement=arm["placement"],
        residency=arm["residency"],
        kv=arm["kv"],
        max_new_tokens=512,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)

    if args.derive_r1:
        doc = derive_r1_from_cb781(out_dir=args.out, run_id=args.run_id)
        print(json.dumps({"ok": True, "derived": doc}, indent=2, default=str))
        return 0

    if args.interleaved:
        return _main_interleaved(args)

    if args.policy is None:
        raise SystemExit(
            "REFUSED -- --policy is required (or pass --interleaved / --derive-r1)"
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
        )
        print(json.dumps({"ok": True, "summary": summary}, indent=2, default=str))
        return 0 if summary["status"] == "complete" else 2

    entries, entries_path = load_w3_entries(args.entries)
    gold_path = entries_path.parent / "multi_turn_gold_selftest.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8-sig")) if gold_path.is_file() else None
    assert_scorer_version(gold)

    cloud = _make_live_cloud(args.cloud_model)
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
        local = _make_openvino_local(args.policy, args.model_spec)

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
        )
        print(json.dumps({"ok": True, "summary": summary}, indent=2, default=str))
        ok_statuses = {"complete", "partial_policy_cap"}
        return 0 if summary["status"] in ok_statuses else 2

    entries, entries_path = load_w3_entries(args.entries)
    gold_path = entries_path.parent / "multi_turn_gold_selftest.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8-sig")) if gold_path.is_file() else None
    assert_scorer_version(gold)

    cloud = _make_live_cloud(args.cloud_model)
    if args.local_script is not None:
        if seal:
            raise SystemExit(
                "REFUSED -- --local-script cannot be sealed; pass --no-seal for debug replay"
            )
        script = json.loads(args.local_script.read_text(encoding="utf-8"))
        local = ScriptedLiveLocalBackend(script=script)
    else:
        # Selected arms share gpu_only RESIDENT u8 int4-4B (match 86d0f4cf).
        local = _make_openvino_local("slo_escalate", args.model_spec)

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
    )
    print(json.dumps({"ok": True, "summary": summary}, indent=2, default=str))
    ok_statuses = {"complete", "partial_policy_cap"}
    return 0 if summary["status"] in ok_statuses else 2


if __name__ == "__main__":
    raise SystemExit(main())
