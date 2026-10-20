"""tools/get_pyspy.ps1 (Task AX): download-only py-spy fetch, venv freeze unchanged."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "get_pyspy.ps1"
PWSH = shutil.which("pwsh")

FAKE_PY = """#!/bin/sh
if [ "$3" = "freeze" ]; then cat "$FAKE_DIR/freeze.txt"; exit 0; fi
if [ "$3" = "download" ]; then
  if [ "$FAKE_MODE" = "fail" ]; then echo "ERROR: No matching distribution" >&2; exit 1; fi
  d=""
  while [ $# -gt 0 ]; do if [ "$1" = "-d" ]; then d="$2"; fi; shift; done
  cp "$FAKE_DIR/wheel.whl" "$d/py_spy-0.4.2-py2.py3-none-win_amd64.whl"
  if [ "$FAKE_MODE" = "mutate" ]; then echo "py-spy==0.4.2" >> "$FAKE_DIR/freeze.txt"; fi
  exit 0
fi
exit 9
"""


def _setup(tmp: Path, *, exe_in_wheel: bool = True) -> tuple[Path, str]:
    fake = tmp / "fake"
    fake.mkdir()
    py = fake / "python"
    py.write_text(FAKE_PY, encoding="ascii")
    py.chmod(py.stat().st_mode | stat.S_IEXEC)
    (fake / "freeze.txt").write_text("numpy==1.26.4\nopenvino==2026.2.1\n", encoding="ascii")
    whl = fake / "wheel.whl"
    with zipfile.ZipFile(whl, "w") as z:
        name = "py_spy-0.4.2.data/scripts/py-spy.exe" if exe_in_wheel else "py_spy/README"
        z.writestr(name, "#!/bin/sh\necho py-spy 0.4.2\n")
    return py, hashlib.sha256(whl.read_bytes()).hexdigest()


def _run(tmp: Path, py: Path, sha: str, mode: str = "") -> subprocess.CompletedProcess[str]:
    assert PWSH is not None
    return subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SCRIPT),
            "-Python",
            str(py),
            "-ToolsDir",
            str(tmp / "seam_tools"),
            "-WheelSha256",
            sha,
        ],
        capture_output=True,
        text=True,
        timeout=120,
        env={
            **os.environ,
            "FAKE_DIR": str(py.parent),
            "FAKE_MODE": mode,
            "POWERSHELL_TELEMETRY_OPTOUT": "1",
        },
    )


def _lines(done: subprocess.CompletedProcess[str]) -> list[str]:
    return done.stdout.splitlines()


pytestmark = pytest.mark.skipif(PWSH is None, reason="pwsh not installed")


def test_download_extract_and_freeze_unchanged(tmp_path: Path) -> None:
    py, sha = _setup(tmp_path)
    done = _run(tmp_path, py, sha)
    out = _lines(done)
    assert done.returncode == 0, done.stdout + done.stderr
    exe = tmp_path / "seam_tools" / "py-spy.exe"
    assert exe.read_text() == "#!/bin/sh\necho py-spy 0.4.2\n"
    assert any(x.startswith("WHEEL py_spy-0.4.2-") for x in out)
    exe_sha = hashlib.sha256(exe.read_bytes()).hexdigest().upper()
    assert f"SHA256 {exe_sha}" in out
    before = next(x for x in out if x.startswith("FREEZE_BEFORE "))
    after = next(x for x in out if x.startswith("FREEZE_AFTER "))
    assert before.split()[1] == after.split()[1]
    assert out[-1] == "PIP_FREEZE_UNCHANGED"
    # Second run: already present, nothing downloaded.
    again = _run(tmp_path, py, sha, mode="fail")
    assert again.returncode == 0
    assert any(x.startswith("PRESENT ") for x in _lines(again))


def test_download_failure_exits_2(tmp_path: Path) -> None:
    py, sha = _setup(tmp_path)
    done = _run(tmp_path, py, sha, mode="fail")
    assert done.returncode == 2
    assert any(x.startswith("DOWNLOAD_FAILED py-spy==0.4.2") for x in _lines(done))
    assert not (tmp_path / "seam_tools" / "py-spy.exe").exists()


def test_wheel_hash_mismatch_exits_5(tmp_path: Path) -> None:
    py, _sha = _setup(tmp_path)
    done = _run(tmp_path, py, "0" * 64)
    assert done.returncode == 5
    assert not (tmp_path / "seam_tools" / "py-spy.exe").exists()


def test_no_exe_in_wheel_exits_3(tmp_path: Path) -> None:
    py, sha = _setup(tmp_path, exe_in_wheel=False)
    done = _run(tmp_path, py, sha)
    assert done.returncode == 3


def test_changed_freeze_exits_4(tmp_path: Path) -> None:
    py, sha = _setup(tmp_path)
    done = _run(tmp_path, py, sha, mode="mutate")
    assert done.returncode == 4
    assert "PIP_FREEZE_CHANGED" in _lines(done)


def test_script_downloads_only_and_is_pinned() -> None:
    text = SCRIPT.read_text(encoding="ascii")
    assert "pip download" in text and "--no-deps --only-binary=:all:" in text
    assert "pip install" not in text
    assert '[string]$Version = "0.4.2"' in text
