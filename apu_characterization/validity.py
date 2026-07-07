"""Which experiment artifacts are publishable vs debug-only.



Policy (non-negotiable for papers, slides, and findings):



- **publishable** — real LangGraph agent with live OpenAI API decisions,

  audit PASS, Linux-resolution platform (or replication n≥5 with medians/IQR).



- **windows_footnote_only** — OpenAI run on Windows; tick-quantized, not quotable.



- **audit_failed** — accounting assertions failed; do not cite.



- **debug_only** — mock/scripted decision path; instrumentation check only.

"""



from __future__ import annotations



PUBLISHABLE = "publishable"

DEBUG_ONLY = "debug_only"

AUDIT_FAILED = "audit_failed"

WINDOWS_FOOTNOTE_ONLY = "windows_footnote_only"



DEBUG_BANNER = (

    "> **DEBUG ONLY — NOT VALID EXPERIMENTAL DATA.** "

    "This artifact used a mock or scripted decision path (no live OpenAI agent). "

    "Use only to verify instrumentation and invariants. "

    "Do not cite in papers, slides, or findings."

)



PUBLISHABLE_BANNER = (

    "> **Publishable run.** Live OpenAI API agent decisions "

    "(`--backend openai`), audit PASS, Linux-resolution platform (or "

    "replication n≥5). Numbers below may be used in research outputs "

    "subject to denominators and caveats in the report."

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

    return PUBLISHABLE if backend == "openai" else DEBUG_ONLY





def validity_banner(validity: str) -> str:

    if validity == PUBLISHABLE:

        return PUBLISHABLE_BANNER

    if validity == AUDIT_FAILED:

        return AUDIT_FAILED_BANNER

    if validity == WINDOWS_FOOTNOTE_ONLY:

        return WINDOWS_FOOTNOTE_BANNER

    return DEBUG_BANNER


