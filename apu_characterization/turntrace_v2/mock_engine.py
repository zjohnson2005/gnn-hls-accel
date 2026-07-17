"""Deterministic mock local engine for CI calibration and replay tests."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class MockEngineConfig:
    model_id: str = "synthetic-local"
    quantization: str = "fp16"
    engine: str = "mock"
    engine_version: str = "0.1"
    hardware: str = "ci"
    # f(n) = a n^2 + b n + c  (ms)
    a: float = 1e-8
    b: float = 2e-3
    c: float = 0.5
    decode_tokens_per_sec: float = 50.0


class MockEngine:
    def __init__(self, config: MockEngineConfig | None = None) -> None:
        self.config = config or MockEngineConfig()
        self._prefix_cache: list[str] | None = None

    def prefill_ms(self, n_tokens: int, *, prefix_hit_tokens: int = 0) -> float:
        effective = max(0, int(n_tokens) - int(prefix_hit_tokens))
        n = float(effective)
        cfg = self.config
        return cfg.a * (n**2) + cfg.b * n + cfg.c

    def decode_ms(self, tokens_out: int) -> float:
        rate = self.config.decode_tokens_per_sec
        return 1000.0 * float(tokens_out) / rate if rate > 0 else 0.0

    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 8,
        use_cache: bool = False,
        reset_cache: bool = False,
        output_text: str | None = None,
    ) -> dict[str, Any]:
        if reset_cache:
            self._prefix_cache = None
        tokens = prompt.split()
        prefix_hits = 0
        cache_state = "disabled"
        if use_cache and self._prefix_cache is not None:
            n = min(len(self._prefix_cache), len(tokens))
            while prefix_hits < n and self._prefix_cache[prefix_hits] == tokens[prefix_hits]:
                prefix_hits += 1
            cache_state = "warm-hit" if prefix_hits == len(tokens) else (
                "warm-partial" if prefix_hits > 0 else "cold"
            )
        elif use_cache:
            cache_state = "cold"
        t_prefill = self.prefill_ms(len(tokens), prefix_hit_tokens=prefix_hits)
        text = output_text or ("ok " * max_tokens).strip()
        out_n = len(text.split())
        t_decode = self.decode_ms(out_n)
        # Sleep a tiny amount so wall clocks move in real runs if desired.
        time.sleep(0.0)
        if use_cache:
            self._prefix_cache = tokens
        return {
            "text": text,
            "context_tokens_in": len(tokens),
            "tokens_out": out_n,
            "t_prefill_ms": t_prefill,
            "t_decode_ms": t_decode,
            "cache_state": cache_state,
            "prefix_hit_tokens": prefix_hits,
            "model_id": self.config.model_id,
            "quantization": self.config.quantization,
            "engine": self.config.engine,
            "engine_version": self.config.engine_version,
        }

    def as_model_fn(self, fixed_output: str | None = None):
        def _fn(context: Any, sampling: Mapping[str, Any]) -> str:
            prompt = context if isinstance(context, str) else str(context)
            result = self.complete(
                prompt,
                max_tokens=int(sampling.get("max_tokens") or 8),
                use_cache=False,
                output_text=fixed_output,
            )
            return str(result["text"])

        return _fn
