"""Pure offline derivation from OA-01 proxy, exec, and subject artifacts."""

from __future__ import annotations

import base64
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from apu_characterization.oa01.schema import (
    ApiBoundaryRecord,
    ToolExecSpan,
    TurnRecord,
)
from apu_characterization.turntrace_v2.labeling import detect_loop_membership


def load_api_records(path: Path) -> list[ApiBoundaryRecord]:
    records: list[ApiBoundaryRecord] = []
    if not Path(path).is_file():
        return records
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(ApiBoundaryRecord.from_dict(json.loads(line)))
    return sorted(records, key=lambda r: (r.call_index, r.upstream_send_unix_ns))


def load_exec_spans(path: Path) -> list[ToolExecSpan]:
    starts: dict[str, dict[str, Any]] = {}
    spans: list[ToolExecSpan] = []
    if not Path(path).is_file():
        return spans
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        span_id = str(event["span_id"])
        if event["event"] == "start":
            starts[span_id] = event
            continue
        start = starts.pop(span_id, None)
        if start is None:
            continue
        spans.append(
            ToolExecSpan(
                schema_version="oa01_exec_span_v1",
                trajectory_id=str(start["trajectory_id"]),
                span_id=span_id,
                argv=[str(x) for x in start.get("argv", [])],
                docker_operation=str(start.get("docker_operation", "")),
                container_id=start.get("container_id"),
                command=start.get("command"),
                start_unix_ns=int(start["unix_ns"]),
                end_unix_ns=int(event["unix_ns"]),
                returncode=int(event.get("returncode", -1)),
                signal=event.get("signal"),
            )
        )
    for span_id, start in starts.items():
        spans.append(
            ToolExecSpan(
                schema_version="oa01_exec_span_v1",
                trajectory_id=str(start["trajectory_id"]),
                span_id=span_id,
                argv=[str(x) for x in start.get("argv", [])],
                docker_operation=str(start.get("docker_operation", "")),
                container_id=start.get("container_id"),
                command=start.get("command"),
                start_unix_ns=int(start["unix_ns"]),
                end_unix_ns=int(start["unix_ns"]),
                returncode=-1,
                flags=["missing_exec_end"],
            )
        )
    return sorted(spans, key=lambda s: s.start_unix_ns)


def _canonical_prompt(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    # Stable schema fields first so local LCP tracks provider prefix caching
    # more closely than message-first alphabetical key order.
    prompt_fields = {
        key: value[key]
        for key in (
            "tools",
            "tool_choice",
            "response_format",
            "instructions",
            "text",
            "input",
            "messages",
        )
        if key in value
    }
    return json.dumps(
        prompt_fields, ensure_ascii=False, separators=(",", ":")
    )


def tokenize_prompt(text: str, model_id: str) -> tuple[list[int | str], str]:
    try:
        import tiktoken

        normalized = model_id.split("/", 1)[-1]
        try:
            encoding = tiktoken.encoding_for_model(normalized)
        except KeyError:
            encoding = tiktoken.get_encoding("o200k_base")
        return list(encoding.encode(text)), f"tiktoken:{encoding.name}"
    except ImportError:
        # Unit-test fallback only. Live preflight requires tiktoken.
        return re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE), "regex_fallback_debug"


def _lcp_len(left: Sequence[Any], right: Sequence[Any]) -> int:
    limit = min(len(left), len(right))
    idx = 0
    while idx < limit and left[idx] == right[idx]:
        idx += 1
    return idx


