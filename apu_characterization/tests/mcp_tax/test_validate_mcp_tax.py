from __future__ import annotations

from apu_characterization.mcp_tax.contracts import protocol_sha256
from apu_characterization.mcp_tax.validate import validate_mcp_tax


def _artifact() -> dict:
    return {
        "protocol_version": "mcp_tax_v1.5",
        "protocol_sha256": protocol_sha256(),
        "result_validity": "protocol_microbenchmark",
        "platform": "Linux-6.8.0-generic-x86_64",
        "git": {"commit": "abc123", "dirty": "no"},
        "core_pins": {"client": [2], "server": [3], "os_analysis": [0, 1]},
        "software": {"python": "3.12"},
        "kernel_version": "6.8.0-generic",
        "sdk_lock": {"sha256": "a" * 64},
        "certificate": {"sha256": "b" * 64},
        "audit": {
            "pass": True,
            "violations": [],
            "gates": {
                name: {"pass": True, "errors": []}
                for name in ("G1", "G2", "G3", "G4", "G5", "G6", "G7")
            },
            "diffuseness_verdict": {
                "verdict": "deferred_insufficient_population",
                "binding": False,
            },
        },
        "cells": [
            {
                "cell_id": "cell",
                "n": 5,
                "seeds": [0, 1, 2, 3, 4],
                "all_runs_retained": True,
                "coordinates": {"transport": "http_sse_tls_on"},
            }
        ],
    }


def test_native_clean_n5_artifact_passes() -> None:
    assert validate_mcp_tax(_artifact()) == []


def test_publishable_validation_refuses_wsl_dirty_and_underreplicated() -> None:
    artifact = _artifact()
    artifact["platform"] = "Linux-WSL2-microsoft-standard"
    artifact["git"]["dirty"] = "yes"
    artifact["cells"][0]["n"] = 1
    artifact["cells"][0]["seeds"] = [0]
    errors = validate_mcp_tax(artifact)
    assert any("WSL is debug-only" in error for error in errors)
    assert any("not clean" in error for error in errors)
    assert any("n=1" in error for error in errors)


def test_explicit_debug_smoke_allows_debug_wsl_dirty_n1() -> None:
    artifact = _artifact()
    artifact["result_validity"] = "debug_only"
    artifact["platform"] = "Linux-WSL2-microsoft-standard"
    artifact["git"]["dirty"] = "yes"
    artifact["cells"][0]["n"] = 1
    artifact["cells"][0]["seeds"] = [0]
    assert validate_mcp_tax(artifact, debug_smoke=True) == []
