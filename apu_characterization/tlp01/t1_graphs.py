"""Phase T1: build and serialize dependence graphs from frozen T0 traces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from apu_characterization.tlp01.contracts import TraceEvent, sha256_bytes, sha256_json
from apu_characterization.tlp01.dependence import DependenceTierName, tier_0_edges
from apu_characterization.tlp01.graph import DependenceGraph, build_graph
from apu_characterization.tlp01.labels import find_rung_labels
from apu_characterization.tlp01.schema import load_frozen_trace


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = (
    REPO_ROOT / "apu_characterization/out/tlp01/traces/manifest.json"
)
DEFAULT_OUT = REPO_ROOT / "apu_characterization/out/tlp01/dependence_graphs"
DEFAULT_OUT_V2 = REPO_ROOT / "apu_characterization/out/tlp01/dependence_graphs_v2"


def load_sessions_from_manifest(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], list[tuple[dict[str, Any], list[TraceEvent]]]]:
    """Load frozen traces via T0 manifest paths (append-only store; no edits)."""
    root = repo_root or REPO_ROOT
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: list[tuple[dict[str, Any], list[TraceEvent]]] = []
    for entry in manifest.get("traces") or []:
        path = root / str(entry["path"])
        events = load_frozen_trace(path)
        rows.append((entry, events))
    return manifest, rows


def graph_to_dict(graph: DependenceGraph) -> dict[str, Any]:
    edges = sorted(
        (
            {
                "src_seq": edge.src_seq,
                "dst_seq": edge.dst_seq,
                "kind": edge.kind,
                "tier": edge.tier,
                "reason": edge.reason,
                "edge_class": edge.edge_class,
                "derivation_ref": edge.derivation_ref,
            }
            for edge in graph.edges
        ),
        key=lambda e: (
            e["src_seq"],
            e["dst_seq"],
            e["edge_class"],
            e["kind"],
            e["reason"],
        ),
    )
    class_counts: dict[str, int] = {}
    for edge in edges:
        class_counts[edge["edge_class"]] = class_counts.get(edge["edge_class"], 0) + 1
    return {
        "graph_format": getattr(graph, "graph_format", "tlp01_graph_v2"),
        "session_id": graph.session_id,
        "tier": graph.tier,
        "nodes": graph.nodes,
        "edge_count": len(edges),
        "data_edge_count": sum(1 for e in edges if e["kind"] == "data"),
        "control_edge_count": sum(1 for e in edges if e["kind"] == "control"),
        "edge_class_counts": class_counts,
        "ordering_conservation": getattr(graph, "conservation", {}),
        "is_dag": graph.is_dag(),
        "topological_levels": graph.topological_levels() if graph.is_dag() else None,
        "edges": edges,
    }


def build_session_graphs(
    events: Sequence[TraceEvent],
) -> dict[DependenceTierName, DependenceGraph]:
    tiers: list[DependenceTierName] = ["Tier_S", "Tier_C"]
    if any(event.dep_refs is not None for event in events):
        # Instrumented traces always include Tier-0 (may be empty edge set).
        tiers = ["Tier_0", "Tier_S", "Tier_C"]
    return {tier: build_graph(events, tier) for tier in tiers}


def write_session_graphs(
    *,
    entry: dict[str, Any],
    events: Sequence[TraceEvent],
    out_dir: Path,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or REPO_ROOT
    graphs = build_session_graphs(events)
    session_id = events[0].session_id
    session_dir = out_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Any] = {
        "session_id": session_id,
        "source": entry.get("source"),
        "task_id": entry.get("task_id"),
        "task_class": entry.get("task_class") or events[0].task_class,
        "seed": entry.get("seed", events[0].seed),
        "trace_path": entry.get("path"),
        "trace_sha256": entry.get("trace_sha256"),
        "tiers": {},
    }
    for tier, graph in graphs.items():
        payload = graph_to_dict(graph)
        path = session_dir / f"{tier}.json"
        blob = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if find_rung_labels(blob):
            raise ValueError(f"rung labels leaked into {path}")
        path.write_text(blob, encoding="utf-8")
        try:
            rel = str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            rel = str(path)
        written["tiers"][tier] = {
            "path": rel,
            "edge_count": payload["edge_count"],
            "data_edge_count": payload["data_edge_count"],
            "graph_sha256": sha256_bytes(path.read_bytes()),
        }
    # Coverage note for Tier-0 absence on S1.
    if "Tier_0" not in graphs:
        written["tier0_status"] = "not_instrumented_null_dep_refs"
        written["tier0_edge_count"] = None
    else:
        written["tier0_status"] = "instrumented"
        written["tier0_edge_count"] = len(tier_0_edges(events))
    return written


def _replication_by_task_id(
    rows: list[tuple[dict[str, Any], list[TraceEvent]]],
    *,
    required_seeds: int,
) -> dict[str, Any]:
    """G-R at task_id granularity (S2 is load-bearing for T1; S1 is coverage)."""
    from collections import defaultdict

    by_source: dict[str, dict[str, set[int]]] = {
        "S1": defaultdict(set),
        "S2": defaultdict(set),
    }
    for entry, _events in rows:
        source = str(entry.get("source") or "UNK")
        task_id = str(entry.get("task_id") or "UNK")
        seed = int(entry.get("seed") if entry.get("seed") is not None else 0)
        if source in by_source:
            by_source[source][task_id].add(seed)

    def _summary(bucket: dict[str, set[int]]) -> dict[str, Any]:
        errors = [
            f"{task_id}: {len(seeds)} seeds < required {required_seeds}"
            for task_id, seeds in sorted(bucket.items())
            if len(seeds) < required_seeds
        ]
        return {
            "pass": not errors,
            "errors": errors,
            "seeds_by_task_id": {
                task_id: sorted(seeds) for task_id, seeds in sorted(bucket.items())
            },
            "tasks_meeting_n": sum(
                1 for seeds in bucket.values() if len(seeds) >= required_seeds
            ),
            "tasks_total": len(bucket),
        }

    s1 = _summary(by_source["S1"])
    s2 = _summary(by_source["S2"])
    return {
        "required_seeds": required_seeds,
        "S2": s2,
        "S1": s1,
        # Ceiling source must be fully replicated; S1 sparsity is a known
        # extraction ceiling and does not block T1 graph freeze.
        "t1_load_bearing_pass": s2["pass"],
    }


def run_t1(
    *,
    manifest_path: Path = DEFAULT_MANIFEST,
    out_dir: Path = DEFAULT_OUT,
) -> dict[str, Any]:
    from apu_characterization.tlp01.audit import audit_experiment
    from apu_characterization.tlp01.contracts import load_protocol

    manifest, rows = load_sessions_from_manifest(manifest_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    per_session_meta: list[dict[str, Any]] = []
    sessions = [events for _, events in rows]
    for entry, events in rows:
        per_session_meta.append(
            write_session_graphs(entry=entry, events=events, out_dir=out_dir)
        )

    audit = audit_experiment(sessions, kappa=None)
    required = int(load_protocol()["gates"]["G_R"]["required_seeds"])
    replication = _replication_by_task_id(rows, required_seeds=required)
    # Replace class-aggregated G-R (misleading on mixed S1 yield) with the
    # task_id stratification T2 cells will actually use.
    audit["gates"]["G_R"] = {
        "name": "replication",
        "evaluated": True,
        "pass": replication["t1_load_bearing_pass"],
        "errors": list(replication["S2"]["errors"]),
        "stratification": "task_id",
        "s2": replication["S2"],
        "s1_coverage": replication["S1"],
        "note": (
            "T1 load-bearing G-R is S2 task_id × seed (ceiling source). "
            "S1 coverage is reported but not load-bearing for T1 freeze; "
            "T2 must only band cells with n>=required_seeds."
        ),
    }

    # T1 load-bearing: G-V / G-D / G-A / G-R(S2). G-J demotion expected without κ.
    load_bearing = ("G_V", "G_D", "G_A", "G_R")
    t1_pass = all(audit["gates"][name]["pass"] for name in load_bearing)

    by_source: dict[str, int] = {}
    tier0_sessions = 0
    for meta in per_session_meta:
        src = str(meta.get("source") or "UNK")
        by_source[src] = by_source.get(src, 0) + 1
        if meta.get("tier0_status") == "instrumented":
            tier0_sessions += 1

    index_body = {
        "phase": "T1",
        "t0_manifest_sha256": manifest.get("manifest_sha256"),
        "sessions": len(per_session_meta),
        "by_source": by_source,
        "tier0_instrumented_sessions": tier0_sessions,
        "gates": {
            name: {
                "pass": audit["gates"][name]["pass"],
                "error_count": len(audit["gates"][name].get("errors") or []),
            }
            for name in ("G_V", "G_D", "G_A", "G_R", "G_J")
        },
        "replication": replication,
        "t1_pass": t1_pass,
        "per_session": per_session_meta,
        "note": (
            "T1 produces dependence graphs + gate inventory only. "
            "No M-model counterfactuals, no claim rungs, no phase diagram."
        ),
    }
    index = dict(index_body)
    index["index_sha256"] = sha256_json(index_body)
    blob = json.dumps(index, indent=2, sort_keys=True) + "\n"
    if find_rung_labels(blob):
        raise ValueError("rung labels leaked into T1 index")
    (out_dir / "index.json").write_text(blob, encoding="utf-8")
    (out_dir / "audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return index
