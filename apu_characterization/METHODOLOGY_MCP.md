# MCP-01 methodology: controlled protocol-tax microbenchmark

Protocol lock: `mcp_tax_v1.5` (`mcp_tax/protocol_v1.json`).

## Scope and validity

MCP-01 measures host CPU and wait introduced by MCP message handling. It uses
deterministic no-op tools so tool bodies and model decisions cannot enter the
protocol tax. Passing bare-metal results use
`result_validity: protocol_microbenchmark`; WSL2 and unit/smoke results are
`debug_only`.

This class licenses only protocol/transport claims. It does not satisfy the
live-OpenAI policy for agent CPU-share characterization.

## Parallelism doctrine

- Build: independent testbench, instrument, transport, and analysis workstreams.
- Measurement: exactly one cell/seed process pair at a time, guarded by a
  host-wide lock.
- Analysis: process-pool fan-out over immutable completed run directories.

## CPU taxonomy

The six CPU categories are frozen:

1. `MSG_SERIAL`: JSON-RPC construction, encode, decode, and parse.
2. `MSG_VALIDATE`: parameter and result JSON Schema validation only.
   TLS handshake and certificate crypto are **not** booked here.
3. `MSG_FRAME`: stdio, HTTP, and SSE framing.
4. `MSG_TRANSPORT_CPU`: pipe/socket syscall CPU and TLS handshake/crypto path
   (provenance `transport_tls_handshake` for handshake; `transport_syscall`
   for send/recv). This is the crypto/NIC-overlap slice, not DFA validation.
   **HTTP/SSE connection pattern:** the primary SSE transport uses one
   connection per measured message (`Connection: close`). Per-message TLS
   handshake CPU is therefore a property of that connection pattern, not of
   AES-GCM record encryption on a reused session. Connection reuse would move
   handshake into `SESSION_SETUP`.
