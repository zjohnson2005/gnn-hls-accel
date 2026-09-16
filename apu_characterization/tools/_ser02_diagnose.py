"""SER-02 control-failure diagnosis helpers (ephemeral; see ser02_diagnosis.md)."""

from __future__ import annotations

from pathlib import Path

from apu_characterization.tlp01.dependence import tier_0_edges, tier_c_edges, tier_s_edges
from apu_characterization.tlp01.graph import build_graph
from apu_characterization.tlp01.schedule import (
    simulate_in_order,
    simulate_in_order_work,
    simulate_model,
)
from apu_characterization.tlp01.schema import load_frozen_trace

ROOT = Path(__file__).resolve().parents[1] / "out/tlp01/traces/S2"


def edge_keys(edges):
    return {(e.src_seq, e.dst_seq, e.kind) for e in edges}


def pair_keys(edges):
    return {(e.src_seq, e.dst_seq) for e in edges}


def dump_session(task: str, seed: int) -> None:
    path = ROOT / f"S2-{task}-s{seed}.jsonl"
    events = load_frozen_trace(path)
    t0 = tier_0_edges(events)
    ts = tier_s_edges(events)
    tc = tier_c_edges(events)
    t0p, tsp, tcp = pair_keys(t0), pair_keys(ts), pair_keys(tc)
    print(f"\n===== {task} s{seed} n={len(events)} =====")
    print(
        f"t0={len(t0)} ts={len(ts)} tc={len(tc)} "
        f"t0_subseteq_ts={edge_keys(t0) <= edge_keys(ts)} "
        f"t0_subseteq_tc={edge_keys(t0) <= edge_keys(tc)}"
    )
    for e in sorted(events, key=lambda x: x.seq):
        print("---")
        print(
            f"seq={e.seq} type={e.event_type} tool={e.tool_name} "
            f"dep_refs={e.dep_refs} control_parent={e.control_parent_seq}"
        )
        print(f"  result_ids={e.result_ids} result_ref={e.result_ref}")
        print(f"  INPUT:\n{(e.input_text or '')[:1500]}")
        print(f"  OUTPUT:\n{(e.output_text or '')[:1500]}")
    ordered = sorted(events, key=lambda x: x.seq)
    seqs = [e.seq for e in ordered]
    print("ADJACENT harness pairs:")
    for a, b in zip(seqs, seqs[1:]):
        flags = []
        if (a, b) in t0p:
            flags.append("T0")
        if (a, b) in tsp:
            flags.append("TS")
        if (a, b) in tcp:
            flags.append("TC")
        print(f"  {a}->{b}: {flags or ['NONE']}")
    print("ALL T0:", sorted(t0p))
    print("ALL TS:", sorted(tsp))
    print("ALL TC:", sorted(tcp))
    ts_by = {(e.src_seq, e.dst_seq, e.kind): e.reason for e in ts}
    for e in sorted(t0, key=lambda x: (x.src_seq, x.dst_seq)):
        print(
            f"  t0 {e.src_seq}->{e.dst_seq} kind={e.kind}: "
            f"in_ts={ts_by.get((e.src_seq, e.dst_seq, e.kind), 'MISSING')}"
        )
    for tier in ("Tier_S", "Tier_C"):
        r = simulate_model(events, "M1", tier)
        print(
            f"M1 {tier}: speedup={r.speedup:.4f} "
            f"max_in_flight={r.max_in_flight} makespan={r.makespan_ns}"
        )
    rec = simulate_in_order(events).makespan_ns
    work = simulate_in_order_work(events).makespan_ns
    print(f"recorded_wall={rec} work_serial={work} ratio={rec/max(work,1):.3f}")
    g = build_graph(events, "Tier_S")
    preds = {n: sorted(g.predecessors(n)) for n in sorted(g.nodes)}
    print("Tier_S predecessors:", preds)
    # Independent roots / width: nodes with empty preds among tool_calls
    tools = [e for e in ordered if e.event_type == "tool_call"]
    indep = [e.seq for e in tools if not preds.get(e.seq)]
    print("Tier_S independent tool roots:", indep)


