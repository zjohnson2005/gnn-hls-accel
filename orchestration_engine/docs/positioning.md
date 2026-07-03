# Positioning — agent orchestration unit

## Empty row in the landscape

Score competitors on five axes: custom hardware, agent-orchestration target,
dynamic runtime graph, datacenter scale, coordination first-class.

| System | HW | Agent | Dynamic graph | DC scale | Coord first-class |
|--------|----|-------|---------------|----------|-------------------|
| Task Superscalar / Picos | yes | no | no | partial | yes (wrong regime) |
| Halo, Agent.xpu, Helium | no/partial | yes | no/static | varies | approximated away |
| LangGraph / Plan-Execute-Replan | no | yes | yes | yes | yes |
| NVIDIA Vera / dense CPU | GP-HW | yes | n/a | yes | SW |
| **This project (target)** | **yes** | **yes** | **yes** | **yes** | **yes** |

## What is not novel

- CSR dependency graph + readiness counters + scatter on completion = Picos /
  Task Superscalar (15 years, on RISC-V).
- Dataflow firing / graph scatter = GNN accelerator substrate (FlowGNN, this
  repo's `gcn_layer_stream`).

## What may be novel

1. **Regime:** external tasks at second scale, outstanding-wait dominated (MSHR
   reframe), not microsecond local tasks.
2. **Dynamic graph in hardware:** runtime append, conditional fan-out, prune —
   no prior-art scaffold.
3. **Method:** LightningSim fast DSE to answer *whether* custom hardware beats
   software before silicon.
4. **Coordination nodes** as scheduled entities, not folded into profiled costs
   (contrast Halo).

## Positioning paragraph (paper-ready)

Software agent dispatch splits into two measured regimes: scan-class schedulers
whose per-decision cost grows with the number of **live agents** (measured 59x
from N=10 to N=1000), and event-driven frameworks whose cost is flat but carries
a large constant (LangGraph measured ~1.7 ms/decision; ideal asyncio ~2 µs).
Hardware scatter-on-completion costs grow only with **fan-out** at a ~0.01 µs
constant. We characterize both gaps — complexity class vs scan schedulers,
constant factor + energy vs frameworks — on trace-calibrated tool-heavy agent
graphs, implement the engine in HLS, and use cycle-accurate simulation to
determine whether custom silicon wins in the external, second-scale,
dynamic-graph datacenter regime — without assuming the answer.

## Two hardware targets from real traces

Real OpenAI traces split coordination into per-session **graph setup**
(1.7–3.4 ms/agent; 20–25 pp of accelerable CPU) and **steady-state dispatch**
(250–850 µs/decision; 12–25%). Setup maps to the engine's dynamic graph-load /
append path (novelty claim 2); steady-state maps to scatter-on-completion.
Attacking both makes the dynamic-graph feature load-bearing, not decorative.

## Relationship to prior work in this repo

| Prior repo track | Role after pivot |
|------------------|------------------|
| GNN HLS / hls4ml | Substrate inspiration (CSR, scatter, DATAFLOW) |
| `fifo_pareto/` | Evaluation methodology (LightningSim V2 DSE) |
| `cost_model_3d/` | Optional parallel; not the thesis spine |

## Why hardware, if software can just be fixed?

Deployed LangGraph dispatch measures ~1.7 ms/decision; an ideal event-driven
loop measures ~2 µs — an **850x software-engineering gap**. State this
finding first (it is ours, not a reviewer's objection): the cheapest industry
fix is better software. The hardware case must therefore hold **against the
fixed software**, on grounds software cannot reach:

1. **Energy per decision** — first-order ~10x vs ideal asyncio, ~10^4x vs
   deployed frameworks (see `dynamic_graph_cost_model.md`; csynth pending).
2. **Freeing host cores entirely** — sharded event loops still burn 2–4
   datacenter cores at scale; the engine offloads coordination wholesale.
3. **Deterministic tail latency** — dispatch on dedicated silicon is immune
   to host contention, GC pauses, and noisy neighbors; software p99 is not.
4. **The dynamic-graph load path** — session/graph construction costs
   1.7–3.4 ms per agent in software (measured); the engine's streamed
   append targets ~1 µs (design model). Software pays this too, and no
   event-loop rewrite removes it.

Interface honesty: PCIe-attached, the engine is near parity with
kernel-bypass software per completion (~1 µs both) — the win there is
throughput, energy, and offload. On-SoC integration retains the raw
latency win. Full-path table lives in gate check 11.

## Questions still open (for Callie / GT authors)

1. Is GT/Intel characterization group collaborator or competitor?
2. Is orchestration engine the long-horizon thesis vs near-term Ramulator win?
3. Negative result publishability in target venues?
