"""H-1 live hybrid runner — one routing policy per sealed arm.

Policies (``--policy``):
  cloud_only        every turn to cloud
  agnostic_default  local cpu-p NON_RESIDENT int4-4B; router sees task+model only
  slo_escalate      local; escalate on TTFT>10s or decode<6 tok/s or ctx>CAP-1;
                    stay on cloud for the rest of that entry
  emission_escalate local; escalate when no parseable tool call; stay on cloud
                    for the rest of that entry

This module must never open prediction files under derived/d1_replay/ (blinding).
Operators pass ``--max-usd`` explicitly; the launcher may compute the 1.5×
default *outside* this process.

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
CTX_LIMIT = 10_000  # CAP-1 / C-2 cold-start ctx limit

POLICIES = (
    "cloud_only",
    "agnostic_default",
    "slo_escalate",
    "emission_escalate",
    "full_signal_bounceback",  # R2c
)

# R2c: bounce to cloud for one turn, then resume local.
BOUNCE_STEP_BUDGET = 5  # within-turn step count; not MAXIMUM_STEP_LIMIT (20)
BOUNCE_TRIGGERS = (
    "no_parseable_tool_call",
    "step_budget",
    "tool_exec_error",
)

# Local agent-loop stop reasons (entry-level). Distinct events — do not collapse.
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
    turn: int
    trigger: str  # one of BOUNCE_TRIGGERS

    def as_dict(self) -> dict[str, Any]:
        return {"turn": self.turn, "trigger": self.trigger}


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
    where the session stopped. Turns after it did not execute — not SLO
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


def turn_meets_slo(*, ttft_s: float | None, decode_tok_s: float | None, n_ctx: int) -> bool:
    if ttft_s is not None and ttft_s > TTFT_SLO_S:
        return False
    if decode_tok_s is not None and decode_tok_s < DECODE_SLO_TOK_S:
        return False
    if n_ctx > CTX_LIMIT:
        return False
    return True


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
    n_ctx: int,
) -> tuple[bool, str | None]:
    if already_on_cloud:
        return True, "stay_cloud"
    reasons: list[str] = []
    if ttft_s is not None and ttft_s > TTFT_SLO_S:
        reasons.append(f"ttft>{TTFT_SLO_S}")
    if decode_tok_s is not None and decode_tok_s < DECODE_SLO_TOK_S:
        reasons.append(f"decode<{DECODE_SLO_TOK_S}")
    if n_ctx > CTX_LIMIT:
        reasons.append(f"ctx>{CTX_LIMIT}")
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
    # When set (OpenVINO measured path), use as-is — genuine residual, not re-filled.
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

    Probe ``run_multi_turn_agent_entry`` scores in-memory; sealed H-1 trees
    86d0f4cf / 8ffd8371 dropped that payload. Future seals keep it.
    Scope is local-probe only (pre-escalation generation), never improvised.
    """
    if not isinstance(local, OpenVinoLocalBackend):
        return
    eid = str(entry["id"])
    row = local._entry_cache.get(eid)
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
    """

    # entry_id -> list of per-turn dicts
    script: dict[str, list[dict[str, Any]]]
    stop_reasons: dict[str, str] = field(default_factory=dict)
    BACKEND_KIND = "stub"

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

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        rows = self.script[str(entry["id"])]
        if turn_idx >= len(rows):
            raise SystemExit(
                f"REFUSED -- stub turn_idx={turn_idx} out of range "
                f"(n_script={len(rows)}); hybrid must stop at turns_executed"
            )
        row = rows[turn_idx]
        wall = float(row.get("turn_wall_s", 0.05))
        t_gen = float(row.get("t_generate", wall * 0.6))
        t_tok = float(row.get("t_tokenize", wall * 0.1))
        t_tmpl = float(row.get("t_template_build", wall * 0.1))
        t_tool = float(row.get("t_tool_exec", wall * 0.1))
        phases = finalize_phase_timers(
            turn_wall_s=wall,
            t_tool_exec=t_tool,
            t_template_build=t_tmpl,
            t_tokenize=t_tok,
            t_generate=t_gen,
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
            raw_text=str(row.get("raw_text", "")),
            n_steps=(int(row["n_steps"]) if "n_steps" in row else None),
            tool_exec_error=bool(row.get("tool_exec_error", False)),
            tool_exec_error_class=(
                str(row["tool_exec_error_class"])
                if row.get("tool_exec_error_class") is not None
                else None
            ),
        )

    def accept_cloud_context(
        self, entry: dict[str, Any], turn_idx: int, *, text: str
    ) -> None:
        """Record cloud bounce text into local context (stub bookkeeping)."""
        eid = str(entry["id"])
        if not hasattr(self, "_cloud_context"):
            self._cloud_context = {}  # type: ignore[attr-defined]
        self._cloud_context.setdefault(eid, {})[turn_idx] = text  # type: ignore[attr-defined]


@dataclass
class StubCloudBackend:
    tokens_in: int = 1000
    tokens_out: int = 200
    wall_s: float = 0.02
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
            cloud_context_text="[cloud_bounce_context]",
        )


def arm_id_for_h1(arm: dict[str, str]) -> str:
    """Map H-1 arm_config placement/kv → delta_n.yaml arm id."""
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

    Generation is ``bfcl_feasibility_probe.run_multi_turn_agent_entry`` (the
    library function behind ``run_w3_bfcl_quality`` / ``run_x2_feasibility``).
    ``seam/measurement.py`` is the machine-validity envelope only — it does
    not generate tokens; no change was required there.

    Per entry the agent loop runs once (greedy, max_new_tokens=512, W-3 decode
    settings). ``run_turn`` indexes measured ``turn_metrics`` — no scripted
    values. RESIDENT/NON_RESIDENT and KV pins are enforced at pipeline load.
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

    BACKEND_KIND = "openvino"

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

    def _ensure_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        eid = str(entry["id"])
        if eid in self._entry_cache:
            return self._entry_cache[eid]
        import tools.bfcl_feasibility_probe as probe

        if "raw_entry" not in entry or "question" not in entry:
            raise SystemExit(
                f"REFUSED -- entry {eid} missing raw_entry/question "
                "(need full BFCL multi_turn probe entry, not a fixture stub)"
            )
        row = probe.run_multi_turn_agent_entry(
            pipe=self.pipe,
            tokenizer=self.tokenizer,
            cfg=self.cfg,
            entry=entry,
            residency_mode=self.residency,
            ov_genai=self.ov_genai,
        )
        self._entry_cache[eid] = row
        return row

    def local_span(self, entry: dict[str, Any]) -> LocalEntrySpan:
        row = self._ensure_entry(entry)
        turns_in = int(row.get("n_user_turns") or turns_in_entry_count(entry))
        metrics = row.get("turn_metrics") or []
        if not isinstance(metrics, list):
            raise SystemExit(
                f"REFUSED -- turn_metrics not a list for {entry.get('id')}: "
                f"type={type(metrics).__name__}"
            )
        turns_ex = len(metrics)
        reason = row.get("stop_reason")
        if reason not in STOP_REASONS:
            if bool(row.get("force_quit")):
                reason = "max_steps"
            elif turns_ex >= turns_in:
                reason = "completed"
            else:
                raise SystemExit(
                    f"REFUSED -- probe row for {entry.get('id')} missing stop_reason "
                    f"with turns_executed={turns_ex} < turns_in_entry={turns_in}; "
                    f"force_quit={row.get('force_quit')!r} observed_stop={row.get('stop_reason')!r}"
                )
        return LocalEntrySpan(turns_in, turns_ex, str(reason))

    def run_turn(self, entry: dict[str, Any], turn_idx: int, *, model: str) -> BackendTurn:
        row = self._ensure_entry(entry)
        metrics = row.get("turn_metrics") or []
        if not isinstance(metrics, list):
            raise SystemExit(
                f"REFUSED -- turn_metrics not a list for {entry.get('id')}: "
                f"type={type(metrics).__name__}"
            )
        # Short turn_metrics is normal (session stopped). Caller must not index
        # past turns_executed — that is a hybrid-loop bug, not an agent failure.
        if turn_idx >= len(metrics):
            raise SystemExit(
                f"REFUSED -- turn_idx={turn_idx} out of range for entry "
                f"{entry.get('id')} (n_turn_metrics={len(metrics)}). "
                f"Use local_span() and stop at turns_executed; do not assume "
                f"len(turn_metrics) == turns_in_entry."
            )
        tm = metrics[turn_idx]
        if not isinstance(tm, dict):
            raise SystemExit(
                f"REFUSED -- turn_metrics[{turn_idx}] not a dict: "
                f"type={type(tm).__name__} value={tm!r}"
            )
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
        raw_list = row["model_result_raw"] if "model_result_raw" in row else None
        if not isinstance(raw_list, list):
            raise SystemExit(
                f"REFUSED -- entry row missing model_result_raw list; "
                f"observed_keys={sorted(row.keys()) if isinstance(row, dict) else None}"
            )
        # model_result_raw may also be short when the session stopped early.
        raws = raw_list[turn_idx] if turn_idx < len(raw_list) else []
        if not isinstance(raws, list):
            raise SystemExit(
                f"REFUSED -- model_result_raw[{turn_idx}] not a list: "
                f"type={type(raws).__name__}"
            )
        raw_text = "\n".join(str(t) for t in raws if t)
        # Same criterion W-3 uses: a successful decode_execute_qwen step.
        emitted = int(tm["n_decoded_steps"] or 0) > 0
        prompt_tokens = tm["prompt_tokens"]
        n_ctx = int(prompt_tokens) if prompt_tokens is not None else 0
        tool_err = bool(tm.get("tool_exec_error", False))
        tool_err_class = tm.get("tool_exec_error_class")
        if tool_err_class is not None:
            tool_err_class = str(tool_err_class)
        n_steps = int(tm["n_decoded_steps"] or 0)
        # Phase timers are measured residuals from the agent loop (genuine t_other).
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
    if policy == "full_signal_bounceback" and isinstance(local, OpenVinoLocalBackend):
        raise SystemExit(
            "REFUSED -- full_signal_bounceback (R2c) requires turn-by-turn local "
            "generation with cloud context injection; OpenVinoLocalBackend still "
            "precomputes the full entry and cannot bounce. Use a turn-by-turn "
            "backend before sealing R2c."
        )
    if not isinstance(local, OpenVinoLocalBackend):
        raise SystemExit(
            "REFUSED -- --seal requires OpenVinoLocalBackend for hybrid policies. "
            f"Got {local_backend_kind(local)}. Stub/scripted runs cannot be sealed."
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
    """One Anthropic user-turn (native tool-use agent steps) → BackendTurn."""

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
      different events — recorded as ``stop_reason``, not emission escalate.
    - full_signal_bounceback (R2c): on (a) no parseable tool call, (b) step
      count ≥ ``BOUNCE_STEP_BUDGET`` (5) within the turn, or (c) tool exec
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
                result.bounces.append(BounceEvent(turn=turn_idx, trigger=trigger))
                result.cloud_usd_entry += bt_c.cloud_usd
                # Inject cloud output into local context; do NOT stay on cloud.
                accept = getattr(local, "accept_cloud_context", None)
                if callable(accept):
                    accept(
                        entry,
                        turn_idx,
                        text=bt_c.cloud_context_text or bt_c.raw_text or "[cloud]",
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
                n_ctx=bt.n_ctx,
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
                if turn_meets_slo(ttft_s=t.ttft_s, decode_tok_s=t.decode_tok_s, n_ctx=t.n_ctx)
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


def derive_r1_from_cb781(
    *,
    out_dir: Path,
    seal_dir: Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Scale sealed cb781dbf (n=20 cpu-p NON_RESIDENT) → 200-entry DERIVED R1.

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
            f"sealed {CB781_SEAL} (n=20 → n=200)."
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
        "--max-usd",
        type=float,
        default=None,
        help="Hard cloud spend cap (required for live policies; refuse without it)",
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

    if args.policy is None:
        raise SystemExit("REFUSED -- --policy is required (or pass --derive-r1)")
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


if __name__ == "__main__":
    raise SystemExit(main())
