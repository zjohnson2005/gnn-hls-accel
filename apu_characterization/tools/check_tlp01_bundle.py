"""Data-independent TLP-01 source, protocol, and gate preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from apu_characterization.tlp01.contracts import (
    GATE_NAMES,
    MACHINE_MODELS,
    load_protocol,
    validate_lock,
    validate_template,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED = (
    "apu_characterization/tlp01/protocol_tlp01_v2.json",
    "apu_characterization/tlp01/contracts.py",
    "apu_characterization/tlp01/protocol_lock.py",
    "apu_characterization/tlp01/schema.py",
    "apu_characterization/tlp01/extract.py",
    "apu_characterization/tlp01/dependence.py",
    "apu_characterization/tlp01/graph.py",
    "apu_characterization/tlp01/schedule.py",
    "apu_characterization/tlp01/predictor.py",
    "apu_characterization/tlp01/phase_diagram.py",
    "apu_characterization/tlp01/labels.py",
    "apu_characterization/tlp01/bystander.py",
    "apu_characterization/tlp01/audit.py",
    "apu_characterization/tlp01/analyze.py",
    "apu_characterization/tlp01/report.py",
    "apu_characterization/tlp01/runner.py",
    "apu_characterization/tlp01/s2_harness.py",
    "apu_characterization/tlp01/s2_task_manifest.json",
    "apu_characterization/tlp01/t0_audit.py",
    "apu_characterization/tlp01/t1_graphs.py",
    "apu_characterization/tlp01/replication_floor.py",
    "apu_characterization/tlp01/died_ledger.json",
    "apu_characterization/METHODOLOGY_TLP01.md",
    "apu_characterization/METHODOLOGY_ARC_TLP01.md",
    "apu_characterization/PREDICTIONS_TLP01.md",
    "apu_characterization/PROMOTION_SUMMARY.md",
    "apu_characterization/VERIFIABLE_DATA.md",
)


def check_bundle(locked_protocol: Path | None = None) -> list[str]:
    errors = [
        f"missing required source: {relative}"
        for relative in REQUIRED
        if not (REPO_ROOT / relative).is_file()
    ]
    template = load_protocol()
    errors.extend(validate_template(template))
    for gate in GATE_NAMES:
        if gate not in template["gates"]:
            errors.append(f"missing gate {gate}")
    for model in MACHINE_MODELS:
        if model not in template["machine_models"]:
            errors.append(f"missing machine model {model}")
    if template["dependence_oracles"]["Tier_J"]["headline_load_bearing"]:
        errors.append("Tier_J must not be headline-load-bearing")
    if "Praetor achieves" not in str(template["projection"]["blocked_subject_claim"]):
        errors.append("projection must block 'Praetor achieves'")
    ledger = json.loads(
        (REPO_ROOT / "apu_characterization/tlp01/died_ledger.json").read_text(
            encoding="utf-8"
        )
    )
    entries = ledger.get("entries") or []
    if len(entries) < 16:
        errors.append(
            "died-ledger must include entries through #16 (closeout / headroom / v1 quarantine)"
        )
    ids = {int(entry.get("id", -1)) for entry in entries}
    if 4 not in ids or 5 not in ids:
        errors.append("died-ledger entries #4 (overlap credit) and #5 (smoke labels) required")
    if 6 not in ids or 7 not in ids:
        errors.append(
            "died-ledger entries #6 (work baseline) and #7 (rung suspension) required"
        )
    if 8 not in ids or 9 not in ids or 10 not in ids:
        errors.append(
            "died-ledger entries #8 (SER-02 mechanism), #9 (Tier-0⊆Tier-S), "
            "and #10 (Check A calibration) required"
        )
    if 11 not in ids or 12 not in ids or 13 not in ids:
        errors.append(
            "died-ledger entries #11 (taxonomy), #12 (M1a/M1b), #13 (Check A v2) required"
        )
    if 14 not in ids or 15 not in ids or 16 not in ids:
        errors.append(
            "died-ledger entries #14 (headroom criteria), #15 (canonical claims), "
            "#16 (v1 quarantine closeout) required"
        )
    proto_gd = (template.get("gates") or {}).get("G_D") or {}
    if "tier0_subseteq_tier_s" not in proto_gd:
        errors.append("protocol G_D must include tier0_subseteq_tier_s clause")
    if "edge_taxonomy" not in template:
        errors.append("protocol must include edge_taxonomy block")
    if "M1" in (template.get("machine_models") or {}):
        errors.append("protocol must not list unqualified M1 after taxonomy v2")
    if "M1a" not in (template.get("machine_models") or {}) or "M1b" not in (
        template.get("machine_models") or {}
    ):
        errors.append("protocol must define M1a and M1b")
    if "canonical_claims" not in template:
        errors.append("protocol must include canonical_claims block")
    headroom = ((template.get("edge_taxonomy") or {}).get("speculation_headroom") or {})
    if "rungs" not in headroom or "H-1" not in (headroom.get("rungs") or {}):
        errors.append("protocol v2.1 must define speculation_headroom H-1/H-2/H-3 rungs")
    if "speculation_frontier" not in template:
        errors.append("speculation_frontier block missing from protocol")
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
        print("TLP-01 bundle check FAILED:")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)
    print("TLP-01 bundle check OK")


if __name__ == "__main__":
    main()
