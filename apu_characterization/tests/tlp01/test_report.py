from __future__ import annotations

import json

from apu_characterization.tlp01.analyze import analyze_experiment
from apu_characterization.tlp01.audit import audit_experiment
from apu_characterization.tlp01.extract import make_synthetic_parallel_session
from apu_characterization.tlp01.report import append_died_claim, render_report


def test_report_contains_bracket_discipline_and_related_work() -> None:
    sessions = [
        make_synthetic_parallel_session(session_id=f"syn-FO-s{seed}", seed=seed)
        for seed in range(5)
    ]
    aggregate = analyze_experiment(sessions)
    audit = audit_experiment(sessions, kappa=None)
    text = render_report(aggregate, audit=audit, died_ledger={"entries": []})
    assert "S/C" in text or "Tier-C" in text
    assert "Blocked claims" in text
    assert "Tier D" in text
    assert "PASTE" in text
    assert "phase diagram" in text.lower()
    assert "nobody harvests" not in text.lower()
    assert "universally unharvested" not in text.lower()
    assert "smoke_diagnostic:" in text
    assert "rung_1a" not in text
    assert "rung_1b" not in text
    assert "rung_2a" not in text
    assert "rung_2b" not in text
    assert "rung_3a" not in text
    assert "rung_3b" not in text


def test_died_ledger_is_append_only(tmp_path) -> None:
    path = tmp_path / "died_ledger.json"
    path.write_text(
        json.dumps(
            {
                "protocol_version": "tlp01_v1",
                "entries": [],
                "policy": "Append-only.",
            }
        ),
        encoding="utf-8",
    )
    first = append_died_claim(
        path, claim="c1", reason="r1", evidence=["e1"]
    )
    second = append_died_claim(
        path, claim="c2", reason="r2", evidence=["e2"]
    )
    ledger = json.loads(path.read_text(encoding="utf-8"))
    assert first["id"] == 1
    assert second["id"] == 2
    assert len(ledger["entries"]) == 2
