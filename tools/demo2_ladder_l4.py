"""DEMO-2 $0 ladder rung L4: cold/warm TTFT and decode vs prompt length (Task BC).

Registered in docs/amendments/DEMO2_ARMS_REVISED_2026-10-21.md (part 3, L4).
Measurement host only. Local-only, $0, never touches a held-out pin.

Runtime = arm A exactly: tools.bfcl_feasibility_probe.load_arm_pipeline("gpu_only")
with compiled readback; refuses unless seam.genai_runtime.true_default_verdict is
valid (PA, no SDPA fallback, compiled KV i8, no IR override). No CACHE_DIR.

Prompts: random token ids (seed per N and repeat, ids in [1000, 150000)),
decoded with the IR's HF tokenizer, raw (apply_chat_template False). Content
does not change prefill cost; a fresh random prompt shares no prefix with any
earlier one, so each first generate on it is a cold prefill.
Per N (ascending): R cold generates (max_new_tokens 64, ignore_eos), then one
warm generate on the last cold prompt + 55 random tokens (prefix-cache hit).
Records TTFT (perf_metrics, streamer fallback), decode tok/s, wall, errors
(full text). The sweep stops at the first generate error (the error text is
the record; L5 reads it).

Run (host):  python tools/demo2_ladder_l4.py \\
                 --grid 1024,2048,4096,6144,8192,10240,12288,16384 --repeats 3 \\
                 --out derived/demo2_ladder/L4
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DELTA_TOKENS = 55
MAX_NEW = 64
ID_LO, ID_HI = 1000, 150000


def random_prompt(tokenizer: Any, n: int, seed: int) -> tuple[str, int]:
    """Text of about n tokens; returns (text, exact HF token count)."""
    rng = random.Random(seed)
    ids = [rng.randrange(ID_LO, ID_HI) for _ in range(n)]
    text = str(tokenizer.decode(ids, skip_special_tokens=True))
    return text, len(tokenizer(text, add_special_tokens=False)["input_ids"])


def _utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--model-spec", type=Path, default=ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
    )
    ap.add_argument("--grid", required=True, help="comma-separated prompt lengths, ascending")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label", default="l4")
    a = ap.parse_args(argv)
    grid = [int(x) for x in a.grid.split(",") if x.strip()]
    if grid != sorted(grid) or not grid:
        raise SystemExit("REFUSED -- --grid must be ascending and non-empty")
    import openvino_genai as ov_genai

    import tools.bfcl_feasibility_probe as probe
    from seam.genai_runtime import true_default_verdict

    run_id = str(uuid.uuid4())
    out = a.out / run_id
    out.mkdir(parents=True, exist_ok=True)
    rec: dict[str, Any] = {
        "kind": "demo2_ladder_l4",
        "run_id": run_id,
        "label": a.label,
        "started_utc": _utc(),
        "grid": grid,
        "repeats": a.repeats,
        "max_new_tokens": MAX_NEW,
        "delta_tokens": DELTA_TOKENS,
        "construction": "load_arm_pipeline('gpu_only'), no property, no SchedulerConfig",
        "points": [],
        "status": "started",
    }

    def save() -> None:
        (out / "run.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")

    print(json.dumps({"RUN_ID": run_id, "out": str(out)}), flush=True)
    probe.apply_model_spec(a.model_spec)
    pipe, meta, load_s = probe.load_arm_pipeline("gpu_only", compiled_readback=True)
    loads = [ld for ld in meta.get("loads") or [] if "compiled_readback" in ld]
    cr = loads[-1]["compiled_readback"] if loads else {}
    verdict = true_default_verdict(cr, cr.get("ir_rt_info"))
    rec.update(load_s=round(load_s, 3), compiled_readback=cr, true_default=verdict)
    save()
    if not verdict["valid"]:
        rec["status"] = "refused_arm_a_invalid"
        save()
        raise SystemExit(f"REFUSED -- ARM_A_INVALID {verdict['reasons']}")
    tok = probe._hf_tokenizer()
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = MAX_NEW
    cfg.do_sample = False
    cfg.apply_chat_template = False
    if hasattr(cfg, "ignore_eos"):
        cfg.ignore_eos = True
    for n in grid:
        last = ""
        for r in range(a.repeats + 1):
            warm = r == a.repeats
            if warm:
                suffix, _ = random_prompt(tok, DELTA_TOKENS, n * 100 + 99)
                prompt = last + " " + suffix
            else:
                prompt, _ = random_prompt(tok, n, n * 100 + r)
                last = prompt
            n_tok = len(tok(prompt, add_special_tokens=False)["input_ids"])
            pt = {
                "n_target": n,
                "n_tokens": n_tok,
                "kind": "warm" if warm else "cold",
                "repeat": r,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "utc": _utc(),
            }
            t = time.perf_counter()
            res = probe._timed_generate(pipe, ov_genai, prompt, cfg)
            pt.update(
                ok=res["ok"],
                error=res["error"],
                wall_s=round(time.perf_counter() - t, 3),
                ttft_s=res["ttft_s"],
                ttft_source=res["ttft_source"],
                decode_tok_s=res["decode_tok_s"],
                generated_tokens=res["generated_tokens"],
            )
            rec["points"].append(pt)
            save()
            print(
                json.dumps({"POINT": {k: pt[k] for k in ("n_tokens", "kind", "ttft_s", "ok")}}),
                flush=True,
            )
            if not res["ok"]:
                rec["status"] = "stopped_on_error"
                save()
                return 3
    rec["status"] = "complete"
    rec["ended_utc"] = _utc()
    save()
    print("L4_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
