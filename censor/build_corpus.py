"""Build ``./corpus/normalized/`` from OA-01 atlas + TurnTrace call records.

The engine treats the normalized corpus as read-only. This builder is the
only writer; re-run explicitly when source artifacts change.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from censor.corpus import write_trajectory_jsonl
from censor.schema import Trajectory, Turn

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ATLAS = (
    REPO_ROOT
    / "apu_characterization"
    / "out"
    / "oa01"
    / "OA01_behavioral_atlas.json"
)
DEFAULT_OUT = REPO_ROOT / "corpus" / "normalized"


def _tool_type(step: str, tool_names: list[str]) -> str:
    if tool_names:
        # Collapse bash×N to bash
        uniq = sorted(set(tool_names))
        return "+".join(uniq)
    if not step:
        return "unknown"
    return step.split("+")[0]


def _cloud_turn_success(task_outcome: bool | None, censored: bool) -> bool | None:
    if censored or task_outcome is None:
        return None
    # Trajectory-level label applied to all turns (support-limited).
    return bool(task_outcome)


def from_oa01_atlas(atlas_path: Path) -> list[Trajectory]:
    data = json.loads(atlas_path.read_text(encoding="utf-8"))
    outcomes = {row["trajectory_id"]: row for row in data.get("outcomes") or []}
    spaghetti: dict[str, list[dict[str, Any]]] = data.get("spaghetti") or {}
    trajectories: list[Trajectory] = []
    for tid, turns_raw in sorted(spaghetti.items()):
        meta = outcomes.get(tid, {})
        task_id = str(meta.get("task") or turns_raw[0].get("task_id") or tid)
        success = meta.get("success")
        censored = bool(meta.get("censored", False))
        flags = list(meta.get("flags") or [])
        truncated = "turn_cap" in str(meta.get("censor_reason") or "") or any(
            "truncat" in f.lower() for f in flags
        )
        parse_failure = any(
            x in flags for x in ("empty_patch", "missing_subject_trajectory")
        )
        # SWE-bench official evaluator → exact-match style outcome source.
        outcome_source = "swebench_exact"
        cloud_ok = _cloud_turn_success(success, censored)
        cost_usd = meta.get("cost_usd")
        n_turns = max(1, len(turns_raw))
        per_turn_usd = (
            float(cost_usd) / n_turns if cost_usd is not None else None
        )
        turns: list[Turn] = []
        for t in sorted(turns_raw, key=lambda r: int(r["turn_index"])):
            turns.append(
                Turn(
                    turn_index=int(t["turn_index"]),
                    context_len_before=int(t.get("input_tokens") or 0),
                    tokens_out=int(t.get("output_tokens") or 0),
                    tool_type=_tool_type(
                        str(t.get("step_type_semantic") or ""),
                        list(t.get("tool_names") or []),
                    ),
                    step_type_semantic=str(t.get("step_type_semantic") or "unknown"),
                    logged_latency_ms=(
                        None
                        if t.get("t_model_observed_ms") is None
                        else float(t["t_model_observed_ms"])
                    ),
                    logged_cost_usd=per_turn_usd,
                    necessary_prefill_tokens=(
                        None
                        if t.get("necessary_prefill_tokens") is None
                        else int(t["necessary_prefill_tokens"])
                    ),
                    cloud_success=cloud_ok,
                    local_success=None,
                    local_observed=False,
                )
            )
        trajectories.append(
            Trajectory(
                trajectory_id=tid,
                scaffold="mini_swe_agent",
                task_id=task_id,
                task_class=task_id.split("__")[0] if "__" in task_id else task_id,
                logged_tier="cloud",
                task_outcome=success,
                outcome_source=outcome_source,  # type: ignore[arg-type]
                truncated=truncated,
                parse_failure=parse_failure,
                censored=censored,
                turns=turns,
                flags=flags,
            )
        )
    return trajectories


def from_turntrace_corpus(corpus_dir: Path, scaffold_prefix: str) -> list[Trajectory]:
    """Normalize TurnTrace call_records + trajectory_records."""
    calls_path = corpus_dir / "call_records.jsonl"
    traj_path = corpus_dir / "trajectory_records.jsonl"
    if not calls_path.is_file() or not traj_path.is_file():
        return []
    meta: dict[str, dict[str, Any]] = {}
    for line in traj_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        meta[str(row["trajectory_id"])] = row
    by_tid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in calls_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        by_tid[str(row["trajectory_id"])].append(row)

    out: list[Trajectory] = []
    for tid, calls in sorted(by_tid.items()):
        m = meta.get(tid, {})
        harness = str(m.get("harness_id") or calls[0].get("harness_id") or "unknown")
        deployment = str(m.get("deployment_id") or calls[0].get("deployment_id") or "")
        logged_tier = "local" if deployment.upper().startswith(("L", "CPU")) else "cloud"
        success = m.get("task_success")
        outcome_source = "synthetic" if "synthetic" in str(m.get("workload_id") or "") else "unknown"
        turns: list[Turn] = []
        for c in sorted(calls, key=lambda r: int(r.get("turn_index", 0))):
            feats = c.get("step_features") or {}
            lat = None
            parts = [
                c.get("t_orch_pre_ms"),
                c.get("t_network_ms"),
                c.get("t_prefill_ms"),
                c.get("t_decode_ms"),
                c.get("t_orch_post_ms"),
            ]
            if any(p is not None for p in parts):
                lat = float(sum(float(p or 0.0) for p in parts))
            local_obs = logged_tier == "local"
            turns.append(
                Turn(
                    turn_index=int(c.get("turn_index", 0)),
                    context_len_before=int(
                        c.get("engine_tokens_in") or c.get("context_tokens_in") or 0
                    ),
                    tokens_out=int(c.get("tokens_out") or 0),
                    tool_type=str(feats.get("tool_class") or "unknown"),
                    step_type_semantic=str(c.get("step_type_semantic") or "unknown"),
                    logged_latency_ms=lat,
                    logged_cost_usd=None,
                    necessary_prefill_tokens=(
                        None
                        if c.get("prefill_necessary_tokens") is None
                        else int(c["prefill_necessary_tokens"])
                    ),
                    cloud_success=(bool(success) if logged_tier == "cloud" else None),
                    local_success=(bool(success) if local_obs else None),
                    local_observed=local_obs,
                )
            )
        out.append(
            Trajectory(
                trajectory_id=f"{scaffold_prefix}:{tid}",
                scaffold=f"turntrace_{harness}",
                task_id=str(m.get("workload_id") or tid),
                task_class=str(m.get("workload_id") or "turntrace"),
                logged_tier=logged_tier,  # type: ignore[arg-type]
                task_outcome=success,
                outcome_source=outcome_source,  # type: ignore[arg-type]
                truncated=False,
                parse_failure=False,
                censored=False,
                turns=turns,
                flags=[],
            )
        )
    return out


def discover_turntrace_corpora(root: Path) -> list[Path]:
    """Include cloud_full + cpu_dryrun only (skip smoke / mock / gate)."""
    hits = []
    base = root / "apu_characterization" / "out" / "turntrace_v2"
    if not base.is_dir():
        return hits
    allow = ("cloud_full", "cpu_dryrun")
    for path in base.rglob("call_records.jsonl"):
        parent = path.parent
        text = parent.as_posix()
        if not any(a in text for a in allow):
            continue
        if any(x in text for x in ("_gate_smoke", "cloud_smoke", "cloud_c1_mock")):
            continue
        if (parent / "trajectory_records.jsonl").is_file():
            hits.append(parent)
    return sorted(hits)


def build(
    *,
    atlas_path: Path = DEFAULT_ATLAS,
    out_dir: Path = DEFAULT_OUT,
    include_turntrace: bool = True,
) -> list[Trajectory]:
    trajectories: list[Trajectory] = []
    if atlas_path.is_file():
        trajectories.extend(from_oa01_atlas(atlas_path))
    if include_turntrace:
        for i, corp in enumerate(discover_turntrace_corpora(REPO_ROOT)):
            # Deduplicate by relative path stem
            prefix = corp.relative_to(REPO_ROOT).as_posix().replace("/", "_")
            trajectories.extend(from_turntrace_corpus(corp, scaffold_prefix=prefix))
            _ = i
    if not trajectories:
        raise RuntimeError("No source trajectories found to normalize")
    out_dir.mkdir(parents=True, exist_ok=True)
    # Write per-scaffold files + combined
    by_scaffold: dict[str, list[Trajectory]] = defaultdict(list)
    for tr in trajectories:
        by_scaffold[tr.scaffold].append(tr)
    for scaffold, rows in sorted(by_scaffold.items()):
        safe = scaffold.replace("/", "_")
        write_trajectory_jsonl(out_dir / f"{safe}.jsonl", rows)
    write_trajectory_jsonl(out_dir / "trajectories.jsonl", trajectories)
    manifest = {
        "n_trajectories": len(trajectories),
        "scaffolds": {k: len(v) for k, v in sorted(by_scaffold.items())},
        "sources": {
            "oa01_atlas": str(atlas_path) if atlas_path.is_file() else None,
            "turntrace": include_turntrace,
        },
        "note": "Read-only for the censor engine. Rebuild via python -m censor.build_corpus",
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "SCHEMA.md").write_text(
        """# Normalized censor corpus schema

One JSON object per trajectory (JSONL).

Required fields:
- `trajectory_id`, `scaffold`, `task_id`, `task_class`
- `logged_tier`: `local` | `cloud` (single-tier logged data)
- `task_outcome`: bool | null
- `outcome_source`: `swebench_exact` | `llm_judge` | `synthetic` | `unknown`
- `truncated`, `parse_failure`, `censored`
- `turns[]` with `turn_index`, `context_len_before`, `tokens_out`,
  `tool_type`, `step_type_semantic`, `logged_latency_ms`, `logged_cost_usd`,
  `necessary_prefill_tokens`, `cloud_success`, `local_success`, `local_observed`

There is no logged `route_local` action. Counterfactual local outcomes are
unobserved (`local_observed=false`) unless the source deployment was local.
""",
        encoding="utf-8",
    )
    return trajectories


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--atlas", type=Path, default=DEFAULT_ATLAS)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--no-turntrace", action="store_true")
    args = p.parse_args(argv)
    rows = build(
        atlas_path=args.atlas,
        out_dir=args.out,
        include_turntrace=not args.no_turntrace,
    )
    print(f"Wrote {len(rows)} trajectories to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
