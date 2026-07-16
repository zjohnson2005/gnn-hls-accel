"""Live calibration runner against a real Engine (CPU or cloud)."""

from __future__ import annotations

import json
import random
import statistics
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from apu_characterization.turntrace_v2.calibration import (
    DecodeProfile,
    NetworkBaseline,
    PrefillProfile,
)
from apu_characterization.turntrace_v2.engines import Engine, EngineIdentity


# F1: grid floor extends to 32 (engine tokens). Cap at model ctx separately.
DEFAULT_PREFILL_GRID_CPU = (32, 64, 128, 256, 512, 1024, 1536)
DEFAULT_DECODE_DEPTHS_CPU = (0, 512, 1536)


def _pad_prompt(n_tokens: int, *, seed: int = 0) -> str:
    """Build an approximate-n-token prompt (whitespace stand-in)."""
    rng = random.Random(seed)
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    words = [alphabet[rng.randint(0, len(alphabet) - 1)] for _ in range(max(1, n_tokens))]
    return " ".join(words)


def _exact_engine_token_prompt(
    engine: Engine,
    n_tokens: int,
    *,
    seed: int = 0,
    chat_shaped: bool = True,
) -> str | list[dict[str, str]]:
    """Grow/shrink user content until tokenize_messages length ≈ n_tokens (engine currency).

    When ``chat_shaped`` is True (default), return a system+user message list so
    calibration matches multi-turn chat templates used by trajectories.
    """
    text = _pad_prompt(max(1, n_tokens), seed=seed)
    system = "You are a coding agent. Call tools to fix bugs."

    def _messages(user_text: str) -> list[dict[str, str]]:
        if chat_shaped:
            return [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ]
        return [{"role": "user", "content": user_text}]

    messages = _messages(text)
    try:
        ids = engine.tokenize_messages(messages)
    except Exception:
        ids = engine.tokenize(text)
    guard = 0
    while abs(len(ids) - n_tokens) > 1 and guard < 40:
        guard += 1
        if len(ids) < n_tokens:
            need = n_tokens - len(ids)
            text = text + " " + _pad_prompt(need + 2, seed=seed + guard)
        else:
            words = text.split()
            keep = max(1, int(len(words) * n_tokens / max(1, len(ids))))
            text = " ".join(words[:keep])
        messages = _messages(text)
        try:
            ids = engine.tokenize_messages(messages)
        except Exception:
            ids = engine.tokenize(text)
    return messages if chat_shaped else text


