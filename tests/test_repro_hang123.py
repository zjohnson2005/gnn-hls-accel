"""Task AZ: tools/repro_hang123.py inputs are pinned and checked before any model load."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import repro_hang123 as rp  # noqa: E402

INPUTS = ROOT / "derived" / "repro_hang123" / "inputs_e123_t0.json"
REGISTERED_SHA = "d12142f89702f0ab92a48148abaa034760bb20c87558b58945a92a29a405f2f0"


def test_inputs_match_registration_and_ay_pin() -> None:
    assert hashlib.sha256(INPUTS.read_bytes()).hexdigest() == REGISTERED_SHA
    doc = json.loads(INPUTS.read_text(encoding="utf-8"))
    assert doc["entry_json_sha256"] == rp.ENTRY_JSON_SHA256
    assert doc["steps"][0]["prompt_sha256"] == rp.STEP0_PROMPT_SHA256
    for s in doc["steps"]:
        assert rp.sha(s["prompt"]) == s["prompt_sha256"]
    assert [s["prompt_tokens_hf"] for s in doc["steps"]] == [2189, 34050]


def test_run_refuses_before_loading_on_sha_mismatch(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="REFUSED -- inputs sha256"):
        rp.run(INPUTS, tmp_path, None, "0" * 64)
    doc = json.loads(INPUTS.read_text(encoding="utf-8"))
    doc["steps"][1]["prompt"] += " "
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SystemExit, match="step 1 prompt sha256 mismatch"):
        rp.run(bad, tmp_path, None, None)


def test_entry_pin_checked() -> None:
    assert rp._entry()["id"] == rp.ENTRY_ID


def test_ascii() -> None:
    (ROOT / "tools" / "repro_hang123.py").read_bytes().decode("ascii")


VARIANTS = ROOT / "derived" / "repro_hang123" / "variants"


def test_variant_index_matches_files_and_keeps_the_real_prompt_outside_the_body() -> None:
    from tools import repro_hang123_variants as rv

    index = json.loads((VARIANTS / "INDEX.json").read_text(encoding="utf-8"))
    assert index["base_inputs_sha256"] == REGISTERED_SHA
    base = json.loads(INPUTS.read_text(encoding="utf-8"))
    real = {s["step"]: s["prompt"] for s in base["steps"]}
    for set_name, block in index["sets"].items():
        step = int(set_name[1:])
        a, b = rv.body_span(real[step], step)
        for name, row in block["cells"].items():
            path = VARIANTS / row["file"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row["file_sha256"], name
            doc = json.loads(path.read_text(encoding="utf-8"))
            p = doc["steps"][0]["prompt"]
            assert rp.sha(p) == row["prompt_sha256"] == doc["steps"][0]["prompt_sha256"]
            assert p.startswith(real[step][:a]) and p.endswith(real[step][b:]), name
            tgt = row["body_tokens_target"]
            assert abs(row["body_tokens_hf"] - tgt) <= rv.TOL * tgt + 1, name
    assert len(index["sets"]["S1"]["cells"]) == 19 and len(index["sets"]["S0"]["cells"]) == 18


def _stub_genai(monkeypatch: pytest.MonkeyPatch, calls: list[str]) -> None:
    import types

    class Pipe:
        def __init__(self, *_a: object) -> None:
            pass

        def generate(self, prompt: str, _cfg: object) -> str:
            calls.append(prompt)
            return "done"

    class Cfg:
        pass

    ov = types.ModuleType("openvino")
    ov.__version__ = "stub"  # type: ignore[attr-defined]
    ga = types.ModuleType("openvino_genai")
    ga.LLMPipeline = Pipe  # type: ignore[attr-defined]
    ga.GenerationConfig = Cfg  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openvino", ov)
    monkeypatch.setitem(sys.modules, "openvino_genai", ga)


def test_run_records_each_step_and_uses_only_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    _stub_genai(monkeypatch, calls)
    rc = rp.run(
        INPUTS, tmp_path, 1, REGISTERED_SHA, watchdog_s=600, out_dir=tmp_path / "runs", label="m6"
    )
    assert rc == 0 and len(calls) == 1
    (run_dir,) = list((tmp_path / "runs").iterdir())
    rec = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert rec["status"] == "complete" and rec["steps"][0]["step"] == 1 and rec["steps"][0]["done"]
    assert not (run_dir / "hang_events.json").exists()


def test_watchdog_options_refuse_bad_combinations(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="--py-spy needs --watchdog-s"):
        rp._watchdog(None, tmp_path, "py-spy.exe", "r")
    with pytest.raises(SystemExit, match="--watchdog-s needs --out-dir"):
        rp._watchdog(600, None, None, "r")
