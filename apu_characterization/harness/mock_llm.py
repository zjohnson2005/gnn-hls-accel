"""Mock in-process LLM with seeded lognormal sleep (models I/O wait)."""

from __future__ import annotations

import asyncio
import json
import math
import random
from typing import Any

from ..instr import timed
from ..taxonomy import Category
from .synth_text import make_text


def _lognormal_seconds(rng: random.Random, median: float, sigma: float) -> float:
    # median = exp(mu) for lognormal
    mu = math.log(max(median, 1e-6))
    return rng.lognormvariate(mu, sigma)


_encoder: Any = None
_encoder_tried = False


def _get_encoder() -> Any:
    """Load tiktoken once at module level; first get_encoding may hit the
    network for the BPE file, which must not be charged to TOKENIZATION."""
    global _encoder, _encoder_tried
    if not _encoder_tried:
        _encoder_tried = True
        try:
            import tiktoken

            _encoder = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _encoder = None
    return _encoder


def _count_tokens(text: str) -> int:
    enc = _get_encoder()
    if enc is not None:
        return len(enc.encode(text))
    return max(1, len(text) // 4)


async def mock_llm_call(
    messages: list[dict[str, Any]],
    rng: random.Random,
    median_s: float,
    sigma: float,
    response_bytes: int,
    session_id: str,
) -> dict[str, Any]:
    """Sleep for latency (zero thread CPU), return synthetic tool-call or finish JSON."""
    latency = _lognormal_seconds(rng, median_s, sigma)

    with timed(Category.PROMPT_ASSEMBLY, session_id, bytes_out=sum(len(str(m)) for m in messages)):
        prompt_text = json.dumps(messages)

    with timed(Category.TOKENIZATION, session_id, bytes_in=len(prompt_text)):
        _ = _count_tokens(prompt_text)

    # I/O wait: asyncio sleep costs no thread CPU
    await asyncio.sleep(latency)

    body = make_text(rng, max(64, response_bytes))

    # Response-side token count (context-window bookkeeping) is TOKENIZATION
    # work; leaving it untimed would leak into residual.
    with timed(Category.TOKENIZATION, session_id, bytes_in=len(body)):
        response_tokens = _count_tokens(body)

    response = {"role": "assistant", "content": body, "tokens": response_tokens}

    with timed(Category.SERIALIZATION, session_id, bytes_out=response_bytes):
        raw = json.dumps(response)

    with timed(Category.SERIALIZATION, session_id, bytes_in=len(raw)):
        parsed = json.loads(raw)

    return parsed
