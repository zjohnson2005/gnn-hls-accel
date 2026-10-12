"""Offline H1 context sizing (DEMO-1 groundwork). No model, no API, no device.

Drives the real H1 local turn loop (tools.bfcl_feasibility_probe
MultiTurnAgentSession, the session OpenVinoLocalBackend uses) with a stub
pipeline that answers each user turn with that turn's BFCL ground-truth calls
(one step, encoded as Qwen <tool_call> text), then a fixed closing text. The
calls run in the real BFCL tool environment, so tool outputs (including the
long_context data) enter the context exactly as in a live run. Every prompt
is rendered by render_bfcl_tools_style and counted with the Qwen3-4B HF
tokenizer, as in a live run.

This is a gold-trajectory size, not a model trajectory: a live 4B writes its
own calls and text. multi_turn_base is sized too, as a check against the
sealed d482c621 local turns (p50 3,939, max 6,279).

Usage (scratch venv with bfcl-eval, transformers):
  python tools/h1_context_sizing.py --category multi_turn_long_context \
      --tokenizer <dir with tokenizer.json> --out sizing.json
  python tools/h1_context_sizing.py --make-subset sizing.json \
      --out derived/h1_hybrid/demo1/DEMO1_LONGCTX_30.json

Subset rule (DEMO-1): eligible = entries with at least one turn whose gold
n_ctx exceeds 10,000; draw 30 with random.Random(20260930).sample over the
eligible ids in file order; keep file order. Written as a W-3-shaped entries
list plus a .meta.json beside it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import statistics
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CATEGORIES = ("multi_turn_base", "multi_turn_long_context")
CLOSING_TEXT = "Done."
BANDS = ((0, 10_000), (10_000, 18_500), (18_500, None))
SUBSET_SEED = 20260930
SUBSET_N = 30
SUBSET_MIN_CTX = 10_000


class GoldPipe:
    """Stub LLMPipeline: returns queued texts, one per generate call."""

    def __init__(self) -> None:
        self.queue: list[str] = []
        self.calls = 0

    def generate(self, _prompts: list[str], _cfg: Any) -> Any:
        self.calls += 1
        text = self.queue.pop(0) if self.queue else CLOSING_TEXT
        return types.SimpleNamespace(texts=[text], perf_metrics=None)

    def get_tokenizer(self) -> Any:  # pragma: no cover - mode None never asks
        raise RuntimeError("GoldPipe has no genai tokenizer")


def _install_fake_genai() -> None:
    """begin() imports openvino_genai; mode None never calls into it."""
    if "openvino_genai" not in sys.modules:
        sys.modules["openvino_genai"] = types.ModuleType("openvino_genai")


def bfcl_data_dir(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    import bfcl_eval

    return Path(bfcl_eval.__file__).resolve().parent / "data"


def load_entries(category: str, data_dir: Path) -> list[dict[str, Any]]:
    """Same entry shape as select_multi_turn_entries, for any multi_turn category."""
    import tools.bfcl_feasibility_probe as probe

    probe.BFCL_DATA = data_dir
    probe.BFCL_ANSWERS = data_dir / "possible_answer"
    fname = f"BFCL_v4_{category}.json"
    return probe._select_from_spec(((category, fname, 10_000),), kind="multi_turn")


def size_entry(entry: dict[str, Any], tokenizer: Any) -> dict[str, Any]:
    import tools.bfcl_feasibility_probe as probe

    _install_fake_genai()
    pipe = GoldPipe()
    session = probe.MultiTurnAgentSession(pipe=pipe, tokenizer=tokenizer, cfg=None)
    session.begin(entry)
    turns: list[dict[str, Any]] = []
    try:
        for turn_idx, gold in enumerate(entry["reference"]):
            calls = [str(c) for c in gold]
            pipe.queue = (
                [probe.encode_execute_calls_as_qwen_tool_text(calls), CLOSING_TEXT]
                if calls
                else [CLOSING_TEXT]
            )
            metric = session.run_user_turn(turn_idx)
            steps = [s for s in metric["steps"] if "prompt_tokens" in s]
            turns.append(
                {
                    "turn": turn_idx,
                    "n_ctx": metric["prompt_tokens"],
                    "max_step_prompt_tokens": max(s["prompt_tokens"] for s in steps),
                    "n_steps": len(steps),
                    "n_gold_calls": len(calls),
                    "tool_exec_error": bool(metric.get("tool_exec_error")),
                }
            )
            if session.force_quit:
                break
    finally:
        session._finished = True
    return {
        "entry_id": str(entry["id"]),
        "n_user_turns": len(entry["question"]),
        "turns": turns,
        "max_n_ctx": max((t["n_ctx"] for t in turns), default=None),
        "max_step_prompt_tokens": max((t["max_step_prompt_tokens"] for t in turns), default=None),
        "stop_reason": session.stop_reason,
    }


def _quantile(values: list[int], q: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_turn = [t["n_ctx"] for r in rows for t in r["turns"]]
    per_entry = [r["max_n_ctx"] for r in rows if r["max_n_ctx"] is not None]
    bands: dict[str, Any] = {}
    for lo, hi in BANDS:
        name = f"{lo}-{hi}" if hi else f">{lo}"

        def inside(n: int, lo: int = lo, hi: int | None = hi) -> bool:
            return n > lo and (hi is None or n <= hi)

        bands[name] = {
            "turns": sum(inside(n) for n in per_turn),
            "entries_by_max": sum(inside(n) for n in per_entry),
        }
    has_mid = [
        r["entry_id"] for r in rows if any(10_000 < t["n_ctx"] <= 18_500 for t in r["turns"])
    ]
    return {
        "n_entries": len(rows),
        "n_turns": len(per_turn),
        "turn_n_ctx": {
            "min": min(per_turn),
            "p50": _quantile(per_turn, 0.5),
            "p90": _quantile(per_turn, 0.9),
            "max": max(per_turn),
            "mean": round(statistics.mean(per_turn), 1),
        },
        "entry_max_n_ctx": {
            "min": min(per_entry),
            "p50": _quantile(per_entry, 0.5),
            "max": max(per_entry),
        },
        "bands": bands,
        "entries_with_a_turn_in_10000_18500": len(has_mid),
        "tool_exec_errors": sum(t["tool_exec_error"] for r in rows for t in r["turns"]),
    }


def _versions() -> dict[str, Any]:
    import importlib.metadata as md

    out: dict[str, Any] = {"python": platform.python_version()}
    for name in ("bfcl-eval", "transformers", "tokenizers", "jinja2"):
        try:
            out[name] = md.version(name)
        except md.PackageNotFoundError:
            out[name] = None
    return out


def tokenizer_record(path: Path) -> dict[str, Any]:
    files = {}
    for name in ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja"):
        f = path / name
        if f.is_file():
            files[name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return {"dir": "scratch (not committed)", "sha256": files}


def select_subset(sizing: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(eligible ids, selected ids), both in file order."""
    eligible = [
        r["entry_id"]
        for r in sizing["entries"]
        if any(t["n_ctx"] > SUBSET_MIN_CTX for t in r["turns"])
    ]
    if len(eligible) < SUBSET_N:
        raise SystemExit(f"REFUSED -- {len(eligible)} eligible entries < {SUBSET_N}")
    chosen = set(random.Random(SUBSET_SEED).sample(eligible, SUBSET_N))
    return eligible, [e for e in eligible if e in chosen]