def compare_all(task: str) -> None:
    print(f"\n===== Task2 summary {task} =====")
    all_ok = True
    for seed in range(5):
        events = load_frozen_trace(ROOT / f"S2-{task}-s{seed}.jsonl")
        t0k = edge_keys(tier_0_edges(events))
        tsk = edge_keys(tier_s_edges(events))
        miss = sorted(t0k - tsk)
        if miss:
            all_ok = False
        speeds = {
            tier: simulate_model(events, "M1", tier).speedup
            for tier in ("Tier_S", "Tier_C")
        }
        print(
            f"s{seed}: n={len(events)} t0={len(t0k)} ts={len(tsk)} "
            f"subset_ts={not miss} miss={miss} "
            f"M1S={speeds['Tier_S']:.3f} M1C={speeds['Tier_C']:.3f}"
        )
    print(f"ALL Tier-0 ⊆ Tier-S for {task}: {all_ok}")


def classify_parallel_siblings(task: str = "MT-SER-02") -> None:
    """For each seed: which tool pairs share a parent but have no edge (Branch 3)."""
    print(f"\n===== Parallel siblings under Tier_S ({task}) =====")
    for seed in range(5):
        events = load_frozen_trace(ROOT / f"S2-{task}-s{seed}.jsonl")
        tsp = pair_keys(tier_s_edges(events))
        t0p = pair_keys(tier_0_edges(events))
        tools = sorted(
            [e for e in events if e.event_type == "tool_call"],
            key=lambda e: e.seq,
        )
        # Group by dep_refs parent (first dep) or control parent
        by_parent: dict[int | None, list] = {}
        for e in tools:
            parent = None
            if e.dep_refs:
                parent = e.dep_refs[0]
            by_parent.setdefault(parent, []).append(e)
        print(f"\ns{seed}:")
        for parent, kids in sorted(by_parent.items(), key=lambda x: (x[0] is None, x[0] or -1)):
            if len(kids) < 2:
                continue
            seqs = [k.seq for k in kids]
            print(f"  parent={parent} siblings={seqs} tools={[k.tool_name for k in kids]}")
            for i, a in enumerate(kids):
                for b in kids[i + 1 :]:
                    ab = (a.seq, b.seq) in tsp or (b.seq, a.seq) in tsp
                    ab0 = (a.seq, b.seq) in t0p or (b.seq, a.seq) in t0p
                    print(
                        f"    sibling pair {a.seq}-{b.seq}: "
                        f"TS_edge={ab} T0_edge={ab0}"
                    )


def schedule_detail(task: str, seed: int) -> None:
    events = load_frozen_trace(ROOT / f"S2-{task}-s{seed}.jsonl")
    print(f"\n===== schedule detail {task} s{seed} =====")
    for e in sorted(events, key=lambda x: x.seq):
        print(
            f"  seq={e.seq} type={e.event_type} tool={e.tool_name} "
            f"dur={e.duration_ns} t_issue={e.t_issue_ns} "
            f"t_complete={e.t_complete_ns}"
        )
    work = simulate_in_order_work(events).makespan_ns
    tool_work = sum(
        e.duration_ns for e in events if e.event_type == "tool_call"
    )
    turn_work = sum(e.duration_ns for e in events if e.event_type == "turn")
    print(f"  work={work} tool_work={tool_work} turn_work={turn_work}")
    for tier in ("Tier_S", "Tier_C"):
        g = build_graph(events, tier)
        r = simulate_model(events, "M1", tier)
        print(
            f"  {tier}: speedup={r.speedup:.4f} makespan={r.makespan_ns} "
            f"max_in_flight={r.max_in_flight}"
        )
        print(
            "    preds=",
            {n: g.predecessors(n) for n in sorted(g.nodes)},
        )
        print(
            "    edges=",
            sorted((e.src_seq, e.dst_seq, e.kind) for e in g.edges),
        )
    ts = tier_s_edges(events)
    print(
        "  TS detail:",
        [
            (e.src_seq, e.dst_seq, e.kind, e.reason)
            for e in sorted(ts, key=lambda x: (x.src_seq, x.dst_seq, x.kind))
        ],
    )
    tc = tier_c_edges(events)
    print(
        "  TC-only pairs:",
        sorted(
            set((e.src_seq, e.dst_seq) for e in tc)
            - set((e.src_seq, e.dst_seq) for e in ts)
        ),
    )


