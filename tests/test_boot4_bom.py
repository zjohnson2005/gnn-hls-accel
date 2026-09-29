"""UTF-8 BOM handoff: every boot reader accepts a PowerShell BOM, writers emit none."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.json_io import load_json  # noqa: E402
from tools.boot4_session import _warm_advantages, read_json, seal_session  # noqa: E402
from tools.t2s_queue_watchdog import read_payload  # noqa: E402

READERS = (load_json, read_json, read_payload)


def _bom_file(path: Path, payload: dict[str, object]) -> None:
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps(payload).encode("utf-8"))


def test_every_reader_accepts_a_bom_fixture(tmp_path: Path) -> None:
    payload = {
        "kind": "warm_kv",
        "arm": "gpu_only_f16",
        "turn2_median_prefill_s": {"12000": 1.25},
    }
    path = tmp_path / "summary.json"
    _bom_file(path, payload)
    for reader in READERS:
        loaded = reader(path)
        assert loaded["arm"] == "gpu_only_f16"
        assert loaded["kind"] == "warm_kv"

    parent = tmp_path / "delta_prefill"
    old = parent / "41e419bd-f3e9-43b1-8364-0ebd89fa086b"
    old.mkdir(parents=True)
    _bom_file(old / "summary.json", payload)
    current = parent / "current"
    current.mkdir()
    assert _warm_advantages(current, {"arm": "gpu_only_u8", "turn2_median_prefill_s": {}}) is None


def test_powershell_writer_emits_no_bom(tmp_path: Path) -> None:
    dest = tmp_path / "handoff.json"
    script = ROOT / "tools" / "_utf8_nobom.ps1"
    env = os.environ.copy()
    env["BOM_OUT"] = str(dest)
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f". '{script}'; Write-Utf8NoBom -Path $env:BOM_OUT -Text '{{\"a\":1}}'",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    data = dest.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert json.loads(data.decode("utf-8")) == {"a": 1}


def test_rehearsal_does_not_seal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEAM_REHEARSAL", "1")
    with pytest.raises(SystemExit, match="does not seal"):
        seal_session(tmp_path)


def test_rehearsal_dry_run_announces_the_directory() -> None:
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-File",
            str(ROOT / "tools" / "launch_boot4.ps1"),
            "-DryRun",
            "-Rehearsal",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "rehearsal=true" in proc.stdout
    assert "_rehearsal" in proc.stdout
    assert "smoke_planned WARM-KV f16" in proc.stdout
    assert "DRY_RUN_OK DECODE-MATCH" in proc.stdout
