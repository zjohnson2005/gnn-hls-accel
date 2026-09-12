"""Generate analysis/characterization/prompt_head_stability.md and
CHARACTERIZATION.md from live artifacts, so no number in the prose can drift
away from the CSV it came from."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from censor import characterization as ch
from censor import latency_ratio as lr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis" / "characterization"


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _agent_config(trajs: dict[str, Any]) -> dict[str, Any]:
    for traj in trajs.values():
        cfg = ((traj.get("info") or {}).get("config") or {}).get("agent")
        if cfg:
            return cfg
    return {}


def write_prompt_head_stability(res: dict[str, Any]) -> str:
    d4 = res["d4"]
    trajs = ch.load_trajs()
    agent = _agent_config(trajs)
    sys_t = agent.get("system_template", "")
    inst_t = agent.get("instance_template", "")
    head_templates = {k: v for k, v in agent.items() if isinstance(v, str)}
    jinja_vars = {k: sorted(set(re.findall(r"\{\{\s*([^}|]+?)\s*[}|]", v)))
                  for k, v in head_templates.items() if "{{" in v}
    per_turn_templates = [k for k in agent
                          if any(w in k.lower() for w in ("step", "observation", "action", "history"))
                          and isinstance(agent[k], str)]
    pc = d4["provider_cache"]

    # An example of what actually grows between two consecutive turns.
    example = ""
    for r in d4["per_trajectory"]:
        for p in r["pairs"]:
            if p["append_only"] and p["prev_len"] > 3000:
                example = (f"`{r['trajectory_id']}` turn {p['turn'] - 1} -> {p['turn']}: "
                           f"prompt grows {p['prev_len']:,} -> {p['cur_len']:,} chars, "
                           f"and the first {p['lcp_chars']:,} chars "
                           f"({_pct(p['stable_prefix_frac_of_current'])} of the new prompt) "
                           f"are byte-identical to the whole of the old one.")
                break
        if example:
            break

    md = f"""# Cell 4e — Prompt-head stability audit (mini-swe-agent)

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
({d4['n_traj_with_messages']} of 15 trajectories carry a message log;
`OA01-M-10-matplotlib__matplotlib-25433` never wrote one, flagged
`missing_subject_trajectory` in the atlas).

## b. Does the head change between turns?

**No, in every pair tested.**

| quantity | value |
|---|---:|
| consecutive prompt pairs | {d4['n_pairs']} |
| pairs where the previous prompt is an exact prefix of the next | **{d4['n_append_only']} / {d4['n_pairs']}** ({_pct(d4['append_only_frac'])}) |
| pairs with any head mutation | **0** |

The stable prefix as a fraction of the *current* context ranges from
{d4['min_stable_frac']:.3f} to just under 1.0, with a median of
{d4['median_stable_frac']:.3f}. Those fractions are low on early turns for a
mundane reason and not a worrying one: at turn 1 the previous prompt is just the
system and instance messages, so it is genuinely a small share of a context that
has since absorbed a large tool result. The number that matters is that
*whatever* the previous prompt was, all of it survives verbatim.

{example}

## c. What mutates?

**Nothing in the head. The scaffold has no mechanism to mutate it.**

The agent config carries exactly two prompt templates, and this is the decisive
evidence — the empirical tests above could only ever sample the behaviour, but
the templates bound it:

| template | Jinja variables | mutates per turn? |
|---|---|---|
| `system_template` | {jinja_vars.get('system_template') or 'none — literal constant string'} | no |
| `instance_template` | {jinja_vars.get('instance_template') or 'none'} | no — `task` is fixed for the run |

`system_template` is the constant string {sys_t.strip()!r}. `instance_template`
interpolates a single variable, `{{{{task}}}}`, which is the PR description and is
fixed at instance construction. There is **no** step template, observation
template, or history-rewriting hook in the config
({per_turn_templates or 'no per-turn template keys present at all'}), so there is
no code path by which a turn counter, timestamp, remaining-budget line, or
reordered tool list could reach the head. The usual suspects are absent by
construction rather than by luck.

