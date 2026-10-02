#!/usr/bin/env python3
"""P1 local-quality runner. One GPU pipeline per arm. Smoke does not load a model.

The measurement path is local_only: Qwen3-4B-int4, KV u8, RESIDENT, 200 BFCL
multi-turn tasks. This file does not open a preregistration.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from seam.tools.p1_quality import (  # noqa: E402
    capped_new_tokens,
    compose_greedy_vote,
    entry_record,
    feedback_sha256,
    measured_batch_rate,
    normalize_tool_call,
    run_smoke,
    should_resample,
    step_account,
)

CONFIG_PATH = ROOT / "configs" / "p1_quality.yaml"
# Pooled healthy sessions settled canary turn-2 prefill in this band.
HEALTHY_REF_T2_LOW = 0.70
HEALTHY_REF_T2_HIGH = 0.76


def load_config() -> dict[str, Any]:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("REFUSED -- p1 config is not a mapping")
    return data


class ArmController:
    """Per-entry step clock. The session calls this instead of a bare generate."""

    def __init__(self, cfg: dict[str, Any], *, arm: str, seed: int) -> None:
        self.arm = arm
        self.seed = int(seed)
        self.budget_s = float(cfg["budget_s"])
        self.max_new = int(cfg["max_new_tokens"])
        self.max_attempts = int(cfg["max_resamples"])
        sampling = dict(cfg["sampling"])
        self.temperature = float(sampling["temperature"])
        self.top_p = float(sampling["top_p"])
        self.top_k = int(sampling["top_k"])
        self.extra_k = int(cfg["extra_batch_k"])
        self.band_threshold = int(cfg["context_band_threshold"])
        self.rate_table = dict(cfg["batched_tok_s"])
        self.log: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None
        self._live_decode: float | None = None
        self._reset_open()

    def _reset_open(self) -> None:
        self.step_open = False
        self.t0 = 0.0
        self.samples: list[dict[str, Any]] = []
        self.attempts = 0
        self.stopped = False
        self._emitted: int | None = None
        self._account_elapsed: float | None = None
        self._account_stopped: bool | None = None
        self._k_used: int | None = None
        self._k_requested: int | None = None
        self._samples_finished: int | None = None
        self._vote_agreement: float | None = None
        self._agreement: bool | None = None
        self._override: bool | None = None
        self._greedy_call_sha256: str | None = None
        self._extras_call_sha256: list[str | None] | None = None
        self._source: str | None = None
        self._fallback_to_greedy = False
        self._token_cap: int | None = None
        self._rate_tok_s: float | None = None
        self._table_k: int | None = None
        self._band: int | None = None
        self._decode_source: str | None = None
        self._extra_wall_s: float | None = None
        self._extras_exceeded = False
        self._retention: dict[str, Any] = {}
        self._check_result: str | None = None
        self._checks: list[str] = []
        self._greedy_check: str | None = None
        self._feedback_sha256: list[str] = []
        self._feedback_tokens = 0

    def elapsed(self) -> float:
        if not self.step_open:
            return 0.0
        return time.perf_counter() - self.t0

    def _ensure_open(self) -> None:
        if self.step_open:
            return
        self._reset_open()
        self.step_open = True
        self.t0 = time.perf_counter()

    def retry_empty(self) -> bool:
        return self._retry("empty")

    def retry_exec(self) -> bool:
        return self._retry("exec")

    def _retry(self, reason: str) -> bool:
        if self.attempts >= self.max_attempts:
            return False
        return should_resample(
            arm=self.arm,
            reason=reason,
            elapsed_s=self.elapsed(),
            budget_s=self.budget_s,
        )

    def can_feedback_retry(self, *, n_ctx: int | None) -> bool:
        """A5 only. One more greedy decode while remaining time can buy a token."""
        if self.arm != "A5":
            return False
        if self.attempts >= self.max_attempts:
            return False
        if self.budget_s - self.elapsed() <= 0.0:
            return False
        return self._remaining_cap(requested_k=1, n_ctx=n_ctx) > 0

    def note_feedback(self, text: str, tokens: int) -> None:
        self._feedback_sha256.append(feedback_sha256(text))
        self._feedback_tokens += int(tokens)

    def finish_precheck(self, check: dict[str, Any], *, accepted: bool) -> None:
        """Record the pre-execution class. A later passing decode is the feedback source."""
        result = str(check["result"])
        self._checks.append(result)
        if self.attempts <= 1:
            self._greedy_check = result
        if accepted and self.attempts > 1:
            self._source = "feedback"
            self._check_result = result
            return
        self._source = "greedy"
        self._check_result = result if accepted else self._greedy_check

    def record_retention(
        self,
        *,
        emitted_tokens: int,
        retained_tokens: int,
        emitted_chars: int,
        retained_chars: int,
    ) -> None:
        """A4: tokens emitted against tokens kept in history after the think strip."""
        self._retention = {
            "emitted_tokens": int(emitted_tokens),
            "retained_tokens": int(retained_tokens),
            "emitted_chars": int(emitted_chars),
            "retained_chars": int(retained_chars),
            "thinking_stripped": int(emitted_chars) != int(retained_chars),
        }
        self._emitted = int(emitted_tokens)

    def step_record(self) -> dict[str, Any]:
        tokens = (
            self._emitted
            if self._emitted is not None
            else sum(int(sample["tokens"]) for sample in self.samples)
        )
        elapsed = self.elapsed() if self._account_elapsed is None else self._account_elapsed
        stopped = self.stopped if self._account_stopped is None else self._account_stopped
        n_samples = len(self.samples) if self._samples_finished is None else self._samples_finished
        account = step_account(
            elapsed_s=elapsed,
            budget_s=self.budget_s,
            n_samples=n_samples,
            tokens=tokens,
            stopped_for_budget=stopped,
        )
        if self._fallback_to_greedy:
            account["fallback"] = True
        account["arm"] = self.arm
        account["k_used"] = self._k_used
        account["k_requested"] = self._k_requested
        account["samples_finished"] = self._samples_finished
        account["vote_agreement"] = self._vote_agreement
        account["agreement"] = self._agreement
        account["override"] = self._override
        account["greedy_call_sha256"] = self._greedy_call_sha256
        account["extras_call_sha256"] = self._extras_call_sha256
        account["source"] = self._source
        account["fallback_to_greedy"] = self._fallback_to_greedy
        account["emitted_tokens"] = self._emitted if self._emitted is not None else tokens
        account["retained_tokens"] = None
        account["token_cap"] = self._token_cap
        account["rate_tok_s"] = self._rate_tok_s
        account["table_k"] = self._table_k
        account["context_band"] = self._band
        account["decode_tok_s_source"] = self._decode_source
        account["extra_wall_s"] = self._extra_wall_s
        account["extras_exceeded_remaining"] = self._extras_exceeded
        account["check_result"] = self._check_result
        account["checks"] = list(self._checks) if self._checks else None
        account["feedback_sha256"] = list(self._feedback_sha256) if self._feedback_sha256 else None
        account["feedback_tokens"] = self._feedback_tokens if self._feedback_sha256 else None
        account["attempts"] = self.attempts if self.arm == "A5" else None
        account.update(self._retention)
        self._current = account
        return account

    def close_step(self) -> None:
        if self._current is not None:
            self.log.append(dict(self._current))
            self._current = None
        self._reset_open()

    def generate(
        self, pipe: Any, ov_genai: Any, prompt: Any, *, prompt_tokens: int | None = None
    ) -> dict[str, Any]:
        self._ensure_open()
        self.attempts += 1
        if self.arm == "A1":
            return self._greedy_then_extras(pipe, ov_genai, prompt, prompt_tokens=prompt_tokens)
        if self.arm == "A4":
            return self._thinking(pipe, ov_genai, prompt, prompt_tokens=prompt_tokens)
        sample = self.arm in {"A2", "A3"} and self.attempts > 1
        max_new: int | None = None
        if self.arm == "A5" and self.attempts > 1:
            max_new = self._remaining_cap(requested_k=1, n_ctx=prompt_tokens)
        elif sample:
            max_new = self._remaining_cap(requested_k=1, n_ctx=prompt_tokens)
        row = self._one(pipe, ov_genai, prompt, sample=sample, max_new=max_new)
        tokens = int(row.get("generated_tokens") or 0)
        self.samples.append(
            {"text": row.get("text") or "", "tokens": tokens, "elapsed_s": self.elapsed()}
        )
        if self.arm == "A5":
            self._source = "greedy"
        else:
            self._source = "retry" if sample else "greedy"
        self._k_used = len(self.samples)
        self._k_requested = self._k_used
        self._samples_finished = self._k_used
        self._emitted = sum(int(item["tokens"]) for item in self.samples)
        return row

    def _rate(self, *, requested_k: int, n_ctx: int | None) -> dict[str, Any]:
        chosen = measured_batch_rate(
            self.rate_table,
            requested_k=requested_k,
            n_ctx=n_ctx,
            band_threshold=self.band_threshold,
        )
        self._rate_tok_s = float(chosen["rate_tok_s"])
        self._table_k = int(chosen["table_k"])
        self._band = int(chosen["band"])
        return chosen

    def _remaining_cap(self, *, requested_k: int, n_ctx: int | None) -> int:
        remaining = self.budget_s - self.elapsed()
        chosen = self._rate(requested_k=requested_k, n_ctx=n_ctx)
        cap = capped_new_tokens(
            remaining_s=remaining,
            rate_tok_s=float(chosen["rate_tok_s"]),
            batch_k=int(chosen["table_k"]),
        )
        self._token_cap = cap
        self._decode_source = "table"
        return cap

    def _greedy_then_extras(
        self, pipe: Any, ov_genai: Any, prompt: Any, *, prompt_tokens: int | None
    ) -> dict[str, Any]:
        greedy = self._one(pipe, ov_genai, prompt, sample=False, max_new=None)
        greedy_elapsed = self.elapsed()
        greedy_stopped = self.stopped
        greedy_tokens = int(greedy.get("generated_tokens") or 0)
        self.samples.append(
            {"text": greedy.get("text") or "", "tokens": greedy_tokens, "elapsed_s": greedy_elapsed}
        )
        reported = greedy.get("prompt_tokens_reported")
        n_ctx = int(reported) if reported is not None else prompt_tokens
        remaining = self.budget_s - greedy_elapsed
        extras: list[dict[str, Any]] = []
        extra_wall = 0.0
        exceeded = False
        launched = False
        if bool(greedy.get("ok")) and remaining > 0.0:
            cap = self._remaining_cap(requested_k=self.extra_k, n_ctx=n_ctx)
            if cap > 0:
                launched = True
                extras, extra_wall = self._capped_extras(
                    pipe, ov_genai, prompt, sequences=self.extra_k, max_new=cap
                )
                if extra_wall > remaining:
                    exceeded = True
                    for item in extras:
                        item["finished"] = False
        decision = compose_greedy_vote(greedy_text=str(greedy.get("text") or ""), extras=extras)
        overridden = decision["source"] == "override"
        self._account_elapsed = self.elapsed() if overridden else greedy_elapsed
        self._account_stopped = False if overridden else greedy_stopped
        self._source = str(decision["source"])
        self._k_used = int(decision["k_used"])
        self._k_requested = 1 + self.extra_k if launched else 1
        self._samples_finished = int(decision["samples_finished"])
        self._vote_agreement = decision["vote_agreement"]
        self._agreement = bool(decision["agreement"])
        self._override = bool(decision["override"])
        self._greedy_call_sha256 = decision["greedy_call_sha256"]
        self._extras_call_sha256 = list(decision["extras_call_sha256"])
        self._fallback_to_greedy = bool(decision["fallback_to_greedy"])
        self._extra_wall_s = extra_wall if extras else None
        self._extras_exceeded = exceeded
        used_tokens = greedy_tokens
        if overridden:
            used_tokens += sum(int(item["tokens"]) for item in extras if item.get("finished"))
        self._emitted = used_tokens
        out = dict(greedy)
        out["text"] = decision["text"]
        return out

    def _thinking(
        self, pipe: Any, ov_genai: Any, prompt: Any, *, prompt_tokens: int | None
    ) -> dict[str, Any]:
        remaining = self.budget_s - self.elapsed()
        if self._live_decode is not None and self._live_decode > 0.0:
            rate = self._live_decode
            self._rate_tok_s = rate
            self._table_k = 1
            self._band = None
            self._decode_source = "live"
            cap = capped_new_tokens(remaining_s=remaining, rate_tok_s=rate, batch_k=1)
        else:
            cap = self._remaining_cap(requested_k=1, n_ctx=prompt_tokens)
            self._decode_source = "table"
        self._token_cap = cap
        row = self._one(pipe, ov_genai, prompt, sample=False, max_new=cap)
        observed = row.get("decode_tok_s")
        if observed is not None and float(observed) > 0.0:
            self._live_decode = float(observed)
        tokens = int(row.get("generated_tokens") or 0)
        self.samples.append(
            {"text": row.get("text") or "", "tokens": tokens, "elapsed_s": self.elapsed()}
        )
        self._source = "greedy"
        self._k_used = 1
        self._k_requested = 1
        self._samples_finished = 1
        self._emitted = tokens
        return row

    def _config(
        self, ov_genai: Any, prompt: Any, *, sample: bool, sequences: int, max_new: int | None
    ) -> Any:
        cfg = ov_genai.GenerationConfig()
        cfg.max_new_tokens = self.max_new if max_new is None else int(max_new)
        cfg.do_sample = bool(sample)
        cfg.apply_chat_template = not isinstance(prompt, str)
        cfg.rng_seed = self.seed
        if sequences > 1:
            cfg.num_return_sequences = int(sequences)
        if sample:
            cfg.temperature = self.temperature
            cfg.top_p = self.top_p
            cfg.top_k = self.top_k
        return cfg

    def _one(
        self, pipe: Any, ov_genai: Any, prompt: Any, *, sample: bool, max_new: int | None
    ) -> dict[str, Any]:
        from seam.backends.local_openvino import _extract_metrics, resolve_ttft_ns

        remaining = self.budget_s - self.elapsed()
        if max_new is not None and max_new <= 0:
            self.stopped = True
            return _timed_row(
                ok=True,
                error=None,
                wall_s=0.0,
                text="",
                ttft_ns=None,
                ttft_source=None,
                prompt_tokens=0,
                generated=0,
            )
        cfg = self._config(ov_genai, prompt, sample=sample, sequences=1, max_new=max_new)
        streamer = _BudgetStop(ov_genai, remaining if remaining > 0.0 else 0.0)
        streamer.streamer.t0_ns = time.perf_counter_ns()
        t0 = time.perf_counter()
        exc: BaseException | None = None
        result: Any = None
        try:
            if isinstance(prompt, str):
                result = pipe.generate([prompt], cfg, streamer.streamer)
            else:
                result = pipe.generate(prompt, cfg, streamer.streamer)
        except Exception as err:
            exc = err
        wall_s = time.perf_counter() - t0
        self.stopped = bool(streamer.streamer.stopped_for_budget) or remaining <= 0.0
        texts = list(getattr(result, "texts", []) or [])
        text = str(texts[0]) if texts else ""
        metrics = getattr(result, "perf_metrics", None)
        ttft_ns, prompt_tokens, generated = _extract_metrics(metrics)
        resolved, source = resolve_ttft_ns(ttft_ns, streamer.streamer.ttft_ns)
        return _timed_row(
            ok=exc is None,
            error=None if exc is None else f"{type(exc).__name__}: {exc}",
            wall_s=wall_s,
            text=text,
            ttft_ns=resolved,
            ttft_source=source,
            prompt_tokens=prompt_tokens,
            generated=generated,
        )

    def _capped_extras(
        self, pipe: Any, ov_genai: Any, prompt: Any, *, sequences: int, max_new: int
    ) -> tuple[list[dict[str, Any]], float]:
        from seam.backends.local_openvino import _extract_metrics

        cfg = self._config(ov_genai, prompt, sample=True, sequences=sequences, max_new=max_new)
        t0 = time.perf_counter()
        exc: BaseException | None = None
        result: Any = None
        try:
            if isinstance(prompt, str):
                result = pipe.generate([prompt], cfg)
            else:
                result = pipe.generate(prompt, cfg)
        except Exception as err:
            exc = err
        wall_s = time.perf_counter() - t0
        if exc is not None or result is None:
            return [{"text": "", "tokens": 0, "finished": False}], wall_s
        texts = [str(item) for item in list(getattr(result, "texts", []) or [])]
        _ttft, _prompt, generated = _extract_metrics(getattr(result, "perf_metrics", None))
        per = int(generated) // len(texts) if texts else 0
        rows: list[dict[str, Any]] = []
        for text in texts:
            parsed = normalize_tool_call(text) is not None
            hit_cap = per >= max_new
            rows.append(
                {"text": text, "tokens": per, "finished": bool(text) and (parsed or not hit_cap)}
            )
        if not rows:
            rows.append({"text": "", "tokens": 0, "finished": False})
        return rows, wall_s


class _BudgetStop:
    """Stop a single-sequence decode when the step budget has elapsed."""

    def __init__(self, ov_genai: Any, budget_s: float) -> None:
        class _Streamer(ov_genai.StreamerBase):
            def __init__(self) -> None:
                super().__init__()
                self.t0_ns: int | None = None
                self.ttft_ns: int | None = None
                self.stopped_for_budget = False

            def write(self, _token: Any) -> Any:
                now = time.perf_counter_ns()
                if self.ttft_ns is None and self.t0_ns is not None:
                    self.ttft_ns = now - self.t0_ns
                if self.t0_ns is not None and (now - self.t0_ns) / 1e9 >= budget_s:
                    self.stopped_for_budget = True
                    return ov_genai.StreamingStatus.STOP
                return ov_genai.StreamingStatus.RUNNING

            def end(self) -> None:
                return None

        self.streamer = _Streamer()


def _timed_row(
    *,
    ok: bool,
    error: str | None,
    wall_s: float,
    text: str,
    ttft_ns: int | None,
    ttft_source: str | None,
    prompt_tokens: int,
    generated: int,
) -> dict[str, Any]:
    ttft_s = None if ttft_ns is None or ttft_ns <= 0 else ttft_ns / 1e9
    decode = None
    if generated >= 2 and ttft_s is not None and wall_s > ttft_s:
        decode = (generated - 1) / (wall_s - ttft_s)
    return {
        "ok": ok,
        "error": error,
        "wall_s": wall_s,
        "ttft_s": ttft_s,
        "decode_tok_s": decode,
        "ttft_ns": ttft_ns,
        "ttft_source": ttft_source,
        "prompt_tokens_reported": prompt_tokens or None,
        "generated_tokens": generated or None,
        "text": text,
    }


def _append_entry_jsonl(path: Path, point: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry_record(point), sort_keys=True) + "\n")


def _entries(offset: int, count: int) -> list[dict[str, Any]]:
    import tools.bfcl_feasibility_probe as probe

    rows = sorted(probe.select_multi_turn_entries(), key=lambda item: str(item["id"]))
    if count > 0:
        return rows[offset : offset + count]
    if offset > 0:
        return rows[offset:]
    return rows


class PipelineSlot:
    """The P1 generate pipeline. Absent while a canary runs."""

    def __init__(self, arm_id: str) -> None:
        self.arm_id = arm_id
        self.pipe: Any = None
        self.meta: dict[str, Any] | None = None
        self.load_s: float | None = None
        self.loads = 0

    def load(self) -> None:
        import tools.bfcl_feasibility_probe as probe

        self.pipe, self.meta, self.load_s = probe.load_arm_pipeline(
            self.arm_id,
            enable_prefix_caching=None,
        )
        self.loads += 1

    def release(self) -> None:
        self.pipe = None
        gc.collect()


def bind_idle_canary(guard: Any, slot: Any) -> None:
    """Later checks release the P1 pipeline, run, then load it again."""
    original = guard.run_canary

    def run_canary(*args: Any, **kwargs: Any) -> Any:
        slot.release()
        try:
            return original(*args, **kwargs)
        finally:
            slot.load()

    guard.run_canary = run_canary


def prepare_measurement_canary(guard: Any, slot: Any) -> None:
    """Calibrate on an idle GPU, then hold the pipeline only for BFCL turns."""
    guard.opening()
    bind_idle_canary(guard, slot)
    slot.load()


def calibration_ref_in_healthy_range(ref_t2: float) -> bool:
    return HEALTHY_REF_T2_LOW <= float(ref_t2) <= HEALTHY_REF_T2_HIGH


def quality_summary(
    *,
    session_id: str,
    status: str,
    arm: str,
    seed: int,
    points: list[dict[str, Any]],
    guard: Any,
    pipeline_loads: int,
    load_s: float | None,
    load_meta: dict[str, Any] | None,
    abort_reason: str | None = None,
) -> dict[str, Any]:
    gate = dict(guard.gate)
    return {
        "kind": "p1_quality",
        "session_id": session_id,
        "status": status,
        "abort_reason": abort_reason,
        "arm": arm,
        "seed": seed,
        "entries_completed": len(points),
        "n_probes": len(points),
        "passes": sum(1 for point in points if point["passed"]),
        "in_budget_passes": sum(1 for point in points if point["in_budget_pass"]),
        "pipeline_loads": pipeline_loads,
        "load_s": load_s,
        "load_meta": load_meta,
        "canary": guard.plan_fragment(),
        "canaries": list(guard.canaries),
        "thresholds": {
            "threshold_t1": gate.get("threshold_t1"),
            "threshold_t2": gate.get("threshold_t2"),
            "ref_turn1_prefill_s": gate.get("ref_turn1_prefill_s"),
            "ref_turn2_prefill_s": gate.get("ref_turn2_prefill_s"),
        },
    }


def run_measurement(cfg: dict[str, Any], *, arm: str, seed: int, offset: int, count: int) -> int:
    if os.environ.get("SEAM_REHEARSAL") == "1":
        print("REFUSED -- rehearsal does not start the measurement", flush=True)
        return 1
    import tools.bfcl_feasibility_probe as probe
    from tools.boot4_session import (
        _canary_model,
        _open_canary,
        _publish_cell_status,
        load_harness,
        require_gates,
    )
    from tools.ttft_slo_canary import CanaryDriftAbort

    if arm not in list(cfg["arms"]):
        raise SystemExit(f"REFUSED -- unknown arm {arm}")
    gates = require_gates()
    model_spec = ROOT / str(cfg["model_spec"])
    harness = load_harness(model_spec)
    entries = _entries(offset, count)
    session_id = str(uuid.uuid4())
    out_dir = ROOT / "derived" / "p1_quality" / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    config_bytes = CONFIG_PATH.read_bytes()
    plan: dict[str, Any] = {
        "kind": "p1_quality",
        "session_id": session_id,
        "arm": arm,
        "seed": seed,
        "policy": str(cfg["policy"]),
        "arm_id": str(cfg["arm_id"]),
        "residency": str(cfg["residency"]),
        "budget_s": float(cfg["budget_s"]),
        "entry_offset": offset,
        "entry_count": len(entries),
        "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "gates": gates,
        "status": "running",
    }
    plan_path = out_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _publish_cell_status("running", session_id)
    print(f"RUN_ID {session_id}", flush=True)
    guard = _open_canary(
        model_spec=_canary_model([harness["model_spec"]]),
        work=out_dir / "work",
        plan_path=plan_path,
        planned=len(entries),
    )
    plan["canary"] = guard.plan_fragment()
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    slot = PipelineSlot(str(cfg["arm_id"]))
    prepare_measurement_canary(guard, slot)
    tokenizer = probe._hf_tokenizer()
    import openvino_genai as ov_genai

    cfg_idle = ov_genai.GenerationConfig()
    cfg_idle.max_new_tokens = int(cfg["max_new_tokens"])
    cfg_idle.do_sample = False
    points: list[dict[str, Any]] = []
    probes_log: list[dict[str, Any]] = []
    try:
        for entry in entries:
            controller = ArmController(cfg, arm=arm, seed=seed)
            session = probe.MultiTurnAgentSession(
                pipe=slot.pipe,
                tokenizer=tokenizer,
                cfg=cfg_idle,
                residency_mode=str(cfg["residency"]),
                ov_genai=ov_genai,
            )
            session.p1 = controller
            session.p1_enable_thinking = arm == "A4"
            t0 = time.perf_counter()
            session.begin(entry)
            try:
                questions = entry["question"]
                for turn_idx in range(len(questions)):
                    session.run_user_turn(turn_idx)
                    if session.force_quit:
                        break
            finally:
                result = session.finish()
            wall_s = time.perf_counter() - t0
            passed = bool((result.get("score") or {}).get("valid"))
            steps = list(controller.log)
            point = {
                "id": str(entry["id"]),
                "arm": arm,
                "seed": seed,
                "passed": passed,
                "in_budget_pass": passed
                and bool(steps)
                and all(step["met_budget"] for step in steps),
                "steps": steps,
                "wall_s": wall_s,
                "load_s": slot.load_s,
            }
            points.append(point)
            (out_dir / "points").mkdir(exist_ok=True)
            (out_dir / "points" / f"{entry['id']}.json").write_text(
                json.dumps(point, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _append_entry_jsonl(out_dir / "entries.jsonl", point)
            probes_log.append({"wall_s": wall_s})
            guard.after_probe(probes_log)
    except CanaryDriftAbort as exc:
        summary = quality_summary(
            session_id=session_id,
            status="FAIL_CANARY_DRIFT",
            arm=arm,
            seed=seed,
            points=points,
            guard=guard,
            pipeline_loads=slot.loads,
            load_s=slot.load_s,
            load_meta=slot.meta,
            abort_reason=str(exc.detail),
        )
        (out_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        _publish_cell_status("FAIL_CANARY_DRIFT", session_id)
        print(f"REFUSED -- FAIL_CANARY_DRIFT: {exc.detail}", flush=True)
        return 1
    summary = quality_summary(
        session_id=session_id,
        status="complete",
        arm=arm,
        seed=seed,
        points=points,
        guard=guard,
        pipeline_loads=slot.loads,
        load_s=slot.load_s,
        load_meta=slot.meta,
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _publish_cell_status("complete", session_id)
    print(
        f"P1_COMPLETE arm={arm} seed={seed} in_budget_passes={summary['in_budget_passes']}",
        flush=True,
    )
    return 0


def run_canary_calibration(cfg: dict[str, Any]) -> int:
    """Warm-up plus three idle canaries. Does not load the P1 pipeline."""
    from tools.boot4_session import _canary_model, _open_canary, load_harness

    rehearsal = os.environ.get("SEAM_REHEARSAL") == "1"
    if not rehearsal:
        from tools.boot4_session import require_gates

        require_gates()
    model_spec = ROOT / str(cfg["model_spec"])
    harness = load_harness(model_spec)
    if rehearsal:
        out_dir = ROOT / "derived" / "c2_ttft" / "_launches" / "_rehearsal" / "p1-a0" / "canary"
        session_id = "rehearsal-canary"
    else:
        session_id = str(uuid.uuid4())
        out_dir = ROOT / "derived" / "p1_quality" / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "plan.json"
    plan = {
        "kind": "p1_canary_calibration",
        "session_id": session_id,
        "status": "running",
        "p1_pipeline_loaded": False,
    }
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    guard = _open_canary(
        model_spec=_canary_model([harness["model_spec"]]),
        work=out_dir / "work",
        plan_path=plan_path,
        planned=3,
        enforce_probe_budget=False,
    )
    guard.opening()
    non_warmup = 0
    while not guard.gate.get("calibration_complete"):
        non_warmup = sum(1 for item in guard.canaries if not item.get("warmup"))
        if non_warmup >= 6:
            print("REFUSED -- canary calibration did not arm", flush=True)
            return 1
        guard.run_canary(after_probe_count=-1)
    ref_t2 = float(guard.gate["ref_turn2_prefill_s"])
    series = [
        float(item["turn2_prefill_s"])
        for item in guard.canaries
        if not item.get("warmup") and item.get("turn2_prefill_s") is not None
    ]
    series_text = ",".join(f"{value:.6f}" for value in series)
    print(f"CANARY_CALIBRATION ref_t2={ref_t2:.6f} series={series_text}", flush=True)
    if not calibration_ref_in_healthy_range(ref_t2):
        print(
            "REFUSED -- canary ref_t2="
            f"{ref_t2:.6f} outside {HEALTHY_REF_T2_LOW:.2f}-{HEALTHY_REF_T2_HIGH:.2f}",
            flush=True,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--canary-calibrate", action="store_true")
    parser.add_argument("--arm", default="A0")
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--entry-offset", type=int, default=0)
    parser.add_argument("--entry-count", type=int, default=0)
    args = parser.parse_args(argv)
    if args.smoke and args.canary_calibrate:
        raise SystemExit("REFUSED -- smoke and canary-calibrate are separate")
    if args.smoke:
        run_smoke()
        return 0
    if args.canary_calibrate:
        return run_canary_calibration(load_config())
    return run_measurement(
        load_config(),
        arm=str(args.arm),
        seed=int(args.seed),
        offset=int(args.entry_offset),
        count=int(args.entry_count),
    )


if __name__ == "__main__":
    raise SystemExit(main())
