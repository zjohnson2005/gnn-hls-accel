"""Token counts for the cited BFCL workload figures.

Counts prompts with the Qwen3 tokenizer and the BFCL multi-turn renderer.
Does not load a model and does not call generate.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.bfcl_feasibility_probe import (  # noqa: E402
    BFCL_DATA,
    MODEL_DIR,
    _load_multi_turn_tools,
    render_bfcl_tools_style,
    select_multi_turn_entries,
)

CITED_WORKLOAD_MAX_TOKENS = 7743
CITED_SCHEMA_TOKENS = 2598
OUT_PATH = ROOT / "derived" / "dataset" / "BFCL_TOKEN_COUNTS.json"
D482_RUN_ID = "d482c621-4292-4281-b6a1-8635e5eeb6da"
D482_SEAL = ROOT / "derived" / "h1_hybrid" / f"interleaved_{D482_RUN_ID}"

TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "chat_template.jinja",
    "special_tokens_map.json",
    "added_tokens.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _count(tokenizer: Any, text: str) -> int:
    return len(tokenizer(text)["input_ids"])


def observed_local_n_ctx(seal: Path) -> dict[str, Any]:
    """Max n_ctx on turns whose placement is local, across every policy ledger."""
    best: int | None = None
    where: dict[str, Any] | None = None
    n_local = 0
    policies = sorted((seal / "policies").glob("*/turn_ledger.json"))
    for ledger in policies:
        doc = json.loads(ledger.read_text(encoding="utf-8"))
        for entry in doc.get("entries") or []:
            for turn in entry.get("turns") or []:
                if turn.get("placement") != "local":
                    continue
                raw = turn.get("n_ctx")
                if raw is None:
                    continue
                n_local += 1
                value = int(raw)
                if best is None or value > best:
                    best = value
                    where = {
                        "policy": ledger.parent.name,
                        "entry_id": entry.get("entry_id"),
                        "turn": turn.get("turn"),
                    }
    return {
        "run_id": D482_RUN_ID,
        "n_ctx": best,
        "n_local_turns": n_local,
        "where": where,
    }


def main() -> int:
    from transformers import AutoTokenizer

    entries = select_multi_turn_entries()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    hashed: list[dict[str, str]] = []
    for name in TOKENIZER_FILES:
        path = MODEL_DIR / name
        if path.is_file():
            hashed.append({"path": path.relative_to(ROOT).as_posix(), "sha256": _sha256(path)})
    data_file = BFCL_DATA / "BFCL_v4_multi_turn_base.json"
    hashed.append({"path": data_file.relative_to(ROOT).as_posix(), "sha256": _sha256(data_file)})
    doc_dir = BFCL_DATA / "multi_turn_func_doc"
    for path in sorted(doc_dir.glob("*.json")):
        hashed.append({"path": path.relative_to(ROOT).as_posix(), "sha256": _sha256(path)})

    per_entry: list[dict[str, Any]] = []
    for entry in entries:
        tools = _load_multi_turn_tools(entry["raw_entry"])
        turn0 = [dict(m) for m in entry["question"][0] if isinstance(m, dict)]
        with_tools = render_bfcl_tools_style(tokenizer, turn0, tools)
        without_tools = render_bfcl_tools_style(tokenizer, turn0, [])
        n_with = _count(tokenizer, with_tools)
        n_without = _count(tokenizer, without_tools)
        user_only_messages: list[dict[str, Any]] = []
        user_only_max = 0
        for turn in entry["question"]:
            user_only_messages.extend(dict(m) for m in turn if isinstance(m, dict))
            user_only_max = max(
                user_only_max,
                _count(
                    tokenizer,
                    render_bfcl_tools_style(tokenizer, user_only_messages, tools),
                ),
            )
        per_entry.append(
            {
                "id": entry["id"],
                "turn0_prompt_tokens": n_with,
                "turn0_without_tools_tokens": n_without,
                "turn0_tools_delta_tokens": n_with - n_without,
                "user_turns_only_max_tokens": user_only_max,
                "n_tools": len(tools),
            }
        )

    turn0_values = [row["turn0_prompt_tokens"] for row in per_entry]
    user_only_values = [row["user_turns_only_max_tokens"] for row in per_entry]
    by_id = {row["id"]: row for row in per_entry}
    entry_10 = by_id.get("multi_turn_base_10")
    entry_2 = by_id.get("multi_turn_base_2")
    workload_max = max(user_only_values)
    schema_tokens = entry_10["turn0_prompt_tokens"] if entry_10 else min(turn0_values)
    observed = observed_local_n_ctx(D482_SEAL)

    doc = {
        "method": (
            "HF AutoTokenizer on models/Qwen3-4B-int4-ov, "
            "render_bfcl_tools_style, BFCL_v4_multi_turn_base first 200 entries. "
            "No generate call. workload_max is the longest user-turn stack plus "
            "the tool schema. It does not include model-written mid-turn steps."
        ),
        "cited": {
            "workload_max_tokens": CITED_WORKLOAD_MAX_TOKENS,
            "bfcl_tool_schema_tokens": CITED_SCHEMA_TOKENS,
        },
        "workload_max_tokens": workload_max,
        "workload_max_tokens_dataset": workload_max,
        "workload_max_tokens_observed": observed,
        "bfcl_tool_schema_tokens": schema_tokens,
        "turn0_prompt_tokens": {
            "min": min(turn0_values),
            "max": max(turn0_values),
            "n": len(turn0_values),
        },
        "multi_turn_base_10_turn0_prompt_tokens": (
            None if entry_10 is None else entry_10["turn0_prompt_tokens"]
        ),
        "multi_turn_base_10_tools_delta_tokens": (
            None if entry_10 is None else entry_10["turn0_tools_delta_tokens"]
        ),
        "multi_turn_base_2_turn0_prompt_tokens": (
            None if entry_2 is None else entry_2["turn0_prompt_tokens"]
        ),
        "multi_turn_base_2_user_turns_only_max_tokens": (
            None if entry_2 is None else entry_2["user_turns_only_max_tokens"]
        ),
        "mismatch_vs_cited": {
            "workload_max_tokens": workload_max != CITED_WORKLOAD_MAX_TOKENS,
            "bfcl_tool_schema_tokens": schema_tokens != CITED_SCHEMA_TOKENS,
        },
        "inputs_sha256": hashed,
        "per_entry": per_entry,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_PATH),
                "workload_max_tokens": workload_max,
                "bfcl_tool_schema_tokens": schema_tokens,
                "turn0_min": min(turn0_values),
                "turn0_max": max(turn0_values),
                "entry10": None if entry_10 is None else entry_10["turn0_prompt_tokens"],
                "entry10_delta": None if entry_10 is None else entry_10["turn0_tools_delta_tokens"],
                "entry2_turn0": None if entry_2 is None else entry_2["turn0_prompt_tokens"],
                "entry2_user_only": (
                    None if entry_2 is None else entry_2["user_turns_only_max_tokens"]
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
