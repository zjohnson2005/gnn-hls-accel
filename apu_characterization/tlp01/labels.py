"""Claim-label discipline: rung_* only on real T0 traces; smoke gets diagnostics."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

DATA_SOURCE_REAL = "real_t0_trace"
DATA_SOURCE_SYNTHETIC = "synthetic_smoke"

RUNG_PATTERN = re.compile(r"rung_[123][ab]\b")

# Internal rung keys → smoke-only diagnostic labels (never rung terminology).
SMOKE_DIAGNOSTIC_BY_RUNG = {
    "rung_1a": "smoke_diagnostic: tlp_exists_shape_in_synthetic_surface",
    "rung_2a": "smoke_diagnostic: taxonomy_shape_in_synthetic_surface",
    "rung_3a": "smoke_diagnostic: near_serial_shape_in_synthetic_surface",
    "rung_1b": "smoke_diagnostic: boundary_detected_in_synthetic_surface",
    "rung_2b": "smoke_diagnostic: boundary_praetor_unclear_in_synthetic_surface",
    "rung_3b": "smoke_diagnostic: no_boundary_in_synthetic_surface",
}


def is_real_trace_source(data_source: str | None) -> bool:
    return data_source == DATA_SOURCE_REAL


def _strip_internal_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            key: _strip_internal_keys(value)
            for key, value in obj.items()
            if key != "internal_rung_key_not_for_publication"
        }
    if isinstance(obj, list):
        return [_strip_internal_keys(value) for value in obj]
    return obj


def find_rung_labels(blob: str) -> list[str]:
    return sorted(set(RUNG_PATTERN.findall(blob)))


def finalize_claim_label(
    claim: Mapping[str, Any],
    *,
    data_source: str,
) -> dict[str, Any]:
    """Attach rung_* only for real T0; otherwise emit smoke_diagnostic only."""
    out = dict(claim)
    out["data_source"] = data_source
    rung = out.get("rung")
    if is_real_trace_source(data_source):
        out["smoke_diagnostic"] = None
        return out
    if not isinstance(rung, str) or rung not in SMOKE_DIAGNOSTIC_BY_RUNG:
        raise ValueError(f"cannot map claim to smoke diagnostic: {rung!r}")
    out["smoke_diagnostic"] = SMOKE_DIAGNOSTIC_BY_RUNG[rung]
    out["internal_rung_key_not_for_publication"] = rung
    out["rung"] = None
    out["name"] = "smoke_diagnostic"
    out["language"] = (
        "SYNTHETIC SMOKE ONLY — not a claim rung. "
        f"Diagnostic: {out['smoke_diagnostic']}"
    )
    return out


def audit_g_smoke_label(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    """G-SMOKE-LABEL: fail if rung_* appears on a non-real data source."""
    data_source = str(aggregate.get("data_source") or "")
    errors: list[str] = []
    found: list[str] = []
    if not is_real_trace_source(data_source):
        # Scan affirmative claim surfaces only — blocked_claims may name the bans.
        scan_parts: list[str] = []
        for claim_key in ("ceiling_claim", "frontier_claim", "claim"):
            claim = aggregate.get(claim_key) or {}
            if isinstance(claim, dict):
                scan_parts.append(json.dumps(_strip_internal_keys(dict(claim)), sort_keys=True))
        blob = " ".join(scan_parts)
        found = find_rung_labels(blob)
        if found:
            errors.append(
                f"G-SMOKE-LABEL: rung labels on non-real source "
                f"({data_source or 'missing'}): {found}"
            )
        for claim_key in ("ceiling_claim", "frontier_claim", "claim"):
            claim = aggregate.get(claim_key) or {}
            if not isinstance(claim, dict):
                continue
            if claim.get("rung"):
                errors.append(
                    f"G-SMOKE-LABEL: {claim_key}.rung must be null on smoke "
                    f"(got {claim.get('rung')!r})"
                )
            diagnostic = str(claim.get("smoke_diagnostic") or "")
            if not diagnostic.startswith("smoke_diagnostic:"):
                errors.append(
                    f"G-SMOKE-LABEL: {claim_key} missing smoke_diagnostic on smoke"
                )
    return {
        "name": "smoke_label_discipline",
        "evaluated": True,
        "pass": not errors,
        "errors": errors,
        "data_source": data_source,
        "rung_labels_found": found,
    }


def assert_no_rung_labels_in_text(text: str, *, context: str) -> None:
    found = find_rung_labels(text)
    if found:
        raise AssertionError(f"{context}: forbidden rung labels {found}")


def assert_no_rung_labels_in_smoke_report(text: str, *, context: str) -> None:
    """Smoke reports may document rung bans below the blocked-claims heading."""
    smoke_body = text.split("## Blocked claims", 1)[0]
    assert_no_rung_labels_in_text(smoke_body, context=context)
