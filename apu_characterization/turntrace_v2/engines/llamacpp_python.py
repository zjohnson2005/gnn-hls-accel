"""In-process llama.cpp engine via llama-cpp-python (CPU dry-run path)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from apu_characterization.turntrace_v2.engines import CompletionResult, EngineIdentity


class LlamaCppPythonEngine:
    """CPU-safe local engine using llama-cpp-python bindings.

    Prefer this for P1 when llama-server binaries are unavailable. Records
    llama.cpp timings from the binding when present.
    """

    def __init__(
        self,
        *,
        model_path: str | Path,
        identity: EngineIdentity,
        n_ctx: int = 8192,
        n_threads: int | None = None,
        verbose: bool = False,
    ) -> None:
        from llama_cpp import Llama

        self.identity = identity
        self.model_path = str(model_path)
        kwargs: dict[str, Any] = {
            "model_path": self.model_path,
            "n_ctx": int(n_ctx),
            "verbose": verbose,
            "logits_all": False,
        }
        if n_threads is not None:
            kwargs["n_threads"] = int(n_threads)
        self._llm = Llama(**kwargs)
        self._last_prompt_tokens: list[int] = []

    def close(self) -> None:
        # llama-cpp-python frees on GC; explicit reset if available.
        self._llm = None  # type: ignore[assignment]

    def tokenize(self, text: str) -> list[int]:
        assert self._llm is not None
        return list(self._llm.tokenize(text.encode("utf-8"), add_bos=True))

    def complete(
        self,
        prompt: str | list[dict[str, str]],
        *,
        max_tokens: int = 1,
        temperature: float = 0.0,
        seed: int | None = 0,
        use_cache: bool = False,
        reset_cache: bool = False,
    ) -> CompletionResult:
        assert self._llm is not None
        if isinstance(prompt, list):
            # Flatten chat to a simple prompt for dry-run determinism.
            text = "\n".join(f"{m['role']}: {m['content']}" for m in prompt)
        else:
            text = prompt

        if reset_cache or not use_cache:
            # Reset KV by creating a fresh eval state via empty reset if supported.
            try:
                self._llm.reset()
            except Exception:
                pass
            self._last_prompt_tokens = []

        token_ids = self.tokenize(text)
        prefix_hit = 0
        cache_state = "disabled"
        if use_cache and self._last_prompt_tokens:
            n = min(len(self._last_prompt_tokens), len(token_ids))
            while prefix_hit < n and self._last_prompt_tokens[prefix_hit] == token_ids[prefix_hit]:
                prefix_hit += 1
            if prefix_hit <= 0:
                cache_state = "cold"
            elif prefix_hit >= len(token_ids):
                cache_state = "warm-hit"
            else:
                cache_state = "warm-partial"

        t0 = time.monotonic()
        kwargs: dict[str, Any] = {
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
        }
        if seed is not None:
            kwargs["seed"] = int(seed)
        # llama-cpp-python chat vs completion
        out = self._llm.create_completion(prompt=text, **kwargs)
        t1 = time.monotonic()

        choice = (out.get("choices") or [{}])[0]
        gen_text = str(choice.get("text") or "")
        usage = out.get("usage") or {}
        timings = out.get("timings") or {}

        if timings.get("prompt_ms") is not None:
            t_prefill = float(timings["prompt_ms"])
            prefill_method = "direct"
        else:
            # Approximate: attribute most of the wait before generation to prefill for 1-token outs.
            wall_ms = (t1 - t0) * 1000.0
            t_prefill = wall_ms * 0.85
            prefill_method = "ttft_derived"
        if timings.get("predicted_ms") is not None:
            t_decode = float(timings["predicted_ms"])
        else:
            wall_ms = (t1 - t0) * 1000.0
            t_decode = max(0.0, wall_ms - t_prefill)

        context_tokens = int(usage.get("prompt_tokens") or len(token_ids))
        tokens_out = int(usage.get("completion_tokens") or max(1, len(gen_text.split()) or 1))
        if use_cache:
            cached = timings.get("cache_n")
            if cached is not None:
                prefix_hit = int(cached)
        if use_cache:
            self._last_prompt_tokens = token_ids
        else:
            self._last_prompt_tokens = []

        return CompletionResult(
            text=gen_text,
            engine_tokens_in=context_tokens,
            tokens_out=tokens_out,
            t_prefill_ms=t_prefill,
            t_decode_ms=t_decode,
            t_network_ms=0.0,
            network_method="measured",
            prefill_method=prefill_method,
            cache_state=cache_state,  # type: ignore[arg-type]
            prefix_hit_tokens=prefix_hit,
            model_id=self.identity.model_id,
            quantization=self.identity.quantization,
            engine=self.identity.engine,
            engine_version=self.identity.engine_version,
            reasoning_mode=self.identity.reasoning_mode,
            tokenizer_id=f"llamacpp-python:{self.identity.model_id}",
            requested_tokens_in=len(token_ids),
            engine_token_ids=list(token_ids),
            usage_prompt_tokens_api=int(usage["prompt_tokens"]) if "prompt_tokens" in usage else None,
            usage_completion_tokens_api=int(usage["completion_tokens"])
            if "completion_tokens" in usage
            else None,
            server_processing_ms=None,
            raw_response={"usage": usage, "timings": timings},
            audit_notes=[],
        )
