"""Build derived/SEAL_CENSUS.json and derived/SEAL_CENSUS.md.

Reads run trees. Does not write inside any run directory.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.seal_verify import verify_seal  # noqa: E402
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
PREFIX_RE = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{8})(?![0-9a-fA-F-])")
FINISH_KEYS = (
    "finished_utc",
    "ended_utc",
    "sealed_utc",
    "completed_utc",
    "finished_at",
    "ended_at",
)
SKIP_PARENTS = {"policies", "work", "cells", "artifacts"}
CITE_SUFFIXES = {".json", ".md", ".txt", ".yaml", ".yml"}


def _rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def _tracked_paths() -> set[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return {p for p in proc.stdout.decode("utf-8").split("\0") if p}


def _run_id_of(path: Path) -> str:
    match = UUID_RE.search(path.name)
    if match:
        return match.group(0).lower()
    for name in ("summary.json", "plan.json", ".sealed", "manifest.json"):
        file = path / name
        if not file.is_file() or file.stat().st_size > 8_000_000:
            continue
        try:
            doc = json.loads(file.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict):
            for key in ("run_id", "session_id"):
                value = doc.get(key)
                if isinstance(value, str) and UUID_RE.fullmatch(value):
                    return value.lower()
    return path.name


def _finish_time(path: Path) -> str | None:
    for name in ("summary.json", "plan.json", ".sealed", "manifest.json"):
        file = path / name
        if not file.is_file() or file.stat().st_size > 8_000_000:
            continue
        try:
            doc = json.loads(file.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        found = _find_finish(doc)
        if found:
            return found
    return None


def _find_finish(doc: Any) -> str | None:
    if isinstance(doc, dict):
        for key in FINISH_KEYS:
            value = doc.get(key)
            if isinstance(value, str) and value.strip():
                return value
        for key in ("run_environment", "seal"):
            nested = doc.get(key)
            if isinstance(nested, dict):
                found = _find_finish(nested)
                if found:
                    return found
    return None


def _newest_mtime(path: Path) -> str | None:
    newest: float | None = None
    for file in path.rglob("*"):
        if not file.is_file():
            continue
        stamp = file.stat().st_mtime
        if newest is None or stamp > newest:
            newest = stamp
    if newest is None:
        return None
    return datetime.fromtimestamp(newest, UTC).isoformat()


def _is_run_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    if path.parent.name in SKIP_PARENTS:
        return False
    if path.name in {"VOIDS", "work", "policies", "cells", "artifacts"}:
        return False
    if UUID_RE.search(path.name):
        return any(path.iterdir())
    return (path / ".sealed").is_file()


def discover_runs() -> list[dict[str, Any]]:
    tracked = _tracked_paths()
    found: list[Path] = []
    for base in (ROOT / "derived", ROOT / "raw"):
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if _is_run_dir(path):
                found.append(path)
    rows: list[dict[str, Any]] = []
    for path in sorted(found, key=lambda p: _rel(p)):
        rel = _rel(path)
        prefix = rel + "/"
        is_tracked = any(item == rel or item.startswith(prefix) for item in tracked)
        rows.append(
            {
                "run_id": _run_id_of(path),
                "path": rel,
                "tracked": "y" if is_tracked else "n",
                "verify_seal": verify_seal(path),
                "newest_file_mtime_utc": _newest_mtime(path),
                "recorded_finish_time": _finish_time(path),
            }
        )
    return rows


def _status_for(run_id: str, runs: list[dict[str, Any]]) -> str:
    matches = [row for row in runs if row["run_id"] == run_id.lower()]
    if not matches:
        prefix = run_id.lower()[:8]
        matches = [row for row in runs if str(row["run_id"]).startswith(prefix)]
    if not matches:
        return "NOT_IN_TREE"
    # Prefer a matching seal over an unsealed source copy.
    rank = {"MATCH": 0, "MATCH_LEGACY_SELF_REF": 1, "MISMATCH": 2, "UNSEALED": 3}
    matches.sort(key=lambda row: rank.get(row["verify_seal"], 9))
    best = matches[0]
    if len(matches) == 1:
        return best["verify_seal"]
    return f"{best['verify_seal']}@{best['path']}"


def scan_citations(runs: list[dict[str, Any]]) -> list[dict[str, str]]:
    by_prefix: dict[str, list[str]] = {}
    for row in runs:
        rid = str(row["run_id"])
        if UUID_RE.fullmatch(rid):
            by_prefix.setdefault(rid[:8], []).append(rid)
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    roots = [ROOT / "derived", ROOT / "docs"]
    for base in roots:
        if not base.is_dir():
            continue
        for file in base.rglob("*"):
            if not file.is_file() or file.suffix.lower() not in CITE_SUFFIXES:
                continue
            if file.name in {"SEAL_CENSUS.json", "SEAL_CENSUS.md"}:
                continue
            if file.stat().st_size > 30_000_000:
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            rel = _rel(file)
            cited: list[tuple[str, str]] = []
            for match in UUID_RE.finditer(text):
                cited.append((match.group(0), match.group(0).lower()))
            for match in PREFIX_RE.finditer(text):
                token = match.group(1).lower()
                window = text[max(0, match.start() - 60) : match.end() + 60].lower()
                known = token in by_prefix
                contextual = "run" in window or "session" in window
                if known or contextual:
                    full = by_prefix.get(token, [token])
                    # Ambiguous prefixes stay as the 8-char token.
                    resolved = full[0] if len(full) == 1 else token
                    cited.append((match.group(1), resolved))
            for value, resolved in cited:
                key = (rel, value.lower())
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "file": rel,
                        "value_cited": value,
                        "run_id": resolved,
                        "status": _status_for(resolved, runs),
                    }
                )
    rows.sort(key=lambda row: (row["file"], row["value_cited"]))
    return rows


def _spec_fields(run_path: Path) -> list[dict[str, Any]]:
    """One row per arm_id from work/*.spec.json, else plan.json."""
    specs = sorted(run_path.glob("work/*.spec.json"))
    if not specs:
        specs = sorted(run_path.glob("artifacts/work/*.spec.json"))
    by_arm: dict[str, dict[str, Any]] = {}
    for spec in specs:
        try:
            doc = json.loads(spec.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        arm = str(doc.get("arm_id") or spec.name)
        if arm in by_arm:
            continue
        props = doc.get("arm_properties") if isinstance(doc.get("arm_properties"), dict) else {}
        kv = doc.get("KV_CACHE_PRECISION") or props.get("KV_CACHE_PRECISION")
        by_arm[arm] = {
            "arm_id": doc.get("arm_id"),
            "KV_CACHE_PRECISION": kv,
            "model_dir": doc.get("model_dir"),
            "generate_device": doc.get("generate_device"),
            "affinity_cpus": doc.get("affinity_cpus"),
            "wslock": doc.get("wslock"),
            "max_new_tokens": doc.get("max_new_tokens"),
            "spec_file": _rel(spec),
        }
    return list(by_arm.values())


def _paper(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims = [
        {
            "claim": "cold limit 9750",
            "run_id": "c647f0c7-5cc9-47bb-a491-3450533c34d1",
            "note": "aipc-c1 gpu 4B-int4 ttft_limit_n",
        },
        {
            "claim": "46k retention TTFT 230-253 s",
            "run_id": "2b3316b6-7f6e-474f-9177-bd5a89aeb58c",
            "note": "CAP-4 medians at n=46000: f16 252.708, u8 230.360, u4 239.801",
        },
        {
            "claim": "residency 5.17x",
            "run_id": "cb781dbf-3486-4fbc-a69a-34026f801abe",
            "note": "8148.547/1576.441 = 5.169; pair with 9fdedb46",
        },
        {
            "claim": "residency 5.17x pair",
            "run_id": "9fdedb46-3318-4abc-a56f-50b7d23d25ca",
            "note": "RESIDENT wall 1576.441 s",
        },
        {
            "claim": "tier 3.09x",
            "run_id": "c647f0c7-5cc9-47bb-a491-3450533c34d1",
            "note": "9750/3156 with 322b2f86",
        },
        {
            "claim": "tier 3.09x pair",
            "run_id": "322b2f86-9571-46ae-be6a-ba1cec44e018",
            "note": "8B ttft_limit_n 3156",
        },
        {
            "claim": "tier 1.14x",
            "run_id": "5c714535",
            "note": "18687/16437; T2S trees not in this workspace",
        },
        {
            "claim": "tier 1.14x pair",
            "run_id": "051d2681",
            "note": "evo-t2 8B-int4 limit 16437",
        },
        {
            "claim": "weight 1.25x",
            "run_id": "fea55e0c-b9f8-4ba9-b5ea-558401910d74",
            "note": "9750/7781 with c647f0c7",
        },
        {
            "claim": "placement 19.5x",
            "run_id": "d3dcbd3b-5107-4b5e-a0dd-402f99f6f90c",
            "note": "9750/500 with c647f0c7",
        },
        {
            "claim": "prefill exponents 2.12-2.25",
            "run_id": "2b3316b6-7f6e-474f-9177-bd5a89aeb58c",
            "note": "b=2.1244 u8, 2.1512 u4, 2.2516 f16 on [12000, 76000]",
        },
        {
            "claim": "prefill exponent 1.85",
            "run_id": "65e33de8-ac07-405a-a1f8-53698974afe9",
            "note": "T2S b about 1.8487-1.8533 on the same fit range",
        },
        {
            "claim": "within-platform prediction 0.6% error",
            "run_id": None,
            "note": "No derived or docs file states this figure with a run_id",
        },
        {
            "claim": "8B SLO limit 3156",
            "run_id": "322b2f86-9571-46ae-be6a-ba1cec44e018",
            "note": "ttft_limit_n; passing repeats still under the 10 s SLO",
        },
        {
            "claim": "8B allocation ceiling 3312",
            "run_id": "322b2f86-9571-46ae-be6a-ba1cec44e018",
            "note": "CL_OUT_OF_RESOURCES / memory_wall, not the SLO limit",
        },
    ]
    for claim in claims:
        rid = claim["run_id"]
        claim["status"] = "NOT_LOCATED" if rid is None else _status_for(rid, runs)
    return claims


def _operating_limits(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        path = ROOT / run["path"]
        if "c2_ttft/" not in run["path"] and "cap4/" not in run["path"]:
            continue
        if "/sealed_" in run["path"]:
            continue
        fields = _spec_fields(path)
        if not fields and not run["path"].startswith("derived/c2_ttft/"):
            continue
        rows.append(
            {
                "run_id": run["run_id"],
                "path": run["path"],
                "verify_seal": run["verify_seal"],
                "arms": fields,
            }
        )
    known = {
        "run_id": "051d2681",
        "path": None,
        "verify_seal": "NOT_IN_TREE",
        "arms": [
            {
                "arm_id": None,
                "KV_CACHE_PRECISION": "f16",
                "model_dir": None,
                "generate_device": "GPU",
                "affinity_cpus": [0, 1, 2, 3],
                "wslock": {
                    "mode": "request",
                    "minimum_bytes": 4294967296,
                    "maximum_bytes": 12884901888,
                },
                "max_new_tokens": None,
                "source": "operator note; tree not in workspace",
            }
        ],
    }
    known_4b = {
        "run_id": "5c714535",
        "path": None,
        "verify_seal": "NOT_IN_TREE",
        "arms": [
            {
                "arm_id": None,
                "KV_CACHE_PRECISION": "f16",
                "model_dir": None,
                "generate_device": "GPU",
                "affinity_cpus": [0, 1, 2, 3],
                "wslock": {
                    "mode": "request",
                    "minimum_bytes": 4294967296,
                    "maximum_bytes": 12884901888,
                },
                "max_new_tokens": None,
                "source": "operator note; tree not in workspace",
            }
        ],
    }
    rows.extend([known, known_4b])
    return rows


def _norm(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _confounded_pairs(limits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cross-platform pairs a reader forms from the published limits."""
    by_id = {row["run_id"][:8]: row for row in limits}
    pairs = [
        ("c647f0c7", "5c714535", "4B limit aipc vs evo"),
        ("322b2f86", "051d2681", "8B limit aipc vs evo"),
    ]
    fields = (
        "arm_id",
        "KV_CACHE_PRECISION",
        "model_dir",
        "generate_device",
        "affinity_cpus",
        "wslock",
        "max_new_tokens",
    )
    out: list[dict[str, Any]] = []
    for left_id, right_id, label in pairs:
        left = by_id.get(left_id)
        right = by_id.get(right_id)
        if left is None or right is None:
            out.append({"pair": label, "status": "MISSING_RUN"})
            continue
        flags: list[str] = []
        # Compare each cited arm on the left to the single known right arm.
        right_arm = (right.get("arms") or [{}])[0]
        for arm in left.get("arms") or [{}]:
            for field in fields:
                lv = arm.get(field)
                rv = right_arm.get(field)
                if lv is None or rv is None:
                    continue
                if _norm(lv) != _norm(rv):
                    flag = f"CONFOUNDED({field})"
                    if flag not in flags:
                        flags.append(flag)
        out.append(
            {
                "pair": label,
                "left": left_id,
                "right": right_id,
                "flags": flags or ["none"],
            }
        )
    return out


def _cap3_orphans() -> list[dict[str, Any]]:
    return [
        {
            "value": "slo_s 10.0",
            "class": "CONFIG",
            "where": "c2 plan slo_s and tools/run_h1_hybrid.py TTFT_SLO_S",
        },
        {
            "value": "workload_max_tokens 7743",
            "class": "MEASURED_ORPHAN",
            "where": "cited by tools/c3_cloud_cost_curve.py as GPU multi-turn full_prompt max; no run_id on the figure",
        },
        {
            "value": "bfcl_tool_schema_tokens 2598",
            "class": "MEASURED_ORPHAN",
            "where": "cited beside 7743; appears as prompt_tokens in residency reports without a figure run_id",
        },
        {
            "value": "first SLO miss n=734",
            "class": "MEASURED_FOUND",
            "run_id": "d3dcbd3b-5107-4b5e-a0dd-402f99f6f90c",
        },
        {
            "value": "median prefill 10.86 s",
            "class": "MEASURED_FOUND",
            "run_id": "d3dcbd3b-5107-4b5e-a0dd-402f99f6f90c",
        },
        {
            "value": "CL_OUT_OF_RESOURCES n=3312",
            "class": "MEASURED_FOUND",
            "run_id": "322b2f86-9571-46ae-be6a-ba1cec44e018",
        },
        {
            "value": "passing prefill ~3.2 s",
            "class": "MEASURED_FOUND",
            "run_id": "322b2f86-9571-46ae-be6a-ba1cec44e018",
        },
        {
            "value": "memory_wall n=7937, 3 repeats",
            "class": "MEASURED_FOUND",
            "run_id": "fea55e0c-b9f8-4ba9-b5ea-558401910d74",
        },
        {
            "value": "first SLO miss n=10000, prefill ~10.08 s",
            "class": "MEASURED_FOUND",
            "run_id": "c647f0c7-5cc9-47bb-a491-3450533c34d1",
        },
        {
            "value": "f16 REFUSED_LOW_OVER_SLO n=8000",
            "class": "MEASURED_FOUND",
            "run_id": "c647f0c7-5cc9-47bb-a491-3450533c34d1",
        },
        {
            "value": "schema_share 0.823",
            "class": "DATASET_DERIVED",
            "where": "2598/3156 from the figure arithmetic; not an independent measurement",
        },
    ]


def _markdown(doc: dict[str, Any]) -> str:
    counts: dict[str, int] = {}
    tracked = {"y": 0, "n": 0}
    for row in doc["runs"]:
        counts[row["verify_seal"]] = counts.get(row["verify_seal"], 0) + 1
        tracked[row["tracked"]] = tracked.get(row["tracked"], 0) + 1
    lines = [
        "# Seal census",
        "",
        f"Run directories: {len(doc['runs'])}. Tracked {tracked.get('y', 0)}, untracked {tracked.get('n', 0)}.",
        "",
        "## 4a verify_seal counts",
        "",
        "| status | n |",
        "|---|---:|",
    ]
    for key in ("MATCH", "MATCH_LEGACY_SELF_REF", "MISMATCH", "UNSEALED"):
        lines.append(f"| {key} | {counts.get(key, 0)} |")
    lines.extend(["", "## 4c paper numbers", "", "| claim | run_id | status |", "|---|---|---|"])
    for claim in doc["paper_numbers"]:
        lines.append(
            f"| {claim['claim']} | {claim.get('run_id') or ''} | {claim['status']} |"
        )
    lines.extend(
        [
            "",
            "## 4d cross-platform field flags",
            "",
            "| pair | flags |",
            "|---|---|",
        ]
    )
    for pair in doc["cross_platform_flags"]:
        flags = ", ".join(pair.get("flags") or []) or pair.get("status", "")
        lines.append(f"| {pair.get('pair')} | {flags} |")
    lines.extend(["", "## 4e values without a figure run_id", "", "| value | class |", "|---|---|"])
    for item in doc["cap3_values_without_run_id"]:
        lines.append(f"| {item['value']} | {item['class']} |")
    lines.extend(
        [
            "",
            f"Citations recorded: {len(doc['citations'])}. Full rows are in SEAL_CENSUS.json.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    runs = discover_runs()
    citations = scan_citations(runs)
    limits = _operating_limits(runs)
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "runs": runs,
        "citations": citations,
        "paper_numbers": _paper(runs),
        "operating_limits": limits,
        "cross_platform_flags": _confounded_pairs(limits),
        "cap3_values_without_run_id": _cap3_orphans(),
    }
    out_json = ROOT / "derived" / "SEAL_CENSUS.json"
    out_md = ROOT / "derived" / "SEAL_CENSUS.md"
    out_json.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_markdown(doc), encoding="utf-8")
    print(f"runs={len(runs)} citations={len(citations)}")


if __name__ == "__main__":
    main()
