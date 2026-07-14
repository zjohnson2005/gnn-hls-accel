# Open questions (tail-latency / fan-out collaborators)

Plain-language backlog for someone building a Claude Code (or other framework)
adapter around the same audit and turn-path questions.

## 1. FO-01 residual (~7.9%)

On the publishable v3 replication, FO-01 (9-way search fan-out in one LLM turn)
shows median residual ~7.9% of host CPU (per-session values ~6.6-10.7%, all
under the 15% gate). Leading hypothesis: instrumentation overhead under
fan-out (short-lived executor/HTTP threads finishing after the last sample
burst), consistent with the observer-effect finding at high concurrency in the
mock arm (full-mode schedstat bookkeeping dominating on-CPU samples). An
independent measurement on a different agent framework, with the same residual
invariant, would be strong evidence either way.

## 2. Concurrency / THREADPOOL scaling

Unresolved. Live OpenAI ladder blocked on API rate-limit around c=25-50 while
host util stayed ~2%. That is not an active parallel effort for host-bound
N_max; mock saturation / instr_mode work is the substitute track and remains
`debug_only` for CPU-share headlines.

## 3. Best headline finding (verify before citing)

From `out/latency_collapse_promo_report.md` (mock, throttle, n=5, still
`debug_only` - state the mock caveat in every caption):

- Fixed per-turn software/harness cost is roughly scale-invariant across a
  ~200x LLM-latency sweep at c=1.
- **harness_strict** (ORCH_SETUP+ORCH_DISPATCH+TOKENIZATION+SERIALIZATION):
  **3.9-7.0 ms/turn** across scales (table medians).
- **Primary process band** (local retrieve): **7.8-16.0 ms/turn**.
- **Corrected process band** (remote retrieve substitution): **4.2-11.9 ms/turn**.
- **Crossover X range** (cpu/turn >= LLM median wait, c=1): **5.4-8.4 ms**
  (strict lower 5.4, process upper 8.4; both bounds MEASURED).

The promoted bands in `out/latency_collapse_promoted.md` supersede the
exploratory values previously recorded here.

Negligible at multi-second API latencies; dominant as model response time drops
toward tens of ms. Do not quote these as production CPU shares - the LLM is a
seeded sleep; use them as harness-floor / crossover evidence for THIS instrument
under the stated promotion class in `VERIFIABLE_DATA.md`.

## 4. MCP-01 (protocol tax) — pre-registered before bare metal

Debug tier (`fixphase_resmoke_v8`, protocol now `mcp_tax_v1.4`) supports the
shape below; only the 120×5 native matrix promotes it. Sequence: **v9 gap
split → then 120×5**.

### Retired claims (do not revive)

- **TurnTrace "dispatch echo" / DISPATCH dominance as method-dispatch silicon.**
  Died-ledger #6. Client DISPATCH is ~99.5–99.8% `client_call_inter_region_gaps`;
  true protocol dispatch is ~3 µs client / ~4 µs server. The 1.6 ms that made
  DISPATCH "dominant" is ~99.8% inter-region gap fill inside the client call
  boundary. Pattern across iterations: v7 dissolved TRANSPORT dominance; v8
  provenance dissolved DISPATCH dominance. Dominant categories that lack named
  sub-provenance are presumptive gap-fill (G6 now gates this).
- **2–3 ms "floor-class tax" headline.** Majority gap-fill of unknown nature.
  Quoting it before the gap split repeats the Phase-1 39–59% mistake.

### Earned narrative (debug shape only — not citeable)

- Named, provenance-backed protocol work: ~350–450 µs/msg stdio; ~500 µs plain
  SSE; ~1.5 ms TLS SSE (mostly connection-pattern crypto).
- **Front-rank finding:** connection-per-message TLS (~949 µs handshake +
  ~415 µs syscall under v8 throttle). Confirmed in transport code
  (`Connection: close`); labeled deployment-pattern cost, not record crypto.
  Software fix = connection reuse; hardware story = inline TLS. Cannot dissolve
  the way opaque category lumps dissolve — handshake provenance is named work.
