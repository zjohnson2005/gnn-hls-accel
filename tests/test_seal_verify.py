"""Seal verification: out-of-tree hash, legacy self-ref, out-of-tree voids."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_h1_hybrid import (  # noqa: E402
    StubCloudBackend,
    StubLocalBackend,
    _sha256_tree,
    run_session,
)
from tools.seal_verify import (  # noqa: E402
    seal_verdict,
    strip_legacy_tree_sha256_line,
    tree_sha256,
    verify_seal,
    write_void_notice,
)

FIXTURE = ROOT / "tests" / "fixtures" / "h1_hybrid_3entries.json"
D482 = ROOT / "derived" / "h1_hybrid" / "interleaved_d482c621-4292-4281-b6a1-8635e5eeb6da"


def _write_json(path: Path, obj: dict[str, object]) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_tree_sha256_matches_h1_sealer(tmp_path: Path) -> None:
    (tmp_path / "summary.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / ".sealed").write_text("{}\n", encoding="utf-8")
    assert tree_sha256(tmp_path) == _sha256_tree(tmp_path, exclude={".sealed"})


def test_new_h1_seal_is_match_and_summary_has_no_tree_hash(tmp_path: Path) -> None:
    fix = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out = tmp_path / "run"
    run_session(
        policy="cloud_only",
        entries=fix["entries"],
        out_dir=out,
        max_usd=1000.0,
        local=StubLocalBackend(script=fix["local_script"]),
        cloud=StubCloudBackend(
            tokens_in=fix["cloud_tokens_in"],
            tokens_out=fix["cloud_tokens_out"],
        ),
        skip_entry_assert=True,
        seal=True,
        seal_git={
            "git_head": "abc",
            "dirty": False,
            "tree_status": "CLEAN",
            "git_diff_head_sha256": "0" * 64,
        },
    )
    summary = (out / "summary.json").read_text(encoding="utf-8")
    assert "tree_sha256" not in summary
    assert verify_seal(out) == "MATCH"


def test_legacy_self_ref_after_summary_rewrite(tmp_path: Path) -> None:
    summary = {"status": "complete", "value": 1.25}
    _write_json(tmp_path / "summary.json", summary)
    (tmp_path / "note.txt").write_bytes(b"keep\r\n")
    recorded = tree_sha256(tmp_path)
    summary["tree_sha256"] = recorded
    _write_json(tmp_path / "summary.json", summary)
    (tmp_path / ".sealed").write_text(
        json.dumps({"tree_sha256": recorded}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert verify_seal(tmp_path) == "MATCH_LEGACY_SELF_REF"
    assert tree_sha256(tmp_path) != recorded


def test_strip_removes_comma_when_tree_line_is_last() -> None:
    original = b'{\r\n  "status": "complete"\r\n}\r\n'
    rewritten = b'{\r\n  "status": "complete",\r\n  "tree_sha256": "abc"\r\n}\r\n'
    assert strip_legacy_tree_sha256_line(rewritten) == original


def test_mismatch_and_unsealed(tmp_path: Path) -> None:
    assert verify_seal(tmp_path) == "UNSEALED"
    (tmp_path / "summary.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / ".sealed").write_text(
        json.dumps({"tree_sha256": "0" * 64}) + "\n",
        encoding="utf-8",
    )
    assert verify_seal(tmp_path) == "MISMATCH"


def test_d482_is_legacy_self_ref() -> None:
    assert D482.is_dir()
    assert verify_seal(D482) == "MATCH_LEGACY_SELF_REF"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_tree(root: Path, files: dict[str, bytes], listed: dict[str, str]) -> None:
    for rel, blob in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    (root / "manifest.sha256.json").write_text(
        json.dumps(listed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (root / ".sealed").write_bytes(b"sealed\r\n")


def test_manifest_seal_matches_when_coverage_is_complete(tmp_path: Path) -> None:
    blob = b"point\n"
    _manifest_tree(tmp_path, {"points/n.json": blob}, {"points/n.json": _sha256(blob)})
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    verdict = seal_verdict(tmp_path)
    after = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert verdict.status == "MATCH_MANIFEST"
    assert verdict.files == ()
    assert verify_seal(tmp_path) == "MATCH_MANIFEST"
    assert before == after


def test_manifest_coverage_gap_names_unlisted_missing_and_hash(tmp_path: Path) -> None:
    blob = b"kept\n"
    other = b"other\n"
    _manifest_tree(
        tmp_path,
        {"kept.json": blob, "extra.json": other},
        {"kept.json": "0" * 64, "absent.json": _sha256(b"nope")},
    )
    verdict = seal_verdict(tmp_path)
    assert verdict.status == "MANIFEST_COVERAGE_GAP"
    assert verify_seal(tmp_path) == "MANIFEST_COVERAGE_GAP"
    assert verdict.files == ("extra.json", "absent.json", "kept.json")


def test_word_sealed_without_manifest_stays_unsealed(tmp_path: Path) -> None:
    (tmp_path / ".sealed").write_text("sealed\n", encoding="utf-8")
    (tmp_path / "summary.json").write_text("{}\n", encoding="utf-8")
    assert verify_seal(tmp_path) == "UNSEALED"


def test_void_notice_is_outside_the_run(tmp_path: Path) -> None:
    run = tmp_path / "derived" / "h1_hybrid" / "interleaved_abc"
    run.mkdir(parents=True)
    (run / "summary.json").write_text("{}\n", encoding="utf-8")
    dest = write_void_notice(
        "abc",
        {"reason": "lifecycle crash", "points_at": "derived/h1_hybrid/interleaved_abc/VOID.json"},
        root=tmp_path,
    )
    assert dest == tmp_path / "derived" / "VOIDS" / "abc.json"
    assert dest.is_file()
    assert not (run / "VOID.json").exists()
    assert list(run.iterdir()) == [run / "summary.json"]
