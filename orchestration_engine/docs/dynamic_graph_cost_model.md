# Dynamic graph cost model (paper design, pre-HLS)

The setup-as-graph-construction reframe makes the dynamic-graph path
load-bearing, so it needs numbers. Scatter-on-completion is measured (csynth
415.6 MHz, cosim 17 cycles one-shot / 3 inner); append, prune, and capacity
rows below remain design targets until graph-load HLS lands.

## Node record layout (on-chip)

| field | bits | purpose |
|-------|------|---------|
| pred_remaining | 8 | readiness counter (fan-in ≤ 255) |
| fire_mode + state | 8 | all-of / any-of / threshold, live/fired/pruned |
| succ_offset | 24 | index into edge pool |
| succ_count | 8 | out-degree (v1 flat scope ≤ 8; batch ≤ 64) |
| result_handle | 32 | host DRAM pointer for payload (payload never on-chip) |
| agent_id / graph_id | 16 | multi-tenant tag |
| **total** | **96 (12 B)** | |

Edges: 24-bit node index each (3 B), stored in a segmented free-list pool so
append never compacts live rows.

Per-node on-chip cost with ReAct-like mean out-degree ~1.5:
**12 B + 1.5 × 3 B ≈ 16.5 B/node** (round to 20 B with free-list overhead).

## Operation cost model (cycles)

| op | cycles | mechanism |
|----|--------|-----------|
| append node | ~4 | free-list pop, write record, init counter |
| append edge | ~1/edge | write into segmented succ pool |
| scatter on completion | **3 measured inner** (fan-out=2); **17 cosim one-shot** @ 415.6 MHz (ap_ctrl_hs) | pred decrement per successor (v1) |
| prune subtree | ~2/node lazily | mark-dead bit; reclaim on free-list sweep |
| session load (50-node graph) | ~250–400 | streamed append, ~13 B/cycle at 128-bit AXI |

Key: **session load ≈ 1 µs vs measured 1.7–3.4 ms in LangGraph** — the
setup slice is a ~10³ constant-factor target, same shape as the dispatch
argument. Prune is lazy (mark + background sweep) so it never blocks the
scatter path; compaction is avoided entirely by the segmented free list at
the cost of ~25% pool overhead (included in the 20 B/node figure).

## Capacity (does c=1000 fit on-chip?)

Assume 50 live nodes per agent (generous for ReAct; planner trees larger).

| part | on-chip SRAM | nodes @ 20 B | agents @ 50 nodes |
|------|--------------|--------------|-------------------|
| xczu3eg (edge, 7.6 Mb BRAM) | 0.95 MB | ~47K | **~950** |
| xcvu9p (Alveo U200-class, 43.3 Mb BRAM + 270 Mb URAM) | ~39 MB | ~1.9M | **~39K** |
| Versal / U55C-class (+HBM) | ≥40 MB SRAM | ≥2M | ≥40K |

Conclusion: **c=1000 fits even on the edge part**; datacenter parts hold
tens of thousands of agents on-chip. No spill hierarchy is needed for the
claimed regime (c ≤ 5000) on a datacenter part.

## Spill behavior (if exceeded)

If the edge pool spills to DRAM/HBM: successor-list fetch adds one burst
(~100–200 ns) per completion. The claim degrades from
O(fan-out) × 3.3 ns/edge to O(fan-out) × ~150 ns/edge — still 10³ below
LangGraph's measured 1.7 ms constant and comparable to ideal asyncio's 2 µs
only above out-degree ~13. Spill therefore weakens the constant-factor
margin but does not break the complexity claim; counters (hot, 1 B/node)
stay on-chip regardless.

## Energy (first order; scatter csynth measured, power report pending)

- Engine: small kernel at **415.6 MHz csynth Fmax**, est. 1–3 W dynamic → at 10⁶
  decisions/s ≈ **1–3 µJ/decision**; at full-path 1 µs/completion the
  bound is interconnect, not the engine.
- Host core (Zen-class, ~10 W core running the asyncio loop at measured
  2 µs/decision) ≈ **20 µJ/decision**; LangGraph at 1.7 ms/decision ≈
  **17,000 µJ/decision**.

First-order: ~10x energy vs ideal software, ~10⁴x vs deployed framework.
Replace scatter cycles with power report before citing energy externally.

## What this does NOT yet cover

- Graph-load / append / prune cycle counts (needs HLS beyond scatter kernel).
- Contention on the counter banks at >1 completion/cycle (needs cosim).
- Host-side graph-diff protocol for conditional branches (compiler pass).