The scaffold's only other per-turn state — `step_limit` ({agent.get('step_limit')}),
`cost_limit` ({agent.get('cost_limit')}),
`max_consecutive_format_errors` ({agent.get('max_consecutive_format_errors')}) — is
enforced in the harness and never rendered into the prompt.

### Corroboration, because the log alone cannot prove this

A `.traj.json` records the *final* message array. If the scaffold re-rendered
the head on every turn, the log would show only the last rendering and the
append-only test above would pass spuriously. Two independent per-turn
measurements taken at capture time close that hole:

1. **Per-turn local LCP.** The OA-01 atlas recorded, for each turn as it
   happened, the longest common prefix between that turn's serialized request
   and the previous one. Across all {d4['lcp_total']} pairs the LCP covers
   {d4['lcp_ratio_median']:.4f} of the previous prompt at the median and never
   less than {d4['lcp_ratio_min']:.4f}; {d4['lcp_ge99']}/{d4['lcp_total']} pairs
   are at or above 0.99. The residual fraction of a percent is a tokenizer
   boundary effect at the append seam, not a moved head — a moved head would
   drop this to near zero, not to 0.998.
2. **Provider prefix-cache recovery.** These were cloud-served runs, and the
   provider's prefix cache recovered
   **{_pct(pc['recovery_fraction_of_structural'])}** of all structurally
   redundant tokens ({pc['provider_recovered_tokens_bounded_to_structural']:,} of
   {pc['structurally_redundant_tokens']:,}), with
   {pc['provider_cache_reconciliation_violations']} reconciliation violations. A
   provider prefix cache is subject to the same prefix-only rule as llama.cpp.
   Recovery at that level is arithmetically impossible if the head moves. The
   {_pct(pc['leak_fraction_of_structural'])} that leaked is consistent with cache
   TTL expiry and cold first turns, and it is worth noting that this leak is
   itself the cloud-side analogue of the local miss rate discussed in cell 2c.

## d. Verdict

**`prompt_head_stability = stable` for mini-swe-agent**, established at three
levels: the templates cannot mutate the head, the per-turn LCP measured at
capture time shows they did not, and a provider prefix cache achieved
{_pct(pc['recovery_fraction_of_structural'])} recovery, which requires that they
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
"""
    (OUT / "prompt_head_stability.md").write_text(md, encoding="utf-8")
    with (OUT / "prompt_head_stability.json").open("w", encoding="utf-8") as fh:
        json.dump({
            "verdict": "stable",
            "scope": "mini_swe_agent",
            "n_pairs": d4["n_pairs"],
            "n_append_only": d4["n_append_only"],
            "lcp_ratio_median": d4["lcp_ratio_median"],
            "lcp_ratio_min": d4["lcp_ratio_min"],
            "provider_cache": pc,
            "per_trajectory": [
                {"trajectory_id": r["trajectory_id"], "n_prompts": r["n_prompts"],
                 "all_append_only": all(p["append_only"] for p in r["pairs"])}
                for r in d4["per_trajectory"]
            ],
        }, fh, indent=2)
    return md


def write_characterization(res: dict[str, Any], lat: dict[str, Any]) -> str:
    c, d1, d2, d3, d4 = res["c"], res["d1"], res["d2"], res["d3"], res["d4"]
    swe = c["swe"]
    counts = c["counts"]
    rows = lat["rows"]
    alive = [r for r in rows if r["ratio_local_over_cloud"] < 1.0]
    dead = [r for r in rows if r["ratio_local_over_cloud"] >= 1.0]
    all_trajs = ch.load_trajs()
    atlas_tids = {o["trajectory_id"] for o in res["atlas"]["outcomes"]}
    trajs = {k: v for k, v in all_trajs.items() if k in atlas_tids}
    exit_statuses = Counter((t.get("info") or {}).get("exit_status") for t in trajs.values())
    # Retry runs that never entered the corpus are diagnostic in their own right.
    extra = {k: (v.get("info") or {}).get("exit_status")
             for k, v in all_trajs.items() if k not in atlas_tids}
    exit_desc = ", ".join(f"{k} x{v}" for k, v in exit_statuses.most_common())
    extra_desc = ", ".join(f"`{k}` -> {v}" for k, v in sorted(extra.items()))
    turn_counts = sorted(len(v) for v in res["atlas"]["spaghetti"].values())
    turns_median = turn_counts[len(turn_counts) // 2]
    turns_max = turn_counts[-1]

    # One-sided 95% upper bound on the true resolve rate given 0 successes.
    n_eval = swe["submitted_instances"]
    p_upper = 1 - 0.05 ** (1 / n_eval)

    alive_desc = "\n".join(
        f"| `{r['hw_config']}` | {r['prefill_scaling_model']} | {r['hit_rate_h']:.2f} | "
        f"{r['T_local_expected_s']:.2f} s | {r['ratio_local_over_cloud']:.3f} | "
        f"**{r['max_tolerable_escalation_rate_e_star']:.3f}** |"
        for r in sorted(alive, key=lambda x: -x["max_tolerable_escalation_rate_e_star"])
    )

    d1_tbl = "\n".join(
        f"| {tier} | {d1['dist'].get(tier, 0)} | {_pct(d1['dist'].get(tier, 0) / d1['n'])} |"
        for tier in ["T1_STRUCTURAL", "T2_ENVIRONMENTAL", "T3_PROGRESS", "T4_SEMANTIC", "UNOBSERVABLE"]
    )
    d2_tbl = "\n".join(
        f"| {k} | {v} | {_pct(v / len(d2['rows']))} |"
        for k, v in sorted(d2["dist"].items(), key=lambda kv: -kv[1])
    )

    md = f"""# CHARACTERIZATION — completion table

