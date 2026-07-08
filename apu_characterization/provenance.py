"""Epistemic provenance for CPU category bookings.

Every category total carries one of:

  measured       — direct @timed regions or thread-identity CPU deltas
  step_inferred  — process-time gap assigned by LangGraph step window + node type
  residual       — session-end gap after all other booking (true unattributed)

Headline harness claims must use the **measured** tier only unless a calibration
artifact certifies step-inferred error bounds (see experiments/step_infer_calibration.py).
"""

from __future__ import annotations

from typing import Literal

Provenance = Literal["measured", "step_inferred", "residual"]

MEASURED: Provenance = "measured"
STEP_INFERRED: Provenance = "step_inferred"
RESIDUAL: Provenance = "residual"

PROVENANCE_LABELS: dict[Provenance, str] = {
    MEASURED: "measured (@timed or thread-identity)",
    STEP_INFERRED: "step-inferred (process window → category rule)",
    RESIDUAL: "residual (session-end gap)",
}

# Categories that may appear in step-inferred bookings (heuristic mapping).
STEP_INFER_NODE_CATEGORIES: dict[str, str] = {
    "agent": "CLIENT_HTTP",
    "tools": "FRAMEWORK",
}
