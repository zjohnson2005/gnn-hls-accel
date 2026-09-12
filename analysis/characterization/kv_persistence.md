# KV PERSISTENCE VERIFICATION (Item A) — llama.cpp server

> **VERDICT: `persists` CONFIRMED, and it is the DEFAULT.** Not aspirational, not
> opt-in. Every Phase-2 ROBUST row stands. One non-default configuration
> (`--parallel 1 --cache-ram 0`) does degrade to `recomputes`; that combination
> must be avoided, and it is the only one found that loses state.

**Provenance.** Source read at commit `91f8c9c5fb038c086e13e9cd823c29b33b07ba54`
(2026-07-28, "Disable -ffast-math on HIP (#25495)"), shallow clone of
`ggml-org/llama.cpp`. Empirical run on release build **b10155**
(`llama-b10155-bin-win-cpu-x64`), Qwen2.5-0.5B-Instruct Q4_K_M, CPU backend,
8 threads, `-c 16384`, Windows. Raw timings in `kv_persistence_raw.json`;
server logs in `_server_<config>.log`.

---

## A1. SOURCE READING

All line numbers are at the commit above. The server was split into multiple
translation units; the slot/cache logic now lives in `tools/server/server-context.cpp`
and `tools/server/server-task.cpp`, not the old monolithic `server.cpp`.

### Does a slot retain KV state between independent HTTP requests?

**Yes.** State is held in `server_slot::prompt` (`server-context.cpp:216`), a
`server_prompt` owning the token sequence and the corresponding entries in the
llama context's KV memory for that slot's `seq_id`. Nothing in the request
teardown path clears it — `prompt_clear()` (`server-context.cpp:253-262`, which
calls `common_context_seq_rm(ctx_tgt, id, -1, -1)`) is invoked only from the
eviction paths listed below, never at end-of-request.

### Is prefix reuse automatic, opt-in, or absent by default?

**Automatic.** The per-request flag defaults to on:

```53:53:tools/server/server-task.h
bool cache_prompt    = true; // remember the prompt to avoid reprocessing all prompt
```

`server-schema.cpp:528` seeds it from the server-level default, and
`server-context.cpp:3152` gates all reuse on it. A client that sends no
`cache_prompt` field gets reuse.

Three further defaults matter, and all three favour retention:

| setting | default | source | effect |
|---|---:|---|---|
| `n_parallel` (slots) | **4** | `tools/server/server.cpp:151-155` (auto → 4, `kv_unified = true`) | four independent retained prefixes, not one |
| `slot_prompt_similarity` | **0.1** | `common/common.h:687` | route a request to whichever slot shares the longest prefix |
| `cache_ram_mib` | **8192** | `common/common.h:626` | RAM-backed prompt cache survives slot eviction |
| `n_cache_reuse` | 0 | `common/common.h:621` | chunked mid-prompt KV shifting is OFF; only *prefix* reuse works |

`n_parallel = 4` is easy to miss: `common/common.h:458` declares `n_parallel = 1`,
but `common/arg.cpp:1326` sets it to `-1` ("auto") and the server then resolves
auto to 4. Reading only `common.h` gives the wrong answer, and it changed our
first empirical result (see A2).

### What happens on a partial prefix match — full recompute or delta prefill?

**Delta prefill.** The reuse point is a longest-common-prefix computation:

```3152:3154:tools/server/server-context.cpp
if (slot.task->params.cache_prompt) {
    // reuse any previously computed tokens that are common with the new prompt
    n_past = slot.prompt.tokens.get_common_prefix(input_tokens);
```

The slot then truncates its retained state to the common prefix
(`slot.prompt.tokens.keep_first(n_past)`, `server-context.cpp:3352`) and removes
KV beyond that position (`server-context.cpp:3377-3378`). Only tokens after
`n_past` enter the batch. Reuse is therefore **prefix-only**: a change near the
*start* of the prompt discards everything after it, which is why agent
scaffolds that mutate a system header per turn destroy their own cache.

One guard shapes the numbers in A2 — a slot may never prefill zero tokens:

```3343:3346:tools/server/server-context.cpp
if (n_past == slot.task->n_tokens() && n_past > 0) {
    SLT_WRN(slot, "need to evaluate at least 1 token for each active slot ...");
    n_past--;
```

So an exact repeat reuses `N-1` of `N` tokens, never `N`. Observed exactly.

### What triggers eviction or reset?

Five distinct mechanisms, in the order they bite:

