"""Cache pricing: overstatement RANGE, write premium, Gemini storage rent.

G1. Overstatement is provider-/generation-specific. Never a single number.
G2. Cache WRITE premium (Anthropic 1.25x / 2.0x) belongs in the cost function.
G3. Gemini storage ($/MTok/hour) is explicit residency rent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from censor.anchors import CACHE_TIERS
from censor.prelim_phase1 import _v, load_params, representative_turn


@dataclass(frozen=True)
class CachePrices:
    input_uncached_per_mtok: float
    input_cached_per_mtok: float
    output_per_mtok: float
    cache_write_5m_per_mtok: float | None = None
    cache_write_1h_per_mtok: float | None = None
    storage_per_mtok_per_hour: float | None = None  # Gemini


def overstatement_ratio(
    *,
    total_input_tokens: float,
    output_tokens: float,
    hit_rate: float,
    read_multiplier: float,
    write_multiplier: float | None = None,
    miss_rate_writes: float | None = None,
) -> dict[str, float]:
    """Naive (all-uncached) / cache-aware price.

    Cache-aware = hit*read_mult*base + miss*base [+ miss*write_premium].
    Base cancels; ratio depends only on multipliers and hit rate.
    """
    h = hit_rate
    m = 1.0 - h
    base = 1.0  # normalized
    naive = total_input_tokens * base + output_tokens * 0.0  # output cancels in ratio of input bill
    # For the INPUT bill alone (the overstatement Phase 1 reported):
    aware_read = total_input_tokens * (h * read_multiplier + m * base)
    write_extra = 0.0
    if write_multiplier is not None:
        # Write premium applies to the miss fraction (tokens written into cache).
        wr = miss_rate_writes if miss_rate_writes is not None else m
        # Write is charged as write_mult * base on the written tokens; the read
        # path already counted miss*base for the compute, so the INCREMENTAL
        # write premium is (write_mult - 1) * wr * tokens.
        write_extra = total_input_tokens * wr * (write_multiplier - 1.0)
    aware = aware_read + write_extra
    return {
        "naive_input_cost_norm": naive,
        "aware_input_cost_norm": aware,
        "overstatement_ratio": naive / aware if aware > 0 else float("inf"),
        "read_multiplier": read_multiplier,
        "write_multiplier": write_multiplier or float("nan"),
        "hit_rate": h,
    }


def overstatement_range(
    *,
    hit_rate: float = 0.975,
    include_write_5m: bool = True,
    include_write_1h: bool = True,
) -> list[dict[str, Any]]:
    """G1: overstatement as a RANGE across provider tiers."""
    turn = representative_turn(load_params())
    total_in = turn.total_input_tokens
    out = turn.output_tokens
    rows: list[dict[str, Any]] = []
    for tier in CACHE_TIERS:
        base = overstatement_ratio(
            total_input_tokens=total_in,
            output_tokens=out,
            hit_rate=hit_rate,
            read_multiplier=tier.read_multiplier,
        )
        rows.append({
            "tier": tier.label,
            "read_multiplier": tier.read_multiplier,
            "write_multiplier": None,
            "hit_rate": hit_rate,
            "overstatement_ratio": base["overstatement_ratio"],
            "includes_write_premium": False,
            "source": tier.source,
        })
        if include_write_5m and tier.write_5m_multiplier is not None:
            w = overstatement_ratio(
                total_input_tokens=total_in, output_tokens=out,
                hit_rate=hit_rate, read_multiplier=tier.read_multiplier,
                write_multiplier=tier.write_5m_multiplier,
            )
            rows.append({
                "tier": tier.label,
                "read_multiplier": tier.read_multiplier,
                "write_multiplier": tier.write_5m_multiplier,
                "write_ttl": "5m",
                "hit_rate": hit_rate,
                "overstatement_ratio": w["overstatement_ratio"],
                "includes_write_premium": True,
                "source": tier.source,
            })
        if include_write_1h and tier.write_1h_multiplier is not None:
            w = overstatement_ratio(
                total_input_tokens=total_in, output_tokens=out,
                hit_rate=hit_rate, read_multiplier=tier.read_multiplier,
                write_multiplier=tier.write_1h_multiplier,
            )
            rows.append({
                "tier": tier.label,
                "read_multiplier": tier.read_multiplier,
                "write_multiplier": tier.write_1h_multiplier,
                "write_ttl": "1h",
                "hit_rate": hit_rate,
                "overstatement_ratio": w["overstatement_ratio"],
                "includes_write_premium": True,
                "source": tier.source,
            })
    return rows


def gemini_storage_rent_usd(
    *,
    cached_tokens: float,
    hours: float,
    usd_per_mtok_per_hour: float,
) -> float:
    """G3: explicit residency rent, metered by the hour."""
    return (cached_tokens / 1_000_000.0) * usd_per_mtok_per_hour * hours


def gemini_storage_from_params(hours: float = 1.0) -> dict[str, Any]:
    p = load_params()
    # Prefer an explicit study_params entry; fall back to the published Gemini
    # figure recorded here if the YAML has not yet been extended.
    gem = (p.get("cloud", {}).get("providers", {}).get("google")
           or p.get("cloud", {}).get("providers", {}).get("gemini")
           or {})
    storage_node = None
    for tier in gem.values() if isinstance(gem, dict) else []:
        if isinstance(tier, dict) and "price_cache_storage_per_mtok_per_hour" in tier:
            storage_node = tier["price_cache_storage_per_mtok_per_hour"]
            break
    if storage_node is None:
        # Published Gemini 2.5 context-cache storage (July 2026 secondary sources):
        # $1.00 / MTok / hour is the commonly cited figure; confirm against the
        # live rate card before quoting as a finding. Marked estimated until YAML.
        rate = 1.00
        confidence = "estimated"
        source = (
            "Gemini 2.5+ context-cache storage ~$1.00/MTok/hour "
            "(secondary rate-card summaries; promote to published when pinned "
            "against ai.google.dev pricing)."
        )
    else:
        rate = float(_v(storage_node))
        confidence = storage_node.get("confidence", "published")
        source = storage_node.get("source", "")

    turn = representative_turn(p)
    hit = float(_v(p["workload"]["prefix_cache_hit_rate_tool_result"]))
    cached = turn.total_input_tokens * hit
    rent = gemini_storage_rent_usd(
        cached_tokens=cached, hours=hours, usd_per_mtok_per_hour=rate
    )
    return {
        "cached_tokens": cached,
        "hours": hours,
        "usd_per_mtok_per_hour": rate,
        "storage_rent_usd": rent,
        "confidence": confidence,
        "source": source,
        "framing": (
            "This is residency rent, explicitly metered by the hour — direct "
            "support for the cache-rent framing of Phase 1."
        ),
    }


def t2_with_write_premium(
    *,
    total_input_tokens: float,
    output_tokens: float,
    hit_rate: float,
    price_uncached: float,
    price_cached: float,
    price_output: float,
    price_write: float | None,
) -> dict[str, float]:
    """Cache-aware T2 including optional write premium on the miss fraction."""
    h = hit_rate
    m = 1.0 - h
    cache_read = (total_input_tokens * h / 1e6) * price_cached
    uncached = (total_input_tokens * m / 1e6) * price_uncached
    write = (total_input_tokens * m / 1e6) * price_write if price_write else 0.0
    # When write is charged, the uncached compute and the write are both due on
    # the miss path; some providers subsume write into a single miss price.
    # We treat write as additive on top of uncached (Anthropic's published shape).
    out = (output_tokens / 1e6) * price_output
    naive = (total_input_tokens / 1e6) * price_uncached + out
    aware = cache_read + uncached + write + out
    return {
        "cache_read_usd": cache_read,
        "uncached_prefill_usd": uncached,
        "cache_write_usd": write,
        "output_usd": out,
        "usd_aware": aware,
        "usd_naive": naive,
        "overstatement_ratio": naive / aware if aware > 0 else float("inf"),
        "residency_rent_fraction": cache_read / aware if aware > 0 else float("nan"),
    }
