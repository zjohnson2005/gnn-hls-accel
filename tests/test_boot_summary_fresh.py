"""Each boot summary starts empty, and a partial cell keeps its run id."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _powershell(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_a_new_boot_id_drops_the_previous_refused_row() -> None:
    script = ROOT / "tools" / "boot_cell_result.ps1"
    command = (
        f". '{script}'; "
        "$old = [pscustomobject]@{ "
        "  boot_id = 'boot-a'; "
        "  cells = @([pscustomobject]@{ name = 'stale'; status = 'REFUSED'; run_id = '' }) "
        "}; "
        "$kept = @(Select-BootPriorCells -Existing $old -BootId 'boot-a'); "
        "$dropped = @(Select-BootPriorCells -Existing $old -BootId 'boot-b'); "
        "$legacy = [pscustomobject]@{ cells = $old.cells }; "
        "$unkeyed = @(Select-BootPriorCells -Existing $legacy -BootId 'boot-a'); "
        "Write-Output $kept.Count; "
        "Write-Output $dropped.Count; "
        "Write-Output $unkeyed.Count"
    )
    proc = _powershell(command)
    assert proc.returncode == 0, proc.stderr
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert lines[-3:] == ["1", "0", "0"]
    text = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    assert "Select-BootPriorCells" in text
    assert "boot_id = $script:BootId" in text


def test_status_file_second_line_is_the_run_id(tmp_path: Path) -> None:
    script = ROOT / "tools" / "boot_cell_result.ps1"
    status = tmp_path / "cell-status-0.txt"
    status.write_text(
        "partial\n72776603-7ea0-4279-a425-941d73a0bf57\n",
        encoding="utf-8",
    )
    command = (
        f". '{script}'; "
        f"$row = Read-CellStatusFile -Path '{status}'; "
        "Write-Output $row.Status; "
        "Write-Output $row.RunId"
    )
    proc = _powershell(command)
    assert proc.returncode == 0, proc.stderr
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert lines[-2] == "partial"
    assert lines[-1] == "72776603-7ea0-4279-a425-941d73a0bf57"
    text = (ROOT / "tools" / "launch_boot1.ps1").read_text(encoding="utf-8")
    assert "Read-CellStatusFile" in text
    assert "RunId $recorded.RunId" in text


def test_publish_writes_the_session_id_on_the_second_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools.boot4_session import _publish_cell_status

    path = tmp_path / "cell-status-0.txt"
    monkeypatch.setenv("SEAM_CELL_STATUS_PATH", str(path))
    _publish_cell_status("partial", "72776603-7ea0-4279-a425-941d73a0bf57")
    assert path.read_text(encoding="utf-8") == ("partial\n72776603-7ea0-4279-a425-941d73a0bf57\n")
