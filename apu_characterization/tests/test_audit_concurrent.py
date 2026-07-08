"""Batch-level audit gate for concurrent (c>1) real-agent runs."""

from __future__ import annotations

from apu_characterization.audit import audit_real_agent_artifact


def _concurrent_artifact(
    *,
    batch_host_ns: int,
    provenance_residual_ns: int,
    per_session_residual_ns: int,
) -> dict:
    return {
        "config": {"workers": 5, "instr_version": 3, "backend": "openai"},
        "invariant": {
            "limit": 0.15,
            "residual_fraction": 0.0,
            "total_thread_cpu_ns": batch_host_ns,
        },
        "run": {
            "config": {
                "workers": 5,
                "batch_process_cpu_ns": batch_host_ns,
                "instr_version": 3,
            },
            "totals": {
                "instrumented_cpu_ns": batch_host_ns - 10_000_000,
                "thread_cpu_ns": batch_host_ns,
            },
            "provenance_totals": {
                "residual": provenance_residual_ns,
                "step_inferred": 0,
            },
            "per_category": {"RESIDUAL_UNATTRIBUTED": {"cpu_ns": 0}},
            "per_session": [
                {
                    "session_id": "s0",
                    "task_id": "FO-01",
                    "process_cpu_ns": batch_host_ns,
                    "instrumented_cpu_ns": batch_host_ns,
                    "provenance": {"residual": per_session_residual_ns},
                }
            ],
            "per_session_category": {"s0": {}},
        },
        "per_task": {},
        "result_validity": "publishable",
    }


def test_concurrent_batch_audit_passes_despite_high_per_session_residual() -> None:
    batch_ns = 1_000_000_000
    art = _concurrent_artifact(
        batch_host_ns=batch_ns,
        provenance_residual_ns=50_000_000,
        per_session_residual_ns=900_000_000,
    )
    audit = audit_real_agent_artifact(art)
    assert audit["pass"]
    assert not any("FO-01" in v and "residual-provenance" in v for v in audit["violations"])
    assert any("per-session residual checks waived" in w for w in audit["warnings"])


def test_concurrent_batch_audit_fails_on_batch_provenance() -> None:
    batch_ns = 1_000_000_000
    art = _concurrent_artifact(
        batch_host_ns=batch_ns,
        provenance_residual_ns=200_000_000,
        per_session_residual_ns=200_000_000,
    )
    audit = audit_real_agent_artifact(art)
    assert not audit["pass"]
    assert any("batch (workers=5)" in v for v in audit["violations"])