def turn_tool_ratios(task: str = "MT-SER-02") -> None:
    print(f"\n===== turn/tool ratios {task} =====")
    for seed in range(5):
        events = load_frozen_trace(ROOT / f"S2-{task}-s{seed}.jsonl")
        turn = sum(e.duration_ns for e in events if e.event_type == "turn")
        tools = sum(e.duration_ns for e in events if e.event_type == "tool_call")
        work = turn + tools
        r = simulate_model(events, "M1", "Tier_S")
        # Counterfactual: add synthetic control edge 0->first tool
        from apu_characterization.tlp01.dependence import DependenceEdge
        from apu_characterization.tlp01.graph import DependenceGraph

        base_g = build_graph(events, "Tier_S")
        first_tool = min(e.seq for e in events if e.event_type == "tool_call")
        # M1 uses break_control=True → only data edges constrain schedule.
        extra = DependenceEdge(
            src_seq=0,
            dst_seq=first_tool,
            kind="data",
            tier="Tier_S",
            reason="diag_turn_to_first_tool",
        )
        patched = DependenceGraph(
            session_id=base_g.session_id,
            tier=base_g.tier,
            events=base_g.events,
            edges=set(base_g.edges) | {extra},
        )
        from apu_characterization.tlp01.schedule import _list_scheduling, simulate_in_order_work

        work_ns = simulate_in_order_work(events).makespan_ns
        patched_r = _list_scheduling(
            patched,
            model="M1",
            width=None,
            charge_orch=False,
            break_control=True,
            baseline_makespan_ns=work_ns,
        )
        print(
            f"s{seed}: turn={turn} tools={tools} turn/work={turn/max(work,1):.3f} "
            f"M1S={r.speedup:.3f} M1S_with_0→{first_tool}={patched_r.speedup:.3f} "
            f"inflight={r.max_in_flight}->{patched_r.max_in_flight}"
        )


def fanout_critical_path(task: str = "MT-SER-02", seed: int = 3) -> None:
    """Explain 1.72x: what runs in parallel under Tier_S."""
    events = load_frozen_trace(ROOT / f"S2-{task}-s{seed}.jsonl")
    g = build_graph(events, "Tier_S")
    r = simulate_model(events, "M1", "Tier_S")
    work = simulate_in_order_work(events).makespan_ns
    print(f"\n===== fanout critical path {task} s{seed} =====")
    print(
        f"speedup={r.speedup:.4f} makespan={r.makespan_ns} work={work} "
        f"max_in_flight={r.max_in_flight}"
    )
    # Independent roots among tools
    tools = [e for e in events if e.event_type == "tool_call"]
    roots = [e.seq for e in tools if not g.data_predecessors(e.seq)]
    print("tool roots (no data preds):", roots)
    # How many code_exec share only parent 2
    kids = [e.seq for e in tools if e.dep_refs == (2,)]
    print(f"code_exec with dep_refs=(2,): n={len(kids)} seqs={kids[:8]}...")
    # Are sibling edges data edges in both directions or chain?
    tsp = pair_keys(tier_s_edges(events))
    chainish = sum(1 for a, b in zip(kids, kids[1:]) if (a, b) in tsp)
    print(f"adjacent sibling TS edges among those kids: {chainish}/{max(len(kids)-1,0)}")
    # Count how many sibling pairs lack ANY TS edge
    missing = 0
    present = 0
    for i, a in enumerate(kids):
        for b in kids[i + 1 :]:
            if (a, b) in tsp or (b, a) in tsp:
                present += 1
            else:
                missing += 1
    print(f"sibling pair TS present={present} missing={missing}")


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if mode == "summary":
        compare_all("MT-SER-02")
        compare_all("MT-SER-01")
    elif mode == "dump":
        dump_session("MT-SER-02", 0)
        dump_session("MT-SER-01", 0)
    elif mode == "detail":
        schedule_detail("MT-SER-02", 0)
        schedule_detail("MT-SER-01", 0)
        fanout_critical_path("MT-SER-02", 3)
        fanout_critical_path("MT-SER-02", 0)
        turn_tool_ratios("MT-SER-02")
        turn_tool_ratios("MT-SER-01")
    elif mode == "siblings":
        classify_parallel_siblings("MT-SER-02")
    else:
        raise SystemExit(f"unknown mode {mode}")
