"""Per-request cloud accounting and the cross-arm cost invariant.

d482c621 did not send cache_control. The default caching policy is ``none``,
which leaves the Anthropic request without cache_control.
"""

from __future__ import annotations

import os
import re
from typing import Any

CACHING_POLICIES = ("none", "ephemeral")
# Sealed run d482c621-4292-4281-b6a1-8635e5eeb6da: harness set no cache_control.
DEFAULT_CACHING_POLICY = "none"
TOKEN_COUNT_METHOD = "char_proportional_split_of_input_tokens"

# Anything that looks like an API key or a bearer token is replaced before an
# error string is written to disk. The key itself is never read into a record.
_KEY_LIKE = re.compile(
    r"(sk-ant-[A-Za-z0-9_\-]+|sk-[A-Za-z0-9_\-]{16,}|Bearer\s+[A-Za-z0-9._\-]+"
    r"|x-api-key['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9._\-]+)",
    re.IGNORECASE,
)


def redact_secrets(text: str | None) -> str | None:
    """Mask key-like substrings, and the live ANTHROPIC_API_KEY value if present."""
    if text is None:
        return None
    out = str(text)
    key = os.environ.get("ANTHROPIC_API_KEY") or ""
    if len(key) >= 8:
        out = out.replace(key, "[REDACTED]")
    return _KEY_LIKE.sub("[REDACTED]", out)


def exception_fields(exc: BaseException) -> dict[str, Any]:
    """Error class, HTTP status and request id of an SDK exception, redacted.

    anthropic.APIStatusError carries status_code and request_id; connection
    and timeout errors carry neither. Headers are never copied.
    """
    status = getattr(exc, "status_code", None)
    request_id = getattr(exc, "request_id", None)
    return {
        "error_class": type(exc).__name__,
        "http_status": status if isinstance(status, int) else None,
        "request_id": request_id if isinstance(request_id, str) else None,
        "error_message": redact_secrets(str(exc)),
    }


def apply_caching_policy(kwargs: dict[str, Any], policy: str) -> dict[str, Any]:
    """Return request kwargs. ``none`` does not add cache_control."""
    if policy not in CACHING_POLICIES:
        raise ValueError(f"unknown caching_policy {policy!r}")
    if policy == "none":
        return dict(kwargs)
    out = dict(kwargs)
    tools = list(out.get("tools") or [])
    if tools:
        last = dict(tools[-1])
        last["cache_control"] = {"type": "ephemeral"}
        tools[-1] = last
        out["tools"] = tools
    messages = list(out.get("messages") or [])
    if messages:
        msg = dict(messages[-1])
        content = msg.get("content")
        if isinstance(content, list) and content:
            blocks = list(content)
            block = dict(blocks[-1])
            block["cache_control"] = {"type": "ephemeral"}
            blocks[-1] = block
            msg["content"] = blocks
            messages[-1] = msg
            out["messages"] = messages
    return out


def split_input_tokens(
    total_input: int,
    *,
    system: str,
    tools: str,
    history: str,
    new: str,
) -> dict[str, int]:
    """Split billed input tokens across request components. Parts sum to total_input."""
    parts = {
        "system_tokens": system,
        "tool_schema_tokens": tools,
        "history_tokens": history,
        "new_tokens": new,
    }
    lengths = {name: len(text) for name, text in parts.items()}
    total_chars = sum(lengths.values())
    if total_input < 0:
        raise ValueError("total_input must be >= 0")
    if total_chars == 0 or total_input == 0:
        return dict.fromkeys(parts, 0)
    raw = {name: total_input * length / total_chars for name, length in lengths.items()}
    floors = {name: int(value) for name, value in raw.items()}
    remainder = total_input - sum(floors.values())
    order = sorted(parts, key=lambda name: (raw[name] - floors[name], name), reverse=True)
    for name in order[:remainder]:
        floors[name] += 1
    return floors


def cloud_request_record(
    *,
    model: str,
    turn: int,
    request_index_within_turn: int,
    ok: bool,
    system: str,
    tools: str,
    history: str,
    new: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_creation_input_tokens: int | None,
    cache_read_input_tokens: int | None,
    error: str | None = None,
) -> dict[str, Any]:
    """One Anthropic request. Cache fields stay None when the API did not send them."""
    if input_tokens is None:
        split = {
            "system_tokens": None,
            "tool_schema_tokens": None,
            "history_tokens": None,
            "new_tokens": None,
        }
        method = None
    else:
        split = split_input_tokens(
            input_tokens, system=system, tools=tools, history=history, new=new
        )
        method = TOKEN_COUNT_METHOD
    return {
        "model": model,
        "turn": turn,
        "request_index_within_turn": request_index_within_turn,
        "ok": ok,
        "error": error,
        "token_count_method": method,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
        **split,
    }


