"""Each arm begin constructs a new LLMPipeline so CB prefix blocks do not carry over."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.h1_provenance import PREFIX_BLOCK_CLEAR_CALL  # noqa: E402
from tools.run_h1_hybrid import OpenVinoLocalBackend  # noqa: E402


def _stub() -> OpenVinoLocalBackend:
    return OpenVinoLocalBackend.for_stubbed_generate(
        pipe=object(), tokenizer=object(), cfg=object()
    )


def test_stub_reload_counts_and_does_not_load(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_a: object, **_k: object) -> None:
        raise AssertionError("load_arm_pipeline must not run for a stubbed backend")

    monkeypatch.setattr("tools.bfcl_feasibility_probe.load_arm_pipeline", refuse)
    local = _stub()
    assert local.reload_prefix_cache() == PREFIX_BLOCK_CLEAR_CALL
    assert local.reload_prefix_cache() == "ov_genai.LLMPipeline"
    assert local._prefix_reloads == 2


def test_begin_entry_clears_prefix_blocks_before_the_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local = _stub()
    seen: list[int] = []

    def stop(self: OpenVinoLocalBackend) -> str:
        seen.append(int(self._prefix_reloads) + 1)
        raise SystemExit("stop-after-reload")

    monkeypatch.setattr(OpenVinoLocalBackend, "reload_prefix_cache", stop)
    with pytest.raises(SystemExit, match="stop-after-reload"):
        local.begin_entry({"id": "e0"}, policy="slo_escalate")
    assert seen == [1]
