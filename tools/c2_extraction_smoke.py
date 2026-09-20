"""C-2 pre-launch extraction smoke: one real cell at n=64.

Fails unless the folded worker's _probe_once returns a non-null numeric
prefill_s. Catches the e39aaa86 bug (reading generation metrics off the
run_child wrapper instead of result['child']['generation']).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "derived" / "c2_ttft" / "_extraction_smoke",
    )
    parser.add_argument(
        "--model-spec",
        type=Path,
        default=ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml",
    )
    parser.add_argument("--n-tokens", type=int, default=64)
    parser.add_argument(
        "--arm",
        type=str,
        default="gpu_only_f16",
        help="delta_n arm id for the smoke cell (default gpu_only_f16)",
    )
    args = parser.parse_args(argv)

    from transformers import AutoTokenizer

    from seam.config import resolve_config
    from seam.model_provenance import load_local_spec
    from seam.tools.delta_n import (
        _DELTA_N_PATH,
        _MEASUREMENT_PATH,
        _PLATFORM_PATH,
        prompt_for,
    )
    from tools.run_c1_ceiling import _probe_once

    out_dir: Path = args.out if args.out.is_absolute() else ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "work"
    work_dir.mkdir(exist_ok=True)

    model_spec = args.model_spec if args.model_spec.is_absolute() else ROOT / args.model_spec
    resolved = resolve_config(
        [ROOT / _PLATFORM_PATH, ROOT / _MEASUREMENT_PATH, ROOT / _DELTA_N_PATH],
        repo_root=ROOT,
    )
    cfg = resolved.data
    spec = load_local_spec(model_spec)
    model_dir = str(spec["ir_dir"])
    arms_by_id = {a["id"]: a for a in cfg["arms"]}
    arm_id = str(args.arm).strip()
    if arm_id == "cpu-p":
        arm_id = "A"
    if arm_id not in arms_by_id:
        raise SystemExit(f"REFUSED -- unknown smoke arm {arm_id!r}")
    arm = arms_by_id[arm_id]
    p_cpus = [int(c) for c in cfg["topology"]["p_cpus"]]
    unit = str(cfg["ladder"]["filler_unit"])
    n = int(args.n_tokens)

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    prompt = prompt_for(root=ROOT, tokenizer=tokenizer, n_tokens=n, unit=unit, cache={})
    print(f"[c2_smoke] probe arm={arm_id} n={n} repeat=0", flush=True)
    rep = _probe_once(
        root=ROOT,
        cfg=cfg,
        arm=arm,
        model_dir=model_dir,
        p_cpus=p_cpus,
        work_dir=work_dir,
        prompt=prompt,
        n_tokens=n,
        repeat_i=0,
        label_prefix="c2_smoke",
    )
    prefill = rep.get("prefill_s")
    print(
        f"[c2_smoke] outcome={rep.get('outcome')!r} completed={rep.get('completed')!r} "
        f"prefill_s={prefill!r} decode_tok_s={rep.get('decode_tok_s')!r} "
        f"wall_s={rep.get('wall_s')!r}",
        flush=True,
    )
    if rep.get("outcome") != "pass":
        print("REFUSED -- extraction smoke: outcome is not pass", flush=True)
        return 2
    if prefill is None:
        print(
            "REFUSED -- extraction smoke: prefill_s is null after pass "
            "(accessor must read result['child']['generation']['prefill_s'])",
            flush=True,
        )
        return 3
    if not isinstance(prefill, (int, float)):
        print(
            f"REFUSED -- extraction smoke: prefill_s not numeric ({type(prefill)!r})",
            flush=True,
        )
        return 4
    print(f"EXTRACTION_SMOKE_OK prefill_s={float(prefill)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