def calibrate_prefill(
    engine: Engine,
    *,
    n_grid: Sequence[int] = DEFAULT_PREFILL_GRID_CPU,
    reps: int = 10,
    out_dir: Path | None = None,
    r2_gate: float = 0.99,
    seed: int = 0,
    max_ctx: int | None = None,
    measure_max_tokens: int = 1,
    settle_s: float = 0.0,
) -> PrefillProfile:
    """Sweep f(n) where n is always engine_tokens_in (post-template)."""
    ident = engine.identity
    profile = PrefillProfile(
        model_id=ident.model_id,
        quantization=ident.quantization,
        engine=ident.engine,
        hardware=ident.hardware,
    )
    grid = list(n_grid)
    if max_ctx is not None:
        grid = [n for n in grid if n <= max(64, max_ctx - 64)]
        if not grid:
            raise ValueError(f"no prefill grid points fit in max_ctx={max_ctx}")
    reconciliation_deltas: list[int] = []
    for n in grid:
        # Chat-shaped system+user cannot hit very small n (template floor ~39).
        # Use user-only pads for the floor point so the fitted domain covers 32.
        chat_shaped = n > 48
        for rep in range(reps):
            prompt = _exact_engine_token_prompt(
                engine, n, seed=seed + n + rep, chat_shaped=chat_shaped
            )
            # Discard warm-up after clear.
            engine.complete(
                prompt,
                max_tokens=1,
                temperature=0.0,
                seed=seed,
                use_cache=False,
                reset_cache=True,
            )
            if settle_s > 0:
                time.sleep(settle_s)
            result = engine.complete(
                prompt,
                max_tokens=int(measure_max_tokens),
                temperature=0.0,
                seed=seed,
                use_cache=False,
                reset_cache=True,
            )
            # Record in engine-token currency only.
            profile.add_observation(result.engine_tokens_in, result.t_prefill_ms)
            reconciliation_deltas.append(result.token_reconciliation_delta)
            if settle_s > 0:
                time.sleep(settle_s)
    # F3: widen envelope with multi-turn chat (tool-remapped) samples.
    reconciliation_deltas.extend(probe_multi_turn_reconciliation(engine, seed=seed + 10_000))
    profile.fit(held_out_fraction=0.2, r2_gate=r2_gate, seed=seed)
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = profile.to_dict()
        payload["provisional"] = bool(ident.provisional)
        payload["deployment_id"] = ident.deployment_id
        payload["identity"] = asdict(ident)
        payload["grid_requested"] = list(grid)
        payload["grid_min_engine"] = min(n for n, _ in profile.points)
        payload["grid_max_engine"] = max(n for n, _ in profile.points)
        payload["measure_max_tokens"] = int(measure_max_tokens)
        payload["token_reconciliation"] = _delta_envelope(reconciliation_deltas)
        (out_dir / "prefill_profile.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        (out_dir / "token_reconciliation_envelope.json").write_text(
            json.dumps(payload["token_reconciliation"], indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return profile


def _delta_envelope(deltas: Sequence[int]) -> dict[str, float]:
    if not deltas:
        return {"lo": 0.0, "hi": 0.0, "median": 0.0, "mad": 0.0, "n": 0}
    med = float(statistics.median(deltas))
    mad = float(statistics.median([abs(d - med) for d in deltas])) or 1.0
    # Calibrated envelope: median ± max(16, 3*MAD), expanded to observed min/max
    # so multi-turn template growth (more role markers) stays in-domain.
    half = max(16.0, 3.0 * mad)
    lo = min(med - half, float(min(deltas))) - 8.0
    hi = max(med + half, float(max(deltas))) + 8.0
    return {
        "lo": lo,
        "hi": hi,
        "median": med,
        "mad": mad,
        "n": float(len(deltas)),
    }


def probe_multi_turn_reconciliation(
    engine: Engine,
    *,
    seed: int = 0,
    n_turns: int = 6,
) -> list[int]:
    """F3: collect reconciliation deltas on multi-message chat (incl. tool remap)."""
    deltas: list[int] = []
    history = [
        {"role": "system", "content": "You are a coding agent. Call tools to fix bugs."},
        {"role": "user", "content": "Inspect main.py and ensure add works."},
    ]
    tool_payloads = [
        {"path": "main.py", "content": "def add(a,b): return a+b\n"},
        {"path": "main.py", "ok": True, "n_chars": 24},
        {"passed": True, "tests": 1},
        {"path": "main.py", "content": "def add(a, b):\n    return a + b\n"},
        {"path": "main.py", "ok": True, "n_chars": 32},
        {"passed": True, "tests": 1},
    ]
    for i in range(n_turns):
        result = engine.complete(
            history, max_tokens=1, temperature=0.0, seed=seed + i, use_cache=False, reset_cache=True
        )
        deltas.append(result.token_reconciliation_delta)
        payload = tool_payloads[i % len(tool_payloads)]
        history.append({"role": "assistant", "content": f"tool_call step {i}"})
        history.append({"role": "tool", "content": str(payload)})
    return deltas


def merge_reconciliation_envelopes(*envelopes: dict[str, float]) -> dict[str, float]:
    alive = [e for e in envelopes if e and e.get("n", 0)]
    if not alive:
        return {"lo": 0.0, "hi": 0.0, "median": 0.0, "mad": 0.0, "n": 0}
    return {
        "lo": min(float(e["lo"]) for e in alive),
        "hi": max(float(e["hi"]) for e in alive),
        "median": float(statistics.median([float(e["median"]) for e in alive])),
        "mad": max(float(e.get("mad", 1.0)) for e in alive),
        "n": float(sum(float(e["n"]) for e in alive)),
    }


def calibrate_decode(
    engine: Engine,
    *,
    kv_depths: Sequence[int] = DEFAULT_DECODE_DEPTHS_CPU,
    out_lens: Sequence[int] = (16, 64),
    reps: int = 3,
    out_dir: Path | None = None,
    seed: int = 0,
    max_ctx: int | None = 2048,
) -> DecodeProfile:
    ident = engine.identity
    profile = DecodeProfile(
        model_id=ident.model_id,
        quantization=ident.quantization,
        engine=ident.engine,
        hardware=ident.hardware,
    )
    for depth in kv_depths:
        target = int(depth)
        if max_ctx is not None:
            target = min(target, max(16, max_ctx - 128))
        prompt = _exact_engine_token_prompt(engine, max(16, target), seed=seed + depth)
        for m in out_lens:
            for rep in range(reps):
                result = engine.complete(
                    prompt,
                    max_tokens=m,
                    temperature=0.0,
                    seed=seed + rep,
                    use_cache=False,
                    reset_cache=True,
                )
                t_s = result.t_decode_ms / 1000.0
                rate = (result.tokens_out / t_s) if t_s > 0 else 0.0
                profile.add_observation(
                    kv_depth=result.engine_tokens_in,
                    tokens_out=result.tokens_out,
                    tokens_per_sec=rate,
                )
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = profile.to_dict()
        payload["provisional"] = bool(ident.provisional)
        payload["deployment_id"] = ident.deployment_id
        (out_dir / "decode_profile.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
    return profile


def verify_cache_behavior(
    engine: Engine,
    profile: PrefillProfile,
    *,
    prefix_tokens: int = 512,
    new_tokens: int = 64,
    tol_rel: float = 0.25,
    cold_plausibility: float = 0.25,
    out_dir: Path | None = None,
    seed: int = 0,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Identical-prefix call pair with plausible-cold guard (F2).

    Cold sample = completion with ``cache_prompt=False`` (forced recompute). Slot
    erase is best-effort; many llama-server builds return 501 without
    ``--slot-save-path``, so we do **not** rely on erase for cold timing.

    Warm sample = after a priming ``cache_prompt=True`` call on the same prefix,
    an extended-prefix call with cache enabled.
    """
    implausible_flags: list[str] = []
    diagnosis: list[str] = []
    cold = None
    warm = None
    # Unique nonce so warm priming cannot collide with calibration leftovers.
    nonce = f"ttv2_cache_{seed}_{random.randint(0, 10**9)}"
    prefix_body = _exact_engine_token_prompt(
        engine, prefix_tokens, seed=seed, chat_shaped=False
    )
    assert isinstance(prefix_body, str)
    prefix = nonce + " " + prefix_body
    suffix = _exact_engine_token_prompt(engine, new_tokens, seed=seed + 1, chat_shaped=False)
    assert isinstance(suffix, str)
    second = prefix + " " + suffix

    for attempt in range(max_retries):
        if hasattr(engine, "clear_cache"):
            clear_info = engine.clear_cache(verify=True)  # type: ignore[attr-defined]
        else:
            clear_info = {"acks": ["no_clear_api"]}
        diagnosis.append(f"attempt={attempt} clear={clear_info}")

        # True cold: cache disabled → must recompute full prefill (median of 3).
        cold_samples = []
        for _ in range(3):
            sample = engine.complete(
                prefix,
                max_tokens=1,
                temperature=0.0,
                seed=seed,
                use_cache=False,
                reset_cache=False,
            )
            if not sample.text and sample.tokens_out <= 0:
                raise RuntimeError("cold sample returned empty completion")
            cold_samples.append(sample)
        cold = sorted(cold_samples, key=lambda s: s.t_prefill_ms)[1]  # median by time
        expected_cold = profile.predict_ms(cold.engine_tokens_in, prefer="piecewise")
        if cold.t_prefill_ms < cold_plausibility * expected_cold:
            implausible_flags.append("implausible_cold_sample")
            diagnosis.append(
                f"reject cold {cold.t_prefill_ms:.1f}ms < {cold_plausibility}*f({cold.engine_tokens_in})"
                f"={expected_cold:.1f}ms (cache_prompt=false)"
            )
            nonce = f"ttv2_cache_{seed}_{attempt}_{random.randint(0, 10**9)}"
            prefix = nonce + " " + prefix_body
            second = prefix + " " + suffix
            continue

        # Prime cache, then warm partial on extension.
        engine.complete(
            prefix, max_tokens=1, temperature=0.0, seed=seed, use_cache=True, reset_cache=False
        )
        warm = engine.complete(
            second, max_tokens=1, temperature=0.0, seed=seed, use_cache=True, reset_cache=False
        )
        implausible_flags = []
        break
    else:
        report = {
            "passed": False,
            "implausible_cold_sample": True,
            "implausible_flags": implausible_flags,
            "diagnosis": diagnosis,
            "provisional": bool(engine.identity.provisional),
            "note": "cold path failed plausibility after retries",
        }
        if out_dir is not None:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            (Path(out_dir) / "cache_verification.json").write_text(
                json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
            )
        return report

    assert cold is not None and warm is not None
    if warm.prefix_hit_tokens > warm.engine_tokens_in:
        raise RuntimeError(
            f"prefix_hit_tokens {warm.prefix_hit_tokens} > engine_tokens_in {warm.engine_tokens_in}"
        )

    unhit = max(1, warm.engine_tokens_in - warm.prefix_hit_tokens)
    expected_warm = profile.predict_ms(unhit, prefer="piecewise")
    # Empirical scale from this session's cold (avoids intercept-dominated f(small n) trap).
    expected_warm_emp = cold.t_prefill_ms * (unhit / max(1, cold.engine_tokens_in))
    warm_rel_err = abs(warm.t_prefill_ms - expected_warm) / max(expected_warm, 1e-6)
    warm_rel_err_emp = abs(warm.t_prefill_ms - expected_warm_emp) / max(expected_warm_emp, 1e-6)
    cold_expected = profile.predict_ms(cold.engine_tokens_in, prefer="piecewise")
    cold_rel_err = abs(cold.t_prefill_ms - cold_expected) / max(cold_expected, 1e-6)
    speedup = (warm.t_prefill_ms / cold.t_prefill_ms) if cold.t_prefill_ms > 0 else None

    warm_ok = (
        warm_rel_err <= tol_rel
        or warm_rel_err_emp <= tol_rel
        or (speedup is not None and speedup < 0.25 and warm.t_prefill_ms < 0.4 * cold.t_prefill_ms)
    )
    passed = (
        cold_rel_err <= tol_rel
        and warm_ok
        and (warm.prefix_hit_tokens > 0 or warm.cache_state in ("warm-hit", "warm-partial"))
        and not implausible_flags
        and warm.prefix_hit_tokens <= warm.engine_tokens_in
        and (speedup is None or speedup < 0.5)
    )
    report = {
        "prefix_tokens_requested": prefix_tokens,
        "new_tokens_requested": new_tokens,
        "cold_engine_tokens_in": cold.engine_tokens_in,
        "cold_requested_tokens_in": cold.requested_tokens_in,
        "cold_prefill_ms": cold.t_prefill_ms,
        "cold_expected_ms": cold_expected,
        "cold_rel_err": cold_rel_err,
        "warm_engine_tokens_in": warm.engine_tokens_in,
        "warm_prefill_ms": warm.t_prefill_ms,
        "warm_prefix_hit_tokens": warm.prefix_hit_tokens,
        "warm_cache_state": warm.cache_state,
        "expected_warm_prefill_ms": expected_warm,
        "expected_warm_empirical_ms": expected_warm_emp,
        "warm_rel_err": warm_rel_err,
        "warm_rel_err_empirical": warm_rel_err_emp,
        "warm_over_cold": speedup,
        "passed": passed,
        "tol_rel": tol_rel,
        "cold_plausibility": cold_plausibility,
        "implausible_flags": implausible_flags,
        "diagnosis": diagnosis,
        "provisional": bool(engine.identity.provisional),
        "note": "F2: cold=cache_prompt=false (median of 3); warm=extended after prime",
    }
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cache_verification.json").write_text(
            json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
        )
    return report


def run_network_baseline(
    *,
    endpoint_id: str,
    probe_fn,
    n_probes: int = 100,
    tod_slot: str = "unspecified",
    out_path: Path | None = None,
    provisional: bool = True,
) -> dict[str, Any]:
    """One-command-re-runnable network baseline collector."""
    baseline = NetworkBaseline(endpoint_id=endpoint_id)
    for _ in range(n_probes):
        rtt_ms = float(probe_fn())
        baseline.add_probe(rtt_ms, tod_slot=tod_slot)
    summary = baseline.summary()
    summary["provisional"] = provisional
    summary["tod_slot_this_run"] = tod_slot
    summary["collected_at_unix"] = time.time()
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary
