"""llama.cpp engine via OpenAI-compatible llama-server HTTP API (CPU-safe)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Sequence

from apu_characterization.turntrace_v2.engines import (
    CompletionResult,
    EngineIdentity,
)


# Chat templates known to drop bare ``tool`` roles (TinyLlama chat, etc.).
# Remap is OPT-IN via this allowlist or an explicit constructor flag — never
# applied generically, so P2/P3 models that support tool roles stay honest.
_TOOL_REMAP_MODEL_SUBSTRINGS = ("tinyllama",)


class LlamaCppServerEngine:
    """Talks to llama-server (`--port`) with streaming for TTFT/prefill measurement.

    Works for CPU builds; GPU backends are identical at the API layer so L1*
    cells stay configured-but-dormant until box arrival.
    """

    def __init__(
        self,
        *,
        base_url: str,
        identity: EngineIdentity,
        timeout_s: float = 600.0,
        remap_unsupported_roles: bool | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.identity = identity
        self.timeout_s = timeout_s
        self._clear_acks: list[str] = []
        # None → auto from model_id allowlist; True/False → explicit override.
        self._remap_unsupported_roles_override = remap_unsupported_roles
        self._remap_decision: bool | None = None

    def close(self) -> None:
        return None

    def should_remap_unsupported_roles(self) -> bool:
        """True only for templates known to drop ``tool`` (CPU dry-run TinyLlama).

        P2/P3 OpenAI / tool-capable local models must NOT remap — a silent
        tool→user rewrite would mask real templating bugs in LCP / F3.
        """
        if self._remap_unsupported_roles_override is not None:
            return bool(self._remap_unsupported_roles_override)
        if self._remap_decision is None:
            mid = (self.identity.model_id or "").lower()
            self._remap_decision = any(s in mid for s in _TOOL_REMAP_MODEL_SUBSTRINGS)
        return self._remap_decision

    def health(self) -> dict[str, Any]:
        return self._get_json("/health")

    def props(self) -> dict[str, Any]:
        try:
            return self._get_json("/props")
        except Exception:
            return {}

    def tokenize(self, text: str, *, add_special: bool = False) -> list[int]:
        payload = {"content": text, "add_special": bool(add_special)}
        data = self._post_json("/tokenize", payload)
        tokens = data.get("tokens")
        if isinstance(tokens, list):
            return [int(t) for t in tokens]
        raise RuntimeError("llama-server /tokenize returned no tokens")

    def normalize_messages(self, messages: Sequence[dict[str, str]]) -> list[dict[str, str]]:
        """Optionally map harness roles onto template-supported roles.

        When ``should_remap_unsupported_roles()`` is False (default for
        non-TinyLlama / P2–P3 models), messages pass through unchanged so a
        missing tool-role in the template surfaces as an F3 anomaly rather
        than being silently rewritten.
        """
        if not self.should_remap_unsupported_roles():
            return [{"role": str(m.get("role") or "user"), "content": str(m.get("content") or "")} for m in messages]
        out: list[dict[str, str]] = []
        for m in messages:
            role = str(m.get("role") or "user")
            content = str(m.get("content") or "")
            if role == "tool":
                out.append({"role": "user", "content": f"tool_result: {content}"})
            elif role in ("system", "user", "assistant"):
                out.append({"role": role, "content": content})
            else:
                out.append({"role": "user", "content": f"{role}: {content}"})
        return out

    def apply_chat_template(self, messages: Sequence[dict[str, str]]) -> str:
        """Return the fully templated prompt string the engine would see."""
        messages = self.normalize_messages(messages)
        try:
            data = self._post_json("/apply-template", {"messages": list(messages)})
            for key in ("prompt", "formatted", "content", "result"):
                if data.get(key):
                    return str(data[key])
        except Exception:
            pass
        # Fallback approximation (still better than raw content alone for LCP).
        parts = []
        for m in messages:
            parts.append(f"<|{m.get('role', 'user')}|>\n{m.get('content', '')}")
        parts.append("<|assistant|>\n")
        return "\n".join(parts)

    def tokenize_messages(self, messages: Sequence[dict[str, str]]) -> list[int]:
        templated = self.apply_chat_template(messages)
        try:
            return self.tokenize(templated, add_special=True)
        except Exception:
            return self.tokenize(templated, add_special=False)

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
        if reset_cache:
            self.clear_cache(verify=True)

        if isinstance(prompt, str):
            messages = [{"role": "user", "content": prompt}]
            requested_tokens = len(self.tokenize(prompt, add_special=False))
        else:
            messages = self.normalize_messages(prompt)
            # Requested = sum of content tokenizations (pre-template).
            requested_tokens = 0
            for m in messages:
                requested_tokens += len(self.tokenize(str(m.get("content") or ""), add_special=False))

        engine_token_ids = self.tokenize_messages(messages)
        tokenizer_id = f"llamacpp:{self.identity.model_id}"

        body: dict[str, Any] = {
            "model": self.identity.model_id,
            "messages": messages,  # already normalize_messages'd
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if seed is not None:
            body["seed"] = int(seed)
        body["cache_prompt"] = bool(use_cache)

        t_issue = time.monotonic()
        first_token_t: float | None = None
        last_token_t: float | None = None
        chunks: list[str] = []
        usage: dict[str, Any] = {}
        timings: dict[str, Any] = {}
        finish_reason: str | None = None

        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
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
                    if choice0.get("finish_reason"):
                        finish_reason = str(choice0["finish_reason"])
                    piece = delta.get("content")
                    if piece is not None and piece != "":
                        if first_token_t is None:
                            first_token_t = now
                        chunks.append(str(piece))
                        last_token_t = now
                    elif first_token_t is None and (
                        delta.get("role") is not None or finish_reason
                    ):
                        # Role-only chunk: do not start prefill clock until content or finish.
                        pass
                    if obj.get("usage"):
                        usage = dict(obj["usage"])
                    if obj.get("timings"):
                        timings = dict(obj["timings"])
        except urllib.error.HTTPError as exc:
            body_err = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"llama-server HTTP {exc.code}: {body_err}") from exc

        t_end = time.monotonic()
        # Timer wraps full request lifecycle (send → final byte of stream).
        wall_ms = max(0.0, (t_end - t_issue) * 1000.0)
        if first_token_t is None:
            first_token_t = t_end
        if last_token_t is None:
            last_token_t = first_token_t

        text = "".join(chunks)
        if timings.get("prompt_ms") is not None:
            t_prefill = float(timings["prompt_ms"])
            prefill_method = "direct"
        else:
            t_prefill = max(0.0, (first_token_t - t_issue) * 1000.0)
            prefill_method = "ttft_derived"
        if timings.get("predicted_ms") is not None:
            t_decode = float(timings["predicted_ms"])
        else:
            t_decode = max(0.0, (last_token_t - first_token_t) * 1000.0)

        api_prompt = usage.get("prompt_tokens")
        api_completion = usage.get("completion_tokens")
        engine_tokens = int(api_prompt) if api_prompt is not None else len(engine_token_ids)
        tokens_out = int(api_completion) if api_completion is not None else max(0, len(text.split()))

        notes: list[str] = []
        # Reject empty/error completions as timing samples.
        if max_tokens > 0 and tokens_out <= 0 and not text:
            if finish_reason in ("stop", "length") and api_completion:
                tokens_out = int(api_completion)
            else:
                notes.append("empty_completion")
                raise RuntimeError(
                    f"llama-server returned empty completion (finish_reason={finish_reason!r}); "
                    "not a valid timing sample"
                )

        prefix_hit = 0
        cache_state: str = "disabled"
        if use_cache:
            cached = timings.get("cache_n") or timings.get("prompt_n_cache")
            if cached is not None:
                prefix_hit = int(cached)
                if prefix_hit <= 0:
                    cache_state = "cold"
                elif prefix_hit >= engine_tokens:
                    cache_state = "warm-hit"
                else:
                    cache_state = "warm-partial"
            else:
                cache_state = "cold"

        # Prefer post-call engine count; keep pre-call ids for LCP (same template).
        if api_prompt is not None and abs(int(api_prompt) - len(engine_token_ids)) > 2:
            notes.append("tokenize_vs_usage_delta")

        return CompletionResult(
            text=text,
            engine_tokens_in=engine_tokens,
            tokens_out=max(tokens_out, 1 if max_tokens >= 1 else 0) if text or tokens_out else tokens_out,
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
            tokenizer_id=tokenizer_id,
            requested_tokens_in=int(requested_tokens),
            engine_token_ids=list(engine_token_ids),
            usage_prompt_tokens_api=int(api_prompt) if api_prompt is not None else None,
            usage_completion_tokens_api=int(api_completion) if api_completion is not None else None,
            server_processing_ms=None,
            raw_response={
                "usage": usage,
                "timings": timings,
                "finish_reason": finish_reason,
                "wall_ms": wall_ms,
                "clear_acks": list(self._clear_acks[-3:]),
            },
            audit_notes=notes,
        )

    def clear_cache(self, *, verify: bool = False) -> dict[str, Any]:
        """Erase KV slots. Records acknowledgements for F2 diagnosis.

        When the server was started without ``--slot-save-path``, slot erase
        returns HTTP 501. Remember that and skip further erase storms; cold
        measurement then relies on ``cache_prompt=false`` (see boundary-cases).
        """
        self._clear_acks = []
        if getattr(self, "_slots_unsupported", False):
            self._clear_acks.append("slots_unsupported:skipped")
            return {"acks": list(self._clear_acks), "verify": verify, "skipped": True}
        paths = (
            "/slots/0?action=erase",
            "/slots/1?action=erase",
            "/slots/2?action=erase",
            "/slots/3?action=erase",
        )
        saw_501 = False
        for path in paths:
            try:
                req = urllib.request.Request(
                    self.base_url + path,
                    method="POST",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                    self._clear_acks.append(f"{path}:{resp.status}:{body[:80]}")
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                self._clear_acks.append(f"{path}:err:{exc}")
                if "501" in msg or "not_supported" in msg or "slot-save-path" in msg:
                    saw_501 = True
                    break
        if not saw_501:
            try:
                self._post_json("/slots/0?action=erase", {})
                self._clear_acks.append("/slots/0?action=erase:post_json_ok")
            except Exception as exc:  # noqa: BLE001
                self._clear_acks.append(f"post_json_err:{exc}")
                if "501" in str(exc) or "slot-save-path" in str(exc):
                    saw_501 = True
        if saw_501:
            self._slots_unsupported = True
            self._clear_acks.append("slots_unsupported:latched")
        result = {"acks": list(self._clear_acks), "verify": verify}
        return result

    def _clear_cache(self) -> None:
        self.clear_cache(verify=False)

    def _get_json(self, path: str) -> dict[str, Any]:
        with urllib.request.urlopen(self.base_url + path, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} {path}: {body}") from exc
