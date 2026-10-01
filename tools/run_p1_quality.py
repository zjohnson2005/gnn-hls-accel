#!/usr/bin/env python3
"""P1 local-quality runner. One GPU pipeline per arm. Smoke does not load a model.

The measurement path is local_only: Qwen3-4B-int4, KV u8, RESIDENT, 200 BFCL
multi-turn tasks. This file does not open a preregistration.
"""

from __future__ import annotations

import argparse
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
    majority_vote,
    run_smoke,
    should_resample,
    step_account,
)

CONFIG_PATH = ROOT / "configs" / "p1_quality.yaml"


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
        self.cap = int(cfg["thinking_cap_tokens"])
        self.max_attempts = int(cfg["max_resamples"])
        sampling = dict(cfg["sampling"])
        self.temperature = float(sampling["temperature"])
        self.top_p = float(sampling["top_p"])
        self.top_k = int(sampling["top_k"])
        self.log: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None
        self._reset_open()

    def _reset_open(self) -> None:
        self.step_open = False
        self.t0 = 0.0
        self.samples: list[dict[str, Any]] = []
        self.attempts = 0
        self.stopped = False

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

    def step_record(self) -> dict[str, Any]:
        tokens = sum(int(sample["tokens"]) for sample in self.samples)
        account = step_account(
            elapsed_s=self.elapsed(),
            budget_s=self.budget_s,
            n_samples=len(self.samples),
            tokens=tokens,
            stopped_for_budget=self.stopped,
        )
        account["arm"] = self.arm
        self._current = account
        return account

    def close_step(self) -> None:
        if self._current is not None:
            self.log.append(dict(self._current))
            self._current = None
        self._reset_open()

    def generate(self, pipe: Any, ov_genai: Any, prompt: Any) -> dict[str, Any]:
        self._ensure_open()
        self.attempts += 1
        if self.arm == "A1":
            row, texts = self._parallel(pipe, ov_genai, prompt)
            share = int(row.get("generated_tokens") or 0)
            per = share // len(texts) if texts else share
            for text in texts:
                self.samples.append({"text": text, "tokens": per, "elapsed_s": self.elapsed()})
            if not texts:
                self.samples.append({"text": "", "tokens": 0, "elapsed_s": self.elapsed()})
            return row
        sample = self.arm in {"A2", "A3"} and self.attempts > 1
        row = self._one(pipe, ov_genai, prompt, sample=sample)
        self.samples.append(
            {
                "text": row.get("text") or "",
                "tokens": int(row.get("generated_tokens") or 0),
                "elapsed_s": self.elapsed(),
            }
        )
        return row

    def _config(self, ov_genai: Any, prompt: Any, *, sample: bool, sequences: int) -> Any:
        cfg = ov_genai.GenerationConfig()
        cfg.max_new_tokens = self.cap if self.arm == "A4" else self.max_new
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

    def _one(self, pipe: Any, ov_genai: Any, prompt: Any, *, sample: bool) -> dict[str, Any]:
        from seam.backends.local_openvino import _extract_metrics, resolve_ttft_ns

        cfg = self._config(ov_genai, prompt, sample=sample, sequences=1)
        remaining = self.budget_s - self.elapsed()
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

    def _parallel(self, pipe: Any, ov_genai: Any, prompt: Any) -> tuple[dict[str, Any], list[str]]:
        from seam.backends.local_openvino import _extract_metrics

        cfg = self._config(ov_genai, prompt, sample=True, sequences=4)
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
        self.stopped = False
        texts = [str(item) for item in list(getattr(result, "texts", []) or [])]
        vote = majority_vote(texts) if texts else {"winner": None}
        text = str(vote["winner"] or (texts[0] if texts else ""))
        _ttft_ns, prompt_tokens, generated = _extract_metrics(getattr(result, "perf_metrics", None))
        return (
            _timed_row(
                ok=exc is None,
                error=None if exc is None else f"{type(exc).__name__}: {exc}",
                wall_s=wall_s,
                text=text,
                ttft_ns=None,
                ttft_source=None,
                prompt_tokens=prompt_tokens,
                generated=generated,
            ),
            texts,
        )


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


def _entries(offset: int, count: int) -> list[dict[str, Any]]:
    import tools.bfcl_feasibility_probe as probe

    rows = sorted(probe.select_multi_turn_entries(), key=lambda item: str(item["id"]))
    if count > 0:
        return rows[offset : offset + count]
    if offset > 0:
        return rows[offset:]
    return rows


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
    pipe, meta, load_s = probe.load_arm_pipeline(str(cfg["arm_id"]), enable_prefix_caching=None)
    tokenizer = probe._hf_tokenizer()
    import openvino_genai as ov_genai

    cfg_idle = ov_genai.GenerationConfig()
    cfg_idle.max_new_tokens = int(cfg["max_new_tokens"])
    cfg_idle.do_sample = False
    points: list[dict[str, Any]] = []
    probes_log: list[dict[str, Any]] = []
    try:
        guard.opening()
        for entry in entries:
            controller = ArmController(cfg, arm=arm, seed=seed)
            session = probe.MultiTurnAgentSession(
                pipe=pipe,
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
                "load_s": load_s,
            }
            points.append(point)
            (out_dir / "points").mkdir(exist_ok=True)
            (out_dir / "points" / f"{entry['id']}.json").write_text(
                json.dumps(point, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            probes_log.append({"wall_s": wall_s})
            guard.after_probe(probes_log)
    except CanaryDriftAbort as exc:
        summary = {
            "kind": "p1_quality",
            "session_id": session_id,
            "status": "FAIL_CANARY_DRIFT",
            "abort_reason": str(exc.detail),
            "pipeline_loads": 1,
            "load_meta": meta,
        }
        (out_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        _publish_cell_status("FAIL_CANARY_DRIFT", session_id)
        print(f"REFUSED -- FAIL_CANARY_DRIFT: {exc.detail}", flush=True)
        return 1
    in_budget = sum(1 for point in points if point["in_budget_pass"])
    summary = {
        "kind": "p1_quality",
        "session_id": session_id,
        "status": "complete",
        "arm": arm,
        "seed": seed,
        "n_entries": len(points),
        "passes": sum(1 for point in points if point["passed"]),
        "in_budget_passes": in_budget,
        "pipeline_loads": 1,
        "load_s": load_s,
        "load_meta": meta,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    _publish_cell_status("complete", session_id)
    print(f"P1_COMPLETE arm={arm} seed={seed} in_budget_passes={in_budget}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--arm", default="A0")
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--entry-offset", type=int, default=0)
    parser.add_argument("--entry-count", type=int, default=0)
    args = parser.parse_args(argv)
    if args.smoke:
        run_smoke()
        return 0
    return run_measurement(
        load_config(),
        arm=str(args.arm),
        seed=int(args.seed),
        offset=int(args.entry_offset),
        count=int(args.entry_count),
    )


if __name__ == "__main__":
    raise SystemExit(main())
