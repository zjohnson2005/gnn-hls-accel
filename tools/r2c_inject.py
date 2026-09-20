"""R2c cloud->local context injection (RESIDENT ChatHistory path).

R2c vs R2b
----------
R2b escalates and *stays* on cloud. R2c bounces for one turn then returns
control to local with the cloud assistant turn present in local context so
the next local prefill delta includes it.

ChatHistory / resident_history
------------------------------
OpenVINO GenAI ``ChatHistory.append({"role": "assistant", "content": ...})``
accepts an externally produced assistant turn the same way it accepts a
locally generated one (message list only). Tool messages use the same
``_chat_message_for_genai`` shape as ``run_multi_turn_agent_entry``.

KV validity after external append
---------------------------------
**Invalid.** Prefix/KV state was built from tokens the *local* model emitted.
An injected cloud assistant string was never decoded through the local
pipeline, so the resident KV no longer matches the ChatHistory token
sequence. Policy: call ``pipe.finish_chat()`` (drops chat-mode KV), then on
the next local ``generate(ChatHistory)`` pay a full (or divergence-point)
re-prefill. That re-prefill wall time is a first-class bounce cost
(``re_prefill_s``), not hidden overhead.

Shared tool execution
---------------------
Cloud tool calls on a bounce turn must invoke the same
``execute_multi_turn_func_call`` path with the **same** BFCL ``model_name``
as the local resident session so instance state is shared. Do not spin a
second warm-up with a different ``model_name``.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable


@dataclass
class InjectionReceipt:
    """Record of one cloud->local context injection after a bounce."""

    entry_id: str
    bounce_turn: int
    trigger_class: str
    assistant_text: str
    n_tool_messages: int
    kv_valid_after_inject: bool
    re_prefill_required: bool
    re_prefill_s: float | None
    re_prefill_source: str  # "measured" | "stub_zero" | "inferred_unmeasured" | "pending_next_local"
    control_return_turn: int  # first local turn index after bounce
    cloud_tokens_in: int = 0
    cloud_tokens_out: int = 0
    cloud_usd: float = 0.0
    shared_tool_exec: bool = True
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SharedBfclToolState:
    """Single BFCL model_name + call log shared by local and cloud bounce turns."""

    model_name: str
    calls: list[dict[str, Any]] = field(default_factory=list)
    execute_fn: Callable[..., Any] | None = None

    def execute(
        self,
        decoded: list[str],
        *,
        initial_config: dict[str, Any],
        involved_classes: list[str],
        test_entry_id: str,
        long_context: bool,
    ) -> Any:
        self.calls.append(
            {
                "model_name": self.model_name,
                "n_calls": len(decoded),
                "decoded_head": decoded[:3],
            }
        )
        if self.execute_fn is None:
            # Stub path: no live BFCL instances; record only.
            return [f"stub_ok:{c}" for c in decoded], {}
        return self.execute_fn(
            decoded,
            initial_config,
            involved_classes,
            self.model_name,
            test_entry_id,
            long_context=long_context,
            is_evaL_run=False,
        )


def inject_assistant_into_chat_history(
    history: Any,
    *,
    assistant_text: str,
    tool_messages: list[dict[str, Any]] | None = None,
) -> int:
    """Append cloud assistant (+ optional tool msgs) to a GenAI ChatHistory.

    Returns number of tool messages appended. Does **not** extend KV - caller
    must invalidate chat KV (``finish_chat``) before the next generate.
    """
    history.append({"role": "assistant", "content": str(assistant_text)})
    n_tools = 0
    for msg in tool_messages or []:
        role = str(msg.get("role") or "tool")
        content = str(msg.get("content") or "")
        out: dict[str, Any] = {"role": role, "content": content}
        if msg.get("name") is not None:
            out["name"] = str(msg["name"])
        history.append(out)
        n_tools += 1
    return n_tools


def invalidate_resident_kv(pipe: Any) -> None:
    """Drop chat-mode KV so the next generate re-prefills from ChatHistory."""
    finish = getattr(pipe, "finish_chat", None)
    if callable(finish):
        finish()


def build_injection_receipt(
    *,
    entry_id: str,
    bounce_turn: int,
    trigger_class: str,
    assistant_text: str,
    n_tool_messages: int = 0,
    cloud_tokens_in: int = 0,
    cloud_tokens_out: int = 0,
    cloud_usd: float = 0.0,
    re_prefill_s: float | None = None,
    re_prefill_source: str = "pending_next_local",
    shared_tool_exec: bool = True,
    note: str = "",
) -> InjectionReceipt:
    return InjectionReceipt(
        entry_id=entry_id,
        bounce_turn=bounce_turn,
        trigger_class=trigger_class,
        assistant_text=assistant_text,
        n_tool_messages=n_tool_messages,
        kv_valid_after_inject=False,
        re_prefill_required=True,
        re_prefill_s=re_prefill_s,
        re_prefill_source=re_prefill_source,
        control_return_turn=bounce_turn + 1,
        cloud_tokens_in=cloud_tokens_in,
        cloud_tokens_out=cloud_tokens_out,
        cloud_usd=cloud_usd,
        shared_tool_exec=shared_tool_exec,
        note=note
        or (
            "External assistant append accepted by ChatHistory; "
            "resident KV invalidated; next local generate re-prefills."
        ),
    )


def measure_reprefill_after_inject(
    *,
    pipe: Any,
    ov_genai: Any,
    tools: list[dict[str, Any]],
    seed_messages: list[dict[str, Any]],
    injected_assistant: str,
    next_user: str,
    max_new_tokens: int = 32,
) -> dict[str, Any]:
    """Live smoke: inject assistant, finish_chat, time next generate TTFT as re-prefill.

    Returns a dict with ``re_prefill_s`` (TTFT of post-inject generate) and
    provenance. Caller must hold a loaded RESIDENT pipeline.
    """
    from tools.bfcl_feasibility_probe import build_bfcl_chat_history as _build_hist

    history = _build_hist(ov_genai, list(seed_messages), tools)
    # Warm: one generate so resident KV exists, then inject divergence.
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = int(max_new_tokens)
    cfg.do_sample = False
    cfg.apply_chat_template = True

    t0 = time.perf_counter()
    _ = pipe.generate(history, cfg)
    warm_s = time.perf_counter() - t0

    inject_assistant_into_chat_history(history, assistant_text=injected_assistant)
    invalidate_resident_kv(pipe)
    history.append({"role": "user", "content": next_user})

    t1 = time.perf_counter()
    result = pipe.generate(history, cfg)
    wall_s = time.perf_counter() - t1
    metrics = getattr(result, "perf_metrics", None)
    ttft_s: float | None = None
    if metrics is not None:
        # OpenVINO GenAI reports TTFT in microseconds on recent builds.
        for attr in ("get_ttft", "TTFT", "ttft"):
            fn = getattr(metrics, attr, None)
            if callable(fn):
                raw = fn()
                ttft_s = float(raw) / 1e6 if float(raw) > 1000 else float(raw)
                break
            if fn is not None and not callable(fn):
                raw = float(fn)
                ttft_s = raw / 1e6 if raw > 1000 else raw
                break
    re_prefill_s = float(ttft_s) if ttft_s is not None else float(wall_s)
    return {
        "re_prefill_s": re_prefill_s,
        "re_prefill_source": "measured" if ttft_s is not None else "measured_wall_fallback",
        "warm_generate_s": warm_s,
        "post_inject_generate_wall_s": wall_s,
        "ttft_s": ttft_s,
        "kv_valid_after_inject": False,
        "re_prefill_required": True,
        "note": (
            "Post-inject TTFT is the re-prefill cost of R2c bounce-back under "
            "RESIDENT ChatHistory (finish_chat then generate)."
        ),
    }