def usage_field(usage: Any, name: str) -> int | None:
    """Read one usage attribute. Missing attribute is None, not zero."""
    if usage is None or not hasattr(usage, name):
        return None
    value = getattr(usage, name)
    if value is None:
        return None
    return int(value)


def cloud_usd_nondecreasing(
    arms: list[dict[str, Any]],
    *,
    tol_usd: float = 1e-9,
) -> dict[str, Any]:
    """Cloud USD must be non-decreasing in cloud-served turns across arms on one entry.

    ``arms`` rows need entry_id, n_cloud_turns, cloud_usd.
    When n_i < n_j, usd_i <= usd_j. Equal turn counts are not compared.
    """
    by_entry: dict[str, list[dict[str, Any]]] = {}
    for row in arms:
        by_entry.setdefault(str(row["entry_id"]), []).append(row)
    violations: list[dict[str, Any]] = []
    for entry_id, rows in by_entry.items():
        ordered = sorted(rows, key=lambda r: (int(r["n_cloud_turns"]), str(r.get("policy", ""))))
        for i, left in enumerate(ordered):
            for right in ordered[i + 1 :]:
                n_left = int(left["n_cloud_turns"])
                n_right = int(right["n_cloud_turns"])
                if n_left >= n_right:
                    continue
                usd_left = float(left["cloud_usd"])
                usd_right = float(right["cloud_usd"])
                if usd_left > usd_right + tol_usd:
                    violations.append(
                        {
                            "entry_id": entry_id,
                            "left_policy": left.get("policy"),
                            "right_policy": right.get("policy"),
                            "left_n_cloud_turns": n_left,
                            "right_n_cloud_turns": n_right,
                            "left_cloud_usd": usd_left,
                            "right_cloud_usd": usd_right,
                        }
                    )
    return {
        "status": "FAIL" if violations else "PASS",
        "n_violations": len(violations),
        "violations": violations,
    }


# ---------------------------------------------------------------------------
# Cache-aware price (docs/amendments/DEMO2_PREFREEZE_2026-10-22.md section 1, Task BF0 X2)
# ---------------------------------------------------------------------------
PRICE_FORMULA_ID = (
    "PREFREEZE-2026-10-22-s1: input*p_in + cache_write*1.25*p_in + cache_read*0.10*p_in "
    "+ output*p_out (seam.budget.usd_cost, 5m write rate)"
)
PRICE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


class CloudPriceRefused(SystemExit):
    """A billed request record that cannot be priced (missing usage fields)."""


def load_price_table(path: Any = None) -> Any:
    from pathlib import Path

    from seam.budget import PricingTable

    p = (
        Path(path)
        if path is not None
        else (Path(__file__).resolve().parents[1] / "configs" / "pricing" / "anthropic.yaml")
    )
    return PricingTable.load(p)


def price_request(rec: dict[str, Any], *, table: Any, when: Any, model: str | None = None) -> float:
    """USD of one cloud request record; ok False costs 0; a billed record missing a field refuses."""
    from seam.budget import CallUsage, usd_cost

    if rec.get("ok") is False:
        return 0.0
    missing = [k for k in PRICE_FIELDS if rec.get(k) is None]
    if missing:
        raise CloudPriceRefused(
            f"REFUSED -- cloud request (turn {rec.get('turn')}, request "
            f"{rec.get('request_index_within_turn', rec.get('step'))}) lacks {missing}; "
            "a billed request is never priced as zero"
        )
    m = str(rec.get("model") or model or "")
    tier = table.tier_for(m, when)
    if (
        abs(tier.cache_write_5m_per_mtok - 1.25 * tier.input_per_mtok) > 1e-9
        or abs(tier.cache_read_per_mtok - 0.10 * tier.input_per_mtok) > 1e-9
    ):
        raise CloudPriceRefused(
            f"REFUSED -- price tier {tier.label} for {m} does not match the registered "
            "multipliers (write 1.25x, read 0.10x)"
        )
    return usd_cost(
        CallUsage(
            input_tokens=int(rec["input_tokens"]),
            output_tokens=int(rec["output_tokens"]),
            cache_read_input_tokens=int(rec["cache_read_input_tokens"]),
            cache_creation_input_tokens=int(rec["cache_creation_input_tokens"]),
            cache_write_ttl="5m",
        ),
        tier,
    )


def price_requests(
    recs: list[dict[str, Any]], *, table: Any, when: Any, model: str | None = None
) -> float:
    return sum(price_request(r, table=table, when=when, model=model) for r in recs)
