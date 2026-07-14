"""Which experiment artifacts are publishable vs debug-only.

Policy (non-negotiable for papers, slides, and findings):

- **publishable** — real LangGraph agent with live OpenAI API decisions,
  real open-source tool implementations (sympy/numpy/re/exec), audit PASS,
  Linux-resolution platform (or replication n≥5 with medians/IQR).
  See VERIFIABLE_DATA.md.

- **windows_footnote_only** — OpenAI run on Windows; tick-quantized, not quotable.

- **audit_failed** — accounting assertions failed; do not cite.

- **debug_only** — mock/scripted/synthetic decision path; instrumentation check only.
  Never use for verifiable characterization.

- **protocol_microbenchmark** — controlled deterministic protocol testbench,
  bare-metal Linux, n≥5, clean git, and MCP-01 audit PASS. Quotable only for
  MCP protocol/transport CPU and wait tax, never agent or tool-body shares.

- **capability_scaling** — CAP-01 matched replay of frozen real-model
  candidate pools on bare-metal Linux, n≥5, clean git, and G1-G7 PASS.
  Quotable only for solve rate at fixed budget in the frozen best-of-N task
  population, never as a general intelligence or production CPU-share claim.

- **turn_level_parallelism** — TLP-01 trace-driven limit study. Quotable only
  as Tier-S/Tier-C speedup brackets for traced task classes/harnesses after
  G-V/G-D/G-A/G-R PASS. Never as a point estimate, never as M1-achievable,
  never with Tier-J in the headline.
"""

from __future__ import annotations

PUBLISHABLE = "publishable"
DEBUG_ONLY = "debug_only"
AUDIT_FAILED = "audit_failed"
WINDOWS_FOOTNOTE_ONLY = "windows_footnote_only"
PROTOCOL_MICROBENCHMARK = "protocol_microbenchmark"
CAPABILITY_SCALING = "capability_scaling"
TURN_LEVEL_PARALLELISM = "turn_level_parallelism"

VERIFIABLE_BACKEND = "openai"

DEBUG_BANNER = (
    "> **DEBUG ONLY — NOT VALID EXPERIMENTAL DATA.** "
    "This artifact used a mock, scripted, or synthetic decision path (no live OpenAI agent). "
    "Use only to verify instrumentation and invariants. "
    "Do not cite in papers, slides, or findings. See VERIFIABLE_DATA.md."
)

PUBLISHABLE_BANNER = (
    "> **Publishable run.** Live OpenAI API agent decisions "
    "(`--backend openai`), real open-source tool bodies, audit PASS, "
    "Linux-resolution platform (or replication n≥5). "
    "Numbers may be used in research outputs subject to denominators and "
    "deployment caveats in VERIFIABLE_DATA.md and ATTRIBUTION.md."
)

AUDIT_FAILED_BANNER = (
    "> **AUDIT FAILED — DO NOT CITE.** Accounting assertions failed. "
    "Fix violations before using any numbers from this artifact."
)

WINDOWS_FOOTNOTE_BANNER = (
    "> **Windows footnote only — NOT quotable for headlines.** "
    "Data affected by 15.625 ms thread-time tick quantization. "
    "Re-run on Linux with test_resolution PASS for publishable numbers."
)

PROTOCOL_MICROBENCHMARK_BANNER = (
    "> **Protocol microbenchmark.** Controlled MCP testbench on bare-metal "
    "Linux with deterministic no-op tools, n≥5, clean git, and MCP-01 audit "
    "PASS. Quotable only for protocol/transport CPU and wait tax. It is not "
    "production-agent or tool-compute characterization."
)

CAPABILITY_SCALING_BANNER = (
    "> **Capability-scaling experiment.** Frozen real-model candidate pools "
    "are replayed as matched task-seed streams through measured LangGraph, "
    "Rust, and raw-Python best-of-N loops on qualified bare-metal Linux. "
    "Quotable only for solve rate at fixed budget within the frozen CAP-01 "
    "task population after G1-G7 PASS. Tier D is projection-only."
)

TURN_LEVEL_PARALLELISM_BANNER = (
    "> **Turn-level parallelism limit study.** Trace-driven simulation over "
    "frozen session traces with a Tier-S/Tier-C dependence bracket. Quotable "
    "only as S/C speedup bands for traced task classes after G-V/G-D/G-A/G-R "
    "PASS. M1 is the oracle ceiling, not an achievable claim; M4/M5 are "
    "deployable figures. Tier-J is never headline-load-bearing. Praetor "
    "misprediction penalties are Tier D projection-only."
)


def artifact_stem(experiment: str, validity: str) -> str:
    """Base filename without extension."""
    if validity in (
        PUBLISHABLE,
        PROTOCOL_MICROBENCHMARK,
        CAPABILITY_SCALING,
        TURN_LEVEL_PARALLELISM,
        AUDIT_FAILED,
        WINDOWS_FOOTNOTE_ONLY,
    ):
        return experiment
    return f"{experiment}_debug"


def real_agent_breakdown_stem(backend: str, search_locality: str = "local") -> str:
    """Artifact basename for Experiment 0R (local vs remote-search deployment)."""
    experiment = (
        "real_agent_breakdown"
        if search_locality == "local"
        else "real_agent_breakdown_remote_search"
    )
    return artifact_stem(experiment, validity_for_real_agent_backend(backend))


def validity_for_real_agent_backend(backend: str) -> str:
    return PUBLISHABLE if backend == VERIFIABLE_BACKEND else DEBUG_ONLY


def is_verifiable_backend(backend: str | None) -> bool:
    return backend == VERIFIABLE_BACKEND


def validity_banner(validity: str) -> str:
    if validity == PUBLISHABLE:
        return PUBLISHABLE_BANNER
    if validity == AUDIT_FAILED:
        return AUDIT_FAILED_BANNER
    if validity == WINDOWS_FOOTNOTE_ONLY:
        return WINDOWS_FOOTNOTE_BANNER
    if validity == PROTOCOL_MICROBENCHMARK:
        return PROTOCOL_MICROBENCHMARK_BANNER
    if validity == CAPABILITY_SCALING:
        return CAPABILITY_SCALING_BANNER
    if validity == TURN_LEVEL_PARALLELISM:
        return TURN_LEVEL_PARALLELISM_BANNER
    return DEBUG_BANNER
