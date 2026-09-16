"""Data-independent CAP-01 source, protocol, and matrix preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apu_characterization.cap01.contracts import (
    enumerate_primary_matrix,
    load_protocol,
    validate_lock,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "apu_characterization/cap01/protocol_cap01_v2.json",
    "apu_characterization/cap01/contracts.py",
    "apu_characterization/cap01/protocol_lock.py",
    "apu_characterization/cap01/corpus.py",
    "apu_characterization/cap01/pool.py",
    "apu_characterization/cap01/generation.py",
    "apu_characterization/cap01/verifier.py",
    "apu_characterization/cap01/domain_verifiers.py",
    "apu_characterization/cap01/calibration.py",
    "apu_characterization/cap01/latency.py",
    "apu_characterization/cap01/budget.py",
    "apu_characterization/cap01/instrumentation.py",
    "apu_characterization/cap01/harnesses.py",
    "apu_characterization/cap01/runner.py",
    "apu_characterization/cap01/audit.py",
    "apu_characterization/cap01/floor.py",
    "apu_characterization/cap01/energy.py",
    "apu_characterization/cap01/host.py",
    "apu_characterization/cap01/statistics.py",
    "apu_characterization/cap01/analyze.py",
    "apu_characterization/cap01/report.py",
    "apu_characterization/cap01/schedule.py",
    "apu_characterization/cap01/verification_audit.py",
    "apu_characterization/cap01/figures.py",
    "apu_characterization/cap01/rust_harness/Cargo.toml",
    "apu_characterization/METHODOLOGY_CAP01.md",
    "apu_characterization/VERIFIABLE_DATA.md",
)


def check_bundle(locked_protocol: Path | None = None) -> list[str]:
    errors = [
        f"missing required source: {relative}"
        for relative in REQUIRED
        if not (REPO_ROOT / relative).is_file()
    ]
    template = load_protocol()
    cells = enumerate_primary_matrix(template)
    if len(cells) != 180 or len({cell.cell_id for cell in cells}) != 180:
        errors.append("primary matrix must contain 180 unique cells")
    if "praetor" in template["matrix"]["harnesses"]:
        errors.append("Praetor must not be a measured harness")
    if template["candidate_pool"]["minimum_candidates_per_task"] < 2048:
        errors.append("candidate pool depth reintroduces primary-cell censoring")
    primary = template["statistics"]["primary_cell"]
    if (
        primary["latency_scale_ms"] != 5
        or primary["budget_selection"] != "domain_primary_tier"
        or primary["population"] != "SCALING"
        or primary["contrast"] != ["langgraph", "rust"]
        or len(primary["domains"]) != 5
    ):
        errors.append("primary statistical cell differs from frozen protocol")
    if template["statistics"]["secondary_family"]["correction"] != "Holm":
        errors.append("secondary family must use Holm correction")
    g8 = template["gates"].get("G8") or {}
    if (
        g8.get("name") != "verifier_cost_parity"
        or float(g8.get("relative_tolerance", 0)) != 0.15
        or int(g8.get("minimum_repeats_per_harness_domain", 0)) < 200
    ):
        errors.append("G8 verifier cost parity gate is missing or mistuned")
    ledger = json.loads(
        (REPO_ROOT / "apu_characterization/cap01/died_ledger.json").read_text(
            encoding="utf-8"
        )
    )
    if len(ledger.get("entries") or []) < 4:
        errors.append("four CAP-02 deferral died-ledger entries are required")
    if locked_protocol is not None:
        try:
            locked = json.loads(locked_protocol.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read locked protocol: {exc}")
        else:
            errors.extend(validate_lock(locked))
            if locked.get("protocol_version") != template["protocol_version"]:
                errors.append("locked protocol version differs from source template")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locked-protocol", type=Path)
    args = parser.parse_args()
    errors = check_bundle(args.locked_protocol)
    if errors:
        raise SystemExit("CAP-01 bundle check failed:\n- " + "\n- ".join(errors))
    print("CAP-01 bundle check: PASS")
    print("matrix: 180 cells")
    print("measured harnesses: langgraph, rust, raw_python")
    print("Tier D: projection only")


if __name__ == "__main__":
    main()
