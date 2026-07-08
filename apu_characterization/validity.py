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
"""

from __future__ import annotations

PUBLISHABLE = "publishable"
DEBUG_ONLY = "debug_only"
AUDIT_FAILED = "audit_failed"
WINDOWS_FOOTNOTE_ONLY = "windows_footnote_only"

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


def artifact_stem(experiment: str, validity: str) -> str:
    """Base filename without extension."""
    if validity in (PUBLISHABLE, AUDIT_FAILED, WINDOWS_FOOTNOTE_ONLY):
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
    return DEBUG_BANNER
