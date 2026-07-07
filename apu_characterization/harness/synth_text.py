"""Seeded realistic-ish text generation for synthetic payloads.

BPE tokenizers behave pathologically on single repeated characters, so
padding and mock LLM responses must be word-like text for TOKENIZATION
and SERIALIZATION costs to be honest. Generation happens outside timed
regions; only the downstream encode/parse work is measured.
"""

from __future__ import annotations

import random

_VOCAB = (
    "the a an of to in for with on at from by about into over after under "
    "plan step result value item note detail section report summary answer "
    "garden weather train recipe budget schedule market travel history "
    "water energy light sound money paper glass stone metal cloth "
    "quickly slowly carefully often rarely together apart around between "
    "first second third final next previous large small early late"
).split()


def make_text(rng: random.Random, nbytes: int) -> str:
    """Return word text of at least nbytes (within one word of the target)."""
    if nbytes <= 0:
        return ""
    parts: list[str] = []
    size = 0
    while size < nbytes:
        w = _VOCAB[rng.randrange(len(_VOCAB))]
        parts.append(w)
        size += len(w) + 1
    return " ".join(parts)