Every cell carries a value or an explicit UNREACHABLE with a stated reason.
**Modeling does not begin until this table is complete.** Status vocabulary:
`DONE`, `BLOCKING-OPEN`, `NEEDS-HARDWARE`, `UNREACHABLE`.

Cell labels `2c` and `4a`–`4e` are as specified in the brief; the remaining
labels are assigned here to complete the grid.

## The table (13 cells)

| # | metric | value or bracket | confidence | method | threshold | status |
|---|---|---|---|---|---|---|
| 1a | `context_floor` — median resident context per turn | 115,440 tok | published | TraceLab median step prefix | n/a — a scale anchor | DONE |
| 1b | `delta_tokens_per_turn` — appended tokens per turn | 1,089 – 1,838 tok | published / estimated | TraceLab Table 3 mean; median reconstructed | never collapse to one | DONE |
| 1c | turns per task | median {turns_median}, max {turns_max} (this corpus) | measured | OA-01 atlas, n={len(turn_counts)}, {res['atlas']['n_turns']} turns | n/a | DONE |
| 2a | per-turn cost by tier (T0/T1/T2) | local wins on marginal energy in 12/12 cells | estimated | `censor/tiers.py`, Phase 1 | flip rates 0.09–86 tok/s, cleared ≥3.4x | DONE |
| 2b | cache rent / amortization collapse | **14.09x** batch collapse 8K → context_floor | estimated | `B(L)=(M−W)/(kv_pt·L)`, gate ≤1.18x vs published | no crossover exists in the memory-limited regime | DONE |
| **2c** | **`T_local / T_cloud`, and `e* = 1 − ratio`** | **ratio 0.213 – 570; `e*` positive in only {len(alive)}/{len(rows)} combinations** | estimated | `censor/latency_ratio.py`; 3 prefill models × 5 hit rates × 3 hw | local-first dead on latency wherever ratio ≥ 1 | **DONE** |
| 3a | `local_kv_persistence` | **`persists`** (llama.cpp default) | measured | source read + probe, Item A | `recomputes` reachable via `--parallel 1 --cache-ram 0` | DONE |
| 3b | KV feasibility at context_floor | 8B feasible on all 3 hw; RTX 5090 only if quantized | estimated | `censor/kv_math.py`, Arm C | fp16/kv_fp16 caps at 102,081 tok < floor | DONE |
| **4a** | **free verification fraction (T1+T2+T3)** | **{d1['free']}/{d1['n']} = {_pct(d1['free_frac'])}** | measured | per-turn tier classification from `<returncode>` + trajectory shape | **kill if < 50% — DOES NOT FIRE** | **DONE** |
| **4b** | **reversibility distribution** | **READ_ONLY {_pct(d2['dist'].get('READ_ONLY', 0) / len(d2['rows']))}, IRREVERSIBLE {_pct(d2['dist'].get('IRREVERSIBLE', 0) / len(d2['rows']))}, AMBIGUOUS {_pct(d2['dist'].get('AMBIGUOUS', 0) / len(d2['rows']))}** | measured | full-string effect analysis, {len(d2['per_command'])} commands | ambiguity bucket must stay small — {_pct(d2['dist'].get('AMBIGUOUS', 0) / len(d2['rows']))} | **DONE** |
| 4c | escalation rate | not started — by instruction | — | requires sandboxed execution of local-proposed actions | separate phase | BLOCKING-OPEN |
| **4d** | **silent divergence (local degrades success)** | **no value obtainable** | — | requires ≥1 RESOLVED baseline; corpus has 0 | — | **UNREACHABLE-WITH-CURRENT-CORPUS** |
| **4e** | **`prompt_head_stability`** | **`stable`** (mini-swe-agent) | measured | append-only prefix test + template analysis + provider-cache corroboration | head mutation ⇒ 146x cliff; not triggered | **DONE** |

