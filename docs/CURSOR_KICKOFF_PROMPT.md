# Cursor kickoff

Two things go in the repo first:

- `docs/SEAM_research_blueprint.md`
- `docs/PHASE_MINUS1_IMPLEMENTATION_SPEC.md`

Then paste the block below. It is deliberately short — the spec carries the detail, and Cursor works better reading a committed file than parsing a wall of pasted text.

---

## Paste this

```
You are implementing the measurement harness for SEAM, a hardware-aware design-space
exploration project at Georgia Tech's Sharc Lab. Read these two files completely before
writing any code:

  docs/SEAM_research_blueprint.md              <- governing research protocol
  docs/PHASE_MINUS1_IMPLEMENTATION_SPEC.md     <- what you are building

Target platform: Dell XPS 16 DA16260, Intel Core Ultra 5 325 (Panther Lake),
4 P-cores + 4 LP-E cores (8 logical CPUs, no SMT), Intel Xe3 iGPU (4 cores),
Intel NPU 5 (50 TOPS INT8 peak), 16 GB LPDDR5X-7467 soldered and unified across
CPU/iGPU/NPU, no discrete GPU, Windows build 26200.

This is scientific instrumentation, not a demo. The blueprint's §5 audit standard is
binding: every number must trace to a run manifest, raw data is write-once, and no
comparison may run before its noise floor is measured.

Work milestone by milestone in the order given in spec §7: M0 -> M1 -> M2 -> M3 -> M4 -> M5 -> M6.
Do not start a milestone until the previous one's acceptance criteria in §7 are met and
you have shown me the evidence. If you believe a milestone can be skipped or reordered,
say so and wait for me rather than proceeding.

Start with M0 only: correct the platform mislabel in analysis/aipc-c1/MACHINE.md
(it says Lunar Lake; the part is Panther Lake), add the discriminating evidence inline,
add the note that the 4+4/8T topology does not discriminate between the two, and append
the finding to AUDIT_LOG.md. Do not touch anything else yet.

Before you begin, list:
  1. Anything in the spec that is ambiguous or that you think is wrong.
  2. Anything in spec §10 (open empirical questions) that you can resolve by reading
     the existing probe artifacts in analysis/ rather than by running new code.
  3. Your proposed choice for the RAPL bridge (LibreHardwareMonitorLib vs Intel PCM)
     and why.

Do not write speculative code for later milestones. Do not silently swallow exceptions.
Do not use heuristics that assume more than 8 logical CPUs.
```

---

## Suggested `.cursor/rules/seam.md`

Persistent guardrails, so they survive context resets:

```
- Governing docs: docs/SEAM_research_blueprint.md, docs/PHASE_MINUS1_IMPLEMENTATION_SPEC.md.
  Re-read the relevant section before implementing.
- raw/ is write-once. Never modify a file under raw/ after its run completes.
  Never edit files under analysis/ except the documented AF-001 correction.
- Every emitted number must be traceable to a run_id manifest. No exceptions.
- Figures read only from derived/. No hardcoded values in plotting code.
- Never report 50 TOPS as achieved NPU throughput, ~120 GB/s as measured bandwidth,
  or 180 TOPS as anything other than a Platform B aggregate. These are unverified
  or peak figures.
- Platform is 8 logical CPUs, no SMT. Never size worker pools by heuristic.
- No silent retries, no silent exception swallowing, no silent fallback between
  execution targets. Fallbacks are logged events.
- Agent harness: only the model endpoint varies between conditions. Per-model prompt
  tailoring is forbidden — it invalidates hypothesis H1.
- Analysis code consumes blinded_label, never condition_label.
- Python 3.11+, full type hints, ruff + mypy clean, pytest for all non-hardware logic.
- Configs are YAML, resolved and hashed into the manifest. No magic numbers in code.
```

---

## Ordering note

M6 (the H1 pilot) runs on cloud endpoints only, so it does **not** depend on M4 or M5. Once M3 passes, M6 and M4 can proceed in parallel — and M6 is the higher priority of the two, because H1 is the hypothesis that decides whether the project's premise holds.

M4's NPU verdict is the other early-value deliverable: it feeds blueprint Gate G0 and risk R1, and because Platform B is the same NPU generation, whatever you learn transfers directly.
