"""Refresh stored replication artifacts after instrumentation or report fixes.

Recomputes ORCH measured/reconcile splits, batch_attribution, aggregates, audit,
and markdown without re-running OpenAI sessions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import apply_audit_to_artifact, apply_audit_to_replication_batch
from .experiments.single_agent_breakdown import _git_state
from .stats import aggregate_replication_runs, backfill_run_orch_fields, batch_attribution_summary
from .validity import DEBUG_ONLY, PUBLISHABLE, validity_banner


def refresh_seed_artifact(
    artifact: dict[str, Any], *, capture_env: dict[str, Any] | None = None
) -> dict[str, int]:
    """Backfill ORCH fields and recompute batch_attribution + audit for one seed."""
    if capture_env and not artifact.get("env"):
        artifact["env"] = capture_env
    run = artifact.get("run") or {}
    n_backfilled = backfill_run_orch_fields(run)
    total = artifact.get("invariant", {}).get("total_thread_cpu_ns") or run.get(
        "totals", {}
    ).get("thread_cpu_ns", 0)
    artifact["batch_attribution"] = batch_attribution_summary(run, total)
    apply_audit_to_artifact(artifact)
    return {"sessions_backfilled": n_backfilled}


def write_replication_markdown(
    combined: dict[str, Any],
    *,
    json_path: Path,
    search_locality: str,
) -> str:
    """Render replication batch summary markdown."""
    audit = combined.get("audit", {})
    aggregate = combined.get("aggregate", {})
    seeds = combined.get("config", {}).get("seeds") or []
    md_lines = [
        validity_banner(combined["result_validity"]),
        "",
        f"# Replication batch ({search_locality} search, n={len(seeds)} seeds)",
        "",
        f"- audit pass: **{'YES' if audit.get('pass') else 'NO'}**",
        f"- publishable_ok: **{'YES' if audit.get('publishable_ok') else 'NO'}**",
        f"- platform: `{audit.get('platform')}`",
    ]
    git = combined.get("git") or {}
    if git.get("dirty") == "yes":
        allow = combined.get("config", {}).get("allow_dirty")
        if allow:
            md_lines.append(
                "- git: **dirty** (refreshed with `--allow-dirty`; commit before final publishable stamp)"
            )
        else:
            md_lines.append(
                "- git: **dirty** — reproducibility gate FAIL; commit and re-run for publishable stamp"
            )
    md_lines.extend(
        [
            "",
            f"Seeds: {seeds}",
            "",
            "## Aggregate (median [IQR])",
            "",
            f"- Batch host CPU ms: {aggregate['batch_host_cpu_ms']['median']:.1f} "
            f"[{aggregate['batch_host_cpu_ms']['q1']:.1f}–{aggregate['batch_host_cpu_ms']['q3']:.1f}]",
            f"- Pooled TOOL_COMPUTE %: {aggregate['pooled_tool_compute_pct']['median']:.1f} "
            f"[{aggregate['pooled_tool_compute_pct']['q1']:.1f}–"
            f"{aggregate['pooled_tool_compute_pct']['q3']:.1f}]",
            f"- Pooled ORCH %: {aggregate['pooled_orch_pct']['median']:.1f} "
            f"[{aggregate['pooled_orch_pct']['q1']:.1f}–{aggregate['pooled_orch_pct']['q3']:.1f}]",
            f"- Pooled ORCH measured % (stream step residual): "
            f"{aggregate.get('pooled_orch_measured_pct', {}).get('median', 0):.1f} "
            f"[{aggregate.get('pooled_orch_measured_pct', {}).get('q1', 0):.1f}–"
            f"{aggregate.get('pooled_orch_measured_pct', {}).get('q3', 0):.1f}]",
            f"- Pooled ORCH reconcile % (session-end gap booked to ORCH): "
            f"{aggregate.get('pooled_orch_reconcile_pct', {}).get('median', 0):.1f} "
            f"[{aggregate.get('pooled_orch_reconcile_pct', {}).get('q1', 0):.1f}–"
            f"{aggregate.get('pooled_orch_reconcile_pct', {}).get('q3', 0):.1f}]",
            f"- Pooled harness strict % (ORCH+TOKEN+SER): "
            f"{aggregate.get('pooled_harness_strict_pct', aggregate.get('pooled_harness_apu_pct', {})).get('median', 0):.1f} "
            f"[{aggregate.get('pooled_harness_strict_pct', aggregate.get('pooled_harness_apu_pct', {})).get('q1', 0):.1f}–"
            f"{aggregate.get('pooled_harness_strict_pct', aggregate.get('pooled_harness_apu_pct', {})).get('q3', 0):.1f}]",
            "",
        ]
    )
    orch_share = aggregate.get("orch_reconcile_share_of_orch_pct", {})
    if orch_share.get("n", 0) > 0:
        md_lines.append(
            f"- ORCH reconcile as % of total ORCH (per-seed batches): "
            f"{orch_share['median']:.1f} "
            f"[{orch_share['q1']:.1f}–{orch_share['q3']:.1f}] "
            f"(see {aggregate.get('attribution_doc', 'ATTRIBUTION.md')})"
        )
        md_lines.append("")
    md_lines.extend(
        [
            "Execution: 10 sessions per batch, **sequential** (`workers=1`).",
            "",
            "Comparison type: **distribution over seeds** (not matched per-call ablation).",
            "",
        ]
    )
    for v in audit.get("violations", [])[:10]:
        md_lines.append(f"- **VIOLATION:** {v}")
    if len(audit.get("violations", [])) > 10:
        md_lines.append(f"- ... and {len(audit['violations']) - 10} more violations")
    repro = audit.get("repro", {})
    for w in repro.get("warnings", [])[:5]:
        md_lines.append(f"- **REPRO:** {w}")
    md_lines.extend(
        [
            "",
            f"Full data: `{json_path.name}`",
            "",
        ]
    )
    return "\n".join(md_lines)


def refresh_replication_batch(
    json_path: Path,
    *,
    out_dir: Path | None = None,
    allow_dirty: bool = False,
) -> dict[str, Any]:
    """Load replication JSON, backfill attribution, re-audit, rewrite json/md."""
    combined = json.loads(json_path.read_text(encoding="utf-8"))
    out_dir = out_dir or json_path.parent
    cfg = combined.setdefault("config", {})
    if "measurement_git" not in combined and combined.get("git"):
        combined["measurement_git"] = dict(combined["git"])
    combined["git"] = _git_state()
    if combined["git"].get("dirty") == "no":
        cfg.pop("allow_dirty", None)
    elif allow_dirty:
        cfg["allow_dirty"] = True

    backfill_stats = {"sessions_backfilled": 0, "seeds": 0}
    capture_env = combined.get("env")
    for art in combined.get("per_seed_artifacts") or []:
        stats = refresh_seed_artifact(art, capture_env=capture_env)
        backfill_stats["sessions_backfilled"] += stats["sessions_backfilled"]
        backfill_stats["seeds"] += 1

    combined["aggregate"] = aggregate_replication_runs(combined["per_seed_artifacts"])
    backend = cfg.get("backend", "openai")
    combined["result_validity"] = DEBUG_ONLY if backend != "openai" else PUBLISHABLE
    combined["refreshed_utc"] = datetime.now(timezone.utc).isoformat()
    apply_audit_to_replication_batch(combined, allow_dirty=allow_dirty)

    search_locality = cfg.get("search_locality", "remote")
    stem = json_path.stem
    out_json = out_dir / f"{stem}.json"
    out_md = out_dir / f"{stem}.md"
    out_json.write_text(json.dumps(combined, indent=2), encoding="utf-8")
    out_md.write_text(
        write_replication_markdown(
            combined, json_path=out_json, search_locality=search_locality
        ),
        encoding="utf-8",
    )
    combined["_refresh_stats"] = backfill_stats
    return combined