5. `MSG_DISPATCH`: frozen booking paths —
   - server method lookup / response assembly (`server_process.raw_handle`)
   - client `client_result_dispatch` (`response["result"]` routing)
   - client `client_call_inter_region_gaps` (CPU inside the client call
     boundary not covered by nested SERIAL/FRAME/TRANSPORT/VALIDATE/result
     timers)
   v8 raw throttle: gaps ≈99.5–99.8% of client DISPATCH; true method lookup
   only a few µs/msg. **Retired:** treating this as TurnTrace method-dispatch
   echo (died-ledger #6). **Surviving echo candidate:** diffuseness of
   inter-region residue. v9 gap-split mechanisms **and** diffuseness
   confirm/refute verdicts are pre-registered in `OPEN_QUESTIONS.md` §4 before
   data. Provenance tables keep the gap share inspectable; G6 rejects opaque
   dominant lumps without named provenance; G7 conserves any gap decomposition
   against the parent within G3 slack.
6. `SESSION_SETUP`: connection, initialize/capability exchange, and tools/list.
   Reported as one-time per-cell CPU. Observer pairs and SDK−raw steady deltas
   exclude SESSION_SETUP; setup is compared separately.

Unbooked process CPU is `RESIDUAL`. Blocking, runqueue delay, synthetic tool
delay, and unattributed wait are a separate wall ledger and are never booked
as CPU categories.

CPU regions use `thread_time_ns` and Linux schedstat. `perf_counter_ns` marks
wall envelopes only. Client and server conserve independently; their summed
CPU is a derived protocol-tax quantity, not a cross-process wall identity.

Steady-state category medians in the report are restricted to
`raw_jsonrpc × throttle × tool_count=1` so SDK harness-boundary booking and
server-cheap cells cannot pull the median away from the raw measured path.

### Pre-registered matrix expectations (VALIDATE / DFA)

At flat_5 × 256 B × 1 tool, `MSG_VALIDATE` is expected to remain near-free in
software (~µs–tens of µs). The DFA/automaton claim for VALIDATE is tested on
the `pathological_large` schema and payload axes (up to 512 KiB). If those
cells do not inflate VALIDATE, the honest MPE pitch reweights toward
inter-region diffuseness + connection-pattern crypto + serialization/framing;
VALIDATE is not rescued by narrative after the fact.

### Honest headline discipline (until v9)

Do not quote a 2–3 ms/msg "floor-class tax" while the dominant slice is
gap-fill. Named provenance-backed protocol work at benign points is sub-ms
(stdio ~350–450 µs; plain SSE ~500 µs); TLS SSE ~1.5 ms is mostly
connection-pattern handshake. Front-rank defensible finding today:
connection-per-message TLS. Diffuse residue (~1.6 ms/msg) awaits
attribution. Sequence: v9 gap split, then 120×5.

### Bare-metal validation flags

Before quoting Rung 1 numbers, confirm on the 120×5 native run:

1. Observer pairs: stripped ≤ throttle (or explained); n=1 WSL inversions are not publication evidence.
2. SDK−raw steady deltas may be mixed-sign; profile whether `raw_jsonrpc` is lean.
3. SESSION_SETUP variance: report median + spread (v7→v8 SDK setup swung ~3× at n=1).
4. TLS handshake provenance labeled as connection-per-message tax.
5. VALIDATE stress axes decide the DFA story.
6. DISPATCH/gap provenance remains visible; v9 gap split uses pre-registered mechanisms (a–d) and diffuseness verdict criteria in OPEN_QUESTIONS.
7. No floor-class aggregate quote until gaps are attributed.
8. G7: any present gap_decomposition conserves Σ(sub) ≈ parent within G3 slack.

## Instrument modes

- `throttle`: primary; direct category timers plus endpoint close reconcile.
- `full`: observer-only; additional thread/schedstat sampling.
- `stripped`: process CPU, wall, and messages only; no category hooks.

Full-mode data cannot become a headline source. The paired throttle-minus-
stripped delta is measured on this instrument; the TurnTrace 9.6% value is
not inherited.

## Matrix

Mandatory primary factorial:

- transports: stdio, HTTP POST+SSE TLS on, HTTP POST+SSE TLS off
- payload: 256 B, 4 KiB, 64 KiB, 512 KiB
- schema: flat-5, nested-depth-4, pathological-large
- implementation: pinned reference SDK, raw JSON-RPC
- mode: throttle; tool count: 1

This is 72 cells. Full and stripped are added to a deterministic 20% primary
subsample (30 cells). Tool counts 10/100/1000 are tested at 4 KiB,
nested-depth-4 for each transport and implementation (18 cells): 120 cells,
600 seed runs. Stable streamable HTTP adds 40 cells (160/800).

Each seed executes 20 discarded warm-up calls and 200 measured calls, followed
by a 5 second cool-down. Seeds are 0-4. Primary synthetic delay is zero; a
1 ms delay exists only in smoke to prove delay exclusion.

## Frozen audit gates

- G1 residual: per endpoint and combined residual no greater than 15% of
  process CPU plus `max(15.625 ms, 5%)` cell slack.
- G2 matched pair: canonical logical JSON-RPC request hashes are identical for
  equal seed/coordinates across transports and implementations. Wire framing
  is archived but intentionally differs.
- G3 conservation: categories plus residual equal endpoint process CPU within
  `max(0.5 ms, 5%)`; independently measured busy/wait ledgers conserve each
  endpoint wall envelope within the same tolerance.
- G4 observer: full/throttle/stripped pairs exist for the frozen subsample,
  throttle tax is reported, and full is blocked from promotion.
- G5 determinism: all n=5 seeds remain. Flag when IQR/median exceeds 1 or
  maximum exceeds 3 times median.
- G6 attribution: raw client books ≥3 non-zero categories with MSG_FRAME on
  primary transports; no single category exceeds 95% of booked CPU; any
  category exceeding 50% of booked steady CPU must have non-generic named
  provenance covering ≥80% of that category, else fail as presumptive
  gap-fill / opaque lump (thresholds in `protocol_v1.json` audit block).
- G7 gap-split conservation: when `gap_decomposition` is present on a message,
  Σ(mechanism CPU) equals `parent_cpu_ns` within the same G3 conservation
  slack. Absent decomposition → G7 PASS (no-op until v9). Diffuseness
  confirm/refute is recorded from frozen thresholds; it is not free-form.
  Binding verdicts additionally require `verdict_min_population`
  (≥20 measured messages and ≥3 seeds); below that the field is
  `deferred_insufficient_population` with advisory-only logging.
  `gap_gc` measures CPython cyclic collector via `gc.callbacks` only —
  refcount deallocation is unmeasured and folds into `gap_unattributed`.

Thresholds do not move after measurement. Failures remain in the report with
diagnosis.

## Host requirements

Publication mode requires native bare-metal Linux, clean git, performance
governor, recorded turbo state, quiescent load, and disjoint OS/analysis,
client, and server cores with SMT siblings not split across roles. WSL2 may
run the integration smoke only.

## External references and claim tiers

The 12.4 ms stdio, 23.7 ms HTTP/SSE, and 8.3 ms authentication values from
arXiv:2601.17549 are external anchors and appear only in a separately labeled
comparison section.

- Tier A: direct measured passing cells.
- Tier B: medians/IQR, scaling fits, and SDK-minus-raw deltas derived from
  Tier A.
- Derived: `3.9-7.0 ms + calls_per_turn * MCP_tax`.

The report uses only the pre-registered claim rung supported by the data.
