"""Export CallRecord corpus (JSONL always; parquet when pyarrow available)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from apu_characterization.turntrace_v2.derive import flatten_call_dicts
from apu_characterization.turntrace_v2.schema import CallRecord, TrajectoryRecord

SCHEMA_DOC = """# TurnTrace v2 CallRecord / TrajectoryRecord schema

See `protocol_turntrace_v2.json` for the frozen field list (rev. B).

## Changelog (P1 fix pass)

### F3 — dual token currency
- Added `engine_tokens_in` (engine tokenizer / usage ground truth).
- Added `requested_tokens_in` (harness-intended pre-template content tokens).
- Added `token_reconciliation_delta = engine_tokens_in − requested_tokens_in`.
- **`context_tokens_in` is now an alias of `engine_tokens_in`** — all attribution
  (LCP, necessary/redundant, f(n) lookups) uses engine tokens exclusively.
- LCP diffs run over engine-tokenized post-template sequences (`engine_token_ids`).
- Audit flag `token_accounting_anomaly` when reconciliation delta exits the
  calibrated per-(engine, model, template) envelope, or when
  `prefix_hit_tokens > engine_tokens_in`.

### F1 — domain coverage
- Prefill grid floor extended to n=32 (engine tokens).
- Audit flag `attribution_out_of_domain` when `engine_tokens_in` is outside the
  fitted profile `[grid_min, grid_max]`; excluded from headline stats.
- Pre-run coverage check fails the gate if the cell's expected context range is
  not covered by the profile.

### F2 — cold-path integrity
- Cache verification cold sample = `cache_prompt=false` (slot erase is 501 without
  `--slot-save-path` on this llama-server build); see `boundary-cases.md`.
- Flag `implausible_cold_sample` and reject if cold t_prefill < 0.25 × f(n).

### F3 addendum — template role coverage
- Harness `tool` roles are remapped to `user` before `/apply-template` so engine
  token counts include tool payloads (TinyLlama drops bare `tool` roles).

### D1 — intercept booking
- f(n) intercept is booked into `t_prefill_necessary` by construction (conservative;
  biases harness tax downward). See attribution docstring.

## CallRecord
Per model call. Timing decomposition: T_orch_pre/post, T_network, T_prefill, T_decode.
Attribution: t_prefill_necessary_ms / t_prefill_redundant_ms via calibrated f(n).
Step identity: step_type_semantic + step_features (mechanism layer).
Predictable-at-issue: pred_* fields logged before the call returns.
`retemplated_tokens` is first-class (LCP failures that rewrite prior semantic content).

## TrajectoryRecord
Per trajectory. `replay_bundle_path` MUST be non-null for headline runs.
`task_success` + `success_metric` feed Layer 1 swapped-trajectory evaluation.

## Cloud TTFT derivation (open question #1)

Streaming is mandatory. `prefill_method=ttft_derived` for cloud.

| Provider | Available fields | Defensible error bars |
|----------|------------------|------------------------|
| OpenAI | SSE first-content timestamp; optional `openai-processing-ms`; `usage.prompt_tokens` / `completion_tokens` via `stream_options.include_usage` | If processing header present: `t_network = TTFT - processing`, `t_prefill ≈ processing`. Else: `t_prefill = TTFT - NetworkBaseline.median`; quote half-width `(P95 - median)` from the same endpoint's probe set. |
| OpenAI-compatible (C2) | Vendor-dependent usage; rarely server-timing | Same formula with `network_method=estimated:probe_median`. If streaming or usage missing → exclude from headline prefill attribution (`audit_flags`). |

Token reconciliation: always record API usage counts as `engine_tokens_in`; requested content counts as `requested_tokens_in`; flag anomalies via the calibrated envelope.

Network baselines are **location-dependent**. Laptop/WSL baselines are `provisional: true` and must be re-run from the Strix Halo box network before headline cloud attribution from that host.

## Corpus metadata

Every export directory should include `corpus_metadata.json` with at least:
`provisional` (bool), `cell` / `deployment_id`, `headline_eligible` (bool).

CPU dry-run (`CPU0`) is permanently `provisional: true` / `headline_eligible: false`.

## Figures
Every figure script must read only from this corpus — no hand-carried numbers.
"""


def write_schema_doc(path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SCHEMA_DOC, encoding="utf-8")
    return path


def export_jsonl(
    calls: Sequence[CallRecord],
    trajectories: Sequence[TrajectoryRecord],
    out_dir: Path,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    calls_path = out_dir / "call_records.jsonl"
    traj_path = out_dir / "trajectory_records.jsonl"
    with calls_path.open("w", encoding="utf-8") as fh:
        for record in calls:
            fh.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    with traj_path.open("w", encoding="utf-8") as fh:
        for record in trajectories:
            fh.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    schema_path = write_schema_doc(out_dir / "SCHEMA.md")
    return {"calls": calls_path, "trajectories": traj_path, "schema": schema_path}


def export_parquet(
    calls: Sequence[CallRecord],
    trajectories: Sequence[TrajectoryRecord],
    out_dir: Path,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = export_jsonl(calls, trajectories, out_dir)
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        paths["parquet_note"] = out_dir / "PARQUET_SKIPPED.txt"
        paths["parquet_note"].write_text(
            "pyarrow not installed; JSONL corpus is authoritative.\n",
            encoding="utf-8",
        )
        return paths

    call_rows = flatten_call_dicts(calls)
    traj_rows = [t.to_dict() for t in trajectories]
    calls_pq = out_dir / "call_records.parquet"
    traj_pq = out_dir / "trajectory_records.parquet"
    pq.write_table(pa.Table.from_pylist(call_rows), calls_pq)
    pq.write_table(pa.Table.from_pylist(traj_rows), traj_pq)
    paths["calls_parquet"] = calls_pq
    paths["trajectories_parquet"] = traj_pq
    return paths


def load_call_records_jsonl(path: Path) -> list[CallRecord]:
    records: list[CallRecord] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(CallRecord.from_dict(json.loads(line)))
    return records
