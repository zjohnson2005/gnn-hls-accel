"""Measure R2c re-prefill cost after cloud->local ChatHistory injection.

Live smoke on gpu_only RESIDENT when the host allows OpenVINO load.
If gates block live OpenVINO, exit with inferred_unmeasured and do not invent
a number.

Usage:
  python -m tools.measure_r2c_reprefill --model-spec configs/models/Qwen3-4B-int4-ov.yaml
  python -m tools.measure_r2c_reprefill --dry-run   # document inferred path only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.r2c_inject import measure_reprefill_after_inject  # noqa: E402


INFERRED_NOTE = (
    "ChatHistory.append(assistant) accepts an external cloud turn; resident KV "
    "does not stay valid. Policy calls finish_chat then re-prefills on the next "
    "generate(ChatHistory). re_prefill_s is that post-inject TTFT. Not measured "
    "in this process (dry-run or OpenVINO unavailable)."
)


def _dry_run_payload() -> dict[str, Any]:
    return {
        "kind": "r2c_reprefill_smoke",
        "utc": datetime.now(UTC).isoformat(),
        "re_prefill_required": True,
        "kv_valid_after_inject": False,
        "re_prefill_s": None,
        "re_prefill_source": "inferred_unmeasured",
        "note": INFERRED_NOTE,
        "measured": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-spec", type=Path, default=None)
    p.add_argument("--arm-id", default="gpu_only_u8")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not load OpenVINO; emit inferred_unmeasured record only.",
    )
    args = p.parse_args(argv)

    if args.dry_run:
        payload = _dry_run_payload()
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 0

    try:
        import openvino_genai as ov_genai

        import tools.bfcl_feasibility_probe as probe
    except Exception as exc:  # noqa: BLE001 - record gate block honestly
        payload = _dry_run_payload()
        payload["gate_block"] = f"{type(exc).__name__}: {exc}"
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 2

    if args.model_spec is not None:
        probe.apply_model_spec(args.model_spec)
    try:
        pipe, _meta, _load_s = probe.load_arm_pipeline(
            args.arm_id, enable_prefix_caching=None
        )
    except Exception as exc:  # noqa: BLE001
        payload = _dry_run_payload()
        payload["gate_block"] = f"load_arm_pipeline: {type(exc).__name__}: {exc}"
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
        return 2

    measured = measure_reprefill_after_inject(
        pipe=pipe,
        ov_genai=ov_genai,
        tools=[],
        seed_messages=[{"role": "user", "content": "Say ready."}],
        injected_assistant="[cloud bounce assistant for r2c reprefill smoke]",
        next_user="Continue locally.",
        max_new_tokens=16,
    )
    payload = {
        "kind": "r2c_reprefill_smoke",
        "utc": datetime.now(UTC).isoformat(),
        "arm_id": args.arm_id,
        "measured": True,
        **measured,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
