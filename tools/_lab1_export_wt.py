"""LAB-1 export via dedicated worktree — main untouched."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel").resolve()
WT = Path(r"C:\Users\zjohn\Projects\seam-characterization-export").resolve()
BRANCH = "seam/characterization"
FIVE_MB = 5 * 1024 * 1024
PY = str(ROOT / ".venv-seam" / "Scripts" / "python.exe")


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(
        cmd, cwd=str(cwd or ROOT), check=check, text=True, capture_output=True
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def ignore_junk(dirpath: str, names: list[str]) -> set[str]:
    skip = set()
    parts = Path(dirpath).parts
    for n in names:
        if n in {"__pycache__", ".pytest_cache", ".mypy_cache", "node_modules", "_retired"}:
            skip.add(n)
        if n.endswith((".pyc", ".pyo")):
            skip.add(n)
        if "rust_harness" in parts and n == "target":
            skip.add(n)
    return skip


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore_junk)


def hardware_aipc() -> str:
    return '''# Platform A — Dell XPS 16 / Intel Core Ultra 5 325 (Panther Lake).
# SEAM export name: aipc_c1. Canonical evidence: zjohnson2005/gnn-hls-accel.
# Schema fields mirror configs/hardware/evo_t2s.yaml on sharc-lab/APU main.
#
# MEMORY ARCHITECTURE — UNIFIED
#   Xe3 iGPU (Arc-class integrated) shares the single 16 GB LPDDR5X pool with
#   CPU, NPU, OS, weights, and KV. No discrete VRAM.
#
# CPU CORE TOPOLOGY — measured M1 run_id fb5cd2d5-e850-4de1-9b90-d368b5aa9994
#   P-cores (EfficiencyClass=1): 4  logical CPUs 0-3
#   LP-E cores (EfficiencyClass=0): 4  logical CPUs 4-7
#   Total: 8 physical = 8 logical (no SMT on this SKU)
#
hostname: computadora
source: "SEAM Platform A probe + M1 topology verify; see zjohnson2005/gnn-hls-accel configs/platforms/aipc-c1.yaml"
name: aipc_c1
memory_architecture: unified
os: windows
os_version: "11 Pro 10.0.26200"
cpu: Intel(R) Core(TM) Ultra 5 325
cpu_vendor: GenuineIntel
cpu_cores_physical: 8
cpu_cores_logical: 8
cpu_p_cores: 4
cpu_e_cores: 4
cpu_l3_cache_kb: null   # ASSUMED: not yet probe-attested in SEAM export
gpu: Intel(R) Graphics (Xe3 / Arc-class iGPU)
gpu_pci_device: "PCI\\VEN_8086&DEV_B090"
gpu_bios_stolen_mib: null   # ASSUMED: not yet filled from DXGI on this export
gpu_shared_system_mib: null # ASSUMED: dynamic DVMT; fill from DXGI before citing
memory_gb: 16
memory_type: LPDDR5X
memory_speed_mts: 7467
has_npu: true
npu_model: "Intel(R) NPU 5 (NPU 5010)"
npu_tops: UNKNOWN
quant: null
bom_cost_usd: null
reserved_gb: null
achievable_pool_gb: null
bandwidth_gb_s: null
thermal_ceiling_w: null
runtime:
  openvino: "2026.2.1-21919-ede283a88e3-releases/2026/2"
  openvino_genai: "2026.2.1.0-3123-7dea0459b2a"
  note: "Pinned from live load_arm_pipeline meta on Platform A (D-2c inspect)."
gpu_tools:
  nvidia_smi: absent
  rocm_smi: absent
  rocminfo: absent
  intel_gpu_top: absent
  clinfo: absent
notes: >
  Dell XPS 16 DA16260, Intel Core Ultra 5 325 (Panther Lake), 4 P + 4 LP-E,
  8 logical CPUs no SMT, 16 GB unified LPDDR5X, Xe3 iGPU, NPU 5, Windows 11
  build 26200. SEAM Platform A (aipc_c1). Topology citing_run
  fb5cd2d5-e850-4de1-9b90-d368b5aa9994. OpenVINO GenAI 2026.2.1 is the
  local inference stack used for sealed W-3/X-2/C-2 arms. Evidence canonical
  in zjohnson2005/gnn-hls-accel — see docs/SEAM_PROVENANCE.md.
'''


def hardware_evo_ov() -> str:
    return '''# Additive OpenVINO runtime fields for EVO-T2S (does NOT replace evo_t2s.yaml).
name: evo_t2s_openvino
extends: evo_t2s
memory_architecture: unified
os: windows
source: "Additive SEAM export; hardware facts from evo_t2s.yaml (sharc/main)"
runtime:
  openvino: "2026.2.1"   # ASSUMED target until T2S attests exact build string
  openvino_genai: "2026.2.1"  # ASSUMED target until T2S attests
  stack: "OpenVINO GenAI LLMPipeline (same path as SEAM Platform A W-3/X-2)"
notes: >
  Separate additive file so SEAM OpenVINO work on T2S does not overwrite
  configs/hardware/evo_t2s.yaml. Merge reviews should keep both.
'''


def populate(dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    copy_tree(ROOT / "seam", dest / "seam")
    copy_tree(ROOT / "tools", dest / "tools")
    # remove lab1 helper if copied
    for helper in (dest / "tools" / "_lab1_export.py", dest / "tools" / "_lab1_export_wt.py"):
        if helper.exists():
            helper.unlink()

    copy_tree(ROOT / "tests", dest / "tests" / "seam")

    write(dest / "configs" / "hardware" / "aipc_c1.yaml", hardware_aipc())
    write(dest / "configs" / "hardware" / "evo_t2s_openvino.yaml", hardware_evo_ov())
    copy_tree(ROOT / "configs" / "models", dest / "configs" / "models")
    for name in ("platforms", "pricing"):
        src = ROOT / "configs" / name
        if src.is_dir():
            copy_tree(src, dest / "configs" / name)

    d1 = dest / "derived" / "d1_replay"
    d1.mkdir(parents=True)
    allow = {
        "configs.json", "pareto.json", "H1_PREDICTIONS.md", "h1_predictions.json",
        "X2_REPLAY_CHECK.md", "X2_DECOMPOSITION.md", "x2_decomposition.json",
        "CLOUD_COST_FIT.md", "cloud_cost_fit.json",
        "CLOUD_RECONCILIATION.md", "cloud_reconciliation.json",
    }
    for p in (ROOT / "derived" / "d1_replay").iterdir():
        if p.is_file() and p.name in allow:
            shutil.copy2(p, d1 / p.name)

    # sealed index
    rows = []
    for base in (ROOT / "raw", ROOT / "derived"):
        if not base.is_dir():
            continue
        for sealed in base.rglob(".sealed"):
            try:
                doc = json.loads(sealed.read_text(encoding="utf-8"))
            except Exception:
                continue
            parent = sealed.parent
            kind = doc.get("kind") or doc.get("seal_style")
            measured = None
            date = doc.get("sealed_at_utc") or doc.get("sealed_utc")
            summ = parent / "summary.json"
            if summ.is_file():
                try:
                    s = json.loads(summ.read_text(encoding="utf-8"))
                    kind = kind or s.get("kind")
                    if s.get("ttft_limits"):
                        measured = "ttft_limits=" + json.dumps(s["ttft_limits"], sort_keys=True)
                    elif s.get("criterion"):
                        measured = f"criterion={s['criterion']}"
                    date = date or s.get("ended_utc")
                except Exception:
                    pass
            rows.append({
                "run_id": doc.get("run_id") or doc.get("session_id") or parent.name,
                "arm": None,
                "date": date,
                "tree_sha256": doc.get("tree_sha256"),
                "kind": kind,
                "measured": measured,
                "source_path": parent.relative_to(ROOT).as_posix(),
            })
    rows.sort(key=lambda r: (r.get("date") or "", r.get("run_id") or ""))
    write(dest / "derived" / "SEAM_SEALED_INDEX.json", json.dumps(rows, indent=2) + "\n")
    lines = [
        "# SEAM sealed-run index (summaries only)",
        "",
        "Evidence artifacts stay in `zjohnson2005/gnn-hls-accel`. Index only.",
        "",
        "| run_id | date | kind | tree_sha256 (prefix) | measured | source_path |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        th = (r.get("tree_sha256") or "")[:16]
        lines.append(
            f"| `{r.get('run_id')}` | {r.get('date') or ''} | {r.get('kind') or ''} | "
            f"`{th}…` | {r.get('measured') or ''} | `{r.get('source_path')}` |"
        )
    write(dest / "derived" / "SEAM_SEALED_INDEX.md", "\n".join(lines) + "\n")

    # docs
    write(dest / "docs" / "SEAM_PROVENANCE.md", (ROOT / "docs" / "GIT_SHA_MAP.md").exists() and open(ROOT / "docs" / "GIT_SHA_MAP.md", encoding="utf-8").read() and """# SEAM Provenance (export)