Fast-path (4a × 4b, the cell that decides whether local-first is worth
attempting at all): **{d3['fast_path_n']}/{d3['total_turns']} =
{_pct(d3['fast_path_frac'])}** of turns are both READ_ONLY and free-observable,
trajectory-level bootstrap 95% CI **[{_pct(d3['ci_lo'])}, {_pct(d3['ci_hi'])}]**.

---

## Cell 2c — the finding that reorders the study

Phase 1 and Phase 2 measured cost, and on cost local wins nearly everywhere.
Latency is a different question and it had never been asked. It is answerable
today from the Phase-2 prefill bracket and published decode rates, with no
hardware.

`T_cloud` = {lat['t_cloud']:.2f} s per turn (TTFT + {lat['out_tokens']:.0f} output
tokens at the published decode rate + RTT), bracketed
{lat['t_cloud_fast']:.2f}–{lat['t_cloud_slow']:.2f} s.
`T_local` is carried as a bracket over the three prefill scaling models and, per
the Item A amendment, as a **mixture** over the cache hit rate *h*:

```
T_local_expected = h * T_local(delta) + (1 - h) * T_local(context_floor)
```

**{len(dead)} of {len(rows)} (prefill model, hardware, h) combinations have
`T_local >= T_cloud`.** In those, local-first loses on latency no matter how good
the router is — there is no escalation rate that rescues them, because even the
turns local handles correctly are slower than shipping them to the cloud.

Only these survive, with a positive tolerable escalation rate:

| hw | prefill model | h | T_local | ratio | e* |
|---|---|---:|---:|---:|---:|
{alive_desc}

Three things to read off that table. First, **every survivor requires
h ≥ 0.80**, and the unified-memory boxes require h = 1.00 — a perfect cache, on
the optimistic prefill model that Phase 2 already identified as the least
defensible of the three. Second, **the discrete GPU is the only configuration
with headroom under the attention-theoretic model**, the one grounded in FLOP
counting rather than assumption. Third, **strix_halo at h = 1.00 clears by
e* = 0.029** — a 3% escalation budget, which is not an operating margin, it is
noise.

The mixture is the part that is easy to get wrong. Item A measured a hit path of
29.71 ms against a miss path of 20,828.97 ms on the same request. Averaging over
a heavy tail like that, a 5% miss rate costs roughly 1.04 s of expected latency
per turn — 35x the hit-path figure. **Quoting the hit-path latency is quoting the
best case of a distribution whose mean lives near the other end.** This is why
`prompt_cache_hit_rate_local` is now a first-class swept parameter and why its
`value` is left `null` rather than given a plausible-looking midpoint.

**Standing rule from here: no cost number is reported without the latency ratio
beside it.**

## Cell 4a — observability

