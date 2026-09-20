"""LAB-1: build orphan branch seam/characterization export for sharc-lab/APU."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "_seam_export_stage"
BRANCH = "seam/characterization"
FIVE_MB = 5 * 1024 * 1024


def run(cmd: list[str], *, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def copy_tree(src: Path, dst: Path, *, ignore=None) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore)


def ignore_junk(dirpath: str, names: list[str]) -> set[str]:
    skip = set()
    for n in names:
        if n in {"__pycache__", ".pytest_cache", ".mypy_cache", "target", ".rustc_info.json", "node_modules"}:
            skip.add(n)
        if n.endswith((".pyc", ".pyo")):
            skip.add(n)
        if n == "_retired":
            skip.add(n)
    return skip


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build_hardware_aipc_c1() -> str:
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
cpu_e_cores: 4        # LP-E cluster; EfficiencyClass=0
cpu_l3_cache_kb: null   # ASSUMED: not yet probe-attested in SEAM export
gpu: Intel(R) Graphics (Xe3 / Arc-class iGPU)
gpu_pci_device: "PCI\\\\VEN_8086&DEV_B090"
gpu_bios_stolen_mib: null   # ASSUMED: not yet filled from DXGI on this export
gpu_shared_system_mib: null # ASSUMED: dynamic DVMT; fill from DXGI before citing
memory_gb: 16
memory_type: LPDDR5X
memory_speed_mts: 7467      # ConfiguredClockSpeed from MACHINE.md; probe gap noted in aipc-c1.yaml
has_npu: true
npu_model: "Intel(R) NPU 5 (NPU 5010)"
npu_tops: UNKNOWN           # vendor peak INT8 50 TOPS is NOT achieved throughput; do not cite as measured
quant: null
bom_cost_usd: null
reserved_gb: null
achievable_pool_gb: null
bandwidth_gb_s: null        # forbidden until M2.4 measures; leave null
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
  build 26200. SEAM Platform A (aipc-c1). Topology citing_run
  fb5cd2d5-e850-4de1-9b90-d368b5aa9994. OpenVINO GenAI 2026.2.1 is the
  local inference stack used for sealed W-3/X-2/C-2 arms. Evidence canonical
  in zjohnson2005/gnn-hls-accel — see docs/SEAM_PROVENANCE.md.
'''


def build_hardware_evo_t2s_openvino() -> str:
    return '''# Additive OpenVINO runtime fields for EVO-T2S (does NOT replace evo_t2s.yaml).
# Hardware identity remains configs/hardware/evo_t2s.yaml on sharc main.
# This file records the SEAM/OpenVINO stack intended for T2S characterization.
name: evo_t2s_openvino
extends: evo_t2s
memory_architecture: unified
os: windows
source: "Additive SEAM export; hardware facts from evo_t2s.yaml (sharc/main)"
runtime:
  openvino: "2026.2.1"
  openvino_genai: "2026.2.1"
  stack: "OpenVINO GenAI LLMPipeline (same path as SEAM Platform A W-3/X-2)"
  note: >
    evo_t2s.yaml on sharc/main has no runtime pin. Populate exact build strings
    from a T2S load_arm_pipeline meta before citing as MEASURED. Values here are
    ASSUMED targets matching Platform A until T2S attests them.
notes: >
  Separate additive file so SEAM OpenVINO work on T2S does not overwrite
  configs/hardware/evo_t2s.yaml. Merge reviews should keep both.
'''


def build_sealed_index(out: Path) -> list[dict]:
    rows: list[dict] = []
    for base in (ROOT / "raw", ROOT / "derived"):
        if not base.is_dir():
            continue
        for sealed in base.rglob(".sealed"):
            try:
                doc = json.loads(sealed.read_text(encoding="utf-8"))
            except Exception:
                continue
            parent = sealed.parent
            summary_path = parent / "summary.json"
            kind = doc.get("kind") or doc.get("seal_style")
            measured = None
            date = doc.get("sealed_at_utc") or doc.get("sealed_utc")
            if summary_path.is_file():
                try:
                    s = json.loads(summary_path.read_text(encoding="utf-8"))
                    kind = kind or s.get("kind")
                    if s.get("ttft_limits"):
                        measured = f"ttft_limits={json.dumps(s['ttft_limits'], sort_keys=True)}"
                    elif s.get("criterion"):
                        measured = f"criterion={s['criterion']}"
                    elif s.get("status"):
                        measured = f"status={s['status']}"
                    date = date or s.get("ended_utc") or s.get("sealed_utc")
                except Exception:
                    pass
            rows.append(
                {
                    "run_id": doc.get("run_id") or doc.get("session_id") or parent.name,
                    "arm": None,
                    "date": date,
                    "tree_sha256": doc.get("tree_sha256"),
                    "kind": kind,
                    "measured": measured,
                    "source_path": parent.relative_to(ROOT).as_posix(),
                }
            )
    rows.sort(key=lambda r: (r.get("date") or "", r.get("run_id") or ""))
    write(out / "derived" / "SEAM_SEALED_INDEX.json", json.dumps(rows, indent=2) + "\n")
    lines = [
        "# SEAM sealed-run index (summaries only)",
        "",
        "Evidence artifacts stay in `zjohnson2005/gnn-hls-accel`. This table is",
        "an index of sealed `run_id`s with tree hashes — not the payloads.",
        "",
        "| run_id | date | kind | tree_sha256 | measured | source_path |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        rid = r.get("run_id") or ""
        lines.append(
            f"| `{rid}` | {r.get('date') or ''} | {r.get('kind') or ''} | "
            f"`{(r.get('tree_sha256') or '')[:16]}…` | {r.get('measured') or ''} | "
            f"`{r.get('source_path') or ''}` |"
        )
    write(out / "derived" / "SEAM_SEALED_INDEX.md", "\n".join(lines) + "\n")
    return rows


def build_docs(out: Path) -> None:
    write(
        out / "docs" / "SEAM_PROVENANCE.md",
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

Use the sealed index at `derived/SEAM_SEALED_INDEX.md` and the FDR / H-1
summary files under `derived/d1_replay/` to look up run_ids. To inspect
artifacts, clone the canonical repo and open the path listed in the index
`source_path` column (or the sealed directory named by `run_id`).

## GIT_SHA_MAP rewrite (AM-039)

History was rewritten once with `git filter-repo` to strip GitHub-rejected
oversized blobs (`vectors.npy`, a large mock JSON) so the evidence branch
could push. Sealed manifests still cite pre-rewrite commit SHAs via
`git_sha` fields; those sealed files are byte-identical.

The auditable old→new map is `docs/GIT_SHA_MAP.md` (AM-039). Cited SHAs
are **translatable**: for every sealed/ledger-cited commit, the rewritten
tree differs from the pre-rewrite tree only by deletion of the oversized
paths that were never inputs to any sealed run. Evidence tree digest over
`raw/`+`derived/` is unchanged across the rewrite.

Pre-rewrite archive (out of repo): local tag `prerewrite/875dc74`, bundle
SHA-256 `9878b87630586b7a43714aab1644ba95e03575968bb452fac2495680f6ff1792`.

## Requesting or mirroring raw artifacts

1. Clone `zjohnson2005/gnn-hls-accel` (canonical).
2. Locate the sealed directory via `derived/SEAM_SEALED_INDEX.md` or
   `raw/<run_id>/` / `derived/**/sealed_<run_id>/`.
3. Verify with the sealed `tree_sha256` / `.sealed` marker — do not trust
   size alone.
4. If you need a mirror without the full history, request a filtered
   archive of specific `run_id`s from the SEAM maintainer; do not invent
   substitute numbers.

## What this export deliberately omits

`raw/` run dirs, large derived artifacts, corpus, figures, analysis probe
dumps, censor trees, and the prerewrite bundle. Summaries and run_ids only.
""",
    )

    write(
        out / "docs" / "SEAM_OBJECTIVE_TABLE.md",
        """# SEAM axis-by-objective table

Each cell cites a `run_id` (or ASSUMED). Resolve payloads in
`zjohnson2005/gnn-hls-accel` via `derived/SEAM_SEALED_INDEX.md`.

| Axis / objective | What was measured | run_id / seal | Notes |
|---|---|---|---|
| Topology (P vs LP-E map) | Logical CPU clustering | `fb5cd2d5-e850-4de1-9b90-d368b5aa9994` | M1 ACCEPTED; not a performance ratio |
| C-2 TTFT limits (PROVISIONAL, unguarded canary) | turn-1 TTFT limit per KV | `62395fdb-1899-415f-b708-6adc81a24dda` | see also NOTE on unguarded |
| C-2 TTFT (canary present, never armed) | u8/u4 limits 9750 | `c647f0c7-5cc9-47bb-a491-3450533c34d1` | caveat: canary never armed |
| W-3 quality int4 | multi-turn BFCL quality | `6225d6e1-4e0a-41c9-90bb-695ecc5fbe0a` | H-1 entry pin |
| W-3 quality int8 | multi-turn BFCL quality | `1d8db970-4c18-4bcf-824d-d9c141b6eb22` | paired weight |
| X-2 feasibility / R1 source | cpu-p NON_RESIDENT wall | `cb781dbf-3486-4fbc-a69a-34026f801abe` | DERIVED R1 scale source |
| RESIDENT delta-prefill | SD-001 | `41e419bd-f3e9-43b1-8364-0ebd89fa086b` | H-1 input |
| Decode BW+c fit | gpu_only decode | `a784f5ec-5615-4fea-a680-a07874426ae4` | cpu-p decode ASSUMED from gpu fit |
| Commit intercept | — | `83127e1b-9d6e-4103-bee6-2a63c00f479f` | H-1 input |
| H-1 predicted cloud $ (R0/R2a/R2b/R1) | FDR replay predictions | see `derived/d1_replay/H1_PREDICTIONS.md` | numbers cite inputs above |
| Pareto / domination | config frontier | `derived/d1_replay/pareto.json` | replay over sealed configs |
| X-2 replay holdout check | replay consistency | `derived/d1_replay/X2_REPLAY_CHECK.md` | holdout results |

H-1 live MEASURED arms were not sealed in this export cut; predictions remain
replay-derived from the sealed inputs above.
""",
    )

    write(
        out / "docs" / "SEAM_MEASUREMENT_PROTOCOL.md",
        """# SEAM measurement protocol

Named to match sharc `docs/*` SCREAMING_SNAKE convention. Canonical detail:
`docs/CANARY_PROTOCOL.md`, launchers under `tools/`, and Phase −1 spec in the
canonical repo.

## Five gates (launchers)

Before spawn, launchers refuse unless:

1. Uptime / cold-boot gate (CHOSEN/PROVISIONAL where noted)
2. AC power online
3. Best Performance (or equivalent) power plan
4. Available memory ≥ floor (7000 MB for C-2/H-1 class)
5. Tier-1 processes absent (Cursor/chrome/msedge/claude/vmmem)

## Canary (INF-1 / INF-1b)

Fixed cell: `gpu_only_f16`, `n_cached=4000`, `delta=400`, `RESIDENT`.
Calibration `C=3`, `rel_drift_floor=0.05`, `onset_s=657`.

Interval:

```
N = min(floor(onset_s / mean_probe_wall_s),
        floor(planned_probe_count / (C + 1)))
```

Refuse to start if the budget cannot fit C calibration canaries + one armed
check. Refuse to seal with `armed == false` unless `-AllowUnguarded`, which
writes `UNGUARDED` into summary and seal. Trip → `FAIL_CANARY_DRIFT`.

## Sealed runs

Write-once sealed trees with `tree_sha256` / `.sealed` markers. `raw/` is
canonical evidence (not in this export). Every published number traces to a
`run_id`.

## Interleaved arms

Precision / residency matrices interleave arms; canaries fire on a fixed
cell so drift is comparable across the session.

## Pre-registered predictions

Predictions are written into `plan.json` before first probe (example: C-2
AM-038 agreement claim). Amendments require `AMENDMENTS.md` authorization.

## KV readback refusal

OpenVINO `KV_CACHE_PRECISION` is enforced via
`enforce_kv_cache_precision`. Normalized precision lives at
`loads[i].kv_cache_precision.readback.normalized`. Missing or `None`
normalized → **REFUSE** (arm must not run with unverified KV). Mismatch →
`KV_PRECISION_MISMATCH`. Live check: `tests/seam/test_h1_kv_readback_live.py`.
""",
    )

    write(
        out / "docs" / "SEAM_REPLAY_DESIGN.md",
        """# SEAM replay design and holdout results

## Design

`tools/fdr_replay.py` replays sealed local and cloud ledgers under routing
policies without new cloud spend for the local path:

- `cloud_only`
- `agnostic_default` (DERIVED from sealed X-2 `cb781dbf…`, not live)
- `slo_escalate` (TTFT / decode / ctx limits)
- `emission_escalate` (empty / non-parseable tool emission)

Outputs under `derived/d1_replay/`:

| File | Role |
|---|---|
| `configs.json` | Config grid used for Pareto |
| `pareto.json` | Domination / frontier |
| `H1_PREDICTIONS.md` / `h1_predictions.json` | H-1 predicted $ and quality |
| `X2_REPLAY_CHECK.md` | Holdout / consistency check |
| `X2_DECOMPOSITION.md` | Decomposition notes |

## Holdout / check results

See `derived/d1_replay/X2_REPLAY_CHECK.md` and `H1_PREDICTIONS.md` for the
cited run_ids and ASSUMED tags. Cloud $ fit documents ASSUMED(fit=20 entries)
explicitly in `H1_PREDICTIONS.md`.

## Live H-1

`tools/run_h1_hybrid.py` + `tools/launch_h1.ps1` execute policies live with
OpenVINO local backend and Anthropic cloud, cost cap, resume, and seal
guards. Stub backends cannot seal.
""",
    )


