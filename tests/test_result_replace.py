"""Result-file replace retries WinError 5, then raises."""

from __future__ import annotations

from pathlib import Path

import pytest

from seam.tools._delta_n_child import replace_result_file


def test_replace_retries_permission_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    dest = tmp_path / "out.json"
    src = tmp_path / "out.partial"
    src.write_text("{}", encoding="utf-8")
    real = Path.replace

    def fake(self: Path, target: Path) -> Path:
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(5, "Access is denied")
        return real(self, target)

    monkeypatch.setattr(Path, "replace", fake)
    replace_result_file(src, dest, attempts=5, wait_s=0.0, sleep=lambda _seconds: None)
    assert dest.read_text(encoding="utf-8") == "{}"
    assert calls["n"] == 3


def test_replace_raises_after_the_last_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "out.json"
    src = tmp_path / "out.partial"
    src.write_text("{}", encoding="utf-8")

    def fake(self: Path, target: Path) -> Path:
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "replace", fake)
    with pytest.raises(PermissionError):
        replace_result_file(src, dest, attempts=2, wait_s=0.0, sleep=lambda _seconds: None)