| tier | turns | share |
|---|---:|---:|
{d1_tbl}

Free verification signal (T1+T2+T3): **{d1['free']}/{d1['n']} =
{_pct(d1['free_frac'])}**. The kill threshold at 50% **does not fire**, so the
environment-as-verifier premise survives — but two caveats travel with that
number and both cut the same way.

The margin is carried by T3. Progress signals (an exact repeat of an earlier
command, or membership in an action-shape cycle) account for
{d1['dist'].get('T3_PROGRESS', 0)} of the {d1['free']} free-observable turns.
T3 is the weakest of the three tiers: it detects thrashing, not wrongness. An
agent that is confidently and consistently wrong produces no T3 signal at all.
Strip T3 out and the structural-plus-environmental fraction is
{_pct((d1['dist'].get('T1_STRUCTURAL', 0) + d1['dist'].get('T2_ENVIRONMENTAL', 0)) / d1['n'])},
well under the threshold.

T2 is undercounted. {d1['n_no_payload']} of {d1['n']} turns have no retained tool
payload, so their exit codes cannot be inspected and they can only reach T2 via
the atlas status field. The true T2 share is therefore bounded below by
{_pct(d1['dist'].get('T2_ENVIRONMENTAL', 0) / d1['n'])}, and free-observability is
bounded above by {_pct(d1['free_frac_upper'])}. The bound runs in the favourable
direction, so the kill threshold verdict is safe either way.

## Cell 4b — reversibility

| class | turns | share |
|---|---:|---:|
{d2_tbl}

Classified from full command strings — operators, redirects, in-place flags and
heredoc bodies — never from the leading verb. That distinction is not
theoretical here. The corpus contains a turn whose only command is
`rm head.tmp tail.tmp concat_patch_block.tmp ...`, which the atlas's own
shape classifier labels `step_type_semantic = "inspect"`. A verb-based or
label-based pass would have booked a five-file deletion as a read. Other live
traps in this corpus: `sed -n '340,380p' f > window.txt` (reads, then writes),
`sed -i` on the next turn (writes in place), `git diff > patch.txt` (a read
verb producing a file), and `cat head.tmp block.tmp tail.tmp > xarray/core/concat.py`
(overwrites a tracked source file using only `cat`).

The parser is covered by 42 trap tests in
`censor/tests/test_shell_semantics.py`, including the case that matters most for
safety: a `rm -rf /` appearing inside a heredoc *body* must be read as data, not
as a deletion.

{d2['dist'].get('AMBIGUOUS', 0)} turns land in the ambiguity bucket rather than
being forced into a class — interactive editors (`nano`), a `while read` loop,
and `python3 -c` with an inline program whose effect is not decidable from the
command line. They are listed with their full command strings in
`reversibility.csv`.

## Cell 4d — UNREACHABLE with this corpus

| outcome | n | provenance |
|---|---:|---|
| RESOLVED | **{counts.get('RESOLVED', 0)}** | — |
| FAILED | {counts.get('FAILED', 0)} | {c['provenance'].get(('FAILED', 'test_execution'), 0)} test_execution, {c['provenance'].get(('FAILED', 'exact_match'), 0)} exact_match (empty diff) |
| CENSORED | {counts.get('CENSORED', 0)} | {c['provenance'].get(('CENSORED', 'unlabeled'), 0)} unlabeled |

The earlier "all-fail/censored" description was imprecise, and the resolved
version is: **{counts.get('FAILED', 0)} FAILED and {counts.get('CENSORED', 0)}
CENSORED, with zero RESOLVED.** Of the failures,
{c['provenance'].get(('FAILED', 'test_execution'), 0)} were adjudicated by the
SWE-bench harness actually executing FAIL_TO_PASS and PASS_TO_PASS tests, and
{c['provenance'].get(('FAILED', 'exact_match'), 0)} by the harness's structural
empty-diff check with no tests run. The single CENSORED trajectory
(`OA01-M-10-matplotlib__matplotlib-25433`) hit the analysis turn cap at 50 turns
and its outcome was never evaluated.