## Canonical evidence repo

All sealed measurement evidence for SEAM lives in
**[zjohnson2005/gnn-hls-accel](https://github.com/zjohnson2005/gnn-hls-accel)**.
That repository is **canonical for provenance**. This `seam/characterization`
branch on `sharc-lab/APU` is a **reviewable export** of code, configs, and
derived summaries only. It does not move `raw/` payloads.

## How numbers resolve

Every numeric claim in the export docs either:

1. cites a `run_id` that resolves to a sealed tree under `raw/` or
   `derived/` in `zjohnson2005/gnn-hls-accel`, or
2. is explicitly tagged **ASSUMED**.

Use `derived/SEAM_SEALED_INDEX.md` and `derived/d1_replay/` to look up
run_ids. To inspect bytes, clone the canonical repo and open the path in
the index `source_path` column.

## GIT_SHA_MAP rewrite (AM-039)

History was rewritten once with `git filter-repo` to strip GitHub-rejected
oversized blobs so the evidence branch could push. Sealed manifests still
cite pre-rewrite commit SHAs via `git_sha` fields; those sealed files are
byte-identical.

The auditable old→new map is `docs/GIT_SHA_MAP.md` (AM-039). Cited SHAs
are **translatable**: rewritten trees differ from pre-rewrite trees only by
deletion of oversized paths that were never inputs to sealed runs. Evidence
tree digest over `raw/`+`derived/` is unchanged across the rewrite.

Pre-rewrite archive (out of repo): local tag `prerewrite/875dc74`, bundle
SHA-256 `9878b87630586b7a43714aab1644ba95e03575968bb452fac2495680f6ff1792`.

## Requesting or mirroring raw artifacts

1. Clone `zjohnson2005/gnn-hls-accel` (canonical).
2. Locate the sealed directory via `derived/SEAM_SEALED_INDEX.md`.
3. Verify with the sealed `tree_sha256` / `.sealed` marker.
4. For a partial mirror, request specific `run_id`s from the SEAM maintainer;
   do not invent substitute numbers.

## What this export deliberately omits

`raw/` run dirs, large derived artifacts, corpus, figures, analysis probe
dumps, censor trees, and the prerewrite bundle.
""" or "")

    # fix provenance write - the ternary above is ugly; rewrite cleanly
    write(
        dest / "docs" / "SEAM_PROVENANCE.md",
        """# SEAM Provenance (export)

## Canonical evidence repo

All sealed measurement evidence for SEAM lives in
**[zjohnson2005/gnn-hls-accel](https://github.com/zjohnson2005/gnn-hls-accel)**.
That repository is **canonical for provenance**. This `seam/characterization`
branch on `sharc-lab/APU` is a **reviewable export** of code, configs, and
derived summaries only. It does not move `raw/` payloads.

## How numbers resolve

Every numeric claim in the export docs either:

1. cites a `run_id` that resolves to a sealed tree under `raw/` or
   `derived/` in `zjohnson2005/gnn-hls-accel`, or
2. is explicitly tagged **ASSUMED**.

Use `derived/SEAM_SEALED_INDEX.md` and `derived/d1_replay/` to look up
run_ids. To inspect bytes, clone the canonical repo and open the path in
the index `source_path` column.

## GIT_SHA_MAP rewrite (AM-039)

History was rewritten once with `git filter-repo` to strip GitHub-rejected
oversized blobs so the evidence branch could push. Sealed manifests still
cite pre-rewrite commit SHAs via `git_sha` fields; those sealed files are
byte-identical.

The auditable old→new map is `docs/GIT_SHA_MAP.md` (AM-039). Cited SHAs
are **translatable**: rewritten trees differ from pre-rewrite trees only by
deletion of oversized paths that were never inputs to sealed runs. Evidence
tree digest over `raw/`+`derived/` is unchanged across the rewrite.

Pre-rewrite archive (out of repo): local tag `prerewrite/875dc74`, bundle
SHA-256 `9878b87630586b7a43714aab1644ba95e03575968bb452fac2495680f6ff1792`.

## Requesting or mirroring raw artifacts

1. Clone `zjohnson2005/gnn-hls-accel` (canonical).
2. Locate the sealed directory via `derived/SEAM_SEALED_INDEX.md`.
3. Verify with the sealed `tree_sha256` / `.sealed` marker.
4. For a partial mirror, request specific `run_id`s from the SEAM maintainer;
   do not invent substitute numbers.

## What this export deliberately omits

`raw/` run dirs, large derived artifacts, corpus, figures, analysis probe
dumps, censor trees, and the prerewrite bundle.
""",
    )

    write(
        dest / "docs" / "SEAM_OBJECTIVE_TABLE.md",
        """# SEAM axis-by-objective table

Each cell cites a `run_id` (or ASSUMED). Resolve payloads in
`zjohnson2005/gnn-hls-accel` via `derived/SEAM_SEALED_INDEX.md`.

| Axis / objective | What was measured | run_id / seal | Notes |
|---|---|---|---|
| Topology (P vs LP-E map) | Logical CPU clustering | `fb5cd2d5-e850-4de1-9b90-d368b5aa9994` | M1 ACCEPTED; not a performance ratio |
| C-2 TTFT limits (unguarded canary era) | turn-1 TTFT limit per KV | `62395fdb-1899-415f-b708-6adc81a24dda` | see RESULT note on unguarded |
| C-2 TTFT (canary present, never armed) | u8/u4 limits 9750 | `c647f0c7-5cc9-47bb-a491-3450533c34d1` | caveat: canary never armed |
| W-3 quality int4 | multi-turn BFCL quality | `6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a` | H-1 entry pin |
| W-3 quality int8 | multi-turn BFCL quality | `1d8db970-4c18-4bcf-824d-d9c141b6eb22` | paired weight |
| X-2 feasibility / R1 source | cpu-p NON_RESIDENT wall | `cb781dbf-3486-4fbc-a69a-34026f801abe` | DERIVED R1 scale source |
| RESIDENT delta-prefill | SD-001 | `41e419bd-f3e9-43b1-8364-0ebd89fa086b` | H-1 input |
| Decode BW+c fit | gpu_only decode | `a784f5ec-5615-4fea-a680-a07874426ae4` | cpu-p decode ASSUMED from gpu fit |
| Commit intercept | — | `83127e1b-9d6e-4103-bee6-2a63c00f479f` | H-1 input |
| H-1 predicted cloud $ | FDR replay predictions | `derived/d1_replay/H1_PREDICTIONS.md` | cites input run_ids above |
| Pareto / domination | config frontier | `derived/d1_replay/pareto.json` | replay over sealed configs |
| X-2 replay holdout check | replay consistency | `derived/d1_replay/X2_REPLAY_CHECK.md` | holdout results |
""",
    )

    write(
        dest / "docs" / "SEAM_MEASUREMENT_PROTOCOL.md",
        """# SEAM measurement protocol

## Five gates (launchers)

Before spawn, launchers refuse unless: uptime/cold-boot gate; AC online;
Best Performance power plan; Available MB ≥ floor (7000 for C-2/H-1);
tier-1 processes absent (Cursor/chrome/msedge/claude/vmmem).

## Canary (INF-1 / INF-1b)

Fixed cell: `gpu_only_f16`, `n_cached=4000`, `delta=400`, `RESIDENT`.
`C=3`, `rel_drift_floor=0.05`, `onset_s=657`.

```
N = min(floor(onset_s / mean_probe_wall_s),
        floor(planned_probe_count / (C + 1)))
```

Refuse to start if budget cannot fit C + 1 canaries. Refuse to seal with
`armed == false` unless `-AllowUnguarded` (writes `UNGUARDED`). Trip →
`FAIL_CANARY_DRIFT`.

## Sealed runs

Write-once trees with `tree_sha256` / `.sealed`. Every published number
traces to a `run_id` in `zjohnson2005/gnn-hls-accel`.

## Interleaved arms

Matrices interleave arms; canaries use one fixed cell.

## Pre-registered predictions

Written into `plan.json` before first probe (e.g. C-2 AM-038). Amendments
require authorization in `AMENDMENTS.md` (canonical repo).

## KV readback refusal

Normalized precision path:
`loads[i].kv_cache_precision.readback.normalized`.
`None` or missing → REFUSE. Mismatch → `KV_PRECISION_MISMATCH`.
""",
    )

    write(
        dest / "docs" / "SEAM_REPLAY_DESIGN.md",
        """# SEAM replay design and holdout results

## Design

`tools/fdr_replay.py` replays sealed local/cloud ledgers under:

- `cloud_only`
- `agnostic_default` (DERIVED from sealed X-2 `cb781dbf-3486-4fbc-a69a-34026f801abe`)
- `slo_escalate`
- `emission_escalate`

## Outputs (`derived/d1_replay/`)

| File | Role |
|---|---|
| `configs.json` | Config grid |
| `pareto.json` | Domination / frontier |
| `H1_PREDICTIONS.md` | Predicted $ / quality (run_ids cited) |
| `X2_REPLAY_CHECK.md` | Holdout / consistency |

Holdout details and ASSUMED tags: see those files. Cloud $ fit tags
ASSUMED(fit=20 entries) in `H1_PREDICTIONS.md`.
""",
    )

    shutil.copy2(ROOT / "docs" / "GIT_SHA_MAP.md", dest / "docs" / "GIT_SHA_MAP.md")
    canary = ROOT / "docs" / "CANARY_PROTOCOL.md"
    if canary.is_file():
        shutil.copy2(canary, dest / "docs" / "SEAM_CANARY_PROTOCOL.md")

    write(
        dest / "SEAM_EXPORT_README.md",
        """# SEAM characterization export

Reviewable export for `sharc-lab/APU` (`seam/characterization`).

Canonical evidence: `zjohnson2005/gnn-hls-accel`. Start at
`docs/SEAM_PROVENANCE.md`.

Adds only new paths relative to `sharc/main` (no overwrites).
""",
    )
    write(dest / ".gitignore", "__pycache__/\n*.pyc\n.pytest_cache/\n.mypy_cache/\n.venv*/\n")


def verify(dest: Path, sharc_paths: set[str]) -> dict:
    files = [p for p in dest.rglob("*") if p.is_file()]
    sizes = sorted(((p.stat().st_size, p) for p in files), reverse=True)
    report = {
        "top5": [{"path": p.relative_to(dest).as_posix(), "bytes": sz} for sz, p in sizes[:5]],
        "oversize": [
            {"path": p.relative_to(dest).as_posix(), "bytes": sz}
            for sz, p in sizes
            if sz > FIVE_MB
        ],
        "collisions": [],
        "untagged": [],
    }
    for p in files:
        rel = p.relative_to(dest).as_posix()
        if rel in sharc_paths:
            report["collisions"].append(rel)

    # untagged numbers in SEAM docs we authored (not GIT_SHA_MAP hash tables)
    for p in (dest / "docs").glob("SEAM_*.md"):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "ASSUMED" in line or re.search(r"`[0-9a-f]{8}", line):
                continue
            if re.search(r"\b(9750|50 TOPS|120 GB)\b", line) and "ASSUMED" not in line:
                if "9750" in line and "c647f0c7" in line:
                    continue  # cited with run_id on same row ideally
                if "9750" in line and "c647f0c7" not in line:
                    report["untagged"].append(f"{p.name}:{i}:{line.strip()[:100]}")
    return report


def main() -> int:
    sharc_paths = set(run(["git", "ls-tree", "-r", "--name-only", "sharc/main"]).stdout.splitlines())

    # Ensure we're on main and leave it alone
    cur = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    if cur != "main":
        print(f"NOTE -- currently on {cur}; expected main for worktree base")

    # Remove old branch/worktree if present
    run(["git", "worktree", "remove", "--force", str(WT)], check=False)
    run(["git", "branch", "-D", BRANCH], check=False)

    # Orphan branch in new worktree: create empty orphan via
    # git worktree add -B then reset --orphan
    run(["git", "worktree", "add", "--detach", str(WT)])
    run(["git", "checkout", "--orphan", BRANCH], cwd=WT)
    run(["git", "rm", "-rf", "."], cwd=WT, check=False)

    # Clear leftover files in worktree except .git
    for child in list(WT.iterdir()):
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    populate(WT)
    report = verify(WT, sharc_paths)
    write(WT / "EXPORT_VERIFY.json", json.dumps(report, indent=2) + "\n")
    print("VERIFY", json.dumps(report, indent=2))
    if report["oversize"] or report["collisions"]:
        print("REFUSED -- oversize or collisions")
        return 2

    # secrets check: run from worktree if script exists
    sec_script = WT / "tools" / "hooks" / "check_no_secrets.py"
    if sec_script.is_file():
        sec = run([PY, str(sec_script)], cwd=WT, check=False)
        print(sec.stdout)
        print(sec.stderr)
        if sec.returncode != 0:
            print("REFUSED -- secrets")
            return 2
    else:
        print("WARN -- check_no_secrets.py missing in export")

    run(["git", "add", "-A"], cwd=WT)
    run(
        [
            "git",
            "commit",
            "-m",
            "Export SEAM characterization for sharc-lab/APU review\n\n"
            "Orphan branch with code, configs, and derived summaries only.\n"
            "Canonical evidence remains zjohnson2005/gnn-hls-accel.\n",
        ],
        cwd=WT,
    )
    head = run(["git", "rev-parse", "HEAD"], cwd=WT).stdout.strip()
    files = run(["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=WT).stdout.strip().splitlines()
    print("HEAD", head)
    print("N_FILES", len(files))
    print("FILE_LIST_BEGIN")
    for f in files:
        print(f)
    print("FILE_LIST_END")

    # Push
    push = run(
        ["git", "push", "sharc", f"{BRANCH}:refs/heads/{BRANCH}"],
        cwd=WT,
        check=False,
    )
    print(push.stdout)
    print(push.stderr)
    if push.returncode != 0:
        return push.returncode

    print("BRANCH_URL https://github.com/sharc-lab/APU/tree/seam/characterization")
    print("COMPARE https://github.com/sharc-lab/APU/compare/main...seam/characterization")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
