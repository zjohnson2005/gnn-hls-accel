"""Standalone repro of the entry-123 turn-0 stall (Task AZ, P11-HANG-REGIME).

No runner. Two subcommands:

  build (Mac, no model): replay multi_turn_long_context_123 turn 0 on its gold
    path through the runner's own render path (MultiTurnAgentSession,
    render_bfcl_tools_style, a stub pipe that returns the gold tool calls) and
    write every step's rendered prompt string to an inputs JSON with sha256 and
    token counts:
      python tools/repro_hang123.py build --tokenizer <hf tokenizer dir> \
          --bfcl-unpacked <bfcl wheel unpacked dir> --out <inputs.json>

  run (measurement host): LLMPipeline(model_dir, "GPU") with no property and no
    SchedulerConfig (the true default), then for each step: print and flush one
    PRE_GENERATE line, generate the pinned prompt string (apply_chat_template
    False, greedy, max_new_tokens 512), print POST_GENERATE. Refuses if an input's
    sha256 differs from the pinned value.
      python -u tools/repro_hang123.py run --inputs <inputs.json> \
          --model-dir models\\Qwen3-4B-int4-ov [--only-step N]

What it is not: the runner feeds a ChatHistory (RESIDENT) and the model's own
step-0 output; this feeds rendered strings and the gold step-0 call. Prefix
caching is on (latency default), so step 1 reuses step 0's prefix only as far
as the strings agree. A hang here reproduces the stall without the runner; no
hang does not rule the runner path out.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ENTRY_ID = "multi_turn_long_context_123"
PIN = ROOT / "derived" / "h1_hybrid" / "demo1" / "DEMO1_LONGCTX_30.json"
# Pinned by Task AY (analysis/demo2_pilots/AY/GPU_HANG_ENTRY123.md section 4).
ENTRY_JSON_SHA256 = "f78b6c221682e3fa42673d8b9ab536c490c6007016caf827c44414c8815659dc"
STEP0_PROMPT_SHA256 = "d3b347bc19c601c33c964762d5579cfc9a5ebb2020d286ecea583d11bcaa96a9"
MAX_NEW_TOKENS = 512


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _entry() -> dict[str, Any]:
    rows = json.loads(PIN.read_text(encoding="utf-8"))
    e: dict[str, Any] = next(x for x in rows if x["id"] == ENTRY_ID)
    got = hashlib.sha256(json.dumps(e, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if got != ENTRY_JSON_SHA256:
        raise SystemExit(f"REFUSED -- entry JSON sha256 {got} != pinned {ENTRY_JSON_SHA256}")
    return e


def build(tokenizer_dir: Path, bfcl_unpacked: Path, out: Path) -> dict[str, Any]:
    if "openvino_genai" not in sys.modules:
        sys.modules["openvino_genai"] = types.ModuleType("openvino_genai")
    from transformers import AutoTokenizer

    import tools.bfcl_feasibility_probe as probe
    import tools.h1_context_sizing as hs

    probe.BFCL_UNPACKED = bfcl_unpacked
    probe.BFCL_DATA = bfcl_unpacked / "bfcl_eval" / "data"
    probe.BFCL_ANSWERS = probe.BFCL_DATA / "possible_answer"
    tok = AutoTokenizer.from_pretrained(str(tokenizer_dir))
    entry = _entry()

    class CapturePipe(hs.GoldPipe):
        def __init__(self) -> None:
            super().__init__()
            self.prompts: list[str] = []

        def generate(self, prompts: list[str], cfg: Any) -> Any:
            self.prompts.append(str(prompts[0]))
            return super().generate(prompts, cfg)

    pipe = CapturePipe()
    session = probe.MultiTurnAgentSession(pipe=pipe, tokenizer=tok, cfg=None)
    session.begin(entry)
    calls = [str(c) for c in entry["reference"][0]]
    gold_text = probe.encode_execute_calls_as_qwen_tool_text(calls)
    pipe.queue = [gold_text, hs.CLOSING_TEXT]
    session.run_user_turn(0)
    session._finished = True
    steps = []
    for i, p in enumerate(pipe.prompts):
        steps.append(
            {
                "step": i,
                "prompt": p,
                "prompt_chars": len(p),
                "prompt_tokens_hf": len(tok(p)["input_ids"]),
                "prompt_sha256": sha(p),
                "gold_output_after": gold_text if i == 0 else hs.CLOSING_TEXT,
            }
        )
    if not steps or steps[0]["prompt_sha256"] != STEP0_PROMPT_SHA256:
        raise SystemExit("REFUSED -- step-0 prompt does not match the Task AY pin d3b347bc...")
    doc = {
        "kind": "repro_hang123_inputs",
        "entry_id": ENTRY_ID,
        "entry_json_sha256": ENTRY_JSON_SHA256,
        "turn": 0,
        "path": "gold (stub pipe returns the reference calls at step 0, the closing text after)",
        "gold_calls_turn0": calls,
        "tokenizer": "HF tokenizer (counts may differ from the OpenVINO tokenizer on the host)",
        "steps": steps,
    }
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {k: v for k, v in doc.items() if k != "steps"} | {
        "steps": [
            {k: v for k, v in s.items() if k not in ("prompt", "gold_output_after")} for s in steps
        ],
        "inputs_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
    }


def _line(tag: str, **kw: Any) -> None:
    kw["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"{tag} {json.dumps(kw, sort_keys=True)}", flush=True)


def run(inputs: Path, model_dir: Path, only_step: int | None, pinned_sha: str | None) -> int:
    raw = inputs.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if pinned_sha and got != pinned_sha:
        raise SystemExit(f"REFUSED -- inputs sha256 {got} != --inputs-sha256 {pinned_sha}")
    doc = json.loads(raw)
    for s in doc["steps"]:
        if sha(s["prompt"]) != s["prompt_sha256"]:
            raise SystemExit(f"REFUSED -- step {s['step']} prompt sha256 mismatch")
    import openvino as ov
    import openvino_genai as ov_genai

    _line(
        "LOAD_START",
        model_dir=str(model_dir),
        openvino=ov.__version__,
        openvino_genai=getattr(ov_genai, "__version__", "unknown"),
        inputs_sha256=got,
    )
    t0 = time.perf_counter()
    pipe = ov_genai.LLMPipeline(str(model_dir), "GPU")
    _line("LOAD_DONE", load_s=round(time.perf_counter() - t0, 3))
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = MAX_NEW_TOKENS
    cfg.do_sample = False
    cfg.apply_chat_template = False
    for s in doc["steps"]:
        if only_step is not None and s["step"] != only_step:
            continue
        _line(
            "PRE_GENERATE",
            step=s["step"],
            prompt_tokens_hf=s["prompt_tokens_hf"],
            prompt_sha256=s["prompt_sha256"],
        )
        t = time.perf_counter()
        res = pipe.generate(s["prompt"], cfg)
        text = str(res)
        _line(
            "POST_GENERATE",
            step=s["step"],
            wall_s=round(time.perf_counter() - t, 3),
            output_chars=len(text),
            output_sha256=sha(text),
        )
    _line("REPRO_DONE")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--tokenizer", type=Path, required=True)
    b.add_argument("--bfcl-unpacked", type=Path, required=True)
    b.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("run")
    r.add_argument("--inputs", type=Path, required=True)
    r.add_argument("--inputs-sha256", default=None)
    r.add_argument("--model-dir", type=Path, default=ROOT / "models" / "Qwen3-4B-int4-ov")
    r.add_argument("--only-step", type=int, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        print(json.dumps(build(a.tokenizer, a.bfcl_unpacked, a.out), indent=1))
        return 0
    return run(a.inputs, a.model_dir, a.only_step, a.inputs_sha256)


if __name__ == "__main__":
    sys.exit(main())
