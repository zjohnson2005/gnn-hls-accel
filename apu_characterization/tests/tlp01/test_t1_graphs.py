"""T1 graph construction on synthetic sessions (no live data)."""

from __future__ import annotations

from pathlib import Path

from apu_characterization.tlp01.extract import (
    make_synthetic_chain_session,
    make_synthetic_parallel_session,
)
from apu_characterization.tlp01.t1_graphs import (
    build_session_graphs,
    graph_to_dict,
    write_session_graphs,
)


def test_build_session_graphs_includes_tier0_when_instrumented() -> None:
    events = make_synthetic_parallel_session(session_id="syn-t1", width=3)
    graphs = build_session_graphs(events)
    assert set(graphs) == {"Tier_0", "Tier_S", "Tier_C"}
    for graph in graphs.values():
        assert graph.is_dag()
        payload = graph_to_dict(graph)
        assert payload["edge_count"] == len(payload["edges"])


def test_null_dep_refs_skip_tier0_graph() -> None:
    events = make_synthetic_chain_session(session_id="syn-s1-style", steps=3)
    # Force S1-style null dep_refs.
    forced = []
    for event in events:
        data = {
            "session_id": event.session_id,
            "seq": event.seq,
            "event_type": event.event_type,
            "t_issue_ns": event.t_issue_ns,
            "t_complete_ns": event.t_complete_ns,
            "inputs_hash": event.inputs_hash,
            "output_hash": event.output_hash,
            "output_text_ref": event.output_text_ref,
            "tool_name": event.tool_name,
            "args_ref": event.args_ref,
            "result_ref": event.result_ref,
            "stage_timings": dict(event.stage_timings),
            "harness_order_index": event.harness_order_index,
            "task_class": event.task_class,
            "seed": event.seed,
            "dep_refs": None,
            "input_text": event.input_text,
            "output_text": event.output_text,
            "result_ids": list(event.result_ids),
            "control_parent_seq": event.control_parent_seq,
        }
        forced.append(data)
    from apu_characterization.tlp01.schema import validate_trace_events

    parsed = validate_trace_events(forced)
    graphs = build_session_graphs(parsed)
    assert set(graphs) == {"Tier_S", "Tier_C"}


def test_replication_s2_load_bearing() -> None:
    from apu_characterization.tlp01.t1_graphs import _replication_by_task_id

    rows = []
    for seed in range(5):
        ev = make_synthetic_parallel_session(session_id=f"s{seed}", seed=seed)
        rows.append(({"source": "S2", "task_id": "MT-X", "seed": seed}, ev))
    # Sparse S1 must not flip load-bearing bit.
    rows.append(
        (
            {"source": "S1", "task_id": "SO-01", "seed": 0},
            make_synthetic_chain_session(session_id="s1", seed=0, steps=2),
        )
    )
    result = _replication_by_task_id(rows, required_seeds=5)
    assert result["t1_load_bearing_pass"] is True
    assert result["S2"]["pass"] is True
    assert result["S1"]["pass"] is False


def test_write_session_graphs(tmp_path: Path) -> None:
    events = make_synthetic_parallel_session(session_id="S2-syn-s0", seed=0, width=3)
    meta = write_session_graphs(
        entry={
            "source": "S2",
            "task_id": "MT-SYN",
            "task_class": "FO",
            "seed": 0,
            "path": "unused.jsonl",
            "trace_sha256": "abc",
        },
        events=events,
        out_dir=tmp_path,
        repo_root=tmp_path,
    )
    assert meta["tier0_status"] == "instrumented"
    assert (tmp_path / "S2-syn-s0" / "Tier_S.json").is_file()
    assert (tmp_path / "S2-syn-s0" / "Tier_0.json").is_file()
