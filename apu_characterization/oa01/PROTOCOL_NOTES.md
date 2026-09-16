# OA-01 protocol notes

## Subject lock

- Subject: `SWE-agent/mini-swe-agent`
- Commit: `388da74aad620a384ab47669b17c52133e30e7c3`
- Commit date: 2026-07-14
- Main model routing: `openai/gpt-4.1`
- Smoke model routing: `openai/gpt-4o-mini`
- Workload: `princeton-nlp/SWE-bench_Lite`, full `test` split
- Environment: mini-SWE-agent's shipped Docker SWE-bench environment

The subject is installed from the pinned upstream commit. No subject source is
vendored or patched. The only configuration additions are the selected model
and `model.model_kwargs.api_base` pointing to the transparent local proxy.

The shipped `swebench.yaml` supplies prompts, observation formatting,
sampling parameters, tool schema, action behavior, environment timeout, and
native stops. OA-01 does not override them.

## Defaults observed at the lock

At the pinned commit, the shipped benchmark configuration contains:

- `agent.step_limit: 250`
- `agent.cost_limit: 3.0`
- environment command timeout: 60 seconds
- `model.model_kwargs.drop_params: true`
- `model.model_kwargs.parallel_tool_calls: true`
- no temperature, top-p, or seed override

The OA-01 50-turn and 60-minute windows are external observation caps. Hitting
one interrupts the parent subject process and records `censored=true`; it is
not converted to an agent failure. The subject's own native stop may occur
first and remains the authentic outcome.

## Boundary architecture

1. A byte-relaying OpenAI-compatible proxy archives exact bodies, timestamps,
   usage, and provider cache fields. Authorization is forwarded but only a
   digest is archived. Wire bodies may be gzip-compressed; the archive keeps
   those bytes unchanged and decompresses only a parse copy for usage/JSON.
2. `MSWEA_DOCKER_EXECUTABLE` points to an executable observer that invokes the
   real Docker CLI with the original argv and inherited stdio. The subject
   implementation is unchanged.
3. A nonblocking external sidecar snapshots image/git state after each observed
   `docker exec`.
4. All decompositions and taxonomy fields are regenerated offline from raw
   boundary logs and the subject's own trajectory JSON.

## Authenticity-induced timing limitation

The pinned `LitellmModel` is nonstreaming by default. Forcing upstream
streaming would change the subject's provider request and is prohibited.
Therefore nonstreaming calls retain total API-boundary time and first/last byte
timestamps, but do not claim separate cloud prefill/decode/network times. See
`SCHEMA.md`.

The requested decomposition is still complete at the boundary level:
API span + tool span + `t_orch_gap_ms`. The finer model-internal split is null
when the unmodified subject does not expose it.

## Pre-registration

Sampling seed: `20260716`.

Algorithm: sort the full Lite test split by `instance_id`, then evaluate
`random.Random(20260716).sample(population, 15)`. The resulting immutable list
and row hashes are in `task_manifest.json`; its canonical SHA-256 is copied
into `protocol_oa01_v1.json` before any live launch.

Task orders 0–2 are the gpt-4.1 pilot. Orders 3–14 are main. Smoke uses order 0
on gpt-4o-mini and is an instrumentation trajectory, not one of the 15 atlas
rows. Every smoke attempt is retained even though the smoke may be repeated
after instrumentation fixes.

## Local Docker image cache (ops, not subject config)

The subject requests `docker.io/swebench/sweb.eval.x86_64.<id>:latest` names
unchanged. On hosts where Docker Hub blob pulls fail (observed with Docker
Desktop `UseContainerdSnapshotter=true`), operators may pre-pull equivalent
images from Epoch's public GHCR registry and retag them to the official names
via `python -m apu_characterization.oa01.prepull_images`. That is a local
cache fill only; the agent is not redirected to another registry.

## Budget ladder

- Smoke phase: one task/attempt, `$1` phase flag, 15-turn cap.
- Pilot phase: three tasks, `$5` phase flag, full caps.
- Main phase: remaining twelve tasks.
- Per-trajectory anomaly: `$4`, log immediately and continue.
- Arm hard flag: `$50`; stop launching, never terminate the in-flight task for
  budget alone.
- Main launch gate: exactly three retained pilot trajectories and pilot mean
  cost no greater than `$3.00` (2× the preregistered upper estimate).

The append-only ledger prints trajectory and cumulative spend after every
completion.

## Outcome and evaluation

A submitted patch is not called a success. Success is assigned only from the
official SWE-bench evaluator for the frozen task. Crash, empty patch, evaluator
error, native limit, and external censoring remain distinct outcomes.

## Honest scope (frozen report text)

One scaffold, one model, one benchmark, n=15. “Typical” means
typical-of-this-configuration. Report the censored count. Orchestration is
gap-derived and coarse. Sampling is nondeterministic. Provider caching and its
usage fields are cloud-specific. No result from OA-01 is a universal agent,
model, benchmark, or local-hardware claim.

