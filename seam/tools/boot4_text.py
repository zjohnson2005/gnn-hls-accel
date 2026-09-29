"""Exact-token prompt text for the boot-4 warm and decode measurements.

The warm turn-2 strings are distinct and the same token length, so a prefix
cache that hits the shared turn-1 history stops at that history. Nothing here
reads a preregistration or an amendment file.
"""

from __future__ import annotations

from typing import Any

from seam.errors import SeamError

SPAN_NUMERATOR = 63


def decode_span_tok_s(*, t_first_ns: int, t_last_ns: int) -> float:
    """63 gaps between the first generated token and the last."""
    if t_last_ns <= t_first_ns:
        raise SeamError("t_last must be strictly after t_first")
    return SPAN_NUMERATOR / ((t_last_ns - t_first_ns) / 1e9)


def id_count(tokenizer: Any, text: str) -> int:
    """Token count of ``text`` via an OpenVINO GenAI tokenizer."""
    shape = tokenizer.encode(text).input_ids.shape
    return int(shape[-1])


def render_user(tokenizer: Any, content: str) -> str:
    """Chat-template render of one user turn, thinking disabled."""
    return str(
        tokenizer.apply_chat_template(
            [{"role": "user", "content": content}],
            add_generation_prompt=True,
            extra_context={"enable_thinking": False},
        )
    )


def _exact_body(count: Any, target: int, *, prefix: str, unit: str) -> str:
    """Return ``prefix + body`` whose ``count`` is exactly ``target``."""

    def total(body: str) -> int:
        return int(count(prefix + body))

    if total("") > target:
        raise SeamError(f"prefix alone is {total('')} tokens, above the requested {target}")
    # One token per step keeps the upper bound above the true repeat count.
    # count(unit) is not the marginal cost when count renders a chat template.
    low, high = 0, target + 2
    while low < high:
        mid = (low + high + 1) // 2
        if total(unit * mid) <= target:
            low = mid
        else:
            high = mid - 1
    body = unit * low
    pad = " a"
    for _ in range(64):
        current = total(body)
        if current == target:
            return prefix + body
        if current > target:
            raise SeamError(f"overshot while padding to {target}: reached {current}")
        body += pad * (target - current)
    raise SeamError(f"could not construct an exact {target}-token text; stalled at {total(body)}")


def rendered_exact_prompt(tokenizer: Any, target: int, *, unit: str, salt: str) -> str:
    """A fully rendered user prompt that encodes to exactly ``target`` tokens."""
    content = _exact_body(
        lambda text: id_count(tokenizer, render_user(tokenizer, text)),
        target,
        prefix=f"{salt} ",
        unit=unit,
    )
    rendered = render_user(tokenizer, content)
    realized = id_count(tokenizer, rendered)
    if realized != target:
        raise SeamError(f"rendered prompt is {realized} tokens, requested {target}")
    return rendered


def raw_exact_text(tokenizer: Any, target: int, *, unit: str, salt: str) -> str:
    """Text that encodes to exactly ``target`` tokens, with ``salt`` at the front."""
    text = _exact_body(
        lambda body: id_count(tokenizer, body),
        target,
        prefix=f"{salt} ",
        unit=unit,
    )
    realized = id_count(tokenizer, text)
    if realized != target:
        raise SeamError(f"raw text is {realized} tokens, requested {target}")
    return text


def user_content_for_rendered_tokens(tokenizer: Any, target: int, *, unit: str, salt: str) -> str:
    """User-message content whose chat-template render is exactly ``target`` tokens."""
    content = _exact_body(
        lambda text: id_count(tokenizer, render_user(tokenizer, text)),
        target,
        prefix=f"{salt} ",
        unit=unit,
    )
    realized = id_count(tokenizer, render_user(tokenizer, content))
    if realized != target:
        raise SeamError(f"rendered content is {realized} tokens, requested {target}")
    return content