1. **Slot reassignment by LRU.** `get_available_slot()`
   (`server-context.cpp:1530-1637`) first tries LCP-similarity selection
   (`:1544-1588`), and if no slot clears the `slot_prompt_similarity` threshold
   it falls back to least-recently-used (`:1591-1612`). The chosen slot's
   contents are overwritten. **This is the main way state dies.**
2. **RAM prompt cache rescue.** Before overwriting, if `update_cache` is set the
   server *saves* the outgoing prompt and tries to *load* a better-matching one
   (`server-context.cpp:1620-1631` → `prompt_save`/`prompt_load` at `:218-251` →
   `server_prompt_cache::load` at `server-task.cpp:1741-1814`). The cache stores
   full sequence state via `llama_state_seq_get_data_ext`. This is what makes
   eviction recoverable rather than fatal. It is skipped entirely when
   `cache_ram_mib == 0` (`server-context.cpp:1345`).
3. **RAM cache eviction.** `server_prompt_cache::update()`
   (`server-task.cpp:1816-1838`) pops oldest entries once the 8 GiB size limit
   or a dynamic token limit is exceeded. FIFO, not LRU.
4. **Context overflow.** Context shift is **off by default**
   (`common/common.h:572`, `ctx_shift = false`). A prompt exceeding `n_ctx`
   returns `ERROR_TYPE_EXCEED_CONTEXT_SIZE` rather than silently discarding
   history (`server-context.cpp:3131-3150`). Under `--context-shift`, the shift
   path drops `n_discard` tokens from the middle and renumbers positions
   (`:2889-2905`), which invalidates any prefix match past the cut.
5. **Memory pressure purge.** `try_clear_idle_slots()`
   (`server-context.cpp:1645-1670`) clears an idle slot outright when the
   unified KV pool cannot fit a new sequence. Only active under `kv_unified`
   (which auto mode turns on).

Also relevant: **context checkpoints**, `n_ctx_checkpoints = 32` per slot with
`checkpoint_min_step = 8192` (`common/common.h:624-625`), give a third partial
restore path (`server-context.cpp:3315`).

---

## A2. EMPIRICAL TEST

Sequence per configuration. `P` is a 5,200-token deterministic filler prompt;
`P+suffix` appends one short line; `U` is an unrelated 5,200-token prompt.

- **R1** `P` — cold baseline
- **R2** `P+suffix` — does it delta-prefill?
- **R3** `U` — unrelated request, to force slot contention
- **R4** `P+suffix` again — did R3 destroy the state?

`reused` is `timings.cache_n` (`server-context.cpp:501`); `prefilled` is
`timings.prompt_n` (`:503`). Raw, not rounded:

| config | step | total tok | reused | prefilled | prompt_ms |
|---|---|---:|---:|---:|---:|
| **default** (4 slots, cache-ram 8192) | R1 cold | 5200 | 0 | 5200 | 22265.27 |
| | R2 +suffix | 5211 | 5199 | **12** | **152.91** |
| | R3 unrelated | 5200 | 0 | 5200 | 22173.98 |
| | R4 +suffix again | 5211 | 5210 | **1** | **39.25** |
| **cache_ram_off** (4 slots, `--cache-ram 0`) | R1 cold | 5200 | 0 | 5200 | 21490.09 |
| | R2 +suffix | 5211 | 5199 | 12 | 127.14 |
| | R3 unrelated | 5200 | 0 | 5200 | 22302.68 |
| | R4 +suffix again | 5211 | 5210 | 1 | 31.42 |
| **parallel2** (`--parallel 2`) | R1 cold | 5200 | 0 | 5200 | 21558.83 |
| | R2 +suffix | 5211 | 5199 | 12 | 147.07 |
| | R3 unrelated | 5200 | 0 | 5200 | 21044.81 |
| | R4 +suffix again | 5211 | 5210 | 1 | 26.26 |
| **parallel1_cacheram_on** (`--parallel 1`) | R1 cold | 5200 | 0 | 5200 | 21230.05 |
| | R2 +suffix | 5211 | 5199 | 12 | 128.55 |
| | R3 unrelated | 5200 | 0 | 5200 | 21954.92 |
| | R4 +suffix again | 5211 | 5210 | **1** | **29.71** |
| **parallel1_cacheram_off** (`--parallel 1 --cache-ram 0`) | R1 cold | 5200 | 0 | 5200 | 21813.12 |
| | R2 +suffix | 5211 | 5199 | 12 | 144.66 |
| | R3 unrelated | 5200 | 0 | 5200 | 21774.37 |
| | R4 +suffix again | 5211 | **0** | **5211** | **20828.97** |

