"""P1 local-quality decisions. No model and no preregistration file."""

from __future__ import annotations

import json
import math
from typing import Any


def thinking_token_cap(*, spare_s: float, decode_tok_s: float) -> int:
    """Tokens that fit in the spare time at the measured decode rate."""
    if spare_s <= 0.0 or decode_tok_s <= 0.0:
        return 0
    return math.floor(spare_s * decode_tok_s)


def normalize_tool_call(text: str) -> str | None:
    """Canonical name plus arguments. Unparseable text has no vote key."""
    raw = _outer_object(text)
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or "name" not in payload:
        return None
    arguments = payload.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    if not isinstance(arguments, dict):
        return None
    body = {"arguments": arguments, "name": payload["name"]}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def majority_vote(texts: list[str]) -> dict[str, Any]:
    """Majority of normalized tool calls. A tie keeps the first sample."""
    keys = [normalize_tool_call(text) for text in texts]
    counts: dict[str, int] = {}
    first_index: dict[str, int] = {}
    for index, key in enumerate(keys):
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1
        first_index.setdefault(key, index)
    if not counts:
        return {"winner": None, "index": None, "tie": False, "key": None}
    best = max(counts.values())
    tied = [key for key, count in counts.items() if count == best]
    tie = len(tied) > 1
    if tie:
        first = keys[0]
        key = first if first in tied else min(tied, key=lambda item: first_index[item])
    else:
        key = tied[0]
    return {
        "winner": texts[first_index[key]],
        "index": first_index[key],
        "tie": tie,
        "key": key,
    }


def should_resample(*, arm: str, reason: str, elapsed_s: float, budget_s: float) -> bool:
    """One more sample only while this step is still inside the budget."""
    if elapsed_s >= budget_s:
        return False
    if arm == "A2" and reason == "empty":
        return True
    return bool(arm == "A3" and reason == "exec")


def step_account(
    *,
    elapsed_s: float,
    budget_s: float,
    n_samples: int,
    tokens: int,
    stopped_for_budget: bool,
) -> dict[str, Any]:
    """Time-to-action, sample count, tokens, and whether the step used the fallback."""
    if stopped_for_budget:
        tta_s = min(elapsed_s, budget_s)
        fallback = True
    else:
        tta_s = elapsed_s
        fallback = elapsed_s > budget_s
    return {
        "tta_s": tta_s,
        "n_samples": n_samples,
        "tokens": tokens,
        "fallback": fallback,
        "met_budget": tta_s <= budget_s,
    }


def in_budget_pass(*, passed: bool, steps: list[dict[str, Any]]) -> bool:
    """A trajectory counts only when it passes and every local step met the budget."""
    if not passed or not steps:
        return False
    return all(bool(step["met_budget"]) for step in steps)


def _outer_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _play(arm: str, samples: list[dict[str, Any]], *, budget_s: float, cap: int) -> dict[str, Any]:
    """Walk one scripted step the way the runner will."""
    if arm == "A1":
        vote = majority_vote([str(sample["text"]) for sample in samples])
        elapsed = max(float(sample["elapsed_s"]) for sample in samples)
        tokens = sum(int(sample["tokens"]) for sample in samples)
        account = step_account(
            elapsed_s=elapsed,
            budget_s=budget_s,
            n_samples=len(samples),
            tokens=tokens,
            stopped_for_budget=False,
        )
        account["vote_index"] = vote["index"]
        account["voted"] = vote["winner"] is not None
        return account
    chosen: list[dict[str, Any]] = []
    for sample in samples:
        chosen.append(sample)
        elapsed = float(sample["elapsed_s"])
        kind = str(sample["kind"])
        if kind == "empty" and should_resample(
            arm=arm, reason="empty", elapsed_s=elapsed, budget_s=budget_s
        ):
            continue
        if kind == "exec_error" and should_resample(
            arm=arm, reason="exec", elapsed_s=elapsed, budget_s=budget_s
        ):
            continue
        break
    tokens = sum(
        min(int(sample["tokens"]), cap) if arm == "A4" else int(sample["tokens"])
        for sample in chosen
    )
    stopped = any(str(sample["kind"]) == "stopped" for sample in chosen)
    account = step_account(
        elapsed_s=float(chosen[-1]["elapsed_s"]),
        budget_s=budget_s,
        n_samples=len(chosen),
        tokens=tokens,
        stopped_for_budget=stopped,
    )
    account["retried"] = len(chosen) > 1
    return account


