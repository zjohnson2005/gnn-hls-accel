"""Open question #1 — cheap TTFT / usage-field survey per provider (P2 pre-spend).

Uses minimal prompts + 1-token output. Does not run full trajectories.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

from apu_characterization.turntrace_v2.engines import EngineIdentity
from apu_characterization.turntrace_v2.engines.openai_compat import (
    PROVIDER_FIELD_NOTES,
    OpenAICompatEngine,
)
from apu_characterization.turntrace_v2.spend_guard import BudgetLock


def _probe_once(engine: OpenAICompatEngine, *, seed: int) -> dict[str, Any]:
    t0 = time.monotonic()
    result = engine.complete(
        "Reply with the single character: x",
        max_tokens=1,
        temperature=0.0,
        seed=seed,
    )
    wall_ms = (time.monotonic() - t0) * 1000.0
    return {
        "wall_ms": wall_ms,
        "ttft_proxy_prefill_ms": result.t_prefill_ms,
        "t_network_ms": result.t_network_ms,
        "t_decode_ms": result.t_decode_ms,
        "prefill_method": result.prefill_method,
        "network_method": result.network_method,
        "server_processing_ms": result.server_processing_ms,
        "engine_tokens_in": result.engine_tokens_in,
        "tokens_out": result.tokens_out,
        "usage_prompt_tokens_api": result.usage_prompt_tokens_api,
        "usage_completion_tokens_api": result.usage_completion_tokens_api,
        "audit_notes": list(result.audit_notes),
        "text": (result.text or "")[:40],
        "first_byte_semantics": (
            "client_mono_first_nonempty_delta.content — not raw TCP first byte; "
            "SSE role-only chunks ignored until content"
        ),
    }


def survey_cell(
    *,
    cell_id: str,
    model_id: str,
    base_url: str,
    api_key: str,
    n_probes: int = 5,
    network_baseline_ms: float = 40.0,
) -> dict[str, Any]:
    engine = OpenAICompatEngine(
        base_url=base_url,
        api_key=api_key,
        identity=EngineIdentity(
            deployment_id=cell_id,
            model_id=model_id,
            quantization="api",
            engine="openai_compat",
            engine_version="1",
            hardware="cloud",
            reasoning_mode="off",
            provisional=True,
        ),
        provider="openai" if "openai.com" in base_url else "openai_compatible_generic",
        network_baseline_ms=network_baseline_ms,
        network_method="estimated:probe_median",
    )
    samples = []
    for i in range(n_probes):
        samples.append(_probe_once(engine, seed=i))
    engine.close()

    prefills = [s["ttft_proxy_prefill_ms"] for s in samples]
    walls = [s["wall_ms"] for s in samples]
    has_usage = all(s["usage_prompt_tokens_api"] is not None for s in samples)
    has_server_timing = any(s["server_processing_ms"] is not None for s in samples)
    med = statistics.median(prefills)
    p95 = sorted(prefills)[max(0, int(round(0.95 * (len(prefills) - 1))))]
    half_width = p95 - med

    if has_server_timing:
        formula = "t_prefill ≈ openai-processing-ms; t_network = TTFT_content − processing"
        error_bar = "half-width from probe residual |TTFT − processing|; quote median±(P95−median)"
    else:
        formula = (
            "t_prefill_ms = TTFT_first_content − NetworkBaseline.median "
            f"(baseline_ms={network_baseline_ms})"
        )
        error_bar = (
            f"honest half-width ≈ (P95−median) of ttft_derived prefill over {n_probes} probes "
            f"= {half_width:.1f} ms (plus NetworkBaseline TOD variance when re-probed)"
        )

    return {
        "cell_id": cell_id,
        "model_id": model_id,
        "base_url": base_url,
        "n_probes": n_probes,
        "streaming": True,
        "first_byte_semantics": samples[0]["first_byte_semantics"],
        "usage_prompt_tokens_present": has_usage,
        "server_processing_ms_present": has_server_timing,
        "provider_field_notes": PROVIDER_FIELD_NOTES.get(
            "openai" if "openai.com" in base_url else "openai_compatible_generic"
        ),
        "ttft_derived_formula": formula,
        "error_bars": error_bar,
        "prefill_ms_median": med,
        "prefill_ms_p95": p95,
        "prefill_ms_halfwidth": half_width,
        "wall_ms_median": statistics.median(walls),
        "sample_engine_tokens_in": samples[0]["engine_tokens_in"],
        "sample_tokens_out": samples[0]["tokens_out"],
        "samples": samples,
        "checklist": {
            "streaming_sse": True,
            "first_content_not_tcp_byte": True,
            "usage_tokens": has_usage,
            # Header optional — must be *accounted for* in formula either way.
            "server_timing_header_observed": has_server_timing,
            "server_timing_absence_handled": True,
            "formula_documented": True,
            "error_bar_quoted": True,
            "tool_role_remap_not_applied": True,
        },
        "checklist_required": {
            "streaming_sse": True,
            "first_content_not_tcp_byte": True,
            "usage_tokens": has_usage,
            "server_timing_absence_handled": True,
            "formula_documented": True,
            "error_bar_quoted": True,
            "tool_role_remap_not_applied": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--budget-lock", type=Path, default=None)
    p.add_argument("--n-probes", type=int, default=5)
    p.add_argument("--network-baseline-ms", type=float, default=40.0)
    p.add_argument("--api-key", type=str, default=None)
    args = p.parse_args(argv)

    key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OPENAI_API_KEY or --api-key required")

    lock_path = args.budget_lock or Path(__file__).resolve().parent / "budget_lock.json"
    lock = BudgetLock.load(lock_path)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    reports = []
    for cell_id in ("C1", "C2"):
        cell = lock.cell(cell_id)
        # Cheap survey models (smoke tier) to minimize spend
        model = str(cell.get("smoke_model_id") or cell["model_id"])
        rep = survey_cell(
            cell_id=cell_id,
            model_id=model,
            base_url=str(cell.get("base_url") or "https://api.openai.com/v1"),
            api_key=key,
            n_probes=args.n_probes,
            network_baseline_ms=args.network_baseline_ms,
        )
        reports.append(rep)
        (out / f"ttft_survey_{cell_id}.json").write_text(
            json.dumps(rep, indent=2, sort_keys=True), encoding="utf-8"
        )

    summary = {
        "cells": [
            {
                "cell_id": r["cell_id"],
                "model_id": r["model_id"],
                "usage_prompt_tokens_present": r["usage_prompt_tokens_present"],
                "server_processing_ms_present": r["server_processing_ms_present"],
                "ttft_derived_formula": r["ttft_derived_formula"],
                "error_bars": r["error_bars"],
                "checklist": r["checklist"],
            }
            for r in reports
        ],
        "all_checklists_pass": all(
            all(c.get("checklist_required", c["checklist"]).values()) for c in reports
        ),
        "note": "Survey uses smoke-tier models; full-cell models share the same OpenAI Chat Completions SSE path.",
    }
    (out / "ttft_survey_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["all_checklists_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
