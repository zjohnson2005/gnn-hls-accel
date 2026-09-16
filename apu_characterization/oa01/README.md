# OA-01 — authentic end-to-end agent trace

OA-01 observes pinned, unmodified mini-SWE-agent at API and Docker process
boundaries. It is not TurnTrace Layer 1 and has no statistical-power N claim.

## Locked inputs

- Protocol: `protocol_oa01_v1.json`
- Subject: mini-SWE-agent commit
  `388da74aad620a384ab47669b17c52133e30e7c3`
- Tasks: `task_manifest.json` (15 of 300 SWE-bench Lite test tasks, seed
  `20260716`)
- Main model: gpt-4.1 with subject/provider sampling defaults

## Linux/WSL2 workflow

```bash
make oa01-bootstrap
make oa01-gate
make oa01-smoke
# Inspect smoke audit and replay bundle before proceeding.
make oa01-pilot
# Main refuses to launch unless pilot count/cost gate passes.
make oa01-main
make oa01-evaluate
make oa01-atlas
```

The runner is sequential. Every launched pilot/main task gets one immutable run
directory. It refuses re-rolls. Smoke retries use explicit attempt numbers and
all attempts remain archived.

## Important limitation

The pinned subject calls LiteLLM nonstreaming. OA-01 does not force streaming.
API total time, tool time, and gap-derived orchestration are valid; separate
prefill/decode/network fields are null unless an unmodified subject request
actually exposes a valid streaming/provider timing isolate. See `SCHEMA.md`.

## Output

- Raw corpus: `apu_characterization/out/oa01/runs/` (ignored, retain/archive)
- Budget ledger: `apu_characterization/out/oa01/budget_ledger.jsonl`
- Official evaluation: `apu_characterization/out/oa01/evaluation/`
- Deliverable: `OA01_behavioral_atlas.md` and
  `OA01_behavioral_atlas.json`

