from __future__ import annotations

from apu_characterization.turntrace_v2.engines import EngineIdentity
from apu_characterization.turntrace_v2.engines.llamacpp import LlamaCppServerEngine


def _engine(model_id: str, *, remap: bool | None = None) -> LlamaCppServerEngine:
    ident = EngineIdentity(
        deployment_id="CPU0",
        model_id=model_id,
        quantization="Q4_K_M",
        engine="llama.cpp",
        engine_version="test",
        hardware="cpu-host",
        reasoning_mode="off",
        provisional=True,
    )
    return LlamaCppServerEngine(
        base_url="http://127.0.0.1:9",
        identity=ident,
        remap_unsupported_roles=remap,
    )


def test_tinyllama_auto_remaps_tool_role() -> None:
    eng = _engine("tinyllama-1.1b-chat-v1.0")
    assert eng.should_remap_unsupported_roles() is True
    msgs = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "u"},
        {"role": "assistant", "content": "a"},
        {"role": "tool", "content": '{"ok": true}'},
        {"role": "function", "content": "x"},
    ]
    out = eng.normalize_messages(msgs)
    assert [m["role"] for m in out] == ["system", "user", "assistant", "user", "user"]
    assert out[3]["content"].startswith("tool_result:")
    assert out[4]["content"].startswith("function:")


def test_p2_model_does_not_remap_tool_role() -> None:
    """P2/P3 tool-capable models must keep bare tool roles (no silent rewrite)."""
    eng = _engine("gpt-4.1-mini")
    assert eng.should_remap_unsupported_roles() is False
    msgs = [
        {"role": "user", "content": "u"},
        {"role": "tool", "content": '{"ok": true}'},
    ]
    out = eng.normalize_messages(msgs)
    assert [m["role"] for m in out] == ["user", "tool"]
    assert out[1]["content"] == '{"ok": true}'


def test_explicit_override_forces_remap_off_even_for_tinyllama() -> None:
    eng = _engine("tinyllama-1.1b-chat-v1.0", remap=False)
    assert eng.should_remap_unsupported_roles() is False
