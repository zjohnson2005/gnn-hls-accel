"""P0 exchange-rate child. One device, one context, one repeat.

Does not open a preregistration or an amendment file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import traceback
from pathlib import Path
from typing import Any

from seam.tools._delta_n_child import _chat_once, _mem, _Writer
from seam.tools.boot4_text import _exact_body, id_count
from seam.tools.exchange_rate_table import (
    cached_retry_pair,
    isolated_probe,
    skip_over_budget,
    streamer_allowed,
)

_TOOL = {
    "type": "function",
    "function": {
        "name": "echo",
        "description": "Echo the provided text.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
}


def _render_tool(tokenizer: Any, ov_genai: Any, content: str, *, thinking: bool) -> str:
    history = ov_genai.ChatHistory()
    history.set_tools([_TOOL])
    history.set_extra_context({"enable_thinking": thinking})
    history.append({"role": "user", "content": content})
    return str(tokenizer.apply_chat_template(history, True))


def _exact_tool_prompt(
    tokenizer: Any,
    ov_genai: Any,
    target: int,
    *,
    unit: str,
    salt: str,
    thinking: bool,
) -> str:
    prefix = f"{salt} "

    def count(text: str) -> int:
        return id_count(tokenizer, _render_tool(tokenizer, ov_genai, text, thinking=thinking))

    content = _exact_body(count, target, prefix=prefix, unit=unit)
    rendered = _render_tool(tokenizer, ov_genai, content, thinking=thinking)
    realized = id_count(tokenizer, rendered)
    if realized != target:
        raise RuntimeError(f"tool prompt is {realized} tokens, requested {target}")
    return rendered


class _BudgetStreamer:
    """Records the decode span and stops once the budget has elapsed."""

    def __init__(self, ov_genai: Any, budget_s: float | None) -> None:
        class _Streamer(ov_genai.StreamerBase):
            def __init__(self) -> None:
                super().__init__()
                self.t0_ns: int | None = None
                self.first_token_ns: int | None = None
                self.last_token_ns: int | None = None
                self.stopped_for_budget = False

            def write(self, _token: Any) -> Any:
                now = time.perf_counter_ns()
                if self.first_token_ns is None:
                    self.first_token_ns = now
                self.last_token_ns = now
                if (
                    budget_s is not None
                    and self.t0_ns is not None
                    and (now - self.t0_ns) / 1e9 >= budget_s
                ):
                    self.stopped_for_budget = True
                    return ov_genai.StreamingStatus.STOP
                return ov_genai.StreamingStatus.RUNNING

            def end(self) -> None:
                return None

        self.streamer = _Streamer()


def _metrics(result: Any) -> tuple[int | None, int | None]:
    metrics = getattr(result, "perf_metrics", None)
    if metrics is None:
        return None, None
    prompt_tokens = None
    completion_tokens = None
    try:
        prompt_tokens = int(metrics.get_num_input_tokens())
        completion_tokens = int(metrics.get_num_generated_tokens())
    except Exception:
        return None, None
    return prompt_tokens, completion_tokens


def _result_list(result: Any) -> list[Any]:
    if isinstance(result, (list, tuple)):
        return list(result)
    return [result]


def _generate(
    pipe: Any,
    ov_genai: Any,
    prompts: list[str],
    *,
    max_new_tokens: int,
    min_new_tokens: int | None,
    ignore_eos: bool,
    budget_s: float | None,
    stop_on_tool: bool,
) -> dict[str, Any]:
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = int(max_new_tokens)
    if min_new_tokens is not None:
        cfg.min_new_tokens = int(min_new_tokens)
    cfg.do_sample = False
    cfg.ignore_eos = bool(ignore_eos)
    cfg.apply_chat_template = False
    if stop_on_tool:
        cfg.stop_strings = {"</tool_call>"}
        cfg.include_stop_str_in_output = True
    n_seq = len(prompts)
    # pipeline_impl.cpp:530: streaming is possible only with batch size=1
    # and only for greedy or multinomial decoding. A streamer with
    # num_return_sequences > 1, or with more than one prompt, is refused.
    use_streamer = streamer_allowed(n_seq)
    stopped = False
    prefill_s = None
    decode_tok_s = None
    t0 = time.perf_counter()
    if use_streamer:
        probe = _BudgetStreamer(ov_genai, budget_s)
        probe.streamer.t0_ns = time.perf_counter_ns()
        result = pipe.generate(prompts, cfg, probe.streamer)
        stopped = bool(probe.streamer.stopped_for_budget)
        first_ns = probe.streamer.first_token_ns
        last_ns = probe.streamer.last_token_ns
        if first_ns is not None and probe.streamer.t0_ns is not None:
            prefill_s = (first_ns - probe.streamer.t0_ns) / 1e9
    else:
        result = pipe.generate(prompts, cfg)
        first_ns = None
        last_ns = None
    wall_s = time.perf_counter() - t0
    rows = _result_list(result)
    texts: list[str] = []
    prompt_tokens = 0
    completion_tokens = 0
    saw_metrics = False
    for row in rows:
        texts.extend(str(item) for item in (getattr(row, "texts", None) or []))
        prompt_n, completion_n = _metrics(row)
        if completion_n is not None:
            saw_metrics = True
            completion_tokens += completion_n
            prompt_tokens += int(prompt_n or 0)
    if not saw_metrics:
        raise RuntimeError("generate returned no token count")
    if (
        use_streamer
        and first_ns is not None
        and last_ns is not None
        and last_ns > first_ns
        and completion_tokens > n_seq
    ):
        decode_tok_s = (completion_tokens - n_seq) / ((last_ns - first_ns) / 1e9)
    aggregate_tok_s = None
    if wall_s > 0.0 and completion_tokens > 0:
        aggregate_tok_s = completion_tokens / wall_s
    return {
        "wall_s": wall_s,
        "prefill_s": prefill_s,
        "decode_tok_s": decode_tok_s,
        "aggregate_tok_s": aggregate_tok_s,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "n_seq": n_seq,
        "streamer": use_streamer,
        "stopped_for_budget": stopped,
        "text_head": texts[0][:200] if texts else "",
        "texts": texts,
        "schedule": "COLD",
    }


def _run(spec: dict[str, Any], writer: _Writer) -> int:
    from seam.tools._winpower import assert_system_required

    power_req = assert_system_required(
        reason="SEAM exchange-rate child; PowerRequestSystemRequired for generate window",
        role="measurement_child",
    )
    writer.update(phase="power_request", power_request=dict(power_req.record))
    try:
        return _run_body(spec, writer)
    finally:
        power_req.release()
        writer.update(power_request=dict(power_req.record))


def _run_body(spec: dict[str, Any], writer: _Writer) -> int:
    import psutil

    from seam.tools._winmem import lock_working_set, read_working_set_limits

    affinity = spec.get("affinity_cpus")
    if affinity:
        psutil.Process().cpu_affinity([int(cpu) for cpu in affinity])
    writer.update(affinity_readback=[int(cpu) for cpu in psutil.Process().cpu_affinity()])
    wslock = dict(spec.get("wslock") or {})
    if str(wslock.get("mode")) == "request":
        lock_record = lock_working_set(
            minimum_bytes=int(wslock["minimum_bytes"]),
            maximum_bytes=int(wslock["maximum_bytes"]),
        )
    else:
        lock_record = {
            "requested": False,
            "granted": False,
            "mode": str(wslock.get("mode", "off")),
            "before": read_working_set_limits(),
        }
    writer.update(phase="wslock", working_set_lock=lock_record)

    import openvino as ov
    import openvino_genai as ov_genai

    from seam.backends.local_openvino import parse_tool_calls
    from seam.ov_kv_precision import (
        enforce_kv_cache_precision,
        materialize_pipeline_properties,
        requested_kv_cache_precision,
    )
    from seam.tools.boot4_text import rendered_exact_prompt

    plan = dict(spec["exchange"])
    entry = spec["load_sequence"][0]
    device = str(entry["device"])
    properties = materialize_pipeline_properties(dict(entry.get("properties") or {}))
    requested_kv = requested_kv_cache_precision(dict(entry.get("properties") or {}))
    scheduler = ov_genai.SchedulerConfig()
    scheduler.enable_prefix_caching = bool(plan["enable_prefix_caching"])
    scheduler.max_num_seqs = int(plan["max_num_seqs"])
    scheduler.max_num_batched_tokens = int(plan["max_num_batched_tokens"])
    core = ov.Core()
    if requested_kv is not None:
        core.set_property(device, {"KV_CACHE_PRECISION": properties["KV_CACHE_PRECISION"]})
    pipe = ov_genai.LLMPipeline(
        str(spec["model_dir"]),
        device,
        scheduler_config=scheduler,
        **properties,
    )
    kv_check = enforce_kv_cache_precision(device=device, requested=requested_kv, core=core)
    writer.update(
        phase="resident",
        memory_resident_before_inference=_mem(),
        kv_cache_precision_readback=kv_check,
    )
    if not kv_check["match"]:
        writer.update(
            phase="failed",
            completed=False,
            failure_mode=kv_check["failure_mode"],
        )
        return 1

    tokenizer = pipe.get_tokenizer()
    n_tokens = int(plan["context_tokens"])
    unit = str(spec["filler_unit"])
    salt = str(plan["salt"])
    shared = rendered_exact_prompt(tokenizer, n_tokens, unit=unit, salt=salt)
    tool_prompt = _exact_tool_prompt(
        tokenizer,
        ov_genai,
        n_tokens,
        unit=unit,
        salt=salt + "-tool",
        thinking=False,
    )
    think_prompt = _exact_tool_prompt(
        tokenizer,
        ov_genai,
        n_tokens,
        unit=unit,
        salt=salt + "-think",
        thinking=True,
    )
    decode_tokens = int(plan["decode_new_tokens"])
    budget_s = float(plan["budget_s"])
    projected = {
        str(name): float(value) for name, value in dict(plan.get("projected_wall_s") or {}).items()
    }
    skip_multiple = plan.get("skip_budget_multiple")
    skip_multiple_f = None if skip_multiple is None else float(skip_multiple)
    probes: list[dict[str, Any]] = []

    def take(name: str, fn: Any) -> None:
        skipped = skip_over_budget(
            name=name,
            projected_wall_s=projected.get(name),
            budget_s=budget_s,
            multiple=skip_multiple_f,
        )
        probes.append(skipped if skipped is not None else isolated_probe(name, fn))
        writer.update(phase=name, probes=list(probes))

    def batch(concurrency: int) -> dict[str, Any]:
        row = _generate(
            pipe,
            ov_genai,
            [shared] * concurrency,
            max_new_tokens=decode_tokens,
            min_new_tokens=decode_tokens,
            ignore_eos=True,
            budget_s=None,
            stop_on_tool=False,
        )
        row["concurrency"] = concurrency
        return row

    for concurrency in plan["concurrencies"]:
        take(f"batch-{int(concurrency)}", lambda c=int(concurrency): batch(c))

    def thinking() -> dict[str, Any]:
        return _generate(
            pipe,
            ov_genai,
            [think_prompt],
            max_new_tokens=decode_tokens,
            min_new_tokens=decode_tokens,
            ignore_eos=True,
            budget_s=None,
            stop_on_tool=False,
        )

    take("thinking", thinking)

    def retry() -> dict[str, Any]:
        # batch-2 and batch-4 reuse this string and hit. The thinking prompt
        # is a different template and, on GPU, evicted that prefix before the
        # old retry ran, so the measured prefill was a second cold pass.
        # Prime and measure back to back. Same token ids, thinking off, same pipe.
        prime_prompt, measure_prompt = cached_retry_pair(shared)
        token_ids = tokenizer.encode(prime_prompt).input_ids
        flat = token_ids.tolist() if hasattr(token_ids, "tolist") else list(token_ids)
        digest = hashlib.sha256(repr(flat).encode("ascii")).hexdigest()
        prime = _generate(
            pipe,
            ov_genai,
            [prime_prompt],
            max_new_tokens=decode_tokens,
            min_new_tokens=decode_tokens,
            ignore_eos=True,
            budget_s=None,
            stop_on_tool=False,
        )
        row = _generate(
            pipe,
            ov_genai,
            [measure_prompt],
            max_new_tokens=decode_tokens,
            min_new_tokens=decode_tokens,
            ignore_eos=True,
            budget_s=None,
            stop_on_tool=False,
        )
        row["cache_prime_prefill_s"] = prime.get("prefill_s")
        row["prompt_token_sha256"] = digest
        row["enable_thinking"] = False
        row["pipeline_id"] = id(pipe)
        row["intervening_prompts"] = 0
        return row

    take("retry", retry)

    def greedy_tta() -> dict[str, Any]:
        row = _generate(
            pipe,
            ov_genai,
            [tool_prompt],
            max_new_tokens=int(plan["tta_max_new_tokens"]),
            min_new_tokens=None,
            ignore_eos=False,
            budget_s=budget_s,
            stop_on_tool=True,
        )
        full = "\n".join(row.pop("texts"))
        parsed = len(parse_tool_calls(full)) > 0
        row.update(
            {
                "parsed_tool_call": parsed,
                "give_up": not parsed,
                "tta_s": row["wall_s"],
            }
        )
        return row

    take("greedy_tta", greedy_tta)

    def warm() -> dict[str, Any]:
        from seam.tools.boot4_text import raw_exact_text, user_content_for_rendered_tokens

        n_cached = n_tokens
        delta_tokens = int(plan["warm_delta_tokens"])
        warm_tokens = int(plan["warm_decode_new_tokens"])
        turn1_content = user_content_for_rendered_tokens(
            tokenizer, n_cached, unit=unit, salt=salt + "-warm"
        )
        delta = raw_exact_text(tokenizer, delta_tokens, unit=unit, salt=salt + "-warm-d")
        cfg1 = ov_genai.GenerationConfig()
        cfg1.max_new_tokens = 1
        cfg1.do_sample = False
        cfg1.ignore_eos = True
        cfg2 = ov_genai.GenerationConfig()
        cfg2.max_new_tokens = warm_tokens
        cfg2.min_new_tokens = warm_tokens
        cfg2.do_sample = False
        cfg2.ignore_eos = True
        history = ov_genai.ChatHistory()
        history.set_extra_context({"enable_thinking": False})
        history.append({"role": "user", "content": turn1_content})
        turn1 = _chat_once(pipe, history, cfg1, ov_genai)
        reported = turn1.get("prompt_tokens_reported")
        if reported is not None and int(reported) != n_cached:
            raise RuntimeError(
                f"warm turn-1 prompt tokens {reported} do not equal n_cached {n_cached}"
            )
        base = json.loads(json.dumps(history.get_messages()))
        branch = ov_genai.ChatHistory()
        branch.set_extra_context({"enable_thinking": False})
        branch.set_messages(base)
        branch.append({"role": "user", "content": delta})
        turn2 = _chat_once(pipe, branch, cfg2, ov_genai)
        return {
            "schedule": "WARM",
            "n_cached": n_cached,
            "delta_tokens": delta_tokens,
            "decode_new_tokens": warm_tokens,
            "turn1_prefill_s": turn1.get("prefill_s"),
            "turn1_wall_s": turn1.get("wall_s"),
            "turn2_prefill_s": turn2.get("prefill_s"),
            "turn2_wall_s": turn2.get("wall_s"),
            "warm_tta_s": turn2.get("wall_s"),
            "completion_tokens": turn2.get("completion_tokens_reported"),
        }

    take("warm", warm)
    failed = [item for item in probes if item.get("outcome") == "fail"]
    writer.update(
        phase="done" if not failed else "failed",
        completed=not failed,
        failure_mode=None
        if not failed
        else str(failed[0].get("failure_mode") or failed[0]["name"]),
        probes=probes,
        context_tokens=n_tokens,
    )
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    writer = _Writer(args.out)
    writer.update(phase="baseline", memory_baseline=_mem())
    try:
        return _run(spec, writer)
    except BaseException as exc:
        writer.update(
            phase="failed",
            completed=False,
            failure_mode=f"exception:{type(exc).__name__}",
            exception={
                "type": type(exc).__name__,
                "message": str(exc)[:4000],
                "traceback": traceback.format_exc()[:8000],
            },
            memory_at_failure=_mem(),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
