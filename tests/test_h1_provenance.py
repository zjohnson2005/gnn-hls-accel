"""H1 plans, seals, and cloud request records carry the resolved model and config."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.bfcl_feasibility_probe import CLOUD_DEFAULT_MODEL  # noqa: E402
from tools.h1_cloud_accounting import cloud_request_record  # noqa: E402
from tools.h1_provenance import provenance_block, stamp_seal  # noqa: E402
from tools.run_h1_hybrid import (  # noqa: E402
    INTERLEAVE_POLICIES,
    StubCloudBackend,
    StubLocalBackend,
    run_interleaved_session,
)

FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_3entries.json"


def test_request_record_stores_resolved_model() -> None:
    rec = cloud_request_record(
        model=CLOUD_DEFAULT_MODEL,
        turn=0,
        request_index_within_turn=0,
        ok=True,
        system="s",
        tools="t",
        history="h",
        new="n",
        input_tokens=3,
        output_tokens=1,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    )
    assert rec["model"] == "claude-sonnet-5"
    assert rec["model"] != "claude-sonnet"


def test_plan_and_seal_record_model_and_generation(tmp_path: Path) -> None:
    fix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    local = StubLocalBackend(script=fix["local_script"])
    cloud = StubCloudBackend(
        tokens_in=fix["cloud_tokens_in"],
        tokens_out=fix["cloud_tokens_out"],
    )
    cloud.cloud_model = "claude-sonnet-5"  # type: ignore[attr-defined]
    out = tmp_path / "prov"
    run_interleaved_session(
        entries=fix["entries"][:1],
        out_dir=out,
        local=local,
        cloud=cloud,
        policy_caps_usd=dict.fromkeys(INTERLEAVE_POLICIES, 100.0),
        session_max_usd=1000.0,
        run_id="prov-1",
        skip_entry_assert=True,
        seal=False,
    )
    plan = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert plan["cloud_model"] == "claude-sonnet-5"
    assert plan["chat_template"]["enable_thinking"] is False
    gen = plan["generation_config"]
    assert gen["do_sample"] is False
    assert "max_new_tokens" in gen
    assert "temperature" in gen
    seal = stamp_seal({"run_id": "prov-1"}, plan)
    assert seal["cloud_model"] == plan["cloud_model"]
    assert seal["chat_template"] == plan["chat_template"]
    assert seal["generation_config"] == plan["generation_config"]
    runner = (ROOT / "tools" / "run_h1_hybrid.py").read_text(encoding="utf-8")
    assert runner.count("stamp_seal(") >= 5


def test_latin_square_rotates_every_symbol() -> None:
    from tools.h1_provenance import latin_square_order

    policies = ("a", "b", "c")
    orders = {tuple(latin_square_order(policies, f"e{i}", seed=1)) for i in range(24)}
    assert orders == {("a", "b", "c"), ("b", "c", "a"), ("c", "a", "b")}


def test_omitted_cloud_model_resolves_to_runner_default() -> None:
    block = provenance_block(cloud=None)
    assert block["cloud_model"] == CLOUD_DEFAULT_MODEL
    assert block["chat_template"]["enable_thinking"] is False
