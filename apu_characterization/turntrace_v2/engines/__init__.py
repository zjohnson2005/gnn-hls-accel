"""Engine backends for TurnTrace v2 (CPU llama.cpp + OpenAI-compatible cloud)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Sequence


CacheState = Literal["cold", "warm-hit", "warm-partial", "disabled"]


@dataclass
class CompletionResult:
    text: str
    engine_tokens_in: int
    tokens_out: int
    t_prefill_ms: float
    t_decode_ms: float
    t_network_ms: float
    network_method: str
    prefill_method: str
    cache_state: CacheState
    prefix_hit_tokens: int
    model_id: str
    quantization: str
    engine: str
    engine_version: str
    reasoning_mode: str
    tokenizer_id: str
    requested_tokens_in: int = 0
    engine_token_ids: list[int] = field(default_factory=list)
    usage_prompt_tokens_api: int | None = None
    usage_completion_tokens_api: int | None = None
    server_processing_ms: float | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
    audit_notes: list[str] = field(default_factory=list)

    @property
    def context_tokens_in(self) -> int:
        """Alias of engine_tokens_in (F3: single currency for attribution)."""
        return self.engine_tokens_in

    @property
    def token_reconciliation_delta(self) -> int:
        return int(self.engine_tokens_in) - int(self.requested_tokens_in)


@dataclass(frozen=True)
class EngineIdentity:
    deployment_id: str
    model_id: str
    quantization: str
    engine: str
    engine_version: str
    hardware: str
    reasoning_mode: str
    provisional: bool = False


class Engine(Protocol):
    identity: EngineIdentity

    def complete(
        self,
        prompt: str | list[dict[str, str]],
        *,
        max_tokens: int = 1,
        temperature: float = 0.0,
        seed: int | None = 0,
        use_cache: bool = False,
        reset_cache: bool = False,
    ) -> CompletionResult: ...

    def tokenize(self, text: str) -> list[int]: ...

    def tokenize_messages(self, messages: Sequence[dict[str, str]]) -> list[int]: ...

    def close(self) -> None: ...
