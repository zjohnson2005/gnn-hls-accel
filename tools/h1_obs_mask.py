"""OBS_MASK retention arm for the H1 agent loops (DEMO-1 V4).

One implementation for the offline sizing tool (tools/h1_context_sizing.py),
the live local session (OpenVinoLocalBackend) and the live cloud agent loop
(bfcl_feasibility_probe.run_cloud_multi_turn_agent_entry), so all three see
the same observation text.

The transform is seam.retention_prompt.mask_observation (docs/RETENTION_PROTOCOL.md):
keep the first K whitespace tokens of each tool observation, add no marker.
Like that function, it rejoins the kept tokens with single spaces, so an
observation shorter than K still has its whitespace collapsed. Tool state is
not changed; only the text the model sees.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from seam.retention_prompt import mask_observation

ARM = "OBS_MASK"


class ObservationMask:
    """Masks observations at K whitespace tokens and records every observation."""

    def __init__(self, k: int, token_count: Callable[[str], int] | None = None) -> None:
        if int(k) < 1:
            raise ValueError(f"obs_mask K must be >= 1, got {k}")
        self.k = int(k)
        self.token_count = token_count
        self.records: list[dict[str, Any]] = []
        self.context: dict[str, Any] = {}

    def apply(
        self,
        calls: Sequence[Any],
        results: Sequence[Any],
        *,
        source: str,
        entry_id: str,
        turn: int | None,
    ) -> list[str]:
        """Masked text for each result, in order. Records original and kept sizes."""
        out: list[str] = []
        for call, result in zip(calls, results, strict=False):
            text = str(result)
            kept = mask_observation(text, self.k)
            record: dict[str, Any] = {
                **self.context,
                "source": source,
                "entry_id": entry_id,
                "turn": turn,
                "call": str(call).split("(", 1)[0],
                "original_ws_tokens": len(text.split()),
                "kept_ws_tokens": len(kept.split()),
                "truncated": len(text.split()) > self.k,
            }
            if self.token_count is not None:
                record["original_tokens"] = int(self.token_count(text))
                record["kept_tokens"] = int(self.token_count(kept))
            self.records.append(record)
            out.append(kept)
        return out

    def plan_record(self) -> dict[str, Any]:
        return {
            "arm": ARM,
            "k": self.k,
            "unit": "whitespace tokens",
            "transform": "seam.retention_prompt.mask_observation",
            "applies_to": ["local session tool observations", "cloud agent tool results"],
        }

    def ledger(self) -> dict[str, Any]:
        truncated = [r for r in self.records if r["truncated"]]
        return {
            **self.plan_record(),
            "n_observations": len(self.records),
            "n_truncated": len(truncated),
            "observations": list(self.records),
        }


def hf_token_count(tokenizer: Any) -> Callable[[str], int]:
    """Token counter for a HF tokenizer (the H1 local tokenizer)."""

    def count(text: str) -> int:
        return len(tokenizer(text)["input_ids"])

    return count


def install_on_session(session: Any, mask: ObservationMask, *, entry_id: str) -> None:
    """Mask the observations a MultiTurnAgentSession appends to its context.

    Wraps the session's BFCL execute function after begin(); run_user_turn
    reads it at the start of every turn.
    """
    execute = session._execute_multi_turn_func_call

    def masked(decoded: list[str], *args: Any, **kwargs: Any) -> Any:
        results, instances = execute(decoded, *args, **kwargs)
        kept = mask.apply(
            decoded,
            results,
            source="local",
            entry_id=entry_id,
            turn=getattr(session, "_next_turn_idx", None),
        )
        return kept, instances

    session._execute_multi_turn_func_call = masked


def cloud_hook(
    mask: ObservationMask, *, entry_id: str
) -> Callable[[list[str], list[Any], int], list[str]]:
    """observation_hook for run_cloud_multi_turn_agent_entry."""

    def hook(decoded: list[str], results: list[Any], turn_idx: int) -> list[str]:
        return mask.apply(decoded, results, source="cloud", entry_id=entry_id, turn=turn_idx)

    return hook