- Diffuse residue (~1.6 ms/msg) dominates and is under active attribution.
  Surviving cross-instrument echo candidate with TurnTrace v3.1: **diffuseness**
  (cost smeared between named regions), not dispatch dominance.

### v9 gap-split — candidate mechanisms (locked before data)

Interpretations are pre-registered. Do not decide what the split "means" after
seeing numbers.

| ID | Candidate | Implication if dominant |
|----|-----------|-------------------------|
| (a) | Event-loop scheduling / future-resolution between instrumented regions (FRAMEWORK analog) | Supports diffuseness → hardware-relevant; can't be tuned away as "write a better dispatcher" |
| (b) | Instrumentation cost itself (timers sit at region boundaries) | Shrinks the tax honestly; check against stripped/throttle observer bracket |
| (c) | GC / allocator activity | Reassigns the residue; not protocol silicon |
| (d) | Syscall return-path / buffer management missed by TRANSPORT timers | Reassigns into TRANSPORT or a new named slice |

### Mechanism ID map (v1.4.1)

Instrument keys: `gap_event_loop`, `gap_instrumentation`, `gap_gc`,
`gap_syscall_return`, `gap_unattributed`. Legacy aliases `a_event_loop` /
`b_observer` / `c_gc_allocator` / `d_syscall_return` still normalize on read.

### Evidence log (append-only)

- **2026-07-14 — v1.4.1 instrumentation landed (pre-smoke):** population floor
  (`verdict_min_population`) and G7 live path encoded; binding verdict
  mechanically deferred on seed-0 WSL.
- **2026-07-14 — `fixphase_resmoke_v9` (WSL seed-0, 18 cells, debug_only):**
  - G7 LIVE on all raw full/throttle cells; Σ(a..e)=parent within slack.
  - Binding field: `deferred_insufficient_population` (as required).
  - Pre-v1.5 advisory (historical): incorrectly `refuted` on dominant
    `gap_unattributed` (~51–60%) — classifier bug; population floor prevented
    binding harm. Post-v1.5: same shape → `inconclusive`.
  - Named shape: `gap_syscall_return` ~1.0–2.1 ms/msg (mostly adjacent
    segments pending (d) split inspection); `gap_instrumentation` ~4–8 µs;
    `gap_gc` ≈0; `gap_event_loop` unmeasured (sync raw).
  - **v1.5 amendment decided:** (e)>20% ⇒ inconclusive; confirm/refute over
    (a)–(d) only; per-arm verdicts; (d) measured vs adjacent report split.

### v9 gap-split — conservation (G7, locked before data)

When `message_diagnostics[message_id].gap_decomposition` is present:

- `parent_cpu_ns` is the current `client_call_inter_region_gaps` total for that
  message.
- `mechanisms` maps mechanism IDs → CPU ns.
- **Σ(mechanisms) must equal `parent_cpu_ns` within G3 conservation slack**
  (`max(conservation_floor_ns, conservation_fraction × parent)`).
- Failure → G7 FAIL. A split that silently creates or destroys time is a
  mislabeled decomposition; G7 closes that seam the way G6 closes opaque
  category lumps.

G7 is a no-op (PASS) until a decomposition is present.

### Diffuseness verdict criteria (locked; v1.5 amendment applied)

Working definition (eight words): **cost smeared between named instrumented
regions.**

