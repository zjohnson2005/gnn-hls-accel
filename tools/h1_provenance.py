"""Fields every H1 plan and seal must carry. No model calls."""

from __future__ import annotations

import hashlib
from typing import Any

CHAT_TEMPLATE_RENDERER = "tools.bfcl_feasibility_probe.render_bfcl_tools_style"
# CB prefix blocks survive pipe.finish_chat(). A new pipeline is the clear.
PREFIX_BLOCK_CLEAR_CALL = "ov_genai.LLMPipeline"
TTFT_COLD_FRACTION = 0.40
PROJECTION_MIN_ENTRIES = 20
DEFAULT_ARM_ORDER_SEED = 0


def resolved_cloud_model(cloud: Any) -> str:
    """API model id actually passed to messages.create, not the short ARM_CONFIG label."""
    got = getattr(cloud, "cloud_model", None) if cloud is not None else None
    if isinstance(got, str) and got.strip():
        return got.strip()
    from tools.bfcl_feasibility_probe import CLOUD_DEFAULT_MODEL

    return CLOUD_DEFAULT_MODEL


def provenance_block(cloud: Any, local: Any = None) -> dict[str, Any]:
    max_new = 512
    do_sample = False
    apply_chat = False
    cfg = getattr(local, "cfg", None) if local is not None else None
    if cfg is not None:
        max_new = int(getattr(cfg, "max_new_tokens", max_new))
        do_sample = bool(getattr(cfg, "do_sample", False))
        apply_chat = bool(getattr(cfg, "apply_chat_template", False))
    elif local is not None and getattr(local, "max_new_tokens", None) is not None:
        max_new = int(local.max_new_tokens)
    return {
        "cloud_model": resolved_cloud_model(cloud),
        "chat_template": {
            "enable_thinking": False,
            "renderer": CHAT_TEMPLATE_RENDERER,
        },
        "generation_config": {
            "max_new_tokens": max_new,
            "do_sample": do_sample,
            "apply_chat_template": apply_chat,
            "temperature": None,
            "top_p": None,
            "top_k": None,
            "seed": None,
        },
    }


def latin_square_order(
    policies: tuple[str, ...] | list[str],
    entry_id: str,
    *,
    seed: int = DEFAULT_ARM_ORDER_SEED,
) -> list[str]:
    """One row of a Latin square. Row index is sha256(f"{seed}:{entry_id}") mod n."""
    symbols = list(policies)
    n = len(symbols)
    if n == 0:
        return []
    digest = hashlib.sha256(f"{int(seed)}:{entry_id}".encode()).digest()
    row = int.from_bytes(digest[:8], "big") % n
    return [symbols[(row + col) % n] for col in range(n)]


def entry_turn0_local_ttft(rows: list[dict[str, Any]], entry_id: str) -> float | None:
    """First local turn-0 TTFT recorded for this entry, if the ledger has one."""
    for row in rows:
        if str(row.get("entry_id")) != str(entry_id):
            continue
        for turn in row.get("turns") or []:
            if int(turn.get("turn", -1)) != 0:
                continue
            if turn.get("placement") != "local":
                continue
            if turn.get("ttft_s") is None:
                continue
            return float(turn["ttft_s"])
    return None


def prefix_cache_control_failure(
    arms: list[tuple[str, float | None]],
    *,
    fraction: float = TTFT_COLD_FRACTION,
) -> dict[str, Any] | None:
    """Fail when a later local turn-0 TTFT is below ``fraction`` times the first.

    The reference is the first arm in this entry's order that has a local
    turn-0 TTFT. Arms with no local turn-0 are skipped. None means the
    control passed or there was no pair to compare.
    """
    present = [(policy, ttft) for policy, ttft in arms if ttft is not None]
    if len(present) < 2:
        return None
    ref_policy, ref = present[0]
    below = [
        {"policy": policy, "ttft_s": ttft}
        for policy, ttft in present[1:]
        if ttft < fraction * ref
    ]
    if not below:
        return None
    return {
        "reference_policy": ref_policy,
        "reference_ttft_s": ref,
        "fraction": fraction,
        "below": below,
        "arms": [{"policy": policy, "ttft_s": ttft} for policy, ttft in present],
    }


def project_session_cost(
    *,
    running_usd: float,
    n_done: int,
    n_planned: int,
    min_entries: int = PROJECTION_MIN_ENTRIES,
) -> float | None:
    """Linear projection of the session total after ``min_entries`` completed entries.

    None before the guard arms, and once every planned entry has already run.
    """
    if n_done < int(min_entries) or n_done <= 0 or n_planned <= 0:
        return None
    if n_done >= n_planned:
        return None
    return float(running_usd) * float(n_planned) / float(n_done)


def stamp_seal(seal_doc: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    for key in ("cloud_model", "chat_template", "generation_config"):
        if key in plan:
            seal_doc[key] = plan[key]
    return seal_doc
