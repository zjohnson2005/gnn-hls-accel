"""P1 local-quality decisions. No model and no preregistration file."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from seam.reasoning import split_reasoning

_ENTRY_STEP_KEYS = (
    "tta_s",
    "k_used",
    "samples_finished",
    "fallback",
    "vote_agreement",
    "emitted_tokens",
    "retained_tokens",
    "source",
    "met_budget",
    "greedy_call_sha256",
    "extras_call_sha256",
    "agreement",
    "override",
    "check_result",
    "feedback_sha256",
    "feedback_tokens",
    "attempts",
)

_TOOL_CALL_BLOCK = re.compile(r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL)


def capped_new_tokens(*, remaining_s: float, rate_tok_s: float, batch_k: int) -> int:
    """floor(R * measured tok/s / k). Zero when the remaining time cannot buy a token."""
    if remaining_s <= 0.0 or rate_tok_s <= 0.0 or batch_k <= 0:
        return 0
    return math.floor(remaining_s * rate_tok_s / batch_k)


def thinking_token_cap(*, spare_s: float, decode_tok_s: float) -> int:
    """Tokens that fit in the spare time at the measured decode rate."""
    return capped_new_tokens(remaining_s=spare_s, rate_tok_s=decode_tok_s, batch_k=1)


def measured_batch_rate(
    table: dict[Any, dict[Any, Any]],
    *,
    requested_k: int,
    n_ctx: int | None,
    band_threshold: int,
) -> dict[str, Any]:
    """Smallest measured batch k at least the requested k.

    Unknown context uses the band whose per-sequence rate is slower, so the
    token cap cannot grow past the tighter measurement.
    """
    bands = {
        int(band): {int(k): float(rate) for k, rate in dict(rates).items()}
        for band, rates in dict(table).items()
    }

    def pick(band: int) -> tuple[int, float]:
        row = bands[band]
        keys = sorted(row)
        chosen = next((key for key in keys if key >= requested_k), keys[-1])
        return chosen, row[chosen]

    if n_ctx is None:
        ranked: list[tuple[float, int, int, float]] = []
        for band in sorted(bands):
            table_k, rate = pick(band)
            ranked.append((rate / table_k, band, table_k, rate))
        _per, band, table_k, rate = min(ranked, key=lambda item: item[0])
        reason = "unknown_context_slower_band"
    else:
        band = 4000 if int(n_ctx) <= int(band_threshold) else 6000
        table_k, rate = pick(band)
        reason = "context_band"
    return {"band": band, "table_k": table_k, "rate_tok_s": rate, "reason": reason}


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


def feedback_sha256(text: str) -> str:
    """SHA-256 of the feedback text that was appended before the next decode."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def feedback_text(check: dict[str, Any]) -> str:
    """Short user turn naming the pre-execution failure. A passing check has none."""
    result = str(check.get("result") or "")
    name = str(check.get("name") or "")
    argument = str(check.get("argument") or "")
    expected = str(check.get("expected_type") or "")
    if result == "empty":
        return "Pre-execution check failed: empty."
    if result == "unparseable":
        return "Pre-execution check failed: unparseable."
    if result == "unknown_function":
        return f"Pre-execution check failed: unknown function {name}."
    if result == "missing_argument":
        return f"Pre-execution check failed: missing argument {argument} for {name}."
    if result == "extra_argument":
        return f"Pre-execution check failed: extra argument {argument} for {name}."
    if result == "ill_typed":
        return (
            f"Pre-execution check failed: ill-typed argument {argument} "
            f"for {name}; expected {expected}."
        )
    raise ValueError(f"no feedback for check result {result}")