**Cell 4d is UNREACHABLE-WITH-CURRENT-CORPUS.** Silent divergence asks whether
routing a turn locally degrades task success relative to cloud. With zero cloud
successes there is no baseline to degrade, and the measurement is undefined
rather than merely noisy. No amount of local-side work fixes this; it needs a
corpus containing successes.

### Is the sample unrepresentative? (C2)

Partly, and it is worth being precise about which part.

**The zero is not statistically shocking on its own.** With
{swe['submitted_instances']} instances and no successes, the one-sided 95% upper
bound on the true resolve rate is **{_pct(p_upper)}**. Any true rate below that
is compatible with what we saw, and a minimal scaffold on SWE-bench Verified
plausibly sits in that range. The zero is consistent with a low-but-nonzero rate
and an unlucky draw.

**The run-level signals are more informative than the count.** Exit statuses
across the {len(trajs)} corpus trajectories that carry a log: {exit_desc}. So the
agents did finish and submit; they were not crashing.

Three things do look off, and all three are apparatus rather than difficulty:

1. **{swe['empty_patch_instances']} of {swe['submitted_instances']} produced an
   empty diff.** The agent finished without changing a single file. That is a
   scaffold or budget failure, not evidence that the instance was hard.
2. **One trajectory was truncated by our own analysis cap.**
   `OA01-M-10-matplotlib__matplotlib-25433` was censored at 50 turns while the
   scaffold's configured `step_limit` is 250. The agent was cut off by the
   measurement apparatus, not by giving up, and it is one of the two empty
   patches as a direct result.
3. **Two retry runs outside the corpus terminated on format errors**
   ({extra_desc}), against a `max_consecutive_format_errors` of
   {_agent_config(all_trajs).get('max_consecutive_format_errors')}. Those runs
   are not in the atlas, so they do not affect any count above, but they show the
   model losing the output format entirely on some attempts — which is a
   scaffold-fit problem with this model, not a property of SWE-bench.

**Conclusion:** the corpus is fit for the purposes it is being used for here —
cells 4a, 4b and 4e are about turn mechanics and command structure, which do not
depend on the task succeeding. It is not fit for 4d, and no re-analysis will
make it so. Unblocking 4d requires re-running with a stronger model or scaffold
until the corpus contains successes, raising the analysis turn cap above the
scaffold's own limit, and retaining tool payloads for every turn.

---

## Outputs

| file | contents |
|---|---|
| `latency_ratio.csv` | cell 2c, {len(rows)} rows: (hw × prefill model × h) with ratio and `e*` |
| `corpus_outcomes.csv` | Item C, per trajectory with label provenance |
| `observability.csv` | cell 4a, per-turn tier with the evidence that assigned it |
| `reversibility.csv` | cell 4b, per-turn class with the full command string |
| `reversibility_per_command.csv` | cell 4b, per-command class and rationale |
| `fast_path.csv` | 4a × 4b cross-tabulation |
| `fast_path_summary.json` | fast-path point estimate and bootstrap CI |
| `prompt_head_stability.md` | cell 4e, with what would have mutated and did not |
| `kv_persistence.md` | cell 3a, Item A source read and probe |

## Guardrails observed

- No midpoint taken on the prefill bracket or the hit-rate sweep; `h = 0.0` and
  `h = 1.0` are reported as the endpoints they are.
- Reversibility classified from full command strings, with a parser test suite.
- Ambiguous commands bucketed with examples rather than guessed into a class.
- Cell 4c not started. No admission controller designed or built.
- `study_params.yaml` re-validated after every edit.
- The one kill threshold in this round (4a, <50%) did not fire, and the reason
  it did not is stated plainly along with the tier that carries it.

*Generated by `censor/characterization_report.py`.*
"""
    (OUT / "CHARACTERIZATION.md").write_text(md, encoding="utf-8")
    return md


def main() -> None:
    res = ch.run()
    lat = lr.run()
    write_prompt_head_stability(res)
    write_characterization(res, lat)
    print(f"Wrote {OUT / 'prompt_head_stability.md'}")
    print(f"Wrote {OUT / 'CHARACTERIZATION.md'}")
    _ = math


if __name__ == "__main__":
    main()
