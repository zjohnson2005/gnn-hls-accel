"""error_class, requested_bytes, and the logits allocation pattern."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.alloc_diag import diagnose  # noqa: E402
from tools.run_c1_ceiling import classify_c1_failure  # noqa: E402


def _fail(message: str) -> dict[str, object]:
    return {
        "outcome": "fail",
        "failure_mode": "turn1:RuntimeError",
        "child": {"exception": {"type": "RuntimeError", "message": message}},
    }


def test_logits_allocation_records_bytes_and_pattern() -> None:
    message = "failed to allocate logits buffer: requested 303872 bytes"
    classified = classify_c1_failure(_fail(message))
    assert classified["error_class"] == "memory_wall"
    assert classified["failure_kind"] == "memory_wall"
    assert classified["requested_bytes"] == 303872
    assert classified["alloc_logits_pattern"] is True
    assert diagnose(_fail(message))["alloc_logits_pattern"] is True


def test_primitive_failure_is_not_a_logits_allocation() -> None:
    message = "could not execute a primitive primitive_onednn_base.h:550"
    classified = classify_c1_failure(_fail(message))
    assert classified["error_class"] == "onednn_primitive_failure"
    assert classified["requested_bytes"] is None
    assert classified["alloc_logits_pattern"] is False


def test_pass_has_null_error_class() -> None:
    classified = classify_c1_failure({"outcome": "pass"})
    assert classified["error_class"] is None
    assert classified["requested_bytes"] is None
    assert classified["alloc_logits_pattern"] is False
