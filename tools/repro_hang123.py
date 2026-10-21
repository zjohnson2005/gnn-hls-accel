"""Standalone repro of the entry-123 turn-0 stall (Task AZ, P11-HANG-REGIME).

No runner. Three subcommands (variants: tools/repro_hang123_variants.py, Task BA):

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

  run --chain-steps K (Task BB, pilot P11-B; default off): the inputs hold one
    base prompt and a pinned "chain" suffix. After the base generate, K more
    generates follow, each on the previous prompt + its output text + the suffix
    (about 55 new tokens: the shape of 8af10211's steps 2-5). Outputs and every
    prompt's sha256 are recorded in run.json. --stall-s arms the stall watchdog
    (no streamer token for that long: outcome stall); --watchdog-s is then the
    per-generate budget (outcome turn_budget_exceeded).

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


def _watchdog(
    limit_s: float | None,
    out_dir: Path | None,
    py_spy: str | None,
    run_id: str,
    stall_s: float | None = None,
) -> Any:
    """seam.turn_watchdog.TurnWatchdog armed per generate (Task BA); None when off."""
    if limit_s is None and stall_s is None:
        if py_spy:
            raise SystemExit("REFUSED -- --py-spy needs --watchdog-s or --stall-s")
        return None
    if out_dir is None:
        raise SystemExit("REFUSED -- --watchdog-s needs --out-dir (as does --stall-s)")
    from seam.turn_watchdog import TurnWatchdog

    dump = [py_spy, "dump", "--native", "--pid", "{pid}"] if py_spy else None
    wd = TurnWatchdog(
        limit_s=float(limit_s) if limit_s is not None else None,
        out_dir=out_dir,
        run_id=run_id,
        dump_cmd=dump,
        stall_s=float(stall_s) if stall_s is not None else None,
    )
    wd.start()
    return wd


def _chain_prompts(doc: dict[str, Any], only_step: int | None) -> tuple[dict[str, Any], str]:
    """Base step and pinned suffix for --chain-steps; refuses a doc without a chain."""
    chain = doc.get("chain")
    if not isinstance(chain, dict) or "suffix" not in chain:
        raise SystemExit("REFUSED -- --chain-steps needs inputs with a 'chain' suffix")
    if sha(str(chain["suffix"])) != chain.get("suffix_sha256"):
        raise SystemExit("REFUSED -- chain suffix sha256 mismatch")
    steps = [s for s in doc["steps"] if only_step is None or s["step"] == only_step]
    if len(steps) != 1:
        raise SystemExit("REFUSED -- --chain-steps needs exactly one base step (use --only-step)")
    return steps[0], str(chain["suffix"])


def run(
    inputs: Path,
    model_dir: Path,
    only_step: int | None,
    pinned_sha: str | None,
    *,
    watchdog_s: float | None = None,
    out_dir: Path | None = None,
    py_spy: str | None = None,
    label: str = "repro",
    stall_s: float | None = None,
    chain_steps: int | None = None,
) -> int:
    raw = inputs.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if pinned_sha and got != pinned_sha:
        raise SystemExit(f"REFUSED -- inputs sha256 {got} != --inputs-sha256 {pinned_sha}")
    doc = json.loads(raw)
    for s in doc["steps"]:
        if sha(s["prompt"]) != s["prompt_sha256"]:
            raise SystemExit(f"REFUSED -- step {s['step']} prompt sha256 mismatch")
    import uuid

    base: dict[str, Any] | None = None
    suffix = ""
    if chain_steps is not None:
        if chain_steps < 1:
            raise SystemExit("REFUSED -- --chain-steps must be >= 1")
        base, suffix = _chain_prompts(doc, only_step)
    run_id = str(uuid.uuid4())
    record: dict[str, Any] = {
        "kind": "repro_hang123_run",
        "run_id": run_id,
        "label": label,
        "inputs": str(inputs),
        "inputs_sha256": got,
        "only_step": only_step,
        "watchdog_s": watchdog_s,
        "py_spy": py_spy,
        "stall_s": stall_s,
        "chain_steps": chain_steps,
        "construction": "LLMPipeline(model_dir, 'GPU'), no property, no SchedulerConfig",
        "max_new_tokens": MAX_NEW_TOKENS,
        "steps": [],
        "status": "started",
    }
    if out_dir is not None:
        out_dir = out_dir / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
    wd = _watchdog(watchdog_s, out_dir, py_spy, run_id, stall_s)

    def save() -> None:
        if out_dir is not None:
            (out_dir / "run.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")

    import openvino as ov
    import openvino_genai as ov_genai

    record["openvino"] = ov.__version__
    record["openvino_genai"] = getattr(ov_genai, "__version__", "unknown")
    save()
    _line("RUN_ID", run_id=run_id, label=label, out_dir=str(out_dir) if out_dir else None)
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
    if base is not None:
        rc = _run_chain(pipe, ov_genai, cfg, base, suffix, int(chain_steps or 0), wd, record, save)
        if wd is not None:
            wd.stop()
        if rc == 0:
            _line("REPRO_DONE")
        return rc
    for s in doc["steps"]:
        if only_step is not None and s["step"] != only_step:
            continue
        _line(
            "PRE_GENERATE",
            step=s["step"],
            prompt_tokens_hf=s["prompt_tokens_hf"],
            prompt_sha256=s["prompt_sha256"],
        )
        record["steps"].append({"step": s["step"], "pre_generate_utc": _utc(), "done": False})
        save()
        if wd is not None:
            wd.arm(entry_id=f"{label}_{ENTRY_ID}", policy="repro", turn=int(s["step"]))
        t = time.perf_counter()
        try:
            res = pipe.generate(s["prompt"], cfg)
        except Exception as exc:
            record["steps"][-1].update(error=f"{type(exc).__name__}: {exc}")
            record["status"] = "error"
            save()
            _line("GENERATE_ERROR", step=s["step"], error=f"{type(exc).__name__}: {exc}")
            return 2
        finally:
            if wd is not None:
                wd.disarm()
        text = str(res)
        wall = round(time.perf_counter() - t, 3)
        record["steps"][-1].update(
            done=True, wall_s=wall, output_chars=len(text), output_sha256=sha(text)
        )
        save()
        _line(
            "POST_GENERATE",
            step=s["step"],
            wall_s=wall,
            output_chars=len(text),
            output_sha256=sha(text),
        )
    record["status"] = "complete"
    save()
    if wd is not None:
        wd.stop()
    _line("REPRO_DONE")
    return 0


def _run_chain(
    pipe: Any,
    ov_genai: Any,
    cfg: Any,
    base: dict[str, Any],
    suffix: str,
    k: int,
    wd: Any,
    record: dict[str, Any],
    save: Any,
) -> int:
    """Base generate, then k generates on prompt + output + suffix (Task BB)."""
    from seam.backends.local_openvino import _make_ttft_streamer

    prompt = str(base["prompt"])
    on_tok = wd.progress if wd is not None and wd.stall_s is not None else None
    for i in range(k + 1):
        psha = sha(prompt)
        _line("PRE_GENERATE", step=i, prompt_chars=len(prompt), prompt_sha256=psha)
        record["steps"].append(
            {"step": i, "pre_generate_utc": _utc(), "prompt_sha256": psha, "done": False}
        )
        save()
        streamer = _make_ttft_streamer(ov_genai, on_token=on_tok)
        if wd is not None:
            wd.arm(entry_id=f"{record['label']}_chain", policy="repro", turn=i)
        t = time.perf_counter_ns()
        streamer.t0_ns = t
        try:
            res = pipe.generate(prompt, cfg, streamer)
        except Exception as exc:
            record["steps"][-1].update(error=f"{type(exc).__name__}: {exc}")
            record["status"] = "error"
            save()
            _line("GENERATE_ERROR", step=i, error=f"{type(exc).__name__}: {exc}")
            return 2
        finally:
            if wd is not None:
                wd.disarm()
        wall = round((time.perf_counter_ns() - t) / 1e9, 3)
        text = str(res)
        n_in = n_gen = None
        metrics = getattr(res, "perf_metrics", None)
        if metrics is not None:
            try:
                n_in = int(metrics.get_num_input_tokens())
                n_gen = int(metrics.get_num_generated_tokens())
            except Exception as exc:
                record["steps"][-1]["metrics_error"] = f"{type(exc).__name__}: {exc}"
        ttft = streamer.ttft_ns / 1e9 if streamer.ttft_ns else None
        record["steps"][-1].update(
            done=True,
            wall_s=wall,
            ttft_s=None if ttft is None else round(ttft, 3),
            input_tokens=n_in,
            generated_tokens=n_gen,
            streamer_tokens=len(streamer.token_ids),
            output_chars=len(text),
            output_sha256=sha(text),
            output_text=text,
        )
        save()
        _line(
            "POST_GENERATE",
            step=i,
            wall_s=wall,
            ttft_s=record["steps"][-1]["ttft_s"],
            input_tokens=n_in,
            generated_tokens=n_gen,
            output_sha256=sha(text),
        )
        prompt = prompt + text + suffix
    record["status"] = "complete"
    save()
    return 0


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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
    r.add_argument("--watchdog-s", type=float, default=None, help="per-generate limit (exit 86)")
    r.add_argument(
        "--out-dir", type=Path, default=None, help="run record dir (run.json, hang files)"
    )
    r.add_argument("--py-spy", default=None, help="with --watchdog-s: py-spy exe for a native dump")
    r.add_argument("--label", default="repro")
    r.add_argument(
        "--stall-s", type=float, default=None, help="no streamer token for this long: stall"
    )
    r.add_argument(
        "--chain-steps", type=int, default=None, help="Task BB: K generates on prompt+output+suffix"
    )
    v = sub.add_parser("variants")
    v.add_argument("--tokenizer", type=Path, required=True)
    v.add_argument("--bfcl-unpacked", type=Path, required=True)
    v.add_argument("--inputs", type=Path, required=True)
    v.add_argument("--out", type=Path, required=True)
    x = sub.add_parser("p11b-inputs")
    x.add_argument("--tokenizer", type=Path, required=True)
    x.add_argument("--bfcl-unpacked", type=Path, required=True)
    x.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "p11b-inputs":
        from tools.repro_hang123_variants import build_p11b

        idx = build_p11b(a.tokenizer, a.bfcl_unpacked, a.out)
        print(json.dumps(idx, indent=1))
        return 0
    if a.cmd == "build":
        print(json.dumps(build(a.tokenizer, a.bfcl_unpacked, a.out), indent=1))
        return 0
    if a.cmd == "variants":
        from tools.repro_hang123_variants import build_variants

        idx = build_variants(a.tokenizer, a.bfcl_unpacked, a.inputs, a.out)
        print(json.dumps({k: v for k, v in idx.items() if k != "sets"}, indent=1))
        return 0
    return run(
        a.inputs,
        a.model_dir,
        a.only_step,
        a.inputs_sha256,
        watchdog_s=a.watchdog_s,
        out_dir=a.out_dir,
        py_spy=a.py_spy,
        label=a.label,
        stall_s=a.stall_s,
        chain_steps=a.chain_steps,
    )


if __name__ == "__main__":
    sys.exit(main())
