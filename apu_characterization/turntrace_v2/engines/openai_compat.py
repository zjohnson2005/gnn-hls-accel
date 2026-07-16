"""OpenAI-compatible cloud engine with streaming TTFT derivation."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from apu_characterization.turntrace_v2.engines import CompletionResult, EngineIdentity


PROVIDER_FIELD_NOTES: dict[str, dict[str, Any]] = {
    "openai": {
        "streaming": True,
        "usage_in_stream": "stream_options.include_usage",
        "server_timing_header": "openai-processing-ms (when present)",
        "ttft_method": "ttft_derived = (first_content_chunk_mono - request_sent_mono)*1000 - t_network_ms",
        "error_bars": "quote NetworkBaseline median/P95 residual for the endpoint; do not claim tighter than probe variance",
        "token_counts": "usage.prompt_tokens / usage.completion_tokens; reconcile vs local tokenizer when available",
    },
    "openai_compatible_generic": {
        "streaming": True,
        "usage_in_stream": "vendor-dependent; request stream_options.include_usage when supported",
        "server_timing_header": "rarely present; fall back to calibrated RTT probes for t_network",
        "ttft_method": "ttft_derived with estimated:<probe_median> network subtraction",
        "error_bars": "NetworkBaseline P95 - median as half-width when server timing absent",
        "token_counts": "usage fields if present else local tokenizer; flag token_count_mismatch on discrepancy",
    },
}


class OpenAICompatEngine:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        identity: EngineIdentity,
        provider: str = "openai",
        network_baseline_ms: float = 0.0,
        network_method: str = "estimated:probe_median",
        timeout_s: float = 300.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self.identity = identity
        self.provider = provider
        self.network_baseline_ms = float(network_baseline_ms)
        self.network_method = network_method
        self.timeout_s = timeout_s

    def close(self) -> None:
        return None

    def tokenize(self, text: str) -> list[int]:
        # Cloud APIs rarely expose tokenize; return empty and rely on usage fields.
        return []

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
        del use_cache, reset_cache  # provider-controlled
        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = list(prompt)
        body: dict[str, Any] = {
            "model": self.identity.model_id,
            "messages": messages,
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if seed is not None and self.provider == "openai":
            body["seed"] = int(seed)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        t_issue = time.monotonic()
        first_token_t: float | None = None
        last_token_t: float | None = None
        chunks: list[str] = []
        usage: dict[str, Any] = {}
        server_processing_ms: float | None = None
        notes: list[str] = []

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                header_proc = resp.headers.get("openai-processing-ms") or resp.headers.get(
                    "x-openai-processing-ms"
                )
                if header_proc is not None:
                    try:
                        server_processing_ms = float(header_proc)
                    except ValueError:
                        notes.append("unparseable_server_timing")
                for raw in resp:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    if line == "[DONE]":
                        break
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    now = time.monotonic()
                    choice0 = (obj.get("choices") or [{}])[0]
                    delta = choice0.get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        if first_token_t is None:
                            first_token_t = now
                        chunks.append(str(piece))
                        last_token_t = now
                    if obj.get("usage"):
                        usage = dict(obj["usage"])
        except urllib.error.HTTPError as exc:
            raise RuntimeError(exc.read().decode("utf-8", errors="replace")) from exc

        t_end = time.monotonic()
        if first_token_t is None:
            first_token_t = t_end
        if last_token_t is None:
            last_token_t = first_token_t
        ttft_ms = max(0.0, (first_token_t - t_issue) * 1000.0)
        if server_processing_ms is not None:
            t_network = max(0.0, ttft_ms - server_processing_ms)
            network_method = "measured"
            # Prefer server processing as prefill proxy when present.
            t_prefill = server_processing_ms
            prefill_method = "ttft_derived"
        else:
            t_network = self.network_baseline_ms
            network_method = self.network_method
            t_prefill = max(0.0, ttft_ms - t_network)
            prefill_method = "ttft_derived"
        t_decode = max(0.0, (last_token_t - first_token_t) * 1000.0)
        text = "".join(chunks)
        api_prompt = usage.get("prompt_tokens")
        api_completion = usage.get("completion_tokens")
        context_tokens = int(api_prompt) if api_prompt is not None else len(json.dumps(messages).split())
        tokens_out = int(api_completion) if api_completion is not None else max(1, len(text.split()) or 1)
        if api_prompt is None:
            notes.append("usage_prompt_tokens_missing")

        return CompletionResult(
            text=text,
            engine_tokens_in=context_tokens,
            tokens_out=tokens_out,
            t_prefill_ms=t_prefill,
            t_decode_ms=t_decode,
            t_network_ms=t_network,
            network_method=network_method,
            prefill_method=prefill_method,
            cache_state="disabled",
            prefix_hit_tokens=0,
            model_id=self.identity.model_id,
            quantization=self.identity.quantization,
            engine=self.identity.engine,
            engine_version=self.identity.engine_version,
            reasoning_mode=self.identity.reasoning_mode,
            tokenizer_id=f"api_usage:{self.provider}",
            requested_tokens_in=context_tokens,
            engine_token_ids=[],
            usage_prompt_tokens_api=int(api_prompt) if api_prompt is not None else None,
            usage_completion_tokens_api=int(api_completion) if api_completion is not None else None,
            server_processing_ms=server_processing_ms,
            raw_response={"usage": usage, "provider_notes": PROVIDER_FIELD_NOTES.get(self.provider, {})},
            audit_notes=notes,
        )
