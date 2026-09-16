"""Hard G-R replication floor for T2 banding (task_id × seed, n≥5).

Sparse task_ids are excluded from every banded M1–M5 output and routed to a
separate descriptive-only section. Documentation alone is not a gate.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Sequence

from apu_characterization.tlp01.contracts import TraceEvent, load_protocol

_TASK_ID_FROM_SID = re.compile(
    r"^(?:S[12]-)?(?P<task>.+)-s(?P<seed>\d+)(?:-.*)?$"
)


@dataclass(frozen=True)
class SessionRecord:
    events: tuple[TraceEvent, ...]
    task_id: str
    source: str
    seed: int

    @property
    def session_id(self) -> str:
        return self.events[0].session_id if self.events else ""


def required_replication_seeds() -> int:
    return int(load_protocol()["gates"]["G_R"]["required_seeds"])


def infer_task_id(events: Sequence[TraceEvent]) -> str:
    """Infer task_id from S1-/S2- session_id; else fall back to task_class.

    Synthetic smoke sessions (``syn-FO-s0``) keep ``task_class`` as the key so
    existing gate fixtures continue to band under FO/CN.
    """
    if not events:
        return "UNKNOWN"
    sid = events[0].session_id
    if sid.startswith("S1-") or sid.startswith("S2-"):
        match = _TASK_ID_FROM_SID.match(sid)
        if match:
            return match.group("task")
    return events[0].task_class or sid


def infer_source(events: Sequence[TraceEvent]) -> str:
    sid = events[0].session_id if events else ""
    if sid.startswith("S1-"):
        return "S1"
    if sid.startswith("S2-"):
        return "S2"
    return "SYN"


def records_from_sessions(
    sessions: Sequence[Sequence[TraceEvent]],
) -> list[SessionRecord]:
    records: list[SessionRecord] = []
    for events in sessions:
        if not events:
            continue
        records.append(
            SessionRecord(
                events=tuple(events),
                task_id=infer_task_id(events),
                source=infer_source(events),
                seed=int(events[0].seed),
            )
        )
    return records


def partition_by_replication_floor(
    sessions: Sequence[Sequence[TraceEvent]] | Sequence[SessionRecord],
    *,
    required_seeds: int | None = None,
) -> dict[str, Any]:
    """Split sessions into band-eligible vs sparse-descriptive buckets.

    Behavior (a): task_ids with n < required_seeds are excluded from primary
    banded outputs entirely and listed under ``sparse_descriptive``.
    """
    floor = (
        required_seeds
        if required_seeds is not None
        else required_replication_seeds()
    )
    if sessions and isinstance(sessions[0], SessionRecord):
        records = list(sessions)  # type: ignore[arg-type]
    else:
        records = records_from_sessions(sessions)  # type: ignore[arg-type]

    by_task: dict[str, list[SessionRecord]] = defaultdict(list)
    for record in records:
        by_task[record.task_id].append(record)

    eligible: list[SessionRecord] = []
    sparse: list[SessionRecord] = []
    inventory: list[dict[str, Any]] = []
    for task_id, group in sorted(by_task.items()):
        seeds = sorted({r.seed for r in group})
        n = len(seeds)
        sources = sorted({r.source for r in group})
        entry = {
            "task_id": task_id,
            "n": n,
            "seeds": seeds,
            "sources": sources,
            "session_count": len(group),
            "disposition": (
                "banded" if n >= floor else "sparse_descriptive_excluded_from_bands"
            ),
        }
        inventory.append(entry)
        if n >= floor:
            eligible.extend(group)
        else:
            sparse.extend(group)

    return {
        "required_seeds": floor,
        "eligible_records": eligible,
        "sparse_records": sparse,
        "eligible_sessions": [list(r.events) for r in eligible],
        "sparse_sessions": [list(r.events) for r in sparse],
        "inventory": inventory,
        "sparse_task_ids": [
            row for row in inventory if row["disposition"] != "banded"
        ],
        "eligible_task_ids": [
            row for row in inventory if row["disposition"] == "banded"
        ],
        "behavior": "exclusion_with_separate_section",
    }


def assert_no_sparse_in_bands(
    bands: dict[str, Any],
    sparse_task_ids: Sequence[str],
) -> None:
    """Hard assertion: sparse task_ids must not appear in primary band maps."""
    leaked = sorted(set(bands) & set(sparse_task_ids))
    if leaked:
        raise AssertionError(
            "replication-floor gate violated: sparse task_ids in bands: "
            + ", ".join(leaked)
        )
