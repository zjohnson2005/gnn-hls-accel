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
# DEMO-1 envelope bands: [0,468], (468,10000], (10000,16437], (16437,18500], (18500,inf)
# from the sealed cold limits 7f232f86, c2246b1f, 56c116a6, d2d5cc4a.
ENVELOPE_EDGES = (468, 10_000, 16_437, 18_500)
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


def size_entry(
    entry: dict[str, Any], tokenizer: Any, *, obs_mask_k: int | None = None
) -> dict[str, Any]:
    """Size one entry. obs_mask_k applies the OBS_MASK arm
    (seam.retention_prompt.mask_observation) to every tool observation the
    model sees; tool state is unchanged."""
    import tools.bfcl_feasibility_probe as probe
    from seam.retention_prompt import mask_observation

    _install_fake_genai()
    pipe = GoldPipe()
    session = probe.MultiTurnAgentSession(pipe=pipe, tokenizer=tokenizer, cfg=None)
    session.begin(entry)
    observations: list[dict[str, Any]] = []
    execute = session._execute_multi_turn_func_call

    def observed(decoded: list[str], *args: Any, **kwargs: Any) -> Any:
        results, instances = execute(decoded, *args, **kwargs)
        out = []
        for call, result in zip(decoded, results, strict=False):
            text = str(result)
            shown = text if obs_mask_k is None else mask_observation(text, obs_mask_k)
            observations.append(
                {
                    "call": call.split("(", 1)[0],
                    "tokens": len(tokenizer(text)["input_ids"]),
                    "shown_tokens": len(tokenizer(shown)["input_ids"]),
                }
            )
            out.append(shown)
        return out, instances

    session._execute_multi_turn_func_call = observed
    turns: list[dict[str, Any]] = []
    try:
        for turn_idx, gold in enumerate(entry["reference"]):
            calls = [str(c) for c in gold]
            pipe.queue = (
                [probe.encode_execute_calls_as_qwen_tool_text(calls), CLOSING_TEXT]
                if calls
                else [CLOSING_TEXT]
            )
            seen = len(observations)
            metric = session.run_user_turn(turn_idx)
            obs = observations[seen:]
            steps = [s for s in metric["steps"] if "prompt_tokens" in s]
            turns.append(
                {
                    "turn": turn_idx,
                    "n_ctx": metric["prompt_tokens"],
                    "max_step_prompt_tokens": max(s["prompt_tokens"] for s in steps),
                    "n_steps": len(steps),
                    "n_gold_calls": len(calls),
                    "tool_exec_error": bool(metric.get("tool_exec_error")),
                    "max_observation_tokens": max((o["tokens"] for o in obs), default=0),
                    "max_observation_call": (
                        max(obs, key=lambda o: o["tokens"])["call"] if obs else None
                    ),
                    "max_shown_observation_tokens": max(
                        (o["shown_tokens"] for o in obs), default=0
                    ),
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


def envelope_band(n: float) -> str:
    """Name of the DEMO-1 envelope band that holds n."""
    lo = 0
    for edge in ENVELOPE_EDGES:
        if n <= edge:
            return f"({lo},{edge}]" if lo else f"[0,{edge}]"
        lo = edge
    return f"({lo},inf)"


def envelope_bands(per_turn: list[float], per_entry: list[float]) -> dict[str, Any]:
    """Count and share of turns, and of entries by their max, per envelope band."""
    names = [envelope_band(e) for e in ENVELOPE_EDGES] + [envelope_band(ENVELOPE_EDGES[-1] + 1)]
    out: dict[str, Any] = {}
    for name in names:
        turns = sum(envelope_band(n) == name for n in per_turn)
        entries = sum(envelope_band(n) == name for n in per_entry)
        out[name] = {
            "turns": turns,
            "turn_share": round(turns / len(per_turn), 4) if per_turn else None,
            "entries_by_max": entries,
            "entry_share": round(entries / len(per_entry), 4) if per_entry else None,
        }
    return out


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
    envelope = envelope_bands(per_turn, per_entry)
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
        "envelope_bands": envelope,
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


def select_subset(
    sizing: dict[str, Any],
    *,
    n: int = SUBSET_N,
    min_ctx: int | None = SUBSET_MIN_CTX,
    max_ctx: int | None = None,
) -> tuple[list[str], list[str]]:
    """(eligible ids, selected ids), both in file order.

    Eligible: an entry with a turn n_ctx > min_ctx (None: every entry), and,
    when max_ctx is given, a largest turn n_ctx <= max_ctx.
    """
    eligible = []
    for r in sizing["entries"]:
        largest = max((t["n_ctx"] for t in r["turns"]), default=0)
        if min_ctx is not None and largest <= min_ctx:
            continue
        if max_ctx is not None and largest > max_ctx:
            continue
        eligible.append(r["entry_id"])
    if len(eligible) < n:
        raise SystemExit(f"REFUSED -- {len(eligible)} eligible entries < {n}")
    chosen = set(random.Random(SUBSET_SEED).sample(eligible, n))
    return eligible, [e for e in eligible if e in chosen]


def entries_bytes(entries: list[dict[str, Any]]) -> bytes:
    return (json.dumps(entries, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def make_subset(
    sizing_path: Path,
    out: Path,
    data_dir: Path | None,
    *,
    n: int = SUBSET_N,
    min_ctx: int | None = SUBSET_MIN_CTX,
    max_ctx: int | None = None,
) -> int:
    sizing = json.loads(sizing_path.read_text(encoding="utf-8"))
    eligible, selected = select_subset(sizing, n=n, min_ctx=min_ctx, max_ctx=max_ctx)
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
            "eligible = "
            + (
                "every entry"
                if min_ctx is None
                else f"entries with a turn whose gold n_ctx > {min_ctx}"
            )
            + ("" if max_ctx is None else f" and largest turn n_ctx <= {max_ctx}")
            + f"; random.Random({SUBSET_SEED}).sample(eligible in file order, {n}); kept in file order"
        ),
        "sizing_file": sizing_path.as_posix(),
        "retention_arm": sizing.get("retention_arm", "FULL"),
        "obs_mask_k": sizing.get("obs_mask_k"),
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
    parser.add_argument("--obs-mask-k", type=int, default=None, help="OBS_MASK arm K")
    parser.add_argument("--make-subset", type=Path, help="sizing JSON to draw the subset from")
    parser.add_argument("--subset-n", type=int, default=SUBSET_N)
    parser.add_argument(
        "--subset-min-ctx",
        default=str(SUBSET_MIN_CTX),
        help="eligible if a turn n_ctx exceeds this; 'none' = every entry",
    )
    parser.add_argument("--subset-max-ctx", type=int, default=None)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.make_subset is not None:
        min_ctx = None if str(args.subset_min_ctx).lower() == "none" else int(args.subset_min_ctx)
        return make_subset(
            args.make_subset,
            args.out,
            args.bfcl_data,
            n=args.subset_n,
            min_ctx=min_ctx,
            max_ctx=args.subset_max_ctx,
        )
    if args.category is None or args.tokenizer is None:
        raise SystemExit("REFUSED -- sizing needs --category and --tokenizer")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer))
    entries = load_entries(args.category, bfcl_data_dir(args.bfcl_data))
    if args.limit is not None:
        entries = entries[: args.limit]
    rows = [size_entry(e, tokenizer, obs_mask_k=args.obs_mask_k) for e in entries]
    doc = {
        "kind": "h1_context_sizing",
        "measurement": False,
        "trajectory": "gold (BFCL ground-truth calls, one step per turn, closing text 'Done.')",
        "category": args.category,
        "retention_arm": "FULL" if args.obs_mask_k is None else "OBS_MASK",
        "obs_mask_k": args.obs_mask_k,
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
