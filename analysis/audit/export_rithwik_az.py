"""Task AZ part 5: re-export of every run we cite to Rithwik (local bundle; nothing pushed).

"seam/characterization" is the orphan branch of sharc-lab/APU that
tools/_lab1_export_wt.py built in September (LAB-1). This script does not
touch that branch. It writes a local bundle so Rithwik can register the runs on
his side:

  <out>/INDEX.md, <out>/index.json   run_id -> claims, dirs, seal status,
                                     CONFIG_PROVENANCE row
  <out>/runs/<repo path>/...         copies of the committed run dirs
  <out>/MANIFEST.sha256              sha256 of every file in the bundle
  <out>/CONFIG_PROVENANCE.{md,json}  copied from derived/audit/

Run from the repo root:
  python analysis/audit/export_rithwik_az.py ~/seam_closeout_1013/export_rithwik_20261020
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis" / "audit"))

import config_provenance_az as cp  # noqa: E402

# run_id prefix -> claims (PAPER_EVIDENCE_MAP rows, CONFIG_PROVENANCE, Task AW-AZ pilots).
RUNS: dict[str, list[str]] = {
    "c647f0c7": ["I-1 9,750 cold edge: HELD (derived/WITHDRAWN.md)"],
    "c2246b1f": ["I-1 cold edge 10,000 (XPS GPU u8)", "placement 21.4x (GPU side)"],
    "7f232f86": ["placement 21.4x (CPU 468 side)"],
    "2b3316b6": ["46k cold-turn timing 230-253 s; GPU driver 8724 recorded"],
    "553b3a5c": ["I-2 resident limit f16 15,000"],
    "cf3555d5": ["I-2 resident limit u8 (= i8) 20,000"],
    "e4a22dac": ["I-2 resident limit u4 26,500"],
    "a5d19dcc": ["P3 cell 0: true-default resident limit 18,000 (2026-10-20)"],
    "83127e1b": ["I-2/I-8 C-1 f16 to 44,742 by paging (UNSEALED)"],
    "cb781dbf": ["I-3/I-4 cpu-p NON_RESIDENT 0.0; 5.17x"],
    "9fdedb46": ["I-3/I-4 cpu-p RESIDENT 0.729; 5.17x"],
    "afd1aa21": ["I-3/I-4 gpu_only NON_RESIDENT 1.0; 1.53x"],
    "0963168f": ["I-3/I-4 gpu_only RESIDENT 1.0"],
    "322b2f86": ["I-8 CAP-3 8B allocation ceiling 3,312 CL_OUT_OF_RESOURCES"],
    "2804d7fa": ["I-8 36,500 CL_OUT_OF_RESOURCES on the default KV arm"],
    "c759d72f": ["I-8 T2S B390 CL_OUT_OF_RESOURCES in the GPU canary (NPU loaded)"],
    "a784f5ec": ["I-10/E-4/E-5 weight precision: INT8 +1.74 GB, decode 1.3-1.5x"],
    "6225d6e1": ["I-10/E-6/E-7 int4 20/200"],
    "1d8db970": ["I-10/E-6/E-7 int8 23/200"],
    "a427233b": ["I-10 model tier"],
    "69234ed5": ["I-10 model tier"],
    "5c714535": ["E-11 T2S limit"],
    "051d2681": ["E-11 T2S limit"],
    "d2d5cc4a": ["E-11 T2S cold edge 18,500"],
    "56c116a6": ["E-11 T2S limit"],
    "41e419bd": ["E-3 16-bit prefill 15-27% faster at depth"],
    "72776603": ["E-3 warm turn-2 f16 0.639 s at 12k"],
    "1587d2f4": ["E-3 warm turn-2 u8 1.003 s at 12k"],
    "dd2b0779": ["E-3 warm turn-2 u4 0.946 s at 12k"],
    "180dfbb9": ["E-5 DECODE-MATCH int8 30-34% slower"],
    "ac4e5472": ["P0-v2 exchange rate"],
    "faa14a31": ["NPU 1024 -> 960 (T2S)"],
    "9acabbf7": ["NPU 2048 -> 1984 (T2S)"],
    "2ffbd61c": ["NPU 2048 -> 1984 (T2S)"],
    "2972e8c4": ["NPU 4096 -> 4032 TOOLCHAIN_CAP (T2S)"],
    "f7343708": ["DEMO-1 XPS V1"],
    "1acc8c58": ["DEMO-1 XPS V2 CPU"],
    "71d33f7a": ["DEMO-1 XPS V3 (part 1)"],
    "ab88f47f": ["DEMO-1 XPS V3 (part 2)"],
    "a678926e": ["DEMO-1 XPS V4 $0.184/task"],
    "b026f3fd": ["DEMO-1 T2S V1"],
    "a4284ab0": ["DEMO-1 T2S V3"],
    "30caa847": ["DEMO-1 T2S V4 $0.0129/task"],
    "d482c621": ["P-2 quality-reactive routing (W-3 200)"],
    "640ec474": ["DEMO-2 P0b XPS"],
    "39c1c131": ["DEMO-2 P6/P1/P8-i8 BASE_30 XPS"],
    "841b84e4": ["DEMO-2 P6 LONGCTX 1-14 XPS; entry-123 hang 1 (UNSEALED)"],
    "24c1abc0": ["entry-123 hang 2, XPS (UNSEALED)"],
    "15367c3a": ["DEMO-2 P6 LONGCTX 15-30 XPS (123 counted as hang)"],
    "027a07b7": ["P10 C1 prefix caching off: entry-123 hang 3, XPS (UNSEALED)"],
    "1f3a261a": ["DEMO-2 P8-u4 BASE_30 XPS"],
    "162a9b5c": ["DEMO-2 P8-u4 LONGCTX 1-14 XPS"],
    "687bbb9f": ["DEMO-2 P9 drift XPS"],
    "03632ad3": ["DEMO-2 P0b T2S"],
    "b90f1d5b": ["DEMO-2 arm A BASE_30 T2S (P8-i8)"],
    "09932887": ["arm A BASE_30 T2S, unplanned replicate (local-only A/A)"],
    "1a634610": ["DEMO-2 arm A LONGCTX 0-13 T2S"],
    "daa6c026": ["DEMO-2 arm A LONGCTX 15-29 T2S"],
    "bbdd1c0d": ["entry-123 hang 4, T2S (UNSEALED)"],
    "6c610aa6": ["DEMO-2 P8-u4 BASE_30 T2S"],
    "3aa565da": ["DEMO-2 P8-u4 LONGCTX 0-13 T2S"],
    "108d5f43": ["DEMO-2 P8-u4 LONGCTX 15-29 T2S"],
    "16996cdb": ["DEMO-2 P4 off T2S"],
    "4d8e2fb1": ["DEMO-2 P4 K3 T2S"],
    "cc32619a": ["DEMO-2 P4 K5 T2S"],
    "63b2567a": ["DEMO-2 P9 drift T2S"],
    "29209e26": ["DEMO-2 P2 i8 T2S"],
    "0a55c316": ["DEMO-2 P2 u4 T2S"],
    "aa01040d": ["DEMO-2 P2 f16 T2S"],
    "597f40a9": ["DEMO-2 P0a readback XPS"],
    "5e190568": ["DEMO-2 P0a readback T2S (record id)"],
}
EXTRA_DIRS = {"5e190568": ["derived/demo2_pilots/p0a_readback_t2s_20261020"]}


def _dirs(prefix: str) -> list[Path]:
    hits = subprocess.run(
        ["git", "ls-files", "derived"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    out: set[Path] = set()
    for h in hits:
        parts = h.split("/")
        for i, p in enumerate(parts[:-1]):
            if prefix in p and "_launches" not in parts:
                out.add(ROOT.joinpath(*parts[: i + 1]))
                break
    for extra in EXTRA_DIRS.get(prefix, []):
        out.add(ROOT / extra)
    return sorted(out)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(out: Path) -> int:
    if out.exists():
        raise SystemExit(f"REFUSED -- {out} exists; remove it first")
    prov = json.loads((ROOT / "derived/audit/CONFIG_PROVENANCE.json").read_text(encoding="utf-8"))
    prov_by_run: dict[str, list[str]] = {}
    for it in prov["items"]:
        for rid in it["run_ids"]:
            prov_by_run.setdefault(rid[:8], []).append(f"{it['number']} [{it['class']}]")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    rows: list[dict[str, Any]] = []
    for prefix, claims in RUNS.items():
        dirs = _dirs(prefix)
        for d in dirs:
            dst = out / "runs" / d.relative_to(ROOT)
            if d.is_dir():
                shutil.copytree(d, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(d, dst)
        rows.append(
            {
                "run_id_prefix": prefix,
                "claims": claims,
                "dirs": [str(d.relative_to(ROOT)) for d in dirs],
                "seal": cp._seal([d for d in dirs if d.is_dir()]) if dirs else "NOT FOUND",
                "config_provenance": prov_by_run.get(prefix, []),
            }
        )
    for name in ("CONFIG_PROVENANCE.md", "CONFIG_PROVENANCE.json"):
        shutil.copy2(ROOT / "derived/audit" / name, out / name)
    index = {"source_repo": "zjohnson2005/gnn-hls-accel", "source_head": head, "runs": rows}
    (out / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    lines = [
        "# Re-export for Rithwik: runs we cite (Task AZ, 2026-10-20)",
        "",
        f"Source: zjohnson2005/gnn-hls-accel at {head[:12]} (local commit; see the push note in",
        "the Task AZ report). Copies of the committed run dirs are under runs/ at their repo paths;",
        "MANIFEST.sha256 covers every file. 'seam/characterization' is the sharc-lab/APU orphan",
        "branch built by tools/_lab1_export_wt.py (LAB-1, September); this bundle does not touch it.",
        "Seal note: seals made before the -text policy verify after CRLF restore (see",
        "CONFIG_PROVENANCE.md, 'Seal status on this Mac').",
        "",
        "| run_id | claims | dirs | seal | provenance row |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        seal = r["seal"].replace("|", "/")
        lines.append(
            f"| {r['run_id_prefix']} | {'; '.join(r['claims'])} | {len(r['dirs'])} | {seal[:160]} | "
            f"{'; '.join(r['config_provenance']) or '-'} |"
        )
    (out / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    files = sorted(p for p in out.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256")
    (out / "MANIFEST.sha256").write_text(
        "".join(f"{_sha(p)}  {p.relative_to(out)}\n" for p in files), encoding="utf-8"
    )
    print(json.dumps({"out": str(out), "runs": len(rows), "files": len(files),
                      "not_found": [r["run_id_prefix"] for r in rows if not r["dirs"]]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]).expanduser()))
