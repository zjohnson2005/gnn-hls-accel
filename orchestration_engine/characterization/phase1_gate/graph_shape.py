"""Dependency graph shape stats (out-degree distribution)."""

from __future__ import annotations

from dataclasses import dataclass

from orchestration_engine.characterization.langgraph_react.timing import PRESETS
from orchestration_engine.characterization.react_sim import PRESETS as REACT_PRESETS


@dataclass
class GraphShapeStats:
    name: str
    num_nodes: int
    num_edges: int
    max_out_degree: int
    mean_out_degree: float
    p95_out_degree: float
    notes: str


def _stats_from_degrees(name: str, degrees: list[int], notes: str) -> GraphShapeStats:
    if not degrees:
        return GraphShapeStats(name, 0, 0, 0, 0.0, 0.0, notes)
    sorted_d = sorted(degrees)
    n = len(sorted_d)
    p95_idx = min(n - 1, int(0.95 * n))
    return GraphShapeStats(
        name=name,
        num_nodes=n,
        num_edges=sum(sorted_d),
        max_out_degree=max(sorted_d),
        mean_out_degree=sum(sorted_d) / n,
        p95_out_degree=float(sorted_d[p95_idx]),
        notes=notes,
    )


def langgraph_react_chain() -> GraphShapeStats:
    """Typical ReAct loop: agent -> tools -> agent (out-degree 1)."""
    steps = PRESETS["action_heavy"].react_steps
    degrees = [1] * steps + [0]
    return _stats_from_degrees(
        "langgraph_react_chain",
        degrees,
        "Linear ReAct: one successor per LLM/tools step.",
    )


def synthetic_fanout_tree(preset: str = "action_heavy") -> GraphShapeStats:
    """Fan-out tree using react_sim subagent spawn rate as branch factor."""
    p = REACT_PRESETS[preset]
    fanout = max(1, p.timing.subagents_per_step_mean)
    depth = p.steps
    degrees: list[int] = []
    nodes_at_level = 1
    for d in range(depth):
        for _ in range(nodes_at_level):
            deg = fanout if d + 1 < depth else 0
            degrees.append(deg)
        nodes_at_level *= fanout
    return _stats_from_degrees(
        f"synthetic_fanout_{preset}",
        degrees,
        f"Tree fan-out={fanout}, depth={depth} (subagents_per_step_mean from react_sim).",
    )


def high_fanout_planner(num_children: int = 64) -> GraphShapeStats:
    """Stress case: one planner node gates many parallel sub-agents."""
    degrees = [num_children] + [0] * num_children
    return _stats_from_degrees(
        f"planner_fanout_{num_children}",
        degrees,
        "Stress: single node with high fan-out (hardware scatter cost grows).",
    )


def all_graph_shapes() -> list[GraphShapeStats]:
    return [
        langgraph_react_chain(),
        synthetic_fanout_tree("action_heavy"),
        synthetic_fanout_tree("reasoning_heavy"),
        high_fanout_planner(64),
        high_fanout_planner(256),
    ]
