"""DEMO-2 --context-window check (design of 2026-10-14).

Made before each local generate. Kept in its own module so the BFCL probe
and the H1 runner share one rule without importing each other.
"""

from __future__ import annotations

from typing import Any


def context_overflow(
    gen_input_tokens: int, *, max_new_tokens: int, window: int | None, step: int
) -> dict[str, Any] | None:
    """Overflow when the generate input plus max_new_tokens exceeds the window.

    None when the window is off or the step fits.
    """
    if window is None:
        return None
    if int(gen_input_tokens) + int(max_new_tokens) <= int(window):
        return None
    return {
        "n_ctx": int(gen_input_tokens),
        "window": int(window),
        "max_new_tokens": int(max_new_tokens),
        "step": int(step),
    }
