"""3D cost-model experiment on the orchestration engine kernel graph."""

import json
from pathlib import Path

from cost_model_3d.experiment import _fmt_table, run_arms
from cost_model_3d.kernel_graph import KernelEdge, KernelGraph, KernelNode
from cost_model_3d.tech import DEFAULT_TECH

OE_ROOT = Path(__file__).resolve().parents[1] / "orchestration_engine"
OUT = Path(__file__).resolve().parent / "out"


def _read_phase2(name):
    path = OE_ROOT / "characterization" / "out" / "phase2" / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def oe_kernel_graph(edge_ops_per_epoch=500, completions_per_epoch=200):
    """graph_mutator / dispatch / completion_intake / scatter with mixed QoR."""
    csynth = _read_phase2("csynth_scatter.json")
    stream = _read_phase2("cosim_stream.json")
    graph_load = _read_phase2("cosim_graph_load.json")
    banked = _read_phase2("cosim_scatter_banked.json")

    fmax = csynth.get("estimated_fmax_mhz") or 404.4
    scatter_cycles = int(
        stream.get("per_transaction_cycles") or stream.get("latency_cycles") or 16
    )
    load_cycles = int(graph_load.get("latency_cycles") or 300)
    banked_cycles = int(
        banked.get("per_transaction_cycles") or banked.get("latency_cycles") or scatter_cycles
    )

    nodes = [
        KernelNode(
            "graph_mutator",
            "memory",
            compute_cycles=load_cycles,
            macs=0,
            mem_bytes=edge_ops_per_epoch * 16,
            bram=32,
            activity=0.4,
        ),
        KernelNode(
            "dispatch",
            "compute",
            compute_cycles=80,
            macs=200,
            mem_bytes=completions_per_epoch * 8,
            luts=1200,
            activity=0.35,
        ),
        KernelNode(
            "completion_intake",
            "compute",
            compute_cycles=40,
            macs=50,
            mem_bytes=completions_per_epoch * 4,
            luts=600,
            activity=0.3,
        ),
        KernelNode(
            "scatter",
            "compute",
            compute_cycles=scatter_cycles,
            macs=scatter_cycles * 4,
            mem_bytes=completions_per_epoch * 12,
            luts=1800,
            bram=16,
            activity=0.55,
        ),
        KernelNode(
            "scatter_banked",
            "compute",
            compute_cycles=banked_cycles,
            macs=banked_cycles * 4,
            mem_bytes=completions_per_epoch * 12,
            luts=2400,
            bram=20,
            activity=0.55,
        ),
    ]

    edges = [
        KernelEdge("graph_mutator", "scatter", edge_ops_per_epoch * 128, 128),
        KernelEdge("completion_intake", "scatter", completions_per_epoch * 32, 32),
        KernelEdge("scatter", "dispatch", completions_per_epoch * 64, 64),
    ]

    g = KernelGraph(nodes=nodes, edges=edges, meta={"seam_tag": "graph_mutator"})
    g.meta["fmax_mhz"] = fmax
    g.meta["note"] = "dispatch/completion_intake cycles are analytical stubs"
    return g


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    graph = oe_kernel_graph()
    results = run_arms(graph, DEFAULT_TECH)
    best_assign = results.pop("_best_assign", None)

    payload = {
        "graph": "orchestration_engine",
        "meta": graph.meta,
        "arms": {k: v.as_row() for k, v in results.items()},
        "best_assign": best_assign,
        "table": _fmt_table(results),
    }
    out_path = OUT / "oe_experiment.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(payload["table"])
    print("Wrote {0}".format(out_path))


if __name__ == "__main__":
    main()
