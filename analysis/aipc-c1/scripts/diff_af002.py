"""Diff a fresh AF-002 re-probe against the committed provenance artifacts.

Blueprint finding AF-002 asks for the provenance snapshot to be re-runnable and diffable rather than
transcribed once. This script does the diffing half:

1. Records the SHA-256 of every committed artifact, read from bytes on disk, so a manifest emitter or
   an auditor can cite the exact bytes each claim rests on.
2. Decodes the committed artifacts by BOM. They are UTF-16LE (PowerShell 5.1 redirection); reading
   them as UTF-8 produces mojibake in which substring checks are vacuously satisfiable.
3. Diffs each committed artifact against its fresh counterpart and reports the load-bearing claims
   explicitly, because a raw unified diff of two captures taken a day apart is dominated by
   timestamps and section-ordering noise.

The committed artifacts are READ-ONLY (spec section 9.1). This script only reads them.

Usage:
    python analysis/aipc-c1/scripts/diff_af002.py <fresh_dir> [--out <report.md>]
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Committed artifact -> fresh counterpart filename. `_c1_probe.txt` has no counterpart: it carries
#: no hardware content (three lines: timestamp, hostname, "done"), so there is nothing to re-capture.
COUNTERPARTS = {
    "analysis/_c1_machine_probe.txt": "machine_probe.txt",
    "analysis/_c1_drivers_probe.txt": "drivers_probe.txt",
    "analysis/_c1_mem_probe.txt": "mem_probe.txt",
    "analysis/_c1_tools_probe.txt": "tools_probe.txt",
    "analysis/_c1_probe.txt": None,
}

#: Claims MACHINE.md makes that an artifact must attest, and the substring that attests each.
#: Checked against the union of committed text and of fresh text separately, so the report can say
#: which claims moved from unattested to attested.
LOAD_BEARING = [
    ("E1 CPU SKU string", "Intel(R) Core(TM) Ultra 5 325"),
    ("E2 graphics PCI device ID", "DEV_B090"),
    ("chassis", "XPS 16 DA16260"),
    ("OS build 26200", "26200"),
    ("total physical memory 15,976 MB", "15,976 MB"),
    ("memory bank capacity 2 GiB", "2147483648"),
    ("memory bank count 8", "bank_count=8"),
    ("ConfiguredClockSpeed 7467", "7467"),
    ("SPD Speed field 9600", "9600"),
    ("core count 8", "NumberOfCores             : 8"),
    ("logical processor count 8", "NumberOfLogicalProcessors=8"),
    ("EfficiencyClass field", "EfficiencyClass"),
    ("no SMT", "smt=False"),
    ("CPUID family/model/stepping", "Intel64 Family 6 Model 204 Stepping 3"),
]

_BOM_ENCODINGS = [
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
]


def decode_by_bom(path: Path) -> str:
    """Decode a probe artifact using its byte-order mark, falling back to UTF-8."""
    raw = path.read_bytes()
    for bom, encoding in _BOM_ENCODINGS:
        if raw.startswith(bom):
            return raw[len(bom) :].decode(encoding)
    return raw.decode("utf-8")


def encoding_of(path: Path) -> str:
    raw = path.read_bytes()
    for bom, encoding in _BOM_ENCODINGS:
        if raw.startswith(bom):
            return encoding
    return "utf-8 (no BOM)"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def normalise(text: str) -> list[str]:
    """Strip trailing whitespace and drop blank lines before diffing.

    Blank-line runs differ purely because of how each capture was redirected and would otherwise
    dominate the diff.
    """
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fresh_dir", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    fresh_dir: Path = args.fresh_dir.resolve()
    if not fresh_dir.is_dir():
        print(f"not a directory: {fresh_dir}", file=sys.stderr)
        return 2

    out: list[str] = []
    add = out.append

    add("# AF-002 provenance re-capture — diff against committed artifacts")
    add("")
    add(f"Fresh capture: `{fresh_dir.relative_to(REPO_ROOT).as_posix()}`")
    add("")
    add(
        "The committed artifacts under `analysis/` are read-only (spec section 9.1) and were not "
        "modified. Every hash below is computed from bytes on disk at report time, never "
        "transcribed (blueprint AF-002)."
    )
    add("")

    add("## SHA-256 of committed artifacts")
    add("")
    add("| Artifact | Bytes | Encoding | SHA-256 |")
    add("|---|---:|---|---|")
    committed_text: list[str] = []
    for relative in COUNTERPARTS:
        path = REPO_ROOT / relative
        if not path.is_file():
            add(f"| `{relative}` | — | — | **MISSING** |")
            continue
        text = decode_by_bom(path)
        committed_text.append(text)
        add(
            f"| `{relative}` | {path.stat().st_size} | {encoding_of(path)} "
            f"| `{sha256_file(path)}` |"
        )
    add("")

    add("## SHA-256 of fresh capture")
    add("")
    add("| File | Bytes | Encoding | SHA-256 |")
    add("|---|---:|---|---|")
    fresh_text: list[str] = []
    for path in sorted(fresh_dir.glob("*.txt")):
        fresh_text.append(decode_by_bom(path))
        add(
            f"| `{path.name}` | {path.stat().st_size} | {encoding_of(path)} "
            f"| `{sha256_file(path)}` |"
        )
    add("")

    committed_all = "\n".join(committed_text)
    fresh_all = "\n".join(fresh_text)

    add("## Load-bearing claim attestation")
    add("")
    add(
        "`committed` = attested by one of the five original artifacts. `fresh` = attested by this "
        "re-capture. A claim that is fresh-only was previously carried by MACHINE.md with no "
        "artifact behind it."
    )
    add("")
    add("| Claim | Committed | Fresh | Status |")
    add("|---|:---:|:---:|---|")
    for label, needle in LOAD_BEARING:
        in_committed = needle in committed_all
        in_fresh = needle in fresh_all
        if in_committed and in_fresh:
            status = "confirmed by both"
        elif in_fresh:
            status = "**GAP CLOSED** by re-capture"
        elif in_committed:
            status = "committed only — not re-captured"
        else:
            status = "**still unattested**"
        add(f"| {label} | {'yes' if in_committed else 'no'} | {'yes' if in_fresh else 'no'} | {status} |")
    add("")

    add("## Per-artifact unified diff")
    add("")
    for relative, counterpart in COUNTERPARTS.items():
        add(f"### `{relative}`")
        add("")
        if counterpart is None:
            add(
                "No fresh counterpart. This artifact carries no hardware content (a timestamp, the "
                "hostname, and `done`), so there is nothing to re-capture or contradict."
            )
            add("")
            continue

        committed_path = REPO_ROOT / relative
        fresh_path = fresh_dir / counterpart
        if not fresh_path.is_file():
            add(f"Fresh counterpart missing: `{counterpart}`")
            add("")
            continue

        diff = list(
            difflib.unified_diff(
                normalise(decode_by_bom(committed_path)),
                normalise(decode_by_bom(fresh_path)),
                fromfile=relative,
                tofile=f"{fresh_dir.name}/{counterpart}",
                lineterm="",
                n=1,
            )
        )
        if not diff:
            add("Identical after whitespace normalisation.")
        else:
            add(
                f"{len(diff)} diff line(s). The two captures ran different commands "
                f"(the originals used `wmic`, removed on 25H2), so a large diff is expected; "
                f"what matters is the claim table above."
            )
            add("")
            add("```diff")
            out.extend(diff)
            add("```")
        add("")

    report = "\n".join(out) + "\n"
    if args.out:
        # newline="" keeps LF. The repository has core.autocrlf=true and no .gitattributes, so a CRLF
        # file is normalised to LF in the index and its committed bytes stop matching the working
        # copy any cited hash was computed from.
        args.out.write_text(report, encoding="utf-8", newline="")
        print(f"wrote {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