def entries_bytes(entries: list[dict[str, Any]]) -> bytes:
    return (json.dumps(entries, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def make_subset(sizing_path: Path, out: Path, data_dir: Path | None) -> int:
    sizing = json.loads(sizing_path.read_text(encoding="utf-8"))
    eligible, selected = select_subset(sizing)
    by_id = {e["id"]: e for e in load_entries(sizing["category"], bfcl_data_dir(data_dir))}
    entries = [by_id[i] for i in selected]
    payload = entries_bytes(entries)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(payload)
    rows = {r["entry_id"]: r for r in sizing["entries"]}
    meta = {
        "kind": "h1_entry_subset",
        "name": out.stem,
        "category": sizing["category"],
        "rule": (
            f"eligible = entries with a turn whose gold n_ctx > {SUBSET_MIN_CTX}; "
            f"random.Random({SUBSET_SEED}).sample(eligible in file order, {SUBSET_N}); "
            "kept in file order"
        ),
        "seed": SUBSET_SEED,
        "n": len(entries),
        "entries_sha256": hashlib.sha256(payload).hexdigest(),
        "eligible": eligible,
        "selected": selected,
        "sizing_versions": sizing["versions"],
        "sizing_tokenizer": sizing["tokenizer"],
        "selected_sizing": {i: [t["n_ctx"] for t in rows[i]["turns"]] for i in selected},
        "selected_summary": summarize([rows[i] for i in selected]),
    }
    meta_path = out.with_name(out.stem + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(f"SUBSET {out} n={len(entries)} sha256={meta['entries_sha256']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=CATEGORIES)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--bfcl-data", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--make-subset", type=Path, help="sizing JSON to draw the subset from")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.make_subset is not None:
        return make_subset(args.make_subset, args.out, args.bfcl_data)
    if args.category is None or args.tokenizer is None:
        raise SystemExit("REFUSED -- sizing needs --category and --tokenizer")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer))
    entries = load_entries(args.category, bfcl_data_dir(args.bfcl_data))
    if args.limit is not None:
        entries = entries[: args.limit]
    rows = [size_entry(e, tokenizer) for e in entries]
    doc = {
        "kind": "h1_context_sizing",
        "measurement": False,
        "trajectory": "gold (BFCL ground-truth calls, one step per turn, closing text 'Done.')",
        "category": args.category,
        "prompt_render": "bfcl_feasibility_probe.render_bfcl_tools_style via MultiTurnAgentSession",
        "n_ctx_definition": "step-0 prompt tokens of each user turn (the H1 ledger n_ctx)",
        "versions": _versions(),
        "tokenizer": tokenizer_record(args.tokenizer),
        "summary": summarize(rows),
        "entries": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
