"""A live launch_h1.ps1 must leave a clean tree for its worker.

2026-10-13 (T2S 199f3f7d, XPS 16e8ec3f): the worker refused because the
launcher had modified the tracked derived/h1_hybrid/_canary_opening/ files and
left an untracked derived/_gate_probes/gates_<stamp>.json. The launcher now
writes both under derived/h1_hybrid/_launches/<run_id>/ (gitignored) and the
worker records each file with its sha256.

The launcher's writes are simulated on a clean temp repo that uses this
repo's real .gitignore; PowerShell is not run.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from seam.errors import DirtyTreeError
from tools import run_h1_hybrid as rh
from tools.h1_seal_git import launch_evidence_record, seal_git_record

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "tools" / "launch_h1.ps1"
GATES_PS1 = ROOT / "tools" / "_run_measurement_gates.ps1"
RUN_ID = "199f3f7d-0000-4000-8000-000000000000"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=60
    )
    return done.stdout


def _clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "core.autocrlf", "false")
    shutil.copy2(ROOT / ".gitignore", repo / ".gitignore")
    (repo / "tools").mkdir()
    (repo / "tools" / "run_h1_hybrid.py").write_text("x = 1\n", encoding="utf-8")
    tracked = repo / "derived" / "h1_hybrid" / "_canary_opening"
    (tracked / "canaries").mkdir(parents=True)
    (tracked / "opening_plan.json").write_text('{"from": "d482c621"}\n', encoding="utf-8")
    (tracked / "canaries" / "canary.0.json").write_text('{"i": 0}\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    assert _git(repo, "status", "--porcelain") == ""
    return repo


def _live_launcher_writes(repo: Path) -> Path:
    """What launch_h1.ps1 writes before the spawn, at the new paths."""
    session = repo / "derived" / "h1_hybrid" / "_launches" / RUN_ID
    session.mkdir(parents=True)
    (session / "gates_20261013_120000.json").write_text(
        json.dumps({"all_passed": True, "refusal_reasons": []}) + "\n", encoding="utf-8"
    )
    canary = session / "canary_opening"
    (canary / "canaries").mkdir(parents=True)
    (canary / "canaries" / "canary.0.json").write_text('{"i": 0, "new": 1}\n', encoding="utf-8")
    (canary / "opening_plan.json").write_text('{"armed": true}\n', encoding="utf-8")
    # The launcher's own log is gitignored as *.log.
    (repo / "derived" / "h1_hybrid" / "_launches" / "h1_slo_escalate_x.log").write_text(
        "log\n", encoding="utf-8"
    )
    return session


def test_new_paths_leave_a_clean_tree_and_are_recorded(tmp_path) -> None:
    repo = _clean_repo(tmp_path)
    session = _live_launcher_writes(repo)
    rec = seal_git_record(allow_dirty=False, root=repo)
    assert rec["tree_status"] == "CLEAN"
    evidence = launch_evidence_record(session, root=repo)
    assert evidence["dir"] == f"derived/h1_hybrid/_launches/{RUN_ID}"
    paths = [row["path"] for row in evidence["files"]]
    assert paths == [
        f"derived/h1_hybrid/_launches/{RUN_ID}/canary_opening/canaries/canary.0.json",
        f"derived/h1_hybrid/_launches/{RUN_ID}/canary_opening/opening_plan.json",
        f"derived/h1_hybrid/_launches/{RUN_ID}/gates_20261013_120000.json",
    ]
    for row in evidence["files"]:
        data = (repo / row["path"]).read_bytes()
        assert row["sha256"] == hashlib.sha256(data).hexdigest()
        assert row["bytes"] == len(data)
    # The tracked d482c621 copy is untouched.
    assert (repo / "derived/h1_hybrid/_canary_opening/opening_plan.json").read_text(
        encoding="utf-8"
    ) == '{"from": "d482c621"}\n'


def test_runner_cli_records_launch_evidence_in_the_plan_git_block(tmp_path, monkeypatch) -> None:
    repo = _clean_repo(tmp_path)
    session = _live_launcher_writes(repo)
    monkeypatch.setattr(rh, "ROOT", repo)
    seen: dict[str, object] = {}

    def fake_derive(*, out_dir, run_id, seal_git):
        seen["seal_git"] = seal_git
        return {"run_id": run_id}

    monkeypatch.setattr(rh, "derive_r1_from_cb781", fake_derive)
    code = rh.main(
        [
            "--derive-r1",
            "--out",
            str(tmp_path / "out"),
            "--run-id",
            RUN_ID,
            "--launch-evidence-dir",
            str(session),
        ]
    )
    assert code == 0
    git_block = seen["seal_git"]
    assert isinstance(git_block, dict)
    assert git_block["tree_status"] == "CLEAN"
    assert git_block["launch_evidence"]["dir"] == f"derived/h1_hybrid/_launches/{RUN_ID}"
    assert len(git_block["launch_evidence"]["files"]) == 3


def test_old_paths_reproduce_the_refusal(tmp_path) -> None:
    repo = _clean_repo(tmp_path)
    (repo / "derived/h1_hybrid/_canary_opening/canaries/canary.0.json").write_text(
        '{"i": 0, "new": 1}\n', encoding="utf-8"
    )
    (repo / "derived/h1_hybrid/_canary_opening/opening_plan.json").write_text(
        '{"armed": true}\n', encoding="utf-8"
    )
    probes = repo / "derived" / "_gate_probes"
    probes.mkdir(parents=True)
    (probes / "gates_20261013_120000.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(DirtyTreeError) as info:
        seal_git_record(allow_dirty=False, root=repo)
    text = str(info.value)
    assert "3 uncommitted" in text or "_canary_opening" in text


def test_a_real_code_change_still_refuses(tmp_path) -> None:
    repo = _clean_repo(tmp_path)
    _live_launcher_writes(repo)
    (repo / "tools" / "run_h1_hybrid.py").write_text("x = 2\n", encoding="utf-8")
    with pytest.raises(DirtyTreeError):
        seal_git_record(allow_dirty=False, root=repo)


def test_a_new_untracked_source_file_still_refuses(tmp_path) -> None:
    repo = _clean_repo(tmp_path)
    _live_launcher_writes(repo)
    (repo / "tools" / "new_tool.py").write_text("y = 1\n", encoding="utf-8")
    with pytest.raises(DirtyTreeError):
        seal_git_record(allow_dirty=False, root=repo)


def test_missing_or_empty_evidence_dir_refuses(tmp_path) -> None:
    with pytest.raises(SystemExit, match="missing"):
        launch_evidence_record(tmp_path / "nope", root=tmp_path)
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit, match="empty"):
        launch_evidence_record(tmp_path / "empty", root=tmp_path)


def test_ignore_rule_is_narrow() -> None:
    def ignored(rel: str) -> bool:
        done = subprocess.run(
            ["git", "check-ignore", "-q", rel], cwd=ROOT, check=False, capture_output=True
        )
        return done.returncode == 0

    assert ignored(f"derived/h1_hybrid/_launches/{RUN_ID}/gates_1.json")
    assert ignored(f"derived/h1_hybrid/_launches/{RUN_ID}/canary_opening/opening_plan.json")
    assert not ignored("derived/h1_hybrid/_canary_opening/opening_plan.json")
    assert not ignored(f"derived/h1_hybrid/interleaved_{RUN_ID}/plan.json")
    assert not ignored(f"derived/h1_hybrid/slo_escalate_{RUN_ID}/plan.json")
    assert not ignored("derived/_gate_probes/gates_1.json")
    assert not ignored("tools/new_tool.py")


def test_launcher_writes_evidence_to_the_run_dir() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    sid = text.index("$sid = [guid]::NewGuid().ToString()")
    assert text.count("$sid = [guid]::NewGuid().ToString()") == 2  # -DeriveR1 and live
    assert "$SessionLaunchDir = Join-Path $LaunchDir $sid" in text
    gates = text.index("$gateJson = Invoke-SeamMeasurementGates")
    canary = text.index("& $PythonExe @canaryArgs")
    spawn = text.index("& $SpawnPs1 -CommandLine $resolvedCmd")
    main_sid = text.index("$SessionLaunchDir = Join-Path $LaunchDir $sid")
    assert sid < main_sid < gates < canary < spawn
    assert "-ProbeDir $gateProbeDir" in text
    assert '$gateProbeDir = if ($DryRun) { "" } else { $SessionLaunchDir }' in text
    assert '$CanaryOut = Join-Path $SessionLaunchDir "canary_opening"' in text
    assert 'Join-Path $SessionRoot "_canary_opening"' not in text
    assert text.count("' --launch-evidence-dir \"' + $SessionLaunchDir + '\"'") == 2
    # No new waiver: --allow-dirty is only added under -AllowDirty.
    for line in text.splitlines():
        if "--allow-dirty" in line and "+=" not in line and "help" not in line:
            assert "AllowDirty" in line or line.strip().startswith("#") or "allow-dirty'" in line
    gates_text = GATES_PS1.read_text(encoding="utf-8")
    assert '[string]$ProbeDir = ""' in gates_text
    assert "if (-not [string]::IsNullOrWhiteSpace($ProbeDir)) {\n        $outDir = $ProbeDir" in (
        gates_text
    )
