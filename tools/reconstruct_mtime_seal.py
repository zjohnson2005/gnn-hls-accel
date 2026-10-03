"""Copy a c2 run into sealed_<id> when every source mtime is within finish+120s.

Does not modify the source run directory. The tree hash is written only to
.sealed, labeled RECONSTRUCTED, with the mtime evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.seal_verify import tree_sha256, verify_seal  # noqa: E402

COPY_FILES = (
    "plan.json",
    "summary.json",
    "arm_results.json",
    "probes.ndjson",
    "watchdog_kills.jsonl",
)
GATE = timedelta(seconds=120)


def _summary_path(source: Path) -> Path | None:
    for name in ("summary.json", "SUMMARY.json"):
        path = source / name
        if path.is_file():
            return path
    return None


def _finish(source: Path) -> tuple[datetime, str]:
    summary_path = _summary_path(source)
    if summary_path is not None:
        summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
        for key in ("ended_utc", "finished_utc", "sealed_utc"):
            value = summary.get(key)
            if isinstance(value, str) and value.strip():
                return datetime.fromisoformat(value), f"{summary_path.name}:{key}"
    newest: datetime | None = None
    for file in source.rglob("*"):
        if not file.is_file():
            continue
        stamp = datetime.fromtimestamp(file.stat().st_mtime, datetime.now().astimezone().tzinfo)
        if newest is None or stamp > newest:
            newest = stamp
    if newest is None:
        raise SystemExit(f"REFUSED -- no files to seal in {source}")
    return newest, "newest_source_mtime"


def reconstruct(source: Path) -> Path | None:
    source = source.resolve()
    finish, finish_source = _finish(source)
    deadline = finish + GATE
    late: list[tuple[str, str]] = []
    newest_path = ""
    newest_stamp: datetime | None = None
    for file in source.rglob("*"):
        if not file.is_file():
            continue
        stamp = datetime.fromtimestamp(file.stat().st_mtime, finish.tzinfo)
        if newest_stamp is None or stamp > newest_stamp:
            newest_stamp = stamp
            newest_path = file.relative_to(source).as_posix()
        if stamp > deadline:
            late.append((file.relative_to(source).as_posix(), stamp.isoformat()))
    if late:
        print(f"NOT SEALED {source.name}")
        for rel, stamp in sorted(late):
            print(f"  newer than finish+120s: {rel} {stamp}")
        return None
    out = source.parent / f"sealed_{source.name}"
    if out.exists():
        raise SystemExit(f"REFUSED -- seal already exists: {out}")
    out.mkdir(parents=True)
    copied: list[str] = []
    for src in sorted((p for p in source.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        rel = src.relative_to(source)
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied.append(rel.as_posix())
    if not copied:
        raise SystemExit(f"REFUSED -- no seal files in {source}")
    digest = tree_sha256(out)
    marker = {
        "label": "RECONSTRUCTED",
        "run_id": source.name,
        "tree_sha256": digest,
        "mtime_gate_s": 120,
        "recorded_finish_time": finish.isoformat(),
        "finish_source": finish_source,
        "newest_source_file": newest_path,
        "newest_source_mtime_utc": None if newest_stamp is None else newest_stamp.isoformat(),
        "copied_files": copied,
        "source_path": source.relative_to(ROOT).as_posix(),
        "note": (
            "Full source tree copied out of the run directory. "
            "Source bytes were not modified. tree_sha256 is only in this file."
        ),
    }
    (out / ".sealed").write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = verify_seal(out)
    if status != "MATCH":
        raise SystemExit(f"REFUSED -- reconstructed tree verified {status}")
    print(f"SEALED {out.relative_to(ROOT).as_posix()} {digest} {status}")
    return out


_RUN_IN_PATH = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})[\\/](.*)$",
    re.IGNORECASE,
)
MANIFEST_NOTE = (
    "Full tree copied. T2S manifest mtimes used for the finish+120s gate. "
    "Source bytes were not modified. tree_sha256 is only in this file."
)
STAMP_FILES = frozenset({"plan.json", "summary.json"})
STAMP_RULE = "launcher boot-end stamp"
STAMP_REASON = (
    "tools/t2s_queue_watchdog.py _patch_cell_files is called from apply_summary, "
    "which launch_boot1.ps1 Update-T2sForeignEvidence runs in the finally block "
    "immediately before Write-Host BOOT_COMPLETE. The rewrite assigns watchdog_log "
    "and foreign_queue_evidence on plan.json and summary.json. It sets "
    "exclude_from_sealed_results and status FOREIGN_ACTIVITY only when a busy "
    "watchdog line overlaps the cell. It does not assign prefill, ttft, or search fields."
)
_PROBE_FIELDS = ("prefill_s", "decode_tok_s", "outcome", "wall_s", "completed")
_RESULT_NAME = re.compile(r"^(?P<arm>.+)\.n(?P<n>\d+)\.r(?P<r>\d+)\.")


def _aware(stamp: datetime) -> datetime:
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return stamp


def load_host_mtimes(listing: Path) -> dict[str, dict[str, datetime]]:
    """run_id -> relative posix path -> host mtime.

    Pipe rows match derived/c2_ttft/T2S_SOURCE_MANIFEST.txt:
    ``run|rel|size|sha256|mtime``.
    Tab rows match the host listing: ``<UTC ISO>\\t<host path>``.
    """
    found: dict[str, dict[str, datetime]] = {}
    text = listing.read_text(encoding="utf-8-sig")
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if "|" in line and "\t" not in line:
            parts = line.split("|")
            if len(parts) != 5:
                raise SystemExit(f"REFUSED -- manifest line {line_no} is not 5 fields")
            run_id, rel, _size, _digest, stamp_text = parts
            rel_posix = rel.replace("\\", "/")
        else:
            if "\t" not in line:
                raise SystemExit(f"REFUSED -- mtime line {line_no} has no tab")
            stamp_text, host_path = line.split("\t", 1)
            match = _RUN_IN_PATH.search(host_path.strip())
            if match is None:
                raise SystemExit(f"REFUSED -- mtime line {line_no} has no run id")
            run_id, rel = match.group(1), match.group(2)
            rel_posix = rel.replace("\\", "/")
        stamp = _aware(datetime.fromisoformat(stamp_text.strip()))
        found.setdefault(run_id, {})[rel_posix] = stamp
    if not found:
        raise SystemExit(f"REFUSED -- no mtimes in {listing}")
    return found


def load_host_sha256(listing: Path) -> dict[str, dict[str, str]]:
    """run_id -> relative posix path -> sha256. Format: ``digest  run_id/rel``."""
    found: dict[str, dict[str, str]] = {}
    for line_no, raw in enumerate(listing.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        digest, rel = line.split(None, 1)
        if "/" not in rel:
            raise SystemExit(f"REFUSED -- sha256 line {line_no} has no run id")
        run_id, tail = rel.split("/", 1)
        found.setdefault(run_id, {})[tail.replace("\\", "/")] = digest
    return found


def _load_json(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(doc, dict):
        raise SystemExit(f"REFUSED -- {path.name} is not an object")
    return doc


def _probe_rows(source: Path) -> dict[tuple[str, int, int], dict]:
    path = source / "probes.ndjson"
    if not path.is_file():
        raise SystemExit("REFUSED -- launcher boot-end stamp needs probes.ndjson")
    rows: dict[tuple[str, int, int], dict] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        doc = json.loads(line)
        key = (str(doc["arm_id"]), int(doc["n_tokens"]), int(doc["repeat_index"]))
        rows[key] = doc
    if not rows:
        raise SystemExit("REFUSED -- probes.ndjson has no rows")
    return rows


def _walk_probe_dicts(obj: object, found: list[dict]) -> None:
    if isinstance(obj, dict):
        if {"arm_id", "n_tokens", "repeat_index", "prefill_s"} <= set(obj):
            found.append(obj)
        for value in obj.values():
            _walk_probe_dicts(value, found)
    elif isinstance(obj, list):
        for value in obj:
            _walk_probe_dicts(value, found)


def _median_mismatches(
    obj: object, probes: dict[tuple[str, int, int], dict], name: str
) -> list[str]:
    bad: list[str] = []
    if isinstance(obj, dict):
        if "prefill_s_median" in obj and "n_tokens" in obj:
            n_tokens = int(obj["n_tokens"])
            arm = obj.get("arm_id")
            values = [
                row["prefill_s"]
                for (probe_arm, probe_n, _repeat), row in probes.items()
                if probe_n == n_tokens and (arm is None or probe_arm == arm)
            ]
            if values and obj["prefill_s_median"] != statistics.median(values):
                bad.append(f"{name} prefill_s_median at n={n_tokens}")
        for value in obj.values():
            bad.extend(_median_mismatches(value, probes, name))
    elif isinstance(obj, list):
        for value in obj:
            bad.extend(_median_mismatches(value, probes, name))
    return bad


def measured_fields_match(source: Path) -> dict[str, object]:
    """Probe-shaped fields in plan.json and summary.json must equal the raw files.

    The raw files are probes.ndjson and work/*.result.json. Those files are the
    ones that already passed the finish+120s gate.
    """
    probes = _probe_rows(source)
    result_rows = 0
    mismatches: list[str] = []
    for path in sorted((source / "work").glob("*.result.json")):
        match = _RESULT_NAME.match(path.name)
        if match is None:
            mismatches.append(f"unparsed result name {path.name}")
            continue
        result_rows += 1
        key = (match.group("arm"), int(match.group("n")), int(match.group("r")))
        probe = probes.get(key)
        if probe is None:
            mismatches.append(f"result {path.name} has no probe row")
            continue
        generation = _load_json(path).get("generation")
        if not isinstance(generation, dict):
            mismatches.append(f"result {path.name} has no generation")
            continue
        for field in ("prefill_s", "decode_tok_s"):
            if generation.get(field) != probe.get(field):
                mismatches.append(f"{path.name} {field}")
    embedded: dict[str, int] = {}
    for name in ("plan.json", "summary.json"):
        doc = _load_json(source / name)
        found: list[dict] = []
        _walk_probe_dicts(doc, found)
        embedded[name] = len(found)
        for row in found:
            key = (str(row["arm_id"]), int(row["n_tokens"]), int(row["repeat_index"]))
            probe = probes.get(key)
            if probe is None:
                mismatches.append(f"{name} embedded probe {key} is not in probes.ndjson")
                continue
            for field in _PROBE_FIELDS:
                if field in row and row[field] != probe.get(field):
                    mismatches.append(f"{name} {field} {key}")
        mismatches.extend(_median_mismatches(doc, probes, name))
    if mismatches:
        raise SystemExit(
            "REFUSED -- launcher boot-end stamp measured fields differ: "
            + "; ".join(mismatches[:8])
        )
    return {
        "probe_rows": len(probes),
        "result_rows": result_rows,
        "embedded_probe_rows": embedded,
        "mismatches": 0,
    }


def _stamp_allowed(source: Path, late_rels: set[str]) -> dict[str, object]:
    if not late_rels <= STAMP_FILES:
        raise SystemExit(
            "REFUSED -- launcher boot-end stamp applies only to plan.json and summary.json"
        )
    evidence = measured_fields_match(source)
    for name in sorted(late_rels):
        doc = _load_json(source / name)
        if "watchdog_log" not in doc or "foreign_queue_evidence" not in doc:
            raise SystemExit(f"REFUSED -- {name} has no launcher stamp fields")
        if doc.get("status") == "FOREIGN_ACTIVITY" or doc.get("exclude_from_sealed_results"):
            raise SystemExit(
                f"REFUSED -- {name} stamp changed status or exclusion; not provenance-only"
            )
    evidence["stamp_fields"] = ["watchdog_log", "foreign_queue_evidence"]
    return evidence


def _source_rel(source: Path) -> str:
    try:
        return source.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return source.name


def reconstruct_from_host_manifest(
    source: Path,
    listing: Path,
    *,
    sha256_listing: Path | None = None,
    launch_log: Path | None = None,
    boot_complete_utc: datetime | None = None,
    boot_complete_source: str = "",
) -> Path | None:
    """Seal with host mtimes, the path that sealed 5c714535.

    Local copy mtimes are ignored. A host mtime after ended_utc+120s refuses.
    When a host sha256 list is given, every file must match it. The source
    directory is not modified.
    """
    source = source.resolve()
    listing = listing.resolve()
    by_run = load_host_mtimes(listing)
    run_id = source.name
    host_times = by_run.get(run_id)
    if not host_times:
        raise SystemExit(f"REFUSED -- {listing} has no rows for {run_id}")
    local = {path.relative_to(source).as_posix() for path in source.rglob("*") if path.is_file()}
    if local != set(host_times):
        missing = sorted(set(host_times) - local)
        extra = sorted(local - set(host_times))
        raise SystemExit(
            f"REFUSED -- host mtime listing does not match the tree missing={missing} extra={extra}"
        )
    if sha256_listing is not None:
        hashes = load_host_sha256(sha256_listing).get(run_id, {})
        if set(hashes) != local:
            raise SystemExit(f"REFUSED -- host sha256 listing does not match {run_id}")
        for rel in sorted(local):
            blob = (source / rel).read_bytes()
            digest = hashlib.sha256(blob).hexdigest()
            if digest != hashes[rel]:
                raise SystemExit(f"REFUSED -- sha256 mismatch {rel}")
    finish, finish_source = _finish(source)
    deadline = finish + GATE
    late: list[tuple[str, str]] = []
    newest_path = ""
    newest_stamp: datetime | None = None
    for rel, stamp in host_times.items():
        if newest_stamp is None or stamp > newest_stamp:
            newest_stamp = stamp
            newest_path = rel
        if stamp > deadline:
            late.append((rel, stamp.isoformat()))
    stamp_record: dict[str, object] | None = None
    if late:
        late_rels = {rel for rel, _stamp in late}
        stamp_ok = False
        if launch_log is not None and boot_complete_utc is not None and late_rels <= STAMP_FILES:
            log_text = launch_log.read_text(encoding="utf-8-sig")
            shows_stamp = any(line.strip() == "BOOT_COMPLETE" for line in log_text.splitlines())
            within_boot = all(
                _aware(datetime.fromisoformat(stamp)) <= boot_complete_utc for _rel, stamp in late
            )
            if shows_stamp and within_boot:
                measured = _stamp_allowed(source, late_rels)
                stamp_record = {
                    "rule": STAMP_RULE,
                    "reason": STAMP_REASON,
                    "launch_log": _source_rel(launch_log),
                    "launch_log_shows": "BOOT_COMPLETE",
                    "boot_complete_utc": boot_complete_utc.isoformat(),
                    "boot_complete_utc_source": boot_complete_source,
                    "gate_reference": "BOOT_COMPLETE",
                    "files": sorted(late_rels),
                    "measured_fields_match": measured,
                }
                stamp_ok = True
        if not stamp_ok:
            print(f"NOT SEALED {source.name}")
            for rel, stamp in sorted(late):
                print(f"  newer than finish+120s: {rel} {stamp}")
            return None
    out = source.parent / f"sealed_{source.name}"
    if out.exists():
        raise SystemExit(f"REFUSED -- seal already exists: {out}")
    out.mkdir(parents=True)
    for rel in sorted(local):
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, dest)
    digest = tree_sha256(out)
    manifest_sha = hashlib.sha256(listing.read_bytes()).hexdigest()
    marker = {
        "evidence_source": "T2S_SOURCE_MANIFEST",
        "label": "RECONSTRUCTED",
        "manifest_sha256": manifest_sha,
        "mtime_gate_s": 120,
        "newest_source_file": newest_path,
        "newest_source_mtime_utc": None if newest_stamp is None else newest_stamp.isoformat(),
        "note": MANIFEST_NOTE,
        "recorded_finish_time": finish.isoformat(),
        "finish_source": finish_source,
        "run_id": run_id,
        "source_path": _source_rel(source),
        "tree_sha256": digest,
    }
    if stamp_record is not None:
        marker["launcher_boot_end_stamp"] = stamp_record
    (out / ".sealed").write_text(
        json.dumps(marker, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    status = verify_seal(out)
    if status != "MATCH":
        raise SystemExit(f"REFUSED -- reconstructed tree verified {status}")
    try:
        shown = out.relative_to(ROOT).as_posix()
    except ValueError:
        shown = out.name
    print(f"SEALED {shown} {digest} {status}")
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit(
            "usage: reconstruct_mtime_seal.py <source-run-dir> "
            "[--host-mtimes LISTING] [--host-sha256 LISTING] "
            "[--launch-log PATH --boot-complete-utc ISO --boot-complete-source TEXT]"
        )
    source = Path(argv[1])
    mtimes: Path | None = None
    hashes: Path | None = None
    launch_log: Path | None = None
    boot_complete: datetime | None = None
    boot_source = ""
    index = 2
    while index < len(argv):
        flag = argv[index]
        if flag == "--host-mtimes" and index + 1 < len(argv):
            mtimes = Path(argv[index + 1])
            index += 2
        elif flag == "--host-sha256" and index + 1 < len(argv):
            hashes = Path(argv[index + 1])
            index += 2
        elif flag == "--launch-log" and index + 1 < len(argv):
            launch_log = Path(argv[index + 1])
            index += 2
        elif flag == "--boot-complete-utc" and index + 1 < len(argv):
            boot_complete = _aware(datetime.fromisoformat(argv[index + 1]))
            index += 2
        elif flag == "--boot-complete-source" and index + 1 < len(argv):
            boot_source = argv[index + 1]
            index += 2
        else:
            raise SystemExit(f"REFUSED -- unknown argument {flag}")
    if mtimes is None:
        reconstruct(source)
    else:
        reconstruct_from_host_manifest(
            source,
            mtimes,
            sha256_listing=hashes,
            launch_log=launch_log,
            boot_complete_utc=boot_complete,
            boot_complete_source=boot_source,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
