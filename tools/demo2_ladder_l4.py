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


def _verdict(cr: dict[str, Any], kv: str) -> dict[str, Any]:
    """Arm A verdict for kv default; for u4: PA, no fallback, compiled u4, no IR override."""
    from seam.genai_runtime import true_default_verdict

    if kv == "default":
        return true_default_verdict(cr, cr.get("ir_rt_info"))
    reasons = []
    if cr.get("backend") != "PA" or cr.get("sdpa_fallback_warning"):
        reasons.append(
            f"backend {cr.get('backend')!r} / fallback {cr.get('sdpa_fallback_warning')}"
        )
    if cr.get("kv_cache_precision") != kv:
        reasons.append(f"compiled KV {cr.get('kv_cache_precision')!r}, not {kv!r}")
    return {"valid": not reasons, "reasons": reasons}


def p90_of(xs: list[float]) -> float:
    """Nearest-rank p90 (with 3 repeats this is the maximum)."""
    s = sorted(xs)
    return s[max(0, -(-9 * len(s) // 10) - 1)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--model-spec", type=Path, default=ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
    )
    ap.add_argument("--grid", default="", help="comma-separated prompt lengths, ascending")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--label", default="l4")
    ap.add_argument("--kv", choices=("default", "u4"), default="default")
    ap.add_argument("--prompt-lookup", action="store_true", help="R0 build check only")
    ap.add_argument("--warmup-s", type=float, default=0.0, help="untimed warm-up generates first")
    ap.add_argument(
        "--refine-ttft-s",
        type=float,
        default=None,
        help="after the grid, bisect 1,024-multiples between the last grid point whose cold "
        "TTFT p90 is below this and the next one (R1 budget rule)",
    )
    ap.add_argument("--readback-only", action="store_true", help="R0: load, record, exit")
    a = ap.parse_args(argv)
    grid = [int(x) for x in a.grid.split(",") if x.strip()]
    if not a.readback_only and (grid != sorted(grid) or not grid):
        raise SystemExit("REFUSED -- --grid must be ascending and non-empty")
    if a.prompt_lookup and not a.readback_only:
        raise SystemExit("REFUSED -- --prompt-lookup is a readback (R0) check only here")
    import openvino_genai as ov_genai

    import tools.bfcl_feasibility_probe as probe

    run_id = str(uuid.uuid4())
    out = a.out / run_id
    out.mkdir(parents=True, exist_ok=True)
    arm = "gpu_only" if a.kv == "default" else "gpu_only_u4"
    extra = {"prompt_lookup": True} if a.prompt_lookup else None
    rec: dict[str, Any] = {
        "kind": "demo2_ladder_l4",
        "run_id": run_id,
        "label": a.label,
        "started_utc": _utc(),
        "grid": grid,
        "repeats": a.repeats,
        "kv": a.kv,
        "prompt_lookup": a.prompt_lookup,
        "warmup_s": a.warmup_s,
        "refine_ttft_s": a.refine_ttft_s,
        "max_new_tokens": MAX_NEW,
        "delta_tokens": DELTA_TOKENS,
        "construction": f"load_arm_pipeline({arm!r}), extra_properties {extra}, no SchedulerConfig",
        "points": [],
        "status": "started",
    }

    def save() -> None:
        (out / "run.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")

    print(json.dumps({"RUN_ID": run_id, "out": str(out)}), flush=True)
    probe.apply_model_spec(a.model_spec)
    pipe, meta, load_s = probe.load_arm_pipeline(
        arm, compiled_readback=True, extra_properties=extra
    )
    loads = [ld for ld in meta.get("loads") or [] if "compiled_readback" in ld]
    cr = loads[-1]["compiled_readback"] if loads else {}
    verdict = _verdict(cr, a.kv)
    rec.update(load_s=round(load_s, 3), compiled_readback=cr, verdict=verdict, load_meta=meta)
    save()
    if not verdict["valid"]:
        rec["status"] = "refused_invalid_build"
        save()
        raise SystemExit(f"REFUSED -- INVALID_BUILD {verdict['reasons']}")
    if a.readback_only:
        rec["status"] = "readback_only"
        save()
        print("L4_READBACK_DONE", flush=True)
        return 0
    tok = probe._hf_tokenizer()
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = MAX_NEW
    cfg.do_sample = False
    cfg.apply_chat_template = False
    if hasattr(cfg, "ignore_eos"):
        cfg.ignore_eos = True
    if a.warmup_s > 0:
        t_end = time.perf_counter() + a.warmup_s
        k = 0
        while time.perf_counter() < t_end:
            wp, _ = random_prompt(tok, 2048, 7_000_000 + k)
            probe._timed_generate(pipe, ov_genai, wp, cfg)
            k += 1
        rec["warmup_generates"] = k

    def point(n: int) -> list[float] | None:
        """R cold + 1 warm at n. Cold TTFTs, or None on a generate error."""
        last = ""
        cold: list[float] = []
        for r in range(a.repeats + 1):
            warm = r == a.repeats
            if warm:
                suffix, _ = random_prompt(tok, DELTA_TOKENS, n * 100 + 99)
                prompt = last + " " + suffix
            else:
                prompt, _ = random_prompt(tok, n, n * 100 + r)
                last = prompt
            n_tok = len(tok(prompt, add_special_tokens=False)["input_ids"])
            pt: dict[str, Any] = {
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
                return None
            if not warm and res["ttft_s"] is not None:
                cold.append(float(res["ttft_s"]))
        return cold

    lim = a.refine_ttft_s
    last_pass: int | None = None
    first_fail: int | None = None
    for n in grid:
        cold = point(n)
        if cold is None:
            rec["status"] = "stopped_on_error"
            rec["first_error_n"] = n
            first_fail = n
            save()
            break
        if lim is not None:
            if p90_of(cold) < lim:
                last_pass = n
            elif first_fail is None:
                first_fail = n
                break
    if lim is not None and last_pass is not None and first_fail is not None:
        lo, hi = last_pass // 1024, first_fail // 1024
        while hi - lo > 1:
            mid = (lo + hi) // 2
            cold = point(mid * 1024)
            if cold is not None and p90_of(cold) < lim:
                lo = mid
            else:
                hi = mid
        rec["refined_largest_pass"] = lo * 1024
    elif lim is not None and last_pass is not None:
        rec["refined_largest_pass"] = last_pass
        rec["refine_note"] = "no grid point failed; the largest grid point is the bound"
    if rec["status"] == "started":
        rec["status"] = "complete"
    rec["ended_utc"] = _utc()
    save()
    print(
        "L4_DONE", json.dumps({"refined_largest_pass": rec.get("refined_largest_pass")}), flush=True
    )
    return 0 if rec["status"] == "complete" else 3


if __name__ == "__main__":
    sys.exit(main())
