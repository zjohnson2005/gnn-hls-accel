"""Recompute d482c621 escalation decisions from sealed turn signals. Read-only on the run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.run_h1_hybrid import (
    decide_bounceback,
    decide_emission_escalate,
    decide_slo_escalate,
)

RUN_ID = "d482c621-4292-4281-b6a1-8635e5eeb6da"
POLICIES = ("slo_escalate", "emission_escalate", "full_signal_bounceback")
BOUNCE_REASONS = ("no_parseable_tool_call", "step_budget", "tool_exec_error")


def _predict(policy: str, turns: list[dict[str, Any]], index: int) -> tuple[bool, str | None]:
    turn = turns[index]
    already = any(t.get("placement") == "cloud" for t in turns[:index])
    if policy == "slo_escalate":
        return decide_slo_escalate(
            already_on_cloud=already,
            ttft_s=turn.get("ttft_s"),
            decode_tok_s=turn.get("decode_tok_s"),
        )
    if policy == "emission_escalate":
        return decide_emission_escalate(
            already_on_cloud=already,
            emitted_parseable_tool_call=bool(turn.get("emitted_parseable_tool_call")),
        )
    steps = turn.get("decoded_steps")
    n_steps = len(steps) if isinstance(steps, list) else None
    return decide_bounceback(
        emitted_parseable_tool_call=bool(turn.get("emitted_parseable_tool_call")),
        n_steps=n_steps,
        tool_exec_error=bool(turn.get("tool_exec_error")),
    )


def _bounce_reason(turn: dict[str, Any]) -> str | None:
    trigger = turn.get("bounce_trigger")
    if isinstance(trigger, str) and trigger:
        return trigger
    reason = turn.get("escalate_reason")
    if isinstance(reason, str) and reason.startswith("bounce:"):
        return reason.split(":", 1)[1]
    return None


def audit(run_dir: Path) -> dict[str, Any]:
    """Compare decide_* to sealed placement. The ledger has no served_by field."""
    n = 0
    n_ok = 0
    bad: list[dict[str, Any]] = []
    bounce_counts = {name: 0 for name in BOUNCE_REASONS}
    bounce_other = 0
    n_bounce_cloud = 0
    for policy in POLICIES:
        path = run_dir / "policies" / policy / "turn_ledger.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        for entry in doc.get("entries") or []:
            turns = list(entry.get("turns") or [])
            for index, turn in enumerate(turns):
                n += 1
                escalate, reason = _predict(policy, turns, index)
                predicted = "cloud" if escalate else "local"
                sealed = turn.get("placement")
                if predicted == sealed:
                    n_ok += 1
                else:
                    bad.append(
                        {
                            "entry_id": entry.get("entry_id"),
                            "policy": policy,
                            "turn": turn.get("turn"),
                            "sealed_placement": sealed,
                            "predicted_placement": predicted,
                            "predicted_reason": reason,
                            "ttft_s": turn.get("ttft_s"),
                            "decode_tok_s": turn.get("decode_tok_s"),
                            "emitted_parseable_tool_call": turn.get("emitted_parseable_tool_call"),
                            "tool_exec_error": turn.get("tool_exec_error"),
                            "n_decoded_steps": (
                                len(turn["decoded_steps"])
                                if isinstance(turn.get("decoded_steps"), list)
                                else None
                            ),
                            "escalate_reason": turn.get("escalate_reason"),
                            "bounce_trigger": turn.get("bounce_trigger"),
                        }
                    )
                if policy == "full_signal_bounceback" and sealed == "cloud":
                    n_bounce_cloud += 1
                    got = _bounce_reason(turn)
                    if got in bounce_counts:
                        bounce_counts[got] += 1
                    else:
                        bounce_other += 1
    return {
        "run_id": RUN_ID,
        "served_by_field": (
            "The sealed turn has no served_by key. Comparison uses placement "
            "(local or cloud)."
        ),
        "n": n,
        "n_conforming": n_ok,
        "n_nonconforming": len(bad),
        "nonconforming": bad,
        "bounceback_cloud_turns": n_bounce_cloud,
        "bounceback_by_reason": bounce_counts,
        "bounceback_other_reason": bounce_other,
    }
