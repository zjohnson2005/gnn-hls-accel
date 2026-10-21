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