v9/v1.4 criteria remain for named mechanisms. **v1.5 amendment** (decided
pre-bare-metal after v9 advisory exposed the bug; died-ledger #8):

| Verdict | Condition |
|---------|-----------|
| **confirmed** | Among **named** mechanisms (a)–(d) only: no single one exceeds ~50% of **parent** gap time, contributing named mechanisms ≥3 spanning ≥2 boundaries, **and** `gap_unattributed` ≤ 20% of parent (`unattributed_forces_inconclusive_share`). |
| **refuted** | One **named** mechanism (a)–(d) exceeds ~50% of parent. Concentrated **known** cost is fixable ⇒ not diffuse. |
| **inconclusive** | `gap_unattributed` > 20% of parent (large residual is unmeasured — cannot assert "fixable"), **or** named distribution meets neither confirm nor refute. |

**Do not** treat `(e)` as eligible for the >50% refutation trigger. A dominant
residual is the opposite of concentrated-in-a-known-place.

### Per-arm verdict scoping (pre-registered for 120×5)

- **`reference_sdk`:** answers the TurnTrace-echo question (async framework /
  event-loop diffuseness). `(a)` is measurable here.
- **`raw_jsonrpc`:** synchronous — `(a)` is honestly unmeasured. Answers a
  narrower question: whether a lean sync path still carries smeared residue
  (today's advisory shape points at syscall-adjacent + unattributed, not
  framework machinery). If that shape survives bare metal, a **pre-registered
  possible reading** (not a conclusion) is weight toward parse-on-the-wire /
  boundary-attach (N3) rather than framework elimination.
- **Never pool** raw and SDK cells into one diffuseness verdict.

### (d) sub-provenance (report-layer)

`gap_syscall_return` splits into `measured` (named post-return sites still
inside the gap) vs `adjacent_segments` (relabeled transport-adjacent gap
intervals). Adjacent-dominated (d) is presumptive gap-fill wearing a mechanism
name until measured sites cover it — G6 spirit one level down. e% is always
`100 × (e) / parent`, with parent = `client_call_inter_region_gaps`.

### Other pre-registrations

- **VALIDATE / DFA:** near-zero at flat_5×256 B is expected. Stress =
  `pathological_large` + large payloads. Failure to inflate VALIDATE reweights
  the MPE pitch; that outcome is a pre-registered test.
- **Observer / setup:** n=1 WSL may invert stripped vs throttle; SDK setup
  variance (~3× across re-smokes) needs median+spread on bare metal. SDK−raw
  steady deltas may be mixed-sign — raw may not be lean.
- **G6 provenance coverage (`mcp_tax_v1.4`):** any category >50% of booked
  steady CPU must have named provenance covering ≥80%, else
  presumptive gap-fill / opaque lump (alongside the 95% single-category detector).
- **G7 gap-split conservation:** see above; required on all new aggregates.
- **Sub-millisecond timing floors (frozen before authenticity Axis 1 / v10
  TRANSPORT):** `audit.sub_millisecond_timing` in `protocol_v1.json` — absolute
  half-width **5 µs**, relative ±15%, half-width =
  `max(rel × median, 5000 ns, max IQR)`. Idle Axis 1 ratio gate remains
  `cpu/wall < 5%` (separate). Near-zero G5/G6/G7 denominators are
  `below_measurement_resolution`, not FAIL evidence. Source: CAP-01
  died-ledger #5. See `METHODOLOGY_MCP.md` checked finding + standing principle.
  **G6 (v10):** dominant-category lump / provenance-coverage FAILs are suppressed
  when the category CPU is below `transport_sub_provenance_v10.absolute_half_width_ns`
  (5000 ns); near-zero TRANSPORT named subslices are tagged
  `below_measurement_resolution` in G6 details rather than treated as coverage gaps.
- **v10 Axis 5 / MSG_FRAME definition (stdio raw, instrumented path):** request-side
  `json.loads` of harness-canonical bytes was removed as **inauthentic redundant
  work** (died-ledger #9; authenticity audit Axis 5), not as an independent
  performance cut. **Comparability:** any table comparing v10 stdio MSG_FRAME
  to v9-era 120×5 stdio MSG_FRAME must note this category-definition change —
  a FRAME drop is definitional until stated otherwise.
- **APPLIED (v10.1 + Axis 5 read fix) — G6 95% single-category vs named
  direct work:** Suppress the 95% FAIL only when *directly-timed* named
  provenance share ≥ 0.80 after excluding `g6_gap_fill_provenance`. Pre-fix
  stdio @ 512 KiB: 524 378×1-byte reads vs min 9; post-fix: 9 syscalls, LEAN,
  `transport_read` still ~84% of TRANSPORT. Died-ledger #10 updated.
  See `METHODOLOGY_MCP.md` G6 exemption section.
