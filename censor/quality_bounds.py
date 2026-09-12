"""Quality-side Manski bounds. Never a point estimate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from censor.schema import Trajectory, Turn


@dataclass(frozen=True)
class BoundInterval:
    lower: float
    upper: float
    assumption_set: str
    n_trajectories: int
    n_turns: int
    notes: str

    @property
    def width(self) -> float:
        return float(self.upper) - float(self.lower)


def _turn_local_success_bounds(
    turn: Turn,
    *,
    a1_monotonicity: bool,
    a2_rate: float | None,
    a3_lipschitz: bool,
    difficulty: float,
    ref_difficulty: float,
    lipschitz_k: float,
) -> tuple[float, float, str]:
    """Return (lower, upper) success probability bounds for one turn."""
    if turn.local_observed and turn.local_success is not None:
        v = 1.0 if turn.local_success else 0.0
        return v, v, "observed_local"

    # Manski (1990): no assumptions beyond outcome in {0,1}.
    lo, hi = 0.0, 1.0
    note = "manski"

    if a1_monotonicity and turn.cloud_success is False:
        # If cloud failed, local also fails.
        hi = min(hi, 0.0)
        note = "manski+A1"

    if a2_rate is not None:
        # Task-class transfer identifies the unobserved outcome at a2_rate,
        # then intersect with current bounds (never widen past A1).
        if turn.cloud_success is False and a1_monotonicity:
            # A1 dominates: local fails; A2 cannot raise the upper bound.
            lo, hi = 0.0, 0.0
            note = "manski+A1 (A2 dominated on cloud-fail)"
        else:
            lo = hi = a2_rate
            note = note + "+A2"

    if a3_lipschitz and a2_rate is not None:
        # Optional smoothness around a reference difficulty.
        radius = lipschitz_k * abs(difficulty - ref_difficulty)
        lo = max(lo, a2_rate - radius)
        hi = min(hi, a2_rate + radius)
        lo = min(max(lo, 0.0), 1.0)
        hi = min(max(hi, 0.0), 1.0)
        if lo > hi:
            lo, hi = hi, lo
        note = note + "+A3"

    return lo, hi, note


def _task_class_local_rate(
    corpus: Sequence[Trajectory], task_class: str
) -> float | None:
    """Measured local success rate on task_class where local is observed."""
    successes = 0
    n = 0
    for tr in corpus:
        if tr.task_class != task_class:
            continue
        for turn in tr.turns:
            if turn.local_observed and turn.local_success is not None:
                n += 1
                successes += int(bool(turn.local_success))
    if n == 0:
        return None
    return successes / n


def _trajectory_success_bounds(
    trajectory: Trajectory,
    corpus: Sequence[Trajectory],
    *,
    a1: bool,
    a2: bool,
    a3: bool,
    lipschitz_k: float = 0.0,
) -> tuple[float, float, str]:
    """Bound P(trajectory success under local/hybrid) without point estimates.

    Trajectory success requires all turns to succeed under a conservative
    series model: product of per-turn bounds (lower=product of lowers,
    upper=product of uppers). Wide by construction when unobserved.
    """
    a2_rate = _task_class_local_rate(corpus, trajectory.task_class) if a2 else None
    a2_note = ""
    if a2 and a2_rate is None:
        a2_note = "A2 skipped: no local observations in task_class"

    # Reference difficulty = mean context length in class (for A3).
    ref_diffs: list[float] = []
    if a3:
        for tr in corpus:
            if tr.task_class == trajectory.task_class:
                for t in tr.turns:
                    ref_diffs.append(float(t.context_len_before))
    ref_difficulty = sum(ref_diffs) / len(ref_diffs) if ref_diffs else 0.0

    # If trajectory-level local outcome were observed, use it.
    # (Corpus currently has no local-observed trajectories; keep the hook.)
    local_traj_observed = all(t.local_observed for t in trajectory.turns) and bool(
        trajectory.turns
    )
    if local_traj_observed and trajectory.task_outcome is not None:
        v = 1.0 if trajectory.task_outcome else 0.0
        return v, v, "observed_local_trajectory"

    lo_prod, hi_prod = 1.0, 1.0
    notes: list[str] = []
    if a2_note:
        notes.append(a2_note)
    for turn in trajectory.turns:
        lo, hi, note = _turn_local_success_bounds(
            turn,
            a1_monotonicity=a1,
            a2_rate=a2_rate if a2 else None,
            a3_lipschitz=a3 and a2_rate is not None,
            difficulty=float(turn.context_len_before),
            ref_difficulty=ref_difficulty,
            lipschitz_k=lipschitz_k,
        )
        lo_prod *= lo
        hi_prod *= hi
        if note not in notes:
            notes.append(note)

    # A1 at trajectory level: cloud task failure ⇒ local cannot succeed.
    if a1 and trajectory.task_outcome is False:
        hi_prod = min(hi_prod, 0.0)
        lo_prod = min(lo_prod, hi_prod)
        if "A1-trajectory" not in notes:
            notes.append("A1-trajectory")

    return lo_prod, hi_prod, "; ".join(notes)


def manski_bounds(
    trajectory: Trajectory, corpus: Sequence[Trajectory]
) -> tuple[float, float]:
    """Manski (1990) worst-case bounds: no assumptions beyond outcome range."""
    lo, hi, _ = _trajectory_success_bounds(
        trajectory, corpus, a1=False, a2=False, a3=False
    )
    return lo, hi


def bounds_table(
    trajectories: Sequence[Trajectory],
    corpus: Sequence[Trajectory] | None = None,
    *,
    lipschitz_k: float = 1e-4,
) -> list[BoundInterval]:
    """Manski bottom-up: add assumptions one at a time; report widths.

    Citation: Manski, C. F. (1990). "Nonparametric Bounds on Treatment Effects."
    *American Economic Review*, 80(2), 319–323. Bottom-up reporting of how
    each assumption tightens identified sets.
    """
    corpus = list(corpus if corpus is not None else trajectories)
    specs: list[tuple[str, bool, bool, bool]] = [
        ("Manski (no assumptions)", False, False, False),
        ("Manski + A1 monotonicity", True, False, False),
        ("Manski + A1 + A2 task-class transfer", True, True, False),
        ("Manski + A1 + A2 + A3 smoothness", True, True, True),
    ]
    rows: list[BoundInterval] = []
    for name, a1, a2, a3 in specs:
        lowers: list[float] = []
        uppers: list[float] = []
        notes_all: list[str] = []
        n_turns = 0
        for tr in trajectories:
            lo, hi, note = _trajectory_success_bounds(
                tr, corpus, a1=a1, a2=a2, a3=a3, lipschitz_k=lipschitz_k
            )
            lowers.append(lo)
            uppers.append(hi)
            n_turns += len(tr.turns)
            if note and note not in notes_all:
                notes_all.append(note)
        # Aggregate: mean of trajectory-level bounds (still an interval).
        # NEVER collapse to a point estimate.
        if not lowers:
            lo_m, hi_m = 0.0, 1.0
        else:
            lo_m = sum(lowers) / len(lowers)
            hi_m = sum(uppers) / len(uppers)
        rows.append(
            BoundInterval(
                lower=lo_m,
                upper=hi_m,
                assumption_set=name,
                n_trajectories=len(trajectories),
                n_turns=n_turns,
                notes="; ".join(notes_all) if notes_all else "",
            )
        )
    return rows


def format_bounds_table(rows: Iterable[BoundInterval]) -> str:
    lines = [
        "| assumption set | lower | upper | width | n_traj | notes |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.assumption_set} | {r.lower:.4f} | {r.upper:.4f} | "
            f"{r.width:.4f} | {r.n_trajectories} | {r.notes} |"
        )
    lines.append("")
    lines.append(
        "Intervals only — no point estimate of realizable quality ceiling."
    )
    return "\n".join(lines)
