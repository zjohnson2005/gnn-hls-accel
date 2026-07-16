"""Network baseline probes for cloud endpoints (one-command re-run)."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from apu_characterization.turntrace_v2.calibrate_live import run_network_baseline
from apu_characterization.turntrace_v2.engines import EngineIdentity
from apu_characterization.turntrace_v2.engines.openai_compat import OpenAICompatEngine


def _tod_slot_now() -> str:
    hour = datetime.now(timezone.utc).hour
    if hour < 8:
        return "tod_utc_0_8"
    if hour < 16:
        return "tod_utc_8_16"
    return "tod_utc_16_24"


def make_openai_probe(
    *,
    base_url: str,
    model: str,
    api_key: str | None = None,
):
    engine = OpenAICompatEngine(
        base_url=base_url,
        api_key=api_key,
        identity=EngineIdentity(
            deployment_id="C1",
            model_id=model,
            quantization="api",
            engine="openai_compat",
            engine_version="1",
            hardware="cloud",
            reasoning_mode="n/a",
            provisional=True,
        ),
        provider="openai",
        network_baseline_ms=0.0,
    )

    def probe() -> float:
        t0 = time.monotonic()
        engine.complete("ping", max_tokens=1, temperature=0.0, seed=0)
        # Full RTT including prefill of tiny prompt — used as network+queue residue baseline
        # when server timing headers are absent. Documented in SCHEMA.md.
        return (time.monotonic() - t0) * 1000.0

    return probe


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TurnTrace v2 network baseline probes")
    p.add_argument("--endpoint-id", required=True)
    p.add_argument("--base-url", default="https://api.openai.com/v1")
    p.add_argument("--model", default="gpt-4o-mini")
    p.add_argument("--n-probes", type=int, default=100)
    p.add_argument("--tod-slot", default=None)
    p.add_argument(
        "--out",
        type=Path,
        default=Path("apu_characterization/out/turntrace_v2/network_baselines"),
    )
    p.add_argument(
        "--provisional",
        action="store_true",
        default=True,
        help="Mark baseline provisional (required until re-run from Strix Halo network)",
    )
    args = p.parse_args(argv)
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        raise SystemExit("OPENAI_API_KEY required for live network probes")
    tod = args.tod_slot or _tod_slot_now()
    out_path = Path(args.out) / f"{args.endpoint_id}_{tod}.json"
    probe = make_openai_probe(base_url=args.base_url, model=args.model)
    summary = run_network_baseline(
        endpoint_id=args.endpoint_id,
        probe_fn=probe,
        n_probes=args.n_probes,
        tod_slot=tod,
        out_path=out_path,
        provisional=True,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
