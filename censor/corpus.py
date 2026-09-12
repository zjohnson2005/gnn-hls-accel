"""Load read-only normalized corpus from ``./corpus/normalized/``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from censor.schema import OutcomeSource, Tier, Trajectory, Turn

DEFAULT_CORPUS_DIR = Path("corpus") / "normalized"


def _as_tier(value: str) -> Tier:
    v = str(value).lower()
    if v not in ("local", "cloud"):
        raise ValueError(f"invalid logged_tier: {value!r}")
    return v  # type: ignore[return-value]


def _as_outcome_source(value: str) -> OutcomeSource:
    allowed = {"swebench_exact", "llm_judge", "synthetic", "unknown"}
    v = str(value)
    if v not in allowed:
        return "unknown"  # type: ignore[return-value]
    return v  # type: ignore[return-value]


def turn_from_dict(d: dict[str, Any]) -> Turn:
    return Turn(
        turn_index=int(d["turn_index"]),
        context_len_before=int(d["context_len_before"]),
        tokens_out=int(d.get("tokens_out") or d.get("output_tokens") or 0),
        tool_type=str(d.get("tool_type") or "unknown"),
        step_type_semantic=str(d.get("step_type_semantic") or "unknown"),
        logged_latency_ms=(
            None
            if d.get("logged_latency_ms") is None
            else float(d["logged_latency_ms"])
        ),
        logged_cost_usd=(
            None if d.get("logged_cost_usd") is None else float(d["logged_cost_usd"])
        ),
        necessary_prefill_tokens=(
            None
            if d.get("necessary_prefill_tokens") is None
            else int(d["necessary_prefill_tokens"])
        ),
        cloud_success=d.get("cloud_success"),
        local_success=d.get("local_success"),
        local_observed=bool(d.get("local_observed", False)),
    )


def trajectory_from_dict(d: dict[str, Any]) -> Trajectory:
    turns = [turn_from_dict(t) for t in d.get("turns") or []]
    turns.sort(key=lambda t: t.turn_index)
    return Trajectory(
        trajectory_id=str(d["trajectory_id"]),
        scaffold=str(d["scaffold"]),
        task_id=str(d.get("task_id") or d.get("task") or ""),
        task_class=str(d.get("task_class") or d.get("task_id") or "unknown"),
        logged_tier=_as_tier(d.get("logged_tier", "cloud")),
        task_outcome=d.get("task_outcome"),
        outcome_source=_as_outcome_source(d.get("outcome_source", "unknown")),
        truncated=bool(d.get("truncated", False)),
        parse_failure=bool(d.get("parse_failure", False)),
        censored=bool(d.get("censored", False)),
        turns=turns,
        flags=list(d.get("flags") or []),
    )


def load_corpus(corpus_dir: Path | str | None = None) -> list[Trajectory]:
    """Load all ``*.jsonl`` / ``trajectories.jsonl`` under the normalized dir."""
    root = Path(corpus_dir) if corpus_dir else DEFAULT_CORPUS_DIR
    if not root.is_dir():
        raise FileNotFoundError(
            f"Normalized corpus not found at {root.resolve()}. "
            "Run: python -m censor.build_corpus"
        )
    # Prefer the combined file to avoid double-counting per-scaffold shards.
    combined = root / "trajectories.jsonl"
    paths = [combined] if combined.is_file() else sorted(root.glob("*.jsonl"))
    if not paths:
        raise FileNotFoundError(f"No .jsonl files in {root.resolve()}")
    out: list[Trajectory] = []
    seen: set[str] = set()
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            tr = trajectory_from_dict(json.loads(line))
            if tr.trajectory_id in seen:
                continue
            seen.add(tr.trajectory_id)
            out.append(tr)
    if not out:
        raise ValueError(f"Corpus at {root} is empty")
    return out


def write_trajectory_jsonl(path: Path, trajectories: list[Trajectory]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for tr in trajectories:
            fh.write(json.dumps(tr.to_dict(), ensure_ascii=False) + "\n")