Cold prefill rate is ~234 tok/s (5200 / 22.27 s) on this CPU-only box with a
0.5B model — the absolute rate is irrelevant here, only the ratios are.

### What the numbers say

**R2 is `persists`, unambiguously, in every configuration.** 5,199 of 5,211
tokens reused, 12 prefilled, in 152.91 ms against 22,265.27 ms cold — a **146x
reduction in prefill work**. This is the delta-prefill regime, not recompute.

The 12 prefilled tokens are not the suffix length alone: appending text
re-tokenizes the boundary, so the LCP stops one token short of `P`. Small, but
it is why reuse is 5,199 and not 5,200.

**R4 isolates the eviction question, and the first three configs answered it by
accident.** Default `--parallel` is 4, so `U` in R3 landed on a *different*
slot and never evicted `P`. `--parallel 2` behaves the same. Only
`--parallel 1` creates genuine contention. Forcing it:

- `--parallel 1` alone: R4 still reuses 5,210 of 5,211 in **29.71 ms**. The slot
  *was* overwritten by R3; the **RAM prompt cache restored it**
  (`server-task.cpp:1741`).
- `--parallel 1 --cache-ram 0`: R4 reuses **0** and prefills all 5,211 in
  **20,828.97 ms**. Full recompute — `recomputes`, exactly.

That contrast is a clean isolation: **701x** between the two R4s, differing only
in whether the RAM prompt cache exists. Two independent mechanisms deliver
`persists`, and you have to disable both to lose it.

R4 reuses 5,210 rather than 5,211 because of the min-one-token guard at
`server-context.cpp:3343`, as predicted from the source. The code read and the
measurement agree down to the single token.

---

## A3. VERDICT AND CONSEQUENCE

**The default configuration is in the `persists` regime.** `cache_prompt=true`,
four slots, LCP-based slot routing, and an 8 GiB RAM prompt cache are all on
without any flag. `persists` is descriptive of what people actually run, not
aspirational. **The study is not describing a system nobody runs.**

**Every Phase-2 ROBUST row stands.** The `persists` column was the one carrying
them, and it is the default column.

### What breaks it

`persists` does not require non-default flags. It requires *not* setting a
specific hostile pair:

| configuration | regime |
|---|---|
| default | **persists** |
| `--parallel N` for any N ≥ 1, cache-ram on | **persists** |
| `--cache-ram 0` with ≥ 2 slots | **persists** for slot-resident prefixes; loses cross-slot rescue |
| `--parallel 1 --cache-ram 0` | **recomputes** |

So the honest statement is inverted from what the brief anticipated: `persists`
is not conditional on a configuration choice, but it *is* destroyable by one.
A single-slot server with the RAM cache disabled pays full re-prefill on every
context switch. That is a plausible misconfiguration for someone minimising
memory on a small box — precisely the local-hardware scenario this study is
about — so it belongs on the deployment checklist, not in the assumption set.

### Three caveats that do not change the verdict but bound it

1. **Prefix-only reuse.** `n_cache_reuse = 0` by default, so reuse is strictly
   longest-common-prefix. Any scaffold that mutates the *head* of the prompt per
   turn (rotating timestamp, reordered tool list, injected memory block) throws
   away the entire cache and silently lands in `recomputes` while running a
   `persists` configuration. **This is now the most likely real-world route to
   `recomputes`, and it is a scaffold property, not a runtime property.**
2. **Scale.** Measured at 5.2K tokens on a 0.5B model, not at the 115,440-token
   `context_floor` on a 7–8B model. The *mechanism* is size-independent (LCP over
   a token vector, `llama_state_seq_*` over sequence state), but the RAM cache's
   8 GiB limit is not: at 115K context a 7–8B model's sequence state is on the
   order of a GiB, so the default cache holds only a handful of prefixes and the
   FIFO eviction in `server-task.cpp:1816-1838` will start firing. Untested here.
3. **Single runtime.** llama.cpp only. vLLM, SGLang, Ollama, and MLX have their
   own answers. The parameter stays swept; what changes is that `persists` is now
   `measured` for the runtime most likely to be on a local box, rather than
   `guess` for all of them.

### Parameter file consequence

`local_runtime.local_kv_persistence` should move from `confidence: guess` to
`confidence: measured` **for llama.cpp specifically**, with `persists` recorded
as the default-configuration value and `recomputes` retained as a reachable
misconfiguration plus the prompt-head-mutation failure mode. It remains swept.
