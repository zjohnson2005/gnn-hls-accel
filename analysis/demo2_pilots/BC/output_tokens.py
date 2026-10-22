"""Task BC part 1 (facts 2 and 5): generated tokens per local step, think blocks, max_new_tokens.

Mac only, no model. Reads every derived/**/local_turn_telemetry.jsonl (per-step
generated_tokens and, with --debug-raw-text, raw_text), the 8af10211 step_log
(post_generate lines were not written in that run, so only its prompt sizes),
and any extra run directories passed with --extra (uncommitted window copies,
e.g. cddcd9fd). For each run: platform, max_new_tokens from plan.json
generation_config, per-step generated-token counts, how many steps hit the cap,
and how many recorded texts contain "<think>".

Run from the repo root:
  python analysis/demo2_pilots/BC/output_tokens.py [--extra DIR ...] \\
      > analysis/demo2_pilots/BC/output_tokens.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
THINK = re.compile(r"<think>", re.IGNORECASE)


def _pct(xs: list[int], q: float) -> int | None:
    if not xs:
        return None
    s = sorted(xs)
    # nearest-rank percentile
    k = max(0, min(len(s) - 1, int(-(-q * len(s) // 1)) - 1))
    return s[k]


def _summ(xs: list[int]) -> dict[str, Any]:
    return {
        "n": len(xs),
        "p50": _pct(xs, 0.50),
        "p90": _pct(xs, 0.90),
        "p99": _pct(xs, 0.99),
        "max": max(xs) if xs else None,
    }


def _plan(d: Path) -> dict[str, Any]:
    for c in (d, d.parent, d.parent.parent):
        if (c / "plan.json").is_file():
            return dict(json.loads((c / "plan.json").read_text(encoding="utf-8")))
    return {}


def run(d: Path) -> dict[str, Any]:
    plan = _plan(d)
    gc = plan.get("generation_config") or {}
    cap = gc.get("max_new_tokens")
    gen: list[int] = []
    gen_step0: list[int] = []
    n_text = 0
    n_think = 0
    n_cap = 0
    for line in (d / "local_turn_telemetry.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        for st in row.get("steps") or []:
            g = st.get("generated_tokens")
            if isinstance(g, int):
                gen.append(g)
                if st.get("step") == 0:
                    gen_step0.append(g)
                if cap is not None and g >= int(cap):
                    n_cap += 1
            t = st.get("raw_text")
            if isinstance(t, str):
                n_text += 1
                if THINK.search(t):
                    n_think += 1
    try:
        rel = str(d.relative_to(ROOT))
    except ValueError:
        rel = "EXTRA:" + d.name
    return {
        "dir": rel,
        "run_id": plan.get("run_id"),
        "platform_id": plan.get("platform_id"),
        "max_new_tokens": cap,
        "chat_template": plan.get("chat_template"),
        "kv": (plan.get("openvino") or {}).get("kv"),
        "generated_all_steps": _summ(gen),
        "generated_step0": _summ(gen_step0),
        "steps_at_cap": n_cap,
        "steps_with_raw_text": n_text,
        "raw_texts_with_think": n_think,
        "_gen": gen,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", nargs="*", default=[])
    a = ap.parse_args()
    dirs = sorted({p.parent for p in ROOT.glob("derived/**/local_turn_telemetry.jsonl")})
    dirs += [Path(x) for x in a.extra]
    runs = [run(d) for d in dirs]
    pooled: dict[str, list[int]] = {}
    for r in runs:
        pooled.setdefault(str(r["platform_id"]), []).extend(r["_gen"])
    allg = [g for r in runs for g in r["_gen"]]
    for r in runs:
        del r["_gen"]
    out = {
        "task": "BC part 1 facts 2 and 5",
        "n_runs": len(runs),
        "runs": runs,
        "pooled_by_platform": {k: _summ(v) for k, v in pooled.items()},
        "pooled_all": _summ(allg),
        "steps_at_cap_all": sum(r["steps_at_cap"] for r in runs),
        "raw_texts_all": sum(r["steps_with_raw_text"] for r in runs),
        "raw_texts_with_think_all": sum(r["raw_texts_with_think"] for r in runs),
        "max_new_tokens_values": sorted({str(r["max_new_tokens"]) for r in runs}),
    }
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