def stage_export() -> Path:
    if EXPORT.exists():
        shutil.rmtree(EXPORT)
    EXPORT.mkdir(parents=True)

    # a. seam/
    copy_tree(ROOT / "seam", EXPORT / "seam", ignore=ignore_junk)

    # b. tools/ (skip retired, rust target, huge binaries)
    def tools_ignore(dirpath: str, names: list[str]) -> set[str]:
        s = ignore_junk(dirpath, names)
        base = Path(dirpath).name
        for n in names:
            if n.endswith((".exe", ".dll", ".pyd")) and "rust" in dirpath.lower():
                s.add(n)
            if n == "cap01_rust_harness":
                s.add(n)
        if "rust_harness" in Path(dirpath).parts and base == "target":
            s.update(names)
        return s

    copy_tree(ROOT / "tools", EXPORT / "tools", ignore=tools_ignore)

    # c. tests/ under tests/seam/ to avoid colliding conftest/__init__
    copy_tree(ROOT / "tests", EXPORT / "tests" / "seam", ignore=ignore_junk)
    # fixtures
    fix = ROOT / "tests" / "fixtures"
    if fix.is_dir():
        copy_tree(fix, EXPORT / "tests" / "seam" / "fixtures", ignore=ignore_junk)

    # d. hardware configs
    write(EXPORT / "configs" / "hardware" / "aipc_c1.yaml", build_hardware_aipc_c1())
    write(EXPORT / "configs" / "hardware" / "evo_t2s_openvino.yaml", build_hardware_evo_t2s_openvino())

    # e. models
    copy_tree(ROOT / "configs" / "models", EXPORT / "configs" / "models", ignore=ignore_junk)

    # also useful non-colliding configs (optional additive)
    for name in ("platforms", "pricing"):
        src = ROOT / "configs" / name
        if src.is_dir():
            copy_tree(src, EXPORT / "configs" / name, ignore=ignore_junk)

    # f. derived summaries only
    d1_src = ROOT / "derived" / "d1_replay"
    d1_dst = EXPORT / "derived" / "d1_replay"
    d1_dst.mkdir(parents=True)
    allow = {
        "configs.json",
        "pareto.json",
        "H1_PREDICTIONS.md",
        "h1_predictions.json",
        "X2_REPLAY_CHECK.md",
        "X2_DECOMPOSITION.md",
        "x2_decomposition.json",
        "CLOUD_COST_FIT.md",
        "cloud_cost_fit.json",
        "CLOUD_RECONCILIATION.md",
        "cloud_reconciliation.json",
    }
    for p in d1_src.iterdir():
        if p.is_file() and p.name in allow:
            shutil.copy2(p, d1_dst / p.name)

    build_sealed_index(EXPORT)

    # g. docs
    build_docs(EXPORT)
    # GIT_SHA_MAP for provenance translation
    shutil.copy2(ROOT / "docs" / "GIT_SHA_MAP.md", EXPORT / "docs" / "GIT_SHA_MAP.md")
    for name in ("CANARY_PROTOCOL.md",):
        src = ROOT / "docs" / name
        if src.is_file():
            shutil.copy2(src, EXPORT / "docs" / f"SEAM_{name}")

    # Export README (does not overwrite sharc README.md — different name)
    write(
        EXPORT / "SEAM_EXPORT_README.md",
        """# SEAM characterization export

Reviewable export of SEAM onto `sharc-lab/APU` conventions.

- Canonical evidence: `zjohnson2005/gnn-hls-accel`
- Branch: `seam/characterization` (orphan export tree)
- Start: `docs/SEAM_PROVENANCE.md`

Does not modify `sharc/main` files. Adds `seam/`, `tools/`, `tests/seam/`,
`configs/hardware/aipc_c1.yaml`, `configs/hardware/evo_t2s_openvino.yaml`,
`configs/models/`, `derived/` summaries, and `docs/SEAM_*.md`.
""",
    )

    # Minimal .gitignore for the orphan tree
    write(
        EXPORT / ".gitignore",
        """__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.venv*/
*.egg-info/
""",
    )
    return EXPORT


