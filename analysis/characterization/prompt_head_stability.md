# Cell 4e — Prompt-head stability audit (mini-swe-agent)

**VERDICT: `prompt_head_stability = stable`.** For this scaffold, the prompt is
append-only. The head never changes between turns, so llama.cpp's prefix-only
reuse applies in full and the `persists` regime measured in Item A is reachable
in practice, not just in principle.

This matters because reuse in llama.cpp is longest-common-prefix and nothing
else (`n_cache_reuse` defaults to 0). One mutated token near the front of the
prompt voids the entire cache with no error and no warning. The Item A probe
measured that cliff at 152.91 ms -> 22,265.27 ms, a factor of 146. So the
question "does the head move?" decides which side of a 146x step this study's
central parameter sits on, and it is answerable from data already on disk.

---

## a. Method

The prompt as assembled at turn *k* is the full message list preceding the *k*-th
assistant message. Each message is serialized (role, content, and any tool-call
name and arguments) and concatenated. For every consecutive pair we test the
strict question — **is the turn *k-1* prompt an exact byte-prefix of the turn *k*
prompt?** — rather than merely measuring similarity. A scaffold that rewrote one
character of the system prompt would pass a similarity test and fail this one.

Source: `apu_characterization/out/oa01/runs/**/*.traj.json`
(14 of 15 trajectories carry a message log;
`OA01-M-10-matplotlib__matplotlib-25433` never wrote one, flagged
`missing_subject_trajectory` in the atlas).

## b. Does the head change between turns?

**No, in every pair tested.**

| quantity | value |
|---|---:|
| consecutive prompt pairs | 252 |
| pairs where the previous prompt is an exact prefix of the next | **252 / 252** (100.0%) |
| pairs with any head mutation | **0** |

The stable prefix as a fraction of the *current* context ranges from
0.182 to just under 1.0, with a median of
0.966. Those fractions are low on early turns for a
mundane reason and not a worrying one: at turn 1 the previous prompt is just the
system and instance messages, so it is genuinely a small share of a context that
has since absorbed a large tool result. The number that matters is that
*whatever* the previous prompt was, all of it survives verbatim.

`OA01-M-03-pydata__xarray-3364` turn 0 -> 1: prompt grows 5,248 -> 19,670 chars, and the first 5,248 chars (26.7% of the new prompt) are byte-identical to the whole of the old one.

## c. What mutates?

**Nothing in the head. The scaffold has no mechanism to mutate it.**

The agent config carries exactly two prompt templates, and this is the decisive
evidence — the empirical tests above could only ever sample the behaviour, but
the templates bound it:

| template | Jinja variables | mutates per turn? |
|---|---|---|
| `system_template` | none — literal constant string | no |
| `instance_template` | ['task'] | no — `task` is fixed for the run |

`system_template` is the constant string 'You are a helpful assistant that can interact with a computer shell to solve programming tasks.'. `instance_template`
interpolates a single variable, `{{task}}`, which is the PR description and is
fixed at instance construction. There is **no** step template, observation
template, or history-rewriting hook in the config
(no per-turn template keys present at all), so there is
no code path by which a turn counter, timestamp, remaining-budget line, or
reordered tool list could reach the head. The usual suspects are absent by
construction rather than by luck.

The scaffold's only other per-turn state — `step_limit` (250),
`cost_limit` (3.0),
`max_consecutive_format_errors` (3) — is
enforced in the harness and never rendered into the prompt.

### Corroboration, because the log alone cannot prove this

A `.traj.json` records the *final* message array. If the scaffold re-rendered
the head on every turn, the log would show only the last rendering and the
append-only test above would pass spuriously. Two independent per-turn
measurements taken at capture time close that hole:

1. **Per-turn local LCP.** The OA-01 atlas recorded, for each turn as it
   happened, the longest common prefix between that turn's serialized request
   and the previous one. Across all 314 pairs the LCP covers
   0.9998 of the previous prompt at the median and never
   less than 0.9984; 314/314 pairs
   are at or above 0.99. The residual fraction of a percent is a tokenizer
   boundary effect at the append seam, not a moved head — a moved head would
   drop this to near zero, not to 0.998.
2. **Provider prefix-cache recovery.** These were cloud-served runs, and the
   provider's prefix cache recovered
   **94.2%** of all structurally
   redundant tokens (2,669,906 of
   2,835,256), with
   0 reconciliation violations. A
   provider prefix cache is subject to the same prefix-only rule as llama.cpp.
   Recovery at that level is arithmetically impossible if the head moves. The
   5.8% that leaked is consistent with cache
   TTL expiry and cold first turns, and it is worth noting that this leak is
   itself the cloud-side analogue of the local miss rate discussed in cell 2c.

## d. Verdict

**`prompt_head_stability = stable` for mini-swe-agent**, established at three
levels: the templates cannot mutate the head, the per-turn LCP measured at
capture time shows they did not, and a provider prefix cache achieved
94.2% recovery, which requires that they
did not.

**Consequence: the persists-based conclusions of Phases 1 and 2 are NOT voided
for this scaffold.** Every ROBUST row stands, and the `recomputes` branch remains
a swept alternative rather than the realistic default. Had this gone the other
way, `recomputes` would have been the operative case for mini-swe-agent
regardless of how llama.cpp were configured, and the FRAGILE rows would have
become the headline.

### What this does not license

The verdict is scaffold-specific and does not generalize. It says nothing about
scaffolds that inject a memory block, re-rank tools by recent usage, stamp the
system prompt with the date, or compact history in place — all common, all fatal
to prefix reuse, all invisible in the parameter set until this cell existed.
`prompt_head_stability` therefore stays a swept axis in `study_params.yaml` with
`stable` measured only for `mini_swe_agent`.

It also does not remove the cache-capacity problem. A stable head guarantees the
prefix is *reusable*; it does not guarantee the prefix is still *resident*. With
`cache_ram_mib` at its 8,192 default and roughly 1 GiB per entry at
context_floor, FIFO eviction still governs the hit rate. Cell 2c treats the two
separately for that reason.

### A note on where the discipline came from

TraceLab measured cloud-served agents, and cloud-served agents are built around
provider prefix caching because mutating the head costs real money on the
invoice. Local agents have never faced that pressure — a local cache miss shows
up as latency, not as a line item, and until this measurement nobody had priced
it. The required discipline is identical on both sides. mini-swe-agent happens to
satisfy it, and the evidence here suggests that is a consequence of the scaffold
being minimal rather than of anyone having optimized for the local case.

---

*Generated by `censor/characterization_report.py`. Per-pair data in
`prompt_head_stability.json`.*
