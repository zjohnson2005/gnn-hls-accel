"""DEMO-1 gate check 3a: is each step's rendered prompt a token prefix of the next?

RESIDENT (CB prefix caching) can reuse KV only for the longest common token
prefix between the new step's rendered prompt and what is in the cache. This
drives the real H1 local turn loop (tools.bfcl_feasibility_probe
MultiTurnAgentSession, as tools/h1_context_sizing.py does) on the gold
trajectories of DEMO1_PAIRED_15 with OBS_MASK K, captures every rendered
prompt (render_bfcl_tools_style, the HF render the RESIDENT GenAI render is
asserted equal to on the first turn), tokenizes it with the pinned Qwen3-4B
tokenizer, and checks, within each entry, whether prompt(step k) is a token
prefix of prompt(step k+1). Each break is located and classified by the text
at the divergence point.

No model, no device, no API. Needs bfcl-eval and transformers (scratch venv)
and the pinned tokenizer files (configs/models/Qwen3-4B-int4-ov.yaml ir_files).

  python tools/demo1_prefix_check.py --tokenizer <dir> --obs-mask-k 1024 \
      --entries derived/h1_hybrid/demo1/DEMO1_PAIRED_15.json \
      --out analysis/demo1/PREFIX_CHECK_K1024.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CLOSING_TEXT = "Done."
TOKENIZER_FILES = ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja")


class CapturePipe:
    """Stub LLMPipeline: records each rendered prompt, returns queued gold texts."""

    def __init__(self) -> None:
        self.queue: list[str] = []
        self.prompts: list[str] = []
        self.outputs: list[str] = []

    def generate(self, prompts: Any, _cfg: Any, *_args: Any) -> Any:
        prompt = prompts[0] if isinstance(prompts, list) else prompts
        self.prompts.append(str(prompt))
        text = self.queue.pop(0) if self.queue else CLOSING_TEXT
        self.outputs.append(text)
        return types.SimpleNamespace(texts=[text], perf_metrics=None)

    def get_tokenizer(self) -> Any:  # pragma: no cover - mode None never asks
        raise RuntimeError("CapturePipe has no genai tokenizer")


def common_prefix_len(a: list[int], b: list[int]) -> int:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


EMPTY_THINK = "<think>\n\n</think>\n\n"


def classify_break(prev_text: str, next_text: str) -> str:
    """Name the cause from the text where the two renders diverge."""
    i = 0
    n = min(len(prev_text), len(next_text))
    while i < n and prev_text[i] == next_text[i]:
        i += 1
    before = prev_text[i : i + 40]
    after = next_text[i : i + 40]
    tail_start = len(prev_text) - len(EMPTY_THINK)
    if (
        prev_text.endswith(EMPTY_THINK)
        and i >= tail_start
        and not next_text[tail_start:].startswith(EMPTY_THINK)
    ):
        # The generation prompt ends with the empty think block (thinking off);
        # the template does not render it for that assistant message once a
        # later message follows it.
        return "generation_prompt_empty_think_block_not_rendered_in_history"
    if "<think>" in before and "<think>" not in after:
        return "chat_template_drops_think_block_from_earlier_assistant_turn"
    if "<think>" in after and "<think>" not in before:
        return "chat_template_adds_think_block"
    if "<tool_response>" in before or "<tool_response>" in after:
        return "observation_text_changed"
    if i == n:
        return "next_render_is_shorter"
    return "other"


def _point_probe_at_bfcl_data(probe: Any) -> None:
    """As tools/h1_context_sizing.load_entries: tool schemas come from bfcl_eval data."""
    import bfcl_eval

    data = Path(bfcl_eval.__file__).resolve().parent / "data"
    probe.BFCL_DATA = data
    probe.BFCL_ANSWERS = data / "possible_answer"


def check_entry(entry: dict[str, Any], tokenizer: Any, *, obs_mask_k: int | None) -> dict[str, Any]:
    import tools.bfcl_feasibility_probe as probe
    from tools.h1_obs_mask import ObservationMask, install_on_session

    if "openvino_genai" not in sys.modules:
        sys.modules["openvino_genai"] = types.ModuleType("openvino_genai")
    _point_probe_at_bfcl_data(probe)
    pipe = CapturePipe()
    session = probe.MultiTurnAgentSession(pipe=pipe, tokenizer=tokenizer, cfg=None)
    session.begin(entry)
    if obs_mask_k is not None:
        install_on_session(session, ObservationMask(obs_mask_k), entry_id=str(entry["id"]))
    step_turn: list[int] = []
    try:
        for turn_idx, gold in enumerate(entry["reference"]):
            calls = [str(c) for c in gold]
            pipe.queue = (
                [probe.encode_execute_calls_as_qwen_tool_text(calls), CLOSING_TEXT]
                if calls
                else [CLOSING_TEXT]
            )
            before = len(pipe.prompts)
            session.run_user_turn(turn_idx)
            step_turn.extend([turn_idx] * (len(pipe.prompts) - before))
            if session.force_quit:
                break
    finally:
        session._finished = True
    ids = [list(tokenizer(p)["input_ids"]) for p in pipe.prompts]
    transitions = []
    for k in range(len(ids) - 1):
        lcp = common_prefix_len(ids[k], ids[k + 1])
        holds = lcp == len(ids[k])
        same_turn = step_turn[k] == step_turn[k + 1]
        row: dict[str, Any] = {
            "step": k,
            "turn": step_turn[k],
            "next_turn": step_turn[k + 1],
            "boundary": "within_user_turn" if same_turn else "new_user_turn",
            "prompt_tokens": len(ids[k]),
            "next_prompt_tokens": len(ids[k + 1]),
            "common_prefix_tokens": lcp,
            "prefix_holds": holds,
            "reusable_share_of_next": round(lcp / len(ids[k + 1]), 4) if ids[k + 1] else None,
        }
        if not holds:
            row["cause"] = classify_break(pipe.prompts[k], pipe.prompts[k + 1])
            row["tokens_lost_from_prev"] = len(ids[k]) - lcp
        transitions.append(row)
    return {
        "entry_id": str(entry["id"]),
        "n_steps": len(ids),
        "step_prompt_tokens": [len(x) for x in ids],
        "step_turn": step_turn,
        "transitions": transitions,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    trans = [t for r in rows for t in r["transitions"]]
    held = [t for t in trans if t["prefix_holds"]]
    broken = [t for t in trans if not t["prefix_holds"]]
    causes: dict[str, int] = {}
    for t in broken:
        causes[t["cause"]] = causes.get(t["cause"], 0) + 1
    by_boundary: dict[str, dict[str, int]] = {}
    for t in trans:
        slot = by_boundary.setdefault(t["boundary"], {"n": 0, "holds": 0, "breaks": 0})
        slot["n"] += 1
        slot["holds" if t["prefix_holds"] else "breaks"] += 1
    return {
        "n_entries": len(rows),
        "n_transitions": len(trans),
        "n_prefix_holds": len(held),
        "n_prefix_breaks": len(broken),
        "share_prefix_holds": round(len(held) / len(trans), 4) if trans else None,
        "by_boundary": by_boundary,
        "break_causes": causes,
    }


def tokenizer_pins(path: Path) -> dict[str, str]:
    return {
        name: hashlib.sha256((path / name).read_bytes()).hexdigest()
        for name in TOKENIZER_FILES
        if (path / name).is_file()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--entries", type=Path, required=True)
    parser.add_argument("--obs-mask-k", type=int, default=1024)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer))
    entries = json.loads(args.entries.read_text(encoding="utf-8"))
    rows = [check_entry(e, tokenizer, obs_mask_k=args.obs_mask_k) for e in entries]
    doc = {
        "kind": "demo1_prefix_check",
        "gate": "DEMO-1 amendment 2026-10-13c check 3a",
        "entries_file": args.entries.as_posix(),
        "entries_sha256": hashlib.sha256(args.entries.read_bytes()).hexdigest(),
        "obs_mask_k": args.obs_mask_k,
        "render": "tools.bfcl_feasibility_probe.render_bfcl_tools_style (gold trajectories)",
        "tokenizer_sha256": tokenizer_pins(args.tokenizer),
        "summary": summarize(rows),
        "entries": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(doc["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
