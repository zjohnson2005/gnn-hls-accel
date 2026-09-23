"""PARITY-REMEASURE is a document. The ceiling runner must not read it."""

from __future__ import annotations

import builtins
import contextlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREREG_NAMES = (
    "PARITY_REMEASURE_PREREG.json",
    "PARITY_REMEASURE_AMEND_1.json",
)
RUNNER = ROOT / "tools" / "run_c1_ceiling.py"


def test_prereg_exists_and_runner_source_does_not_name_it() -> None:
    for name in PREREG_NAMES:
        assert (ROOT / "derived" / "c2_ttft" / name).is_file()
    text = RUNNER.read_text(encoding="utf-8")
    for name in PREREG_NAMES:
        assert name not in text


def test_ceiling_runner_does_not_open_prereg(monkeypatch) -> None:
    opened: list[str] = []
    real_open = builtins.open

    def guard(file: object, *args: Any, **kwargs: Any) -> Any:
        if any(name in str(file) for name in PREREG_NAMES):
            opened.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guard)
    from tools.run_c1_ceiling import main

    with contextlib.suppress(SystemExit):
        main(["--help"])
    assert opened == []
