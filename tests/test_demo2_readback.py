"""DEMO-2 readback: loads with no properties, reports defaults, writes nothing."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import demo2_readback  # noqa: E402


class _Core:
    def get_property(self, device: str, name: str) -> Any:
        return {
            "SUPPORTED_PROPERTIES": ["KV_CACHE_PRECISION", "FULL_DEVICE_NAME"],
            "KV_CACHE_PRECISION": "<Type: 'int8_t'>",
            "FULL_DEVICE_NAME": "Fake Arc",
        }[name]


def _fakes(calls: list[tuple[str, tuple, dict]]) -> tuple[Any, Any]:
    ov = types.SimpleNamespace(Core=_Core, __version__="2026.2.1")

    class Ids:
        def __init__(self, n: int) -> None:
            self.shape = (1, n)

    class Tok:
        def encode(self, text: str) -> Any:
            return types.SimpleNamespace(input_ids=Ids(len(text.split())))

    ttfts = iter([400.0, 40.0])

    class Pipe:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            calls.append(("LLMPipeline", args, kwargs))

        def get_tokenizer(self) -> Any:
            return Tok()

        def generate(self, prompt: str, cfg: Any) -> Any:
            ttft = next(ttfts)
            metrics = types.SimpleNamespace(get_ttft=lambda: types.SimpleNamespace(mean=ttft))
            return types.SimpleNamespace(perf_metrics=metrics)

    class Cfg:
        max_new_tokens = 0

    genai = types.SimpleNamespace(
        LLMPipeline=Pipe,
        GenerationConfig=Cfg,
        SchedulerConfig=lambda: types.SimpleNamespace(enable_prefix_caching=False),
        __version__="2026.2.1",
    )
    return ov, genai


def test_readback_reports_defaults_without_overrides(tmp_path: Path) -> None:
    calls: list[tuple[str, tuple, dict]] = []
    ov, genai = _fakes(calls)
    doc = demo2_readback.readback(ov, genai, tmp_path / "ir")
    assert calls == [("LLMPipeline", (str(tmp_path / "ir"), "GPU"), {})]
    assert doc["properties_passed"] == {}
    assert doc["device_after_load"]["KV_CACHE_PRECISION"] == "<Type: 'int8_t'>"
    assert doc["device_after_load"]["KEY_CACHE_PRECISION"] == "not supported"
    assert doc["scheduler_config_default_enable_prefix_caching"] is False
    hint = doc["prefix_reuse_hint"]
    assert hint["prompt_tokens"] >= demo2_readback.TARGET_TOKENS
    assert hint["second_over_first_ttft"] == 0.1
    assert list(tmp_path.iterdir()) == []


def test_readback_sources_write_nothing() -> None:
    py = (ROOT / "tools" / "demo2_readback.py").read_text(encoding="utf-8")
    ps = (ROOT / "tools" / "demo2_readback.ps1").read_text(encoding="utf-8")
    for token in ("write_text", "write_bytes", "open(", "mkdir", "json.dump("):
        assert token not in py
    for token in ("Out-File", "Set-Content", "Add-Content", "New-Item", "> "):
        assert token not in ps
