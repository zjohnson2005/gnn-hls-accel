"""Shared quality-row helpers: raw text persist + degenerate max-burn guard.

Used by Q-KV, Q-8B, and Q-REPRO so investigations are never blocked by dropped
``model_result_raw`` again (third time: b1a291f0 postmortem).
"""

from __future__ import annotations

from typing import Any

from seam.errors import SeamError

# Prefer full text. Truncate only when a single generation string exceeds
# 2 * RAW_HEAD_TAIL_CHARS (head + tail kept, total length recorded).
RAW_HEAD_TAIL_CHARS = 512

# ---------------------------------------------------------------------------
# Degenerate consecutive-cell refuse threshold (derived, not invented).
#
# Evidence: void dual-resident session b1a291f0
#   derived/q8b/q8b_b1a291f0-d7a4-48f3-b4fd-154290a9d5c5/
# Signature: 3 early emission_ok cells, then an unbroken streak of 42 cells
# where every turn burned exactly max_new_tokens=512 with n_decoded_steps=0
# (empty tool-call decode) on BOTH arms. Pipeline-state corruption, not
# ordinary BFCL emission noise (Q-KV failures are short EOS / no tools).
#
# N=3 = refuse after three consecutive degenerate cells (any arm mix):
#   - Exceeds one dual-arm entry pair (2 cells), so a single entry cannot
#     alone trip the guard under per-entry dual-arm scheduling.
#   - Matches the earliest multi-entry streak in b1a291f0
#     (base_1/4B, base_2/4B, base_2/8B) — would have aborted before the
#     remaining ~39 garbage cells (~hours of 512-token burns).
# Recorded twin: derived/q8b/DEGENERATE_GUARD.json
# ---------------------------------------------------------------------------
DEGENERATE_CONSECUTIVE_N = 3
DEGENERATE_CITING_RUN = "b1a291f0"
DEGENERATE_CITING_SESSION = "q8b_b1a291f0-d7a4-48f3-b4fd-154290a9d5c5"


def persist_raw_string(text: str, *, head_tail: int = RAW_HEAD_TAIL_CHARS) -> dict[str, Any]:
    """Persist one generation string; truncate to head+tail when oversized."""
    if not isinstance(text, str):
        text = str(text)
    n = len(text)
    if n <= 2 * head_tail:
        return {"text": text, "truncated": False, "length": n}
    return {
        "text_head": text[:head_tail],
        "text_tail": text[-head_tail:],
        "truncated": True,
        "length": n,
    }


def persist_model_result_raw_per_turn(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Return per-turn raw persistence from a probe entry row.

    Probe shape: ``model_result_raw`` is ``list[list[str]]`` (turn → generation steps).
    """
    raw = row.get("model_result_raw")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for turn_idx, turn in enumerate(raw):
        steps_in = turn if isinstance(turn, list) else [turn]
        steps_out: list[dict[str, Any]] = []
        for step_idx, piece in enumerate(steps_in):
            persisted = persist_raw_string(piece if isinstance(piece, str) else str(piece))
            persisted["step"] = step_idx
            steps_out.append(persisted)
        out.append({"turn": turn_idx, "generations": steps_out})
    return out


def turn_is_degenerate_max_burn(
    tm: dict[str, Any],
    *,
    max_new_tokens: int,
) -> bool:
    """True if this turn hit the generation cap with zero decodable tool steps."""
    if int(tm.get("n_decoded_steps") or 0) > 0:
        return False
    gen = tm.get("generated_tokens")
    if gen is not None and int(gen) >= int(max_new_tokens):
        return True
    # Step-level fallback (probe embeds generated_tokens on steps).
    for sm in tm.get("steps") or []:
        if not isinstance(sm, dict):
            continue
        if sm.get("tool_exec_error"):
            continue
        g = sm.get("generated_tokens")
        if g is not None and int(g) >= int(max_new_tokens):
            return True
    return False


def cell_is_degenerate_max_burn(
    row: dict[str, Any],
    *,
    max_new_tokens: int = 512,
) -> bool:
    """True if any measured turn is a max_new_tokens burn with zero decode."""
    metrics = row.get("turn_metrics") or []
    if not metrics:
        return False
    return any(
        turn_is_degenerate_max_burn(tm, max_new_tokens=max_new_tokens) for tm in metrics
    )


class DegenerateOutputGuard:
    """Flag degenerate cells; SeamError-refuse after N consecutive across arms."""

    def __init__(
        self,
        *,
        n: int = DEGENERATE_CONSECUTIVE_N,
        max_new_tokens: int = 512,
    ) -> None:
        self.n = int(n)
        self.max_new_tokens = int(max_new_tokens)
        self.consecutive = 0
        self.flagged: list[dict[str, Any]] = []
        self._refuse_message: str | None = None

    def observe(
        self,
        row: dict[str, Any],
        *,
        entry_id: str,
        arm_id: str,
    ) -> dict[str, Any]:
        """Record streak; does not raise. Call ``raise_if_refused`` after persist."""
        degenerate = cell_is_degenerate_max_burn(
            row, max_new_tokens=self.max_new_tokens
        )
        rec = {
            "entry_id": entry_id,
            "arm_id": arm_id,
            "degenerate_max_burn": degenerate,
            "consecutive_after": None,
        }
        if degenerate:
            self.consecutive += 1
            rec["consecutive_after"] = self.consecutive
            self.flagged.append(rec)
            if self.consecutive >= self.n:
                self._refuse_message = (
                    "REFUSED -- DEGENERATE_OUTPUT_STREAK "
                    f"n={self.consecutive} threshold={self.n} "
                    f"max_new_tokens={self.max_new_tokens} "
                    f"last_entry={entry_id} last_arm={arm_id} "
                    f"citing={DEGENERATE_CITING_RUN} "
                    "(max_new_tokens burn with zero decodable steps; "
                    "pipeline likely corrupt — not silent retry)"
                )
        else:
            self.consecutive = 0
            rec["consecutive_after"] = 0
            self._refuse_message = None
        return rec

    def raise_if_refused(self) -> None:
        if self._refuse_message:
            raise SeamError(self._refuse_message)