def check_pre_execution(text: str, tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify a reply before any tool runs.

    ``ok`` may be executed. ``empty`` and ``unparseable`` have no call.
    ``unknown_function``, ``missing_argument``, ``extra_argument``, and
    ``ill_typed`` are schema failures. A failed result is not executed.
    """
    status, calls = _parse_calls(text)
    if status is not None:
        return _check_row(status)
    schemas = _schema_index(tools)
    for call in calls:
        name = str(call["name"])
        arguments = dict(call["arguments"])
        schema = schemas.get(name)
        if schema is None:
            return _check_row("unknown_function", name=name)
        properties = dict(schema["properties"])
        for required in list(schema["required"]):
            if required not in arguments:
                return _check_row("missing_argument", name=name, argument=str(required))
        if properties:
            for key in sorted(arguments):
                if key not in properties:
                    return _check_row("extra_argument", name=name, argument=key)
        for key, spec in properties.items():
            if key not in arguments or not isinstance(spec, dict):
                continue
            expected = spec.get("type")
            if expected is None or _type_matches(arguments[key], expected):
                continue
            shown = expected if isinstance(expected, str) else json.dumps(expected, sort_keys=True)
            return _check_row("ill_typed", name=name, argument=key, expected_type=str(shown))
    return _check_row("ok")


def _check_row(
    result: str,
    *,
    name: str | None = None,
    argument: str | None = None,
    expected_type: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": result == "ok",
        "result": result,
        "name": name,
        "argument": argument,
        "expected_type": expected_type,
    }


def _schema_index(tools: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for tool in tools:
        function = tool.get("function")
        body = function if isinstance(function, dict) else tool
        if not isinstance(body, dict):
            continue
        name = body.get("name")
        if not isinstance(name, str) or not name:
            continue
        parameters = body.get("parameters") or {}
        if not isinstance(parameters, dict):
            parameters = {}
        properties = parameters.get("properties") or {}
        if not isinstance(properties, dict):
            properties = {}
        required_raw = parameters.get("required") or []
        required = [str(item) for item in required_raw] if isinstance(required_raw, list) else []
        index[name] = {"properties": properties, "required": required}
    return index


def _parse_calls(text: str) -> tuple[str | None, list[dict[str, Any]]]:
    raw = text or ""
    if not raw.strip():
        return "empty", []
    blocks = _TOOL_CALL_BLOCK.findall(raw)
    if blocks:
        payloads: list[Any] = []
        for block in blocks:
            try:
                payloads.append(json.loads(block))
            except json.JSONDecodeError:
                return "unparseable", []
    else:
        objects = _json_objects(raw)
        if not objects:
            return "unparseable", []
        payloads = objects
    calls: list[dict[str, Any]] = []
    for payload in payloads:
        parsed = _one_call(payload)
        if parsed is None:
            return "unparseable", []
        calls.append(parsed)
    if not calls:
        return "unparseable", []
    return None, calls


def _one_call(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or "name" not in payload:
        return None
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        return None
    arguments = payload.get("arguments", payload.get("parameters", {}))
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    if not isinstance(arguments, dict):
        return None
    return {"name": name, "arguments": arguments}


def _json_objects(text: str) -> list[Any] | None:
    found: list[Any] = []
    index = 0
    while index < len(text):
        start = text.find("{", index)
        if start < 0:
            break
        raw = _slice_object(text, start)
        if raw is None:
            return None
        try:
            found.append(json.loads(raw))
        except json.JSONDecodeError:
            return None
        index = start + len(raw)
    return found


def _slice_object(text: str, start: int) -> str | None:
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


def _type_matches(value: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_type_matches(value, item) for item in expected)
    if not isinstance(expected, str):
        return True
    kind = expected.lower()
    if kind in {"string", "str"}:
        return isinstance(value, str)
    if kind in {"integer", "int", "long"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind in {"number", "float", "double"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind in {"boolean", "bool"}:
        return isinstance(value, bool)
    if kind in {"array", "list"}:
        return isinstance(value, list)
    if kind in {"object", "dict"}:
        return isinstance(value, dict)
    return True


def call_sha256(text: str) -> str | None:
    """SHA-256 of the normalized tool call. Unparseable text has no hash."""
    key = normalize_tool_call(text)
    if key is None:
        return None
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def compose_greedy_vote(*, greedy_text: str, extras: list[dict[str, Any]]) -> dict[str, Any]:
    """Extras override greedy only when every finished extra shares one tool call.

    A split among the finished extras keeps the greedy answer. Unfinished extras
    stay out of the agreement check.
    """
    finished = [item for item in extras if item.get("finished")]
    finished_texts = [str(item.get("text") or "") for item in finished]
    keys = [normalize_tool_call(text) for text in finished_texts]
    extra_hashes = [call_sha256(text) for text in finished_texts]
    unanimous = bool(keys) and len(set(keys)) == 1 and keys[0] is not None
    if unanimous:
        chosen = finished_texts[0]
        source = "override"
    else:
        chosen = greedy_text
        source = "greedy"
    if not keys:
        fraction: float | None = None
    else:
        modal = max(set(keys), key=keys.count)
        fraction = sum(1 for key in keys if key == modal) / len(keys)
    return {
        "text": chosen,
        "source": source,
        "k_used": 1 + len(finished),
        "samples_finished": 1 + len(finished),
        "fallback_to_greedy": bool(extras) and not finished,
        "vote_agreement": fraction,
        "vote_index": 1 if unanimous else 0,
        "voted": unanimous,
        "tie": False,
        "agreement": unanimous,
        "override": unanimous,
        "greedy_call_sha256": call_sha256(greedy_text),
        "extras_call_sha256": extra_hashes,
    }


def strip_prior_thinking(text: str) -> dict[str, Any]:
    """Drop Qwen3 think blocks so the next step's history keeps the answer only."""
    retained = split_reasoning(text or "").answer
    return {
        "retained_text": retained,
        "emitted_chars": len(text or ""),
        "retained_chars": len(retained),
        "thinking_stripped": (text or "") != retained,
    }


def entry_record(point: dict[str, Any]) -> dict[str, Any]:
    """One entries.jsonl object. Missing step fields stay null."""
    steps = [
        {key: step.get(key) for key in _ENTRY_STEP_KEYS} for step in list(point.get("steps") or [])
    ]
    return {
        "id": point.get("id"),
        "pass": point.get("passed"),
        "in_budget": point.get("in_budget_pass"),
        "steps": steps,
    }


def recover_entry_record(point: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a jsonl row from a point file that predates entries.jsonl.

    Copies per-step TTA, fallback, and the stored token total. Does not invent
    vote agreement, tool-call text, retained thinking tokens, or a live k choice.
    ``samples_finished`` is the stored ``n_samples`` (texts the batch returned).
    """
    steps: list[dict[str, Any]] = []
    for step in list(point.get("steps") or []):
        copied = dict(step)
        if copied.get("emitted_tokens") is None and copied.get("tokens") is not None:
            copied["emitted_tokens"] = copied["tokens"]
        if copied.get("samples_finished") is None and copied.get("n_samples") is not None:
            copied["samples_finished"] = copied["n_samples"]
        steps.append(copied)
    recovered = dict(point)
    recovered["steps"] = steps
    return entry_record(recovered)


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


def _play_a1(
    task: dict[str, Any], *, budget_s: float, rate_tok_s: float, table_k: int
) -> dict[str, Any]:
    """Greedy stream first. Extras run only inside the remaining time."""
    greedy = dict(task["greedy"])
    stopped = bool(greedy.get("stopped"))
    account = step_account(
        elapsed_s=float(greedy["elapsed_s"]),
        budget_s=budget_s,
        n_samples=1,
        tokens=int(greedy["tokens"]),
        stopped_for_budget=stopped,
    )
    remaining = budget_s - float(account["tta_s"])
    cap = capped_new_tokens(remaining_s=remaining, rate_tok_s=rate_tok_s, batch_k=table_k)
    considered: list[dict[str, Any]] = []
    if remaining > 0.0 and cap > 0:
        for extra in list(task.get("extras") or []):
            fits = int(extra["tokens"]) <= cap
            considered.append({**extra, "finished": bool(extra.get("finished")) and fits})
    decision = compose_greedy_vote(greedy_text=str(greedy["text"]), extras=considered)
    tokens = int(greedy["tokens"])
    if decision["source"] == "override":
        tokens += sum(int(item["tokens"]) for item in considered if item.get("finished"))
        total = float(account["tta_s"]) + float(task.get("extra_elapsed_s") or 0.0)
        account = step_account(
            elapsed_s=total,
            budget_s=budget_s,
            n_samples=int(decision["samples_finished"]),
            tokens=tokens,
            stopped_for_budget=False,
        )
    account["n_samples"] = int(decision["samples_finished"])
    account["tokens"] = tokens
    account["fallback"] = bool(account["fallback"] or decision["fallback_to_greedy"])
    account["source"] = decision["source"]
    account["k_used"] = decision["k_used"]
    account["samples_finished"] = decision["samples_finished"]
    account["vote_agreement"] = decision["vote_agreement"]
    account["vote_index"] = decision["vote_index"]
    account["voted"] = decision["voted"]
    account["fallback_to_greedy"] = decision["fallback_to_greedy"]
    account["agreement"] = decision["agreement"]
    account["override"] = decision["override"]
    account["greedy_call_sha256"] = decision["greedy_call_sha256"]
    account["extras_call_sha256"] = decision["extras_call_sha256"]
    account["token_cap"] = cap
    account["emitted_tokens"] = tokens
    account["retained_tokens"] = None
    return account


def _play_retry(
    arm: str,
    samples: list[dict[str, Any]],
    *,
    budget_s: float,
    rate_tok_s: float,
) -> dict[str, Any]:
    """A retry is taken only when the remaining time can finish it."""
    chosen: list[dict[str, Any]] = []
    skipped = False
    for index, sample in enumerate(samples):
        if index > 0:
            remaining = budget_s - float(chosen[-1]["elapsed_s"])
            token_cap = capped_new_tokens(remaining_s=remaining, rate_tok_s=rate_tok_s, batch_k=1)
            finishes = (
                remaining > 0.0
                and float(sample["elapsed_s"]) <= budget_s
                and int(sample["tokens"]) <= token_cap
                and bool(sample.get("finished", True))
            )
            if not finishes:
                skipped = True
                break
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
    stopped = any(str(sample["kind"]) == "stopped" for sample in chosen)
    account = step_account(
        elapsed_s=float(chosen[-1]["elapsed_s"]),
        budget_s=budget_s,
        n_samples=len(chosen),
        tokens=sum(int(sample["tokens"]) for sample in chosen),
        stopped_for_budget=stopped,
    )
    account["fallback"] = bool(account["fallback"] or skipped)
    account["retried"] = len(chosen) > 1
    account["retry_unfinished"] = skipped
    account["k_used"] = len(chosen)
    account["samples_finished"] = len(chosen)
    account["source"] = "retry" if len(chosen) > 1 else "greedy"
    account["emitted_tokens"] = account["tokens"]
    account["vote_agreement"] = None
    account["retained_tokens"] = None
    return account


def _play_a4(sample: dict[str, Any], *, budget_s: float, decode_tok_s: float) -> dict[str, Any]:
    """Thinking tokens are capped at the live decode rate, then stripped from history."""
    cap = capped_new_tokens(remaining_s=budget_s, rate_tok_s=decode_tok_s, batch_k=1)
    emitted = min(int(sample["tokens"]), cap)
    stopped = str(sample["kind"]) == "stopped" or float(sample["elapsed_s"]) >= budget_s
    account = step_account(
        elapsed_s=float(sample["elapsed_s"]),
        budget_s=budget_s,
        n_samples=1,
        tokens=emitted,
        stopped_for_budget=stopped,
    )
    stripped = strip_prior_thinking(str(sample["text"]))
    account["source"] = "greedy"
    account["k_used"] = 1
    account["samples_finished"] = 1
    account["token_cap"] = cap
    account["emitted_tokens"] = int(sample["tokens"])
    account["retained_tokens"] = sample.get("retained_tokens")
    account["emitted_chars"] = stripped["emitted_chars"]
    account["retained_chars"] = stripped["retained_chars"]
    account["retained_text"] = stripped["retained_text"]
    account["thinking_stripped"] = stripped["thinking_stripped"]
    account["vote_agreement"] = None
    return account


def _play_a0(samples: list[dict[str, Any]], *, budget_s: float) -> dict[str, Any]:
    sample = samples[0]
    stopped = str(sample["kind"]) == "stopped"
    account = step_account(
        elapsed_s=float(sample["elapsed_s"]),
        budget_s=budget_s,
        n_samples=1,
        tokens=int(sample["tokens"]),
        stopped_for_budget=stopped,
    )
    account["source"] = "greedy"
    account["k_used"] = 1
    account["samples_finished"] = 1
    account["emitted_tokens"] = int(sample["tokens"])
    account["retained_tokens"] = None
    account["vote_agreement"] = None
    return account


def _play_a5(
    samples: list[dict[str, Any]],
    *,
    budget_s: float,
    rate_tok_s: float,
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """Feedback decode only when the next sample finishes inside the remaining time.

    A sample that fails the pre-execution check is not executed. When the retry
    does not finish, the step keeps the greedy text. The model-free feedback
    token count is the character length of that feedback string. The runner
    records the tokenizer length of the same string.
    """
    chosen: list[dict[str, Any]] = []
    checks: list[str] = []
    feedback_messages: list[str] = []
    skipped = False
    accepted = False
    greedy_result = "empty"
    for index, sample in enumerate(samples):
        if index > 0:
            remaining = budget_s - float(chosen[-1]["elapsed_s"])
            token_cap = capped_new_tokens(remaining_s=remaining, rate_tok_s=rate_tok_s, batch_k=1)
            finishes = (
                remaining > 0.0
                and float(sample["elapsed_s"]) <= budget_s
                and int(sample["tokens"]) <= token_cap
                and bool(sample.get("finished", True))
            )
            if not finishes:
                skipped = True
                break
            previous = check_pre_execution(str(chosen[-1]["text"]), tools)
            feedback_messages.append(feedback_text(previous))
        check = check_pre_execution(str(sample["text"]), tools)
        chosen.append(sample)
        checks.append(str(check["result"]))
        if index == 0:
            greedy_result = str(check["result"])
        if check["ok"]:
            accepted = True
            break
    stopped = any(str(sample.get("kind")) == "stopped" for sample in chosen)
    account = step_account(
        elapsed_s=float(chosen[-1]["elapsed_s"]),
        budget_s=budget_s,
        n_samples=len(chosen),
        tokens=sum(int(sample["tokens"]) for sample in chosen),
        stopped_for_budget=stopped,
    )
    account["fallback"] = bool(account["fallback"] or skipped)
    account["retry_unfinished"] = skipped
    account["k_used"] = len(chosen)
    account["samples_finished"] = len(chosen)
    account["attempts"] = len(chosen)
    account["source"] = "feedback" if accepted and len(chosen) > 1 else "greedy"
    account["check_result"] = checks[-1] if accepted else greedy_result
    account["checks"] = checks
    account["feedback_sha256"] = (
        [feedback_sha256(message) for message in feedback_messages] if feedback_messages else None
    )
    account["feedback_tokens"] = (
        sum(len(message) for message in feedback_messages) if feedback_messages else None
    )
    account["executed"] = accepted
    account["chosen_text"] = str(chosen[-1]["text"]) if accepted else str(chosen[0]["text"])
    account["emitted_tokens"] = account["tokens"]
    account["vote_agreement"] = None
    account["retained_tokens"] = None
    return account


def run_smoke() -> dict[str, Any]:
    """Greedy cutoff, extras that finish, extras that fall back, and thinking strip."""
    budget_s = 10.0
    # Scripted P0-v2 gpu-4000 batch-4 aggregate and batch-1 decode. The runner
    # reads the same figures from configs/p1_quality.yaml.
    batch4 = 60.98813887904501
    decode = 25.269383662886206
    live_decode = 10.0
    call = {"name": "get_weather", "arguments": {"city": "Paris"}}
    other = {"name": "get_weather", "arguments": {"city": "Lyon"}}
    call_text = json.dumps(call)
    other_text = json.dumps(other)
    think_text = "<think>\nplan the call\n</think>\n" + call_text
    weather_tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }
    ]
    unknown_text = json.dumps({"name": "missing_fn", "arguments": {}})
    a1_override = _play_a1(
        {
            "greedy": {"text": call_text, "elapsed_s": 4.0, "tokens": 40, "stopped": False},
            "extras": [
                {"text": other_text, "tokens": 40, "finished": True},
                {"text": other_text, "tokens": 40, "finished": True},
                {"text": other_text, "tokens": 40, "finished": True},
            ],
            "extra_elapsed_s": 2.0,
        },
        budget_s=budget_s,
        rate_tok_s=batch4,
        table_k=4,
    )
    a1_split = _play_a1(
        {
            "greedy": {"text": call_text, "elapsed_s": 4.0, "tokens": 40, "stopped": False},
            "extras": [
                {"text": call_text, "tokens": 40, "finished": True},
                {"text": other_text, "tokens": 40, "finished": True},
                {"text": other_text, "tokens": 40, "finished": True},
            ],
            "extra_elapsed_s": 2.0,
        },
        budget_s=budget_s,
        rate_tok_s=batch4,
        table_k=4,
    )
    a1_cutoff = _play_a1(
        {"greedy": {"text": call_text, "elapsed_s": 12.0, "tokens": 80, "stopped": True}},
        budget_s=budget_s,
        rate_tok_s=batch4,
        table_k=4,
    )
    a1_fallback = _play_a1(
        {
            "greedy": {"text": call_text, "elapsed_s": 4.0, "tokens": 40, "stopped": False},
            "extras": [
                {"text": other_text, "tokens": 40, "finished": False},
                {"text": other_text, "tokens": 40, "finished": False},
                {"text": other_text, "tokens": 40, "finished": False},
            ],
            "extra_elapsed_s": 2.0,
        },
        budget_s=budget_s,
        rate_tok_s=batch4,
        table_k=4,
    )
    played: dict[str, list[dict[str, Any]]] = {
        "A0": [
            _play_a0(
                [{"text": call_text, "elapsed_s": 4.0, "tokens": 40, "kind": "call"}],
                budget_s=budget_s,
            ),
            _play_a0(
                [{"text": call_text, "elapsed_s": 10.0, "tokens": 20, "kind": "stopped"}],
                budget_s=budget_s,
            ),
        ],
        "A1": [a1_override, a1_split, a1_cutoff, a1_fallback],
        "A2": [
            _play_retry(
                "A2",
                [
                    {"text": "", "elapsed_s": 4.0, "tokens": 2, "kind": "empty"},
                    {"text": call_text, "elapsed_s": 8.0, "tokens": 40, "kind": "call"},
                ],
                budget_s=budget_s,
                rate_tok_s=decode,
            ),
            _play_retry(
                "A2",
                [
                    {"text": "", "elapsed_s": 6.0, "tokens": 2, "kind": "empty"},
                    {"text": call_text, "elapsed_s": 11.0, "tokens": 40, "kind": "call"},
                ],
                budget_s=budget_s,
                rate_tok_s=decode,
            ),
        ],
        "A3": [
            _play_retry(
                "A3",
                [
                    {"text": call_text, "elapsed_s": 3.0, "tokens": 30, "kind": "exec_error"},
                    {"text": call_text, "elapsed_s": 7.0, "tokens": 30, "kind": "call"},
                ],
                budget_s=budget_s,
                rate_tok_s=decode,
            ),
            _play_retry(
                "A3",
                [
                    {"text": call_text, "elapsed_s": 9.5, "tokens": 30, "kind": "exec_error"},
                    {"text": call_text, "elapsed_s": 11.0, "tokens": 30, "kind": "call"},
                ],
                budget_s=budget_s,
                rate_tok_s=decode,
            ),
        ],
        "A4": [
            _play_a4(
                {"text": think_text, "elapsed_s": 4.0, "tokens": 200, "kind": "call"},
                budget_s=budget_s,
                decode_tok_s=live_decode,
            ),
            _play_a4(
                {"text": call_text, "elapsed_s": 10.0, "tokens": 20, "kind": "stopped"},
                budget_s=budget_s,
                decode_tok_s=live_decode,
            ),
        ],
        "A5": [
            _play_a5(
                [
                    {"text": unknown_text, "elapsed_s": 4.0, "tokens": 20, "kind": "call"},
                    {"text": call_text, "elapsed_s": 8.0, "tokens": 40, "kind": "call"},
                ],
                budget_s=budget_s,
                rate_tok_s=decode,
                tools=weather_tools,
            ),
            _play_a5(
                [
                    {"text": unknown_text, "elapsed_s": 9.0, "tokens": 20, "kind": "call"},
                    {"text": call_text, "elapsed_s": 11.0, "tokens": 40, "kind": "call"},
                ],
                budget_s=budget_s,
                rate_tok_s=decode,
                tools=weather_tools,
            ),
        ],
    }
    _require_smoke(played)
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


def _require_smoke(played: dict[str, list[dict[str, Any]]]) -> None:
    a0 = played["A0"]
    if a0[0]["fallback"] or not a0[0]["met_budget"]:
        raise RuntimeError("A0 first task should finish inside the budget")
    if not a0[1]["fallback"] or not a0[1]["met_budget"]:
        raise RuntimeError("A0 second task should stop at the budget and still meet it")
    override, split, cutoff, backed = played["A1"]
    if not override["override"] or override["source"] != "override" or not override["met_budget"]:
        raise RuntimeError("A1 unanimous extras override the greedy answer inside the budget")
    if override["greedy_call_sha256"] in override["extras_call_sha256"]:
        raise RuntimeError("A1 override records a greedy hash distinct from the extras")
    if len(set(override["extras_call_sha256"])) != 1 or not override["agreement"]:
        raise RuntimeError("A1 override requires every finished extra to share one hash")
    if split["override"] or split["agreement"] or split["source"] != "greedy":
        raise RuntimeError("A1 split extras keep the greedy answer")
    if len(set(split["extras_call_sha256"])) < 2 or not split["met_budget"]:
        raise RuntimeError("A1 split records disagreeing extra hashes and stays in budget")
    if cutoff["source"] != "greedy" or cutoff["k_used"] != 1 or cutoff["token_cap"] != 0:
        raise RuntimeError("A1 greedy cutoff leaves no remaining time for extras")
    if not cutoff["fallback"] or not cutoff["met_budget"] or cutoff["tta_s"] != 10.0:
        raise RuntimeError("A1 greedy cutoff meets the budget")
    if backed["source"] != "greedy" or not backed["fallback_to_greedy"] or not backed["met_budget"]:
        raise RuntimeError("A1 unfinished extras fall back to greedy inside the budget")
    if backed["k_used"] != 1 or backed["fallback"] is not True:
        raise RuntimeError("A1 fallback keeps only the greedy sample")
    if played["A2"][0]["n_samples"] != 2 or not played["A2"][0]["met_budget"]:
        raise RuntimeError("A2 should resample an empty call while inside the budget")
    if not played["A2"][1]["retry_unfinished"] or not played["A2"][1]["met_budget"]:
        raise RuntimeError("A2 does not take a retry that would miss the budget")
    if played["A3"][0]["n_samples"] != 2 or not played["A3"][0]["met_budget"]:
        raise RuntimeError("A3 should resample a tool error while inside the budget")
    if not played["A3"][1]["retry_unfinished"] or not played["A3"][1]["met_budget"]:
        raise RuntimeError("A3 does not take a retry that would miss the budget")
    thinking = played["A4"][0]
    if thinking["token_cap"] != 100 or thinking["tokens"] != 100:
        raise RuntimeError("A4 caps thinking tokens at the live decode rate")
    if not thinking["thinking_stripped"] or "<think>" in str(thinking["retained_text"]):
        raise RuntimeError("A4 strips the thinking block before the next step")
    if thinking["emitted_chars"] <= thinking["retained_chars"]:
        raise RuntimeError("A4 records emitted text longer than the retained answer")
    if not played["A4"][1]["fallback"] or not played["A4"][1]["met_budget"]:
        raise RuntimeError("A4 second task should stop at the budget")
    recovered, kept = played["A5"]
    if recovered["source"] != "feedback" or recovered["check_result"] != "ok":
        raise RuntimeError("A5 feedback retry replaces a schema-invalid greedy call")
    if recovered["checks"] != ["unknown_function", "ok"] or recovered["attempts"] != 2:
        raise RuntimeError("A5 records the schema failure and the passing retry")
    if not recovered["executed"] or "get_weather" not in str(recovered["chosen_text"]):
        raise RuntimeError("A5 executes the feedback decode, not the failed call")
    if recovered["chosen_text"] == kept["chosen_text"] or not recovered["met_budget"]:
        raise RuntimeError("A5 does not keep the unknown function once the retry passes")
    named = feedback_text({"result": "unknown_function", "name": "missing_fn"})
    if recovered["feedback_sha256"] != [feedback_sha256(named)]:
        raise RuntimeError("A5 records the hash of the feedback that names the failure")
    if recovered["feedback_tokens"] != len(named):
        raise RuntimeError("A5 records the feedback token count")
    if kept["source"] != "greedy" or kept["check_result"] != "unknown_function":
        raise RuntimeError("A5 keeps the greedy text when the feedback retry misses R")
    if kept["executed"] or "missing_fn" not in str(kept["chosen_text"]) or kept["attempts"] != 1:
        raise RuntimeError("A5 does not execute a call when the retry runs out of R")
    if not kept["retry_unfinished"] or kept["feedback_sha256"] is not None:
        raise RuntimeError("A5 does not append feedback for a retry that cannot finish")
    if not kept["met_budget"]:
        raise RuntimeError("A5 still meets the budget when the retry does not finish")
