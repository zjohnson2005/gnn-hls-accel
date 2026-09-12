"""Artifact audit: LLM-judge exclusion, truncation / parse-failure rates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from censor.phase2_constants import CostModelParams
from censor.schema import Trajectory, group_by_scaffold
from censor.sensitivity import realizable_ceiling_metrics


@dataclass
class AuditStats:
    scaffold: str
    n: int
    n_llm_judge: int
    n_swebench_exact: int
    n_synthetic: int
    truncation_rate: float
    parse_failure_rate: float
    censored_rate: float


def corpus_audit_stats(trajectories: Sequence[Trajectory]) -> list[AuditStats]:
    rows: list[AuditStats] = []
    for scaffold, trajs in sorted(group_by_scaffold(trajectories).items()):
        n = len(trajs)
        rows.append(
            AuditStats(
                scaffold=scaffold,
                n=n,
                n_llm_judge=sum(t.outcome_source == "llm_judge" for t in trajs),
                n_swebench_exact=sum(
                    t.outcome_source == "swebench_exact" for t in trajs
                ),
                n_synthetic=sum(t.outcome_source == "synthetic" for t in trajs),
                truncation_rate=(
                    sum(t.truncated for t in trajs) / n if n else 0.0
                ),
                parse_failure_rate=(
                    sum(t.parse_failure for t in trajs) / n if n else 0.0
                ),
                censored_rate=sum(t.censored for t in trajs) / n if n else 0.0,
            )
        )
    return rows


def waterfall_with_without_llm_judge(
    trajectories: Sequence[Trajectory],
    params: CostModelParams | None = None,
    *,
    seed: int = 0,
) -> list[dict]:
    """Recompute realizable ceiling excluding LLM-judge labels; report both."""
    params = params or CostModelParams()
    out: list[dict] = []
    for scaffold, trajs in sorted(group_by_scaffold(trajectories).items()):
        full = realizable_ceiling_metrics(trajs, params, seed=seed)
        excl = [t for t in trajs if t.outcome_source != "llm_judge"]
        excl_m = (
            realizable_ceiling_metrics(excl, params, seed=seed)
            if excl
            else {k: float("nan") for k in full}
        )
        out.append(
            {
                "scaffold": scaffold,
                "n_full": len(trajs),
                "n_excluding_llm_judge": len(excl),
                "n_llm_judge_removed": len(trajs) - len(excl),
                "unreachable_full": full["unreachable_fraction"],
                "unreachable_excl_llm_judge": excl_m["unreachable_fraction"],
                "realizable_share_full": full["realizable_share_of_naive"],
                "realizable_share_excl_llm_judge": excl_m[
                    "realizable_share_of_naive"
                ],
                "note": (
                    "Published work: judge scoring diverges from exact-match by "
                    "10–24pp on knowledge tasks; truncation affected up to 65% of "
                    "responses in some settings — both can inflate apparent headroom."
                ),
            }
        )
    return out


def render_artifact_audit_md(
    stats: Sequence[AuditStats],
    judge_compare: Sequence[dict],
) -> str:
    lines = [
        "# Artifact audit (Phase 2)",
        "",
        "Written to accompany cost-side waterfall results. Outcome labels are",
        "inherited from public / upstream evaluators; this audit reports how",
        "sensitive the waterfall is to LLM-judge rows and to truncation.",
        "",
        "## Corpus composition",
        "",
        "| scaffold | n | swebench_exact | llm_judge | synthetic | trunc_rate | parse_fail_rate | censored_rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in stats:
        lines.append(
            f"| {s.scaffold} | {s.n} | {s.n_swebench_exact} | {s.n_llm_judge} | "
            f"{s.n_synthetic} | {s.truncation_rate:.3f} | "
            f"{s.parse_failure_rate:.3f} | {s.censored_rate:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Waterfall with LLM-judge trajectories excluded",
            "",
            "| scaffold | n_full | n_excl | unreachable_full | unreachable_excl | realizable_share_full | realizable_share_excl |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in judge_compare:
        lines.append(
            f"| {row['scaffold']} | {row['n_full']} | {row['n_excluding_llm_judge']} | "
            f"{row['unreachable_full']:.4f} | {row['unreachable_excl_llm_judge']:.4f} | "
            f"{row['realizable_share_full']:.4f} | "
            f"{row['realizable_share_excl_llm_judge']:.4f} |"
        )
    if judge_compare:
        lines.extend(["", judge_compare[0]["note"], ""])
    lines.extend(
        [
            "## Flags",
            "",
            "- F4 UNMEASURED",
            "- invariance bias UNMEASURED",
            "",
        ]
    )
    return "\n".join(lines)
