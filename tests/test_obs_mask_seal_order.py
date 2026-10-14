"""The OBS_MASK ledger is written before the seal, so the tree hash covers it.

a678926e (V4 XPS) wrote obs_mask_ledger.json 46 ms after .sealed; its in-run
seal verified MISMATCH on the full directory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.run_h1_hybrid as rh  # noqa: E402
from tools.seal_verify import verify_seal  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_3entries.json"


class _Mask:
    def ledger(self) -> dict:
        return {"arm": "OBS_MASK", "k": 1024, "n_observations": 0, "observations": []}


def _fix() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_single_session_seal_covers_the_ledger(tmp_path) -> None:
    fix = _fix()
    out = tmp_path / "run"
    rh.run_session(
        policy="cloud_only",
        entries=fix["entries"],
        out_dir=out,
        max_usd=5.0,
        local=rh.StubLocalBackend(script=fix["local_script"]),
        cloud=rh.StubCloudBackend(tokens_in=10, tokens_out=5),
        skip_entry_assert=True,
        obs_mask=_Mask(),
    )
    assert (out / "obs_mask_ledger.json").is_file()
    assert verify_seal(out) == "MATCH"


def test_interleaved_seal_covers_the_ledger(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(rh, "assert_seal_allowed", lambda **_kw: None)
    fix = _fix()
    out = tmp_path / "inter"
    rh.run_interleaved_session(
        entries=fix["entries"],
        out_dir=out,
        local=rh.StubLocalBackend(script=fix["local_script"]),
        cloud=rh.StubCloudBackend(tokens_in=10, tokens_out=5),
        policies=("slo_escalate",),
        policy_caps_usd={"slo_escalate": 5.0},
        session_max_usd=5.0,
        run_id="inter-ledger",
        skip_entry_assert=True,
        obs_mask=_Mask(),
    )
    assert (out / "obs_mask_ledger.json").is_file()
    assert verify_seal(out) == "MATCH"


def test_main_no_longer_writes_the_ledger_after_the_session() -> None:
    text = (ROOT / "tools" / "run_h1_hybrid.py").read_text(encoding="utf-8")
    assert "write_obs_mask_ledger(args.out" not in text
    assert text.count("obs_mask=obs_mask,") == 2