def _header_float(headers: Mapping[str, str], *names: str) -> float | None:
    lowered = {str(k).lower(): v for k, v in headers.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def _response_tool_calls(record: ApiBoundaryRecord) -> list[tuple[str, dict[str, Any]]]:
    value = record.response_json
    if not isinstance(value, Mapping):
        return []
    choices = value.get("choices") or []
    if choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message") or {}
        calls = message.get("tool_calls") or []
        calls_out: list[tuple[str, dict[str, Any]]] = []
        for call in calls:
            function = call.get("function") or {}
            if function.get("name"):
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {"_raw": arguments}
                calls_out.append((str(function["name"]), dict(arguments)))
        return calls_out
    output = value.get("output") or value.get("response", {}).get("output") or []
    return [
        (
            str(item.get("name")),
            dict(item.get("arguments") or {})
            if isinstance(item.get("arguments"), Mapping)
            else {"_raw": item.get("arguments")},
        )
        for item in output
        if isinstance(item, Mapping)
        and item.get("type") in {"function_call", "tool_call"}
        and item.get("name")
    ]


def _command_semantic(calls: Sequence[tuple[str, Mapping[str, Any]]]) -> str:
    if not calls:
        return "reason_or_finalize"
    categories: list[str] = []
    for name, arguments in calls:
        if name != "bash":
            categories.append(name)
            continue
        command = str(arguments.get("command", arguments.get("_raw", ""))).lower()
        if "complete_task_and_submit_final_output" in command:
            category = "submit"
        elif re.search(r"\b(pytest|tox|nosetests|npm test|go test|cargo test|make test)\b", command):
            category = "verify"
        elif re.search(
            r"\b(apply_patch|patch)\b|sed\s+-i|perl\s+-pi|>\s*[^&]|tee\s+",
            command,
        ):
            category = "edit"
        elif re.search(r"\b(pip|npm|yarn|pnpm|apt|conda)\s+(install|add)\b", command):
            category = "install"
        elif re.search(r"\bgit\s+(diff|status|show|log)\b", command):
            category = "inspect_diff"
        elif re.search(
            r"\b(rg|grep|find|ls|cat|head|tail|sed\s+-n|awk|tree)\b", command
        ):
            category = "inspect"
        elif re.search(r"\bpython\b|\bnode\b|\bruby\b", command):
            category = "reproduce_or_probe"
        else:
            category = "shell_other"
        categories.append(category)
    return "+".join(categories)


def _union_ms(spans: Iterable[tuple[int, int]], lo: int, hi: int) -> float:
    clipped = sorted(
        (max(lo, start), min(hi, end))
        for start, end in spans
        if end > lo and start < hi and end > start
    )
    if not clipped:
        return 0.0
    total = 0
    cur_lo, cur_hi = clipped[0]
    for start, end in clipped[1:]:
        if start <= cur_hi:
            cur_hi = max(cur_hi, end)
        else:
            total += cur_hi - cur_lo
            cur_lo, cur_hi = start, end
    total += cur_hi - cur_lo
    return total / 1_000_000.0


def derive_turn_records(
    *,
    api_records: Sequence[ApiBoundaryRecord],
    exec_spans: Sequence[ToolExecSpan],
    task_id: str,
    trajectory_start_unix_ns: int,
    trajectory_end_unix_ns: int,
) -> list[TurnRecord]:
    if not api_records:
        return []
    api_records = sorted(api_records, key=lambda r: r.call_index)
    groups: list[list[ApiBoundaryRecord]] = []
    pending: list[ApiBoundaryRecord] = []
    for api_record in api_records:
        pending.append(api_record)
        if api_record.response_status < 400:
            groups.append(pending)
            pending = []
    if pending:
        # A terminal provider-error storm is still a retained logical turn.
        groups.append(pending)
    representative_records = [group[-1] for group in groups]
    prompt_tokens: list[list[int | str]] = []
    tokenizer_ids: list[str] = []
    for record in representative_records:
        tokens, tokenizer_id = tokenize_prompt(
            _canonical_prompt(record.request_json), record.model_id
        )
        prompt_tokens.append(tokens)
        tokenizer_ids.append(tokenizer_id)

    tool_calls_by_turn = [
        _response_tool_calls(record) for record in representative_records
    ]
    tool_names_by_turn = [[name for name, _ in calls] for calls in tool_calls_by_turn]
    semantics = [_command_semantic(calls) for calls in tool_calls_by_turn]
    loops = detect_loop_membership(semantics)
    repeats: Counter[str] = Counter()
    turns: list[TurnRecord] = []
    for idx, (group, record) in enumerate(zip(groups, representative_records)):
        interval_start = (
            trajectory_start_unix_ns
            if idx == 0
            else group[0].request_received_unix_ns
        )
        interval_end = (
            groups[idx + 1][0].request_received_unix_ns
            if idx + 1 < len(groups)
            else trajectory_end_unix_ns
        )
        interval_end = max(interval_end, record.response_relay_complete_unix_ns)
        turn_wall_ms = max(0.0, (interval_end - interval_start) / 1_000_000.0)
        model_spans = [
            (attempt.request_received_unix_ns, attempt.response_relay_complete_unix_ns)
            for attempt in group
        ]
        turn_exec = [
            span
            for span in exec_spans
            if span.docker_operation == "exec"
            and span.start_unix_ns >= record.response_relay_complete_unix_ns
            and span.start_unix_ns < interval_end
        ]
        tool_ms = _union_ms(
            ((s.start_unix_ns, s.end_unix_ns) for s in turn_exec),
            interval_start,
            interval_end,
        )
        accounted_ms = _union_ms(
            [
                *model_spans,
                *((s.start_unix_ns, s.end_unix_ns) for s in turn_exec),
            ],
            interval_start,
            interval_end,
        )
        orch_gap_ms = max(0.0, turn_wall_ms - accounted_ms)

        prior = prompt_tokens[idx - 1] if idx else []
        local_lcp = _lcp_len(prior, prompt_tokens[idx]) if idx else 0
        input_tokens = record.usage.input_tokens
        structural = min(input_tokens, local_lcp)
        local_count = len(prompt_tokens[idx])
        observed_template_delta = max(0, input_tokens - local_count)
        # OpenAI prompt-cache counters are quantized in 128-token blocks and the
        # provider's internal chat serialization is not identical to our local
        # JSON canonicalization. Floor at two quanta so small serialization
        # mismatch does not false-fail an otherwise coherent trajectory.
        cache_quantum = 128
        envelope = max(2 * cache_quantum, observed_template_delta + 32)
        recovered = max(0, record.usage.cached_tokens)
        recomputed = max(0, structural - recovered)
        necessary = max(0, input_tokens - structural)
        flags = [flag for attempt in group for flag in attempt.flags]
        if len(group) > 1:
            flags.append("provider_retry_attempts")
        if recovered > structural + envelope:
            flags.append("provider_cache_reconciliation")
        if tokenizer_ids[idx] == "regex_fallback_debug":
            flags.append("nonproduction_tokenizer")

        processing_ms = _header_float(
            record.response_headers,
            "openai-processing-ms",
            "x-openai-processing-ms",
        )
        if record.stream_requested:
            if processing_ms is not None:
                t_prefill = processing_ms
                t_network = max(0.0, record.upstream_first_byte_ms - processing_ms)
                timing_method = "stream_first_byte_plus_provider_processing"
            else:
                t_prefill = None
                t_network = None
                timing_method = "stream_first_byte_no_server_isolate"
                flags.append("prefill_network_not_isolated")
            t_decode = record.upstream_body_ms
        else:
            # mini-SWE-agent's shipped LiteLLM model uses non-streaming
            # completion. Its first response byte arrives after generation, so
            # splitting prefill/decode/network would fabricate precision.
            t_prefill = None
            t_decode = None
            t_network = None
            timing_method = "nonstreaming_first_byte_includes_decode"
            flags.append("prefill_decode_network_not_isolated")

        semantic = semantics[idx]
        repeats[semantic] += 1
        turns.append(
            TurnRecord(
                trajectory_id=record.trajectory_id,
                task_id=task_id,
                turn_index=idx,
                call_id=record.call_id,
                api_call_ids=[attempt.call_id for attempt in group],
                api_attempt_count=len(group),
                interval_start_unix_ns=interval_start,
                interval_end_unix_ns=interval_end,
                t_turn_wall_ms=turn_wall_ms,
                t_model_observed_ms=_union_ms(
                    model_spans,
                    interval_start,
                    interval_end,
                ),
                t_prefill_ms=t_prefill,
                t_decode_ms=t_decode,
                t_network_ms=t_network,
                timing_method=timing_method,
                t_tool_ms=tool_ms,
                t_orch_gap_ms=orch_gap_ms,
                input_tokens=input_tokens,
                output_tokens=record.usage.output_tokens,
                local_serialized_tokens=local_count,
                local_lcp_tokens=local_lcp,
                structurally_redundant_tokens=structural,
                provider_recovered_tokens=recovered,
                actually_recomputed_redundant_tokens=recomputed,
                necessary_prefill_tokens=necessary,
                template_overhead_envelope_tokens=envelope,
                step_type_semantic=semantic,
                is_tool_call=bool(tool_names_by_turn[idx]),
                tool_names=tool_names_by_turn[idx],
                repeat_count=repeats[semantic],
                loop_membership=loops[idx],
                fanout_siblings=max(0, len(tool_names_by_turn[idx]) - 1),
                status="ok" if record.response_status < 400 else "error",
                audit_flags=sorted(set(flags)),
            )
        )
    return turns


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(dict(row), sort_keys=True) + "\n")
    return path


def decode_raw_body(record: ApiBoundaryRecord, *, response: bool = False) -> bytes:
    encoded = record.response_body_b64 if response else record.request_body_b64
    return base64.b64decode(encoded)