def verify(stage: Path, sharc_paths: set[str]) -> dict:
    report: dict = {"top5": [], "collisions": [], "oversize": [], "untagged": []}
    files = [p for p in stage.rglob("*") if p.is_file()]
    sizes = sorted(((p.stat().st_size, p) for p in files), reverse=True)
    report["top5"] = [
        {"path": str(p.relative_to(stage).as_posix()), "bytes": sz} for sz, p in sizes[:5]
    ]
    report["oversize"] = [
        {"path": str(p.relative_to(stage).as_posix()), "bytes": sz}
        for sz, p in sizes
        if sz > FIVE_MB
    ]
    for p in files:
        rel = p.relative_to(stage).as_posix()
        if rel in sharc_paths:
            report["collisions"].append(rel)

    # Scan exported docs for number-like claims without run_id / ASSUMED
    # Heuristic: markdown lines with digits that look like measurements
    import re

    num_re = re.compile(
        r"(?<![`\\w])(\\d+\\.\\d+|\\d{2,})(?![`\\w/])"
    )
    for p in (stage / "docs").rglob("*.md"):
        if p.name == "GIT_SHA_MAP.md":
            continue
        text = p.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if "run_id" in line.lower() or "ASSUMED" in line or "`" in line and "fb5cd2d5" in text:
                pass
            if not num_re.search(line):
                continue
            # skip headings, tables of hashes, pure dates
            if line.strip().startswith("#"):
                continue
            if "sha" in line.lower() or "SHA" in line:
                continue
            if "run_id" in line or "ASSUMED" in line or "`" in line:
                # if line already has a backtick run-ish id or ASSUMED, ok
                if "ASSUMED" in line or re.search(r"`[0-9a-f]{8}", line):
                    continue
            # flag soft
            if any(tok in line.lower() for tok in ("limit", "tok", "usd", "$", "ttft", "gb", "mb")):
                if "ASSUMED" not in line and not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}", line):
                    report["untagged"].append(f"{p.name}:{i}:{line.strip()[:120]}")

    return report


