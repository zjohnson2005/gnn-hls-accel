"""DEMO-2 $0 ladder rung L1: ground-truth replay with truncated tool outputs (Task BC).

Registered in docs/amendments/DEMO2_ARMS_REVISED_2026-10-21.md (part 3, L1).
No model, no GPU, no cloud. Never reads DEMO2_HELDOUT_60 / _B results; their
entry ids are excluded from the replay.

For every multi_turn_base and multi_turn_long_context entry (held-out ids
excluded), the gold calls are executed one at a time in the BFCL executor
(the runner's executor and shims), in gold order. Before each gold call, its
argument values are checked against the tool outputs seen so far:

- a value is REQUIRED if its text occurs in an earlier tool output (FULL) and
  in no user turn text up to that point (str values of >= 3 characters;
  numbers whose text has >= 3 characters, matched on number boundaries);
- for each (K, shape), the value SURVIVES if its text occurs in at least one
  earlier tool output after truncate_observation(output, K, shape).

State equality: gold calls run unchanged, so the end state equals the FULL
replay by construction; the rung tests only what the model could still read.

Decision rule (fixed before running): choose the smallest K in {512, 1024,
2048} and a shape in {h70t30, json} that preserves 100% of required values;
"head" is reported but never chosen. If none reaches 100%, K = 2048 json is
kept only if it preserves the most values of all candidates, and the misses
are listed for Zach; otherwise retention is dropped from arm C (arm C = B).

Run (Mac):
  python tools/demo2_ladder_l1.py --bfcl-unpacked <dir> --tokenizer <dir> \\
      --out derived/demo2_ladder/L1/l1_replay.json
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import types
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.h1_retention_budget import SHAPES, hf_codec, truncate_observation  # noqa: E402

KS = (512, 1024, 2048)
CATEGORIES = ("multi_turn_base", "multi_turn_long_context")
HELDOUT_META = (
    ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_HELDOUT_60.meta.json",
    ROOT / "derived" / "h1_hybrid" / "demo2" / "DEMO2_HELDOUT_60_B.meta.json",
)
CHOOSABLE = ("h70t30", "json")


def heldout_ids() -> set[str]:
    out: set[str] = set()
    for p in HELDOUT_META:
        out.update(json.loads(p.read_text(encoding="utf-8"))["selected"])
    return out


def _scalars(node: Any) -> list[Any]:
    if isinstance(node, dict):
        return [s for v in node.values() for s in _scalars(v)]
    if isinstance(node, (list, tuple)):
        return [s for v in node for s in _scalars(v)]
    return [node]


def call_values(call: str) -> list[str]:
    """Candidate value texts of one gold call string."""
    node = ast.parse(call, mode="eval").body
    if not isinstance(node, ast.Call):
        return []
    vals: list[Any] = []
    for a in [*node.args, *[k.value for k in node.keywords]]:
        try:
            vals.extend(_scalars(ast.literal_eval(a)))
        except (ValueError, SyntaxError):
            continue
    out: list[str] = []
    for v in vals:
        if isinstance(v, bool) or v is None:
            continue
        t = str(v)
        if len(t) >= 3:
            out.append(t)
    return out


def occurs(value: str, text: str) -> bool:
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return re.search(r"(?<![\d.])" + re.escape(value) + r"(?![\d])", text) is not None
    return value in text


def replay_entry(entry: dict[str, Any], encode: Any, decode: Any) -> dict[str, Any]:
    from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import (
        execute_multi_turn_func_call,
    )

    raw = entry["raw_entry"]
    cat = entry["category"]
    model_name = "l1_" + uuid.uuid4().hex[:12]
    long_ctx = "long_context" in cat or "composite" in cat
    args = (raw.get("initial_config") or {}, raw.get("involved_classes") or [], model_name)
    execute_multi_turn_func_call(
        [], *args, str(raw["id"]), long_context=long_ctx, is_evaL_run=False
    )
    seen: list[str] = []  # FULL tool outputs so far
    user_text = ""
    required: list[dict[str, Any]] = []
    obs_tokens: list[int] = []
    for t_idx, gold in enumerate(entry["reference"]):
        for m in entry["question"][t_idx]:
            if isinstance(m, dict):
                user_text += "\n" + str(m.get("content") or "")
        for call in [str(c) for c in gold]:
            for v in call_values(call):
                if occurs(v, user_text):
                    continue
                where = [i for i, o in enumerate(seen) if occurs(v, o)]
                if where:
                    required.append({"turn": t_idx, "call": call[:120], "value": v, "obs": where})
            results, _ = execute_multi_turn_func_call(
                [call], *args, str(raw["id"]), long_context=long_ctx, is_evaL_run=False
            )
            for r in results:
                seen.append(str(r))
                obs_tokens.append(len(encode(str(r))))
    cand: dict[str, Any] = {}
    for k in KS:
        for shape in SHAPES:
            trunc = [truncate_observation(o, k, shape, encode, decode) for o in seen]
            lost = [r for r in required if not any(occurs(r["value"], trunc[i]) for i in r["obs"])]
            cand[f"{k}_{shape}"] = {
                "n_required": len(required),
                "n_lost": len(lost),
                "lost": lost[:20],
                "kept_tokens": sum(len(encode(x)) for x in trunc),
            }
    return {
        "entry_id": str(raw["id"]),
        "category": cat,
        "n_observations": len(seen),
        "full_tokens": sum(obs_tokens),
        "max_observation_tokens": max(obs_tokens, default=0),
        "n_required_values": len(required),
        "candidates": cand,
    }


def decide(per_entry: list[dict[str, Any]]) -> dict[str, Any]:
    tot: dict[str, dict[str, int]] = {}
    for e in per_entry:
        for key, c in e["candidates"].items():
            t = tot.setdefault(key, {"required": 0, "lost": 0, "kept_tokens": 0})
            t["required"] += c["n_required"]
            t["lost"] += c["n_lost"]
            t["kept_tokens"] += c["kept_tokens"]
    full = sum(e["full_tokens"] for e in per_entry)
    for t in tot.values():
        t["kept_share_of_full_tokens"] = round(t["kept_tokens"] / full, 4) if full else None
    chosen = None
    for k in KS:
        ok = [s for s in CHOOSABLE if tot[f"{k}_{s}"]["lost"] == 0]
        if ok:
            # Prefer json, then h70t30, at the smallest K that preserves everything.
            chosen = {"k": k, "shape": "json" if "json" in ok else ok[0], "rule": "100% preserved"}
            break
    if chosen is None:
        best = min((tot[f"{k}_{s}"]["lost"], -k, s) for k in KS for s in CHOOSABLE)
        if best[1] == -2048 and best[2] == "json":
            chosen = {"k": 2048, "shape": "json", "rule": "no candidate at 100%; 2048 json best"}
        else:
            chosen = {"k": None, "shape": None, "rule": "no candidate at 100%; retention dropped"}
    return {"totals": tot, "full_tokens": full, "chosen": chosen}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bfcl-unpacked", type=Path, required=True)
    ap.add_argument("--tokenizer", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None, help="first N entries per category (smoke)")
    a = ap.parse_args(argv)
    if "openvino_genai" not in sys.modules:
        sys.modules["openvino_genai"] = types.ModuleType("openvino_genai")
    sys.path.insert(0, str(a.bfcl_unpacked))
    from transformers import AutoTokenizer

    import tools.bfcl_feasibility_probe as probe
    import tools.h1_context_sizing as hs
    from apu_characterization.cap01.bfcl_shims import install_bfcl_runtime_shims

    install_bfcl_runtime_shims()
    probe.BFCL_UNPACKED = a.bfcl_unpacked
    tok = AutoTokenizer.from_pretrained(str(a.tokenizer))
    encode, decode = hf_codec(tok)
    excluded = heldout_ids()
    data = a.bfcl_unpacked / "bfcl_eval" / "data"
    rows: list[dict[str, Any]] = []
    n_excluded = 0
    for cat in CATEGORIES:
        entries = hs.load_entries(cat, data)
        if a.limit is not None:
            entries = entries[: a.limit]
        for e in entries:
            if str(e["id"]) in excluded:
                n_excluded += 1
                continue
            rows.append(replay_entry(e, encode, decode))
    tok_sha = {
        f: hashlib.sha256((a.tokenizer / f).read_bytes()).hexdigest()
        for f in ("tokenizer.json", "tokenizer_config.json")
        if (a.tokenizer / f).is_file()
    }
    doc = {
        "rung": "L1",
        "task": "BC",
        "measurement": False,
        "excluded_heldout_entries": n_excluded,
        "n_entries": len(rows),
        "ks": list(KS),
        "shapes": list(SHAPES),
        "tokenizer_sha256": tok_sha,
        "decision": decide(rows),
        "entries": rows,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(doc["decision"]["chosen"]), doc["n_entries"], "entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