def run_smoke() -> dict[str, Any]:
    """Two tasks per arm. Covers the vote, both retries, and the budget fallback."""
    budget_s = 10.0
    cap = 141
    call = {"name": "get_weather", "arguments": {"city": "Paris"}}
    other = {"name": "get_weather", "arguments": {"city": "Lyon"}}
    call_text = json.dumps(call)
    other_text = json.dumps(other)
    tasks = {
        "A0": [
            [{"text": call_text, "elapsed_s": 4.0, "tokens": 40, "kind": "call"}],
            [{"text": call_text, "elapsed_s": 10.0, "tokens": 20, "kind": "stopped"}],
        ],
        "A1": [
            [
                {"text": call_text, "elapsed_s": 7.0, "tokens": 40, "kind": "call"},
                {"text": call_text, "elapsed_s": 7.0, "tokens": 41, "kind": "call"},
                {"text": other_text, "elapsed_s": 7.0, "tokens": 39, "kind": "call"},
                {"text": other_text, "elapsed_s": 7.0, "tokens": 42, "kind": "call"},
            ],
            [
                {"text": call_text, "elapsed_s": 12.0, "tokens": 80, "kind": "call"},
                {"text": call_text, "elapsed_s": 12.0, "tokens": 80, "kind": "call"},
                {"text": call_text, "elapsed_s": 12.0, "tokens": 80, "kind": "call"},
                {"text": other_text, "elapsed_s": 12.0, "tokens": 80, "kind": "call"},
            ],
        ],
        "A2": [
            [
                {"text": "", "elapsed_s": 4.0, "tokens": 2, "kind": "empty"},
                {"text": call_text, "elapsed_s": 8.0, "tokens": 40, "kind": "call"},
            ],
            [
                {"text": "", "elapsed_s": 6.0, "tokens": 2, "kind": "empty"},
                {"text": call_text, "elapsed_s": 11.0, "tokens": 40, "kind": "call"},
            ],
        ],
        "A3": [
            [
                {"text": call_text, "elapsed_s": 3.0, "tokens": 30, "kind": "exec_error"},
                {"text": call_text, "elapsed_s": 7.0, "tokens": 30, "kind": "call"},
            ],
            [
                {"text": call_text, "elapsed_s": 9.5, "tokens": 30, "kind": "exec_error"},
                {"text": call_text, "elapsed_s": 11.0, "tokens": 30, "kind": "call"},
            ],
        ],
        "A4": [
            [{"text": call_text, "elapsed_s": 8.0, "tokens": 200, "kind": "call"}],
            [{"text": call_text, "elapsed_s": 10.0, "tokens": 141, "kind": "stopped"}],
        ],
    }
    played: dict[str, list[dict[str, Any]]] = {}
    for arm, arm_tasks in tasks.items():
        played[arm] = [_play(arm, samples, budget_s=budget_s, cap=cap) for samples in arm_tasks]
    _require_smoke(played, cap=cap)
    for arm, rows in played.items():
        vote = int(any(row.get("voted") for row in rows))
        retry = int(any(row.get("retried") for row in rows))
        fallback = int(any(row["fallback"] for row in rows))
        print(
            f"SMOKE_ARM {arm} pass tasks={len(rows)} vote={vote} retry={retry} fallback={fallback}",
            flush=True,
        )
    print("SMOKE_ALL_PASS", flush=True)
    return {"arms": played, "ok": True}


def _require_smoke(played: dict[str, list[dict[str, Any]]], *, cap: int) -> None:
    a0 = played["A0"]
    if a0[0]["fallback"] or not a0[0]["met_budget"]:
        raise RuntimeError("A0 first task should finish inside the budget")
    if not a0[1]["fallback"] or not a0[1]["met_budget"]:
        raise RuntimeError("A0 second task should stop at the budget and still meet it")
    a1 = played["A1"]
    if not a1[0]["voted"] or a1[0]["fallback"] or a1[0]["n_samples"] != 4:
        raise RuntimeError("A1 first task should vote four samples inside the budget")
    if a1[0]["vote_index"] != 0:
        raise RuntimeError("A1 tie between two and two keeps the first sample")
    if not a1[1]["fallback"] or a1[1]["met_budget"]:
        raise RuntimeError("A1 second task is the over-budget fallback")
    if played["A2"][0]["n_samples"] != 2 or not played["A2"][0]["met_budget"]:
        raise RuntimeError("A2 should resample an empty call while inside the budget")
    if not played["A2"][1]["fallback"] or played["A2"][1]["met_budget"]:
        raise RuntimeError("A2 second resample misses the budget")
    if played["A3"][0]["n_samples"] != 2 or not played["A3"][0]["met_budget"]:
        raise RuntimeError("A3 should resample a tool error while inside the budget")
    if not played["A3"][1]["fallback"] or played["A3"][1]["met_budget"]:
        raise RuntimeError("A3 second resample misses the budget")
    if played["A4"][0]["tokens"] != cap:
        raise RuntimeError("A4 caps thinking tokens at the spare-time budget")
    if not played["A4"][1]["fallback"] or not played["A4"][1]["met_budget"]:
        raise RuntimeError("A4 second task should stop at the budget")