def main() -> int:
    sharc_paths = set(
        run(["git", "ls-tree", "-r", "--name-only", "sharc/main"]).stdout.splitlines()
    )
    stage = stage_export()
    report = verify(stage, sharc_paths)
    write(stage / "EXPORT_VERIFY.json", json.dumps(report, indent=2) + "\n")
    print("VERIFY", json.dumps(report, indent=2))
    if report["oversize"]:
        print("REFUSED -- files >5MB present", flush=True)
        return 2
    if report["collisions"]:
        print("REFUSED -- path collisions with sharc/main", flush=True)
        return 2

    # Secrets check against staged tree (run from ROOT with path args if supported)
    # Create orphan branch and replace tree with stage
    # Save current branch
    cur = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    print("current_branch", cur)

    # Build orphan
    run(["git", "checkout", "--orphan", BRANCH], check=False)
    # orphan may fail if exists
    br = run(["git", "branch", "--list", BRANCH]).stdout.strip()
    if BRANCH in br and cur != BRANCH:
        run(["git", "branch", "-D", BRANCH], check=False)
        run(["git", "checkout", "--orphan", BRANCH])

    # Remove all tracked files from index/worktree carefully
    run(["git", "rm", "-rf", "."], check=False)
    # Clean leftover (keep .git)
    for child in ROOT.iterdir():
        if child.name in {".git", "_seam_export_stage", ".venv-seam", ".venv-oa01"}:
            continue
        if child.name.startswith(".venv"):
            continue
        # Don't delete local venvs / large ignored
        if child.is_dir() and child.name in {"raw", "derived", "analysis", "apu_characterization"}:
            # leave on disk but untracked — for orphan we need worktree clean of export-unwanted
            # Actually orphan checkout emptied index; working tree still has files.
            # Strategy: move stage contents into place via rsync-like copy into a clean worktree dir
            pass

    # Safer approach: use git read-tree empty + checkout stage via temporary
    # Reset soft: clear index, then copy only stage files into ROOT for commit
    # First, checkout orphan already done — wipe everything except .git and stage and venv
    keep = {".git", "_seam_export_stage", ".venv-seam", ".venv-oa01", ".gitignore"}
    for child in list(ROOT.iterdir()):
        if child.name in keep or child.name.startswith(".venv"):
            continue
        if child.name in {".cursor", ".cursorignore", ".idea"}:
            continue
        try:
            if child.is_dir():
                # skip deleting huge raw if we can leave it untracked — but it would get added if we git add .
                # So we must not git add raw. We'll git add only from stage by copying stage over a clean subset.
                pass
        except Exception as e:
            print("warn", child, e)

    # Copy stage files into ROOT paths (overlay), then git add only those paths
    for src in stage.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(stage)
        dst = ROOT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        run(["git", "add", "-f", str(rel)])

    # Secrets check
    sec = run(
        [sys.executable, "tools/hooks/check_no_secrets.py"],
        check=False,
    )
    print(sec.stdout)
    print(sec.stderr)
    if sec.returncode != 0:
        print("REFUSED -- secrets check failed")
        return 2

    msg = (
        "Export SEAM characterization for sharc-lab/APU review\n\n"
        "Orphan branch: code, configs, and derived summaries only.\n"
        "Canonical evidence remains zjohnson2005/gnn-hls-accel.\n"
    )
    run(["git", "commit", "-m", msg])
    print("COMMIT", run(["git", "rev-parse", "HEAD"]).stdout.strip())
    print("FILES", run(["git", "ls-tree", "-r", "--name-only", "HEAD"]).stdout.count("\n"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
