"""Freeze tlp01_trace_v2 schema hash before any S2 session runs."""

from __future__ import annotations

import json
from pathlib import Path

from apu_characterization.tlp01.contracts import load_protocol, sha256_json
from apu_characterization.tlp01.labels import find_rung_labels

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "apu_characterization/out/tlp01/traces/SCHEMA_FREEZE.json"
MANIFEST = REPO / "apu_characterization/tlp01/s2_task_manifest.json"


def main() -> None:
    protocol = load_protocol()
    schema = protocol["trace_schema"]
    if schema.get("version") != "tlp01_trace_v2":
        raise SystemExit("schema version must be tlp01_trace_v2")
    if "dep_refs" not in schema.get("required_fields", []):
        raise SystemExit("dep_refs must be required before freeze")
    if "Tier_0" not in protocol.get("dependence_oracles", {}):
        raise SystemExit("Tier_0 oracle required before freeze")
    digest = sha256_json(schema)
    payload = {
        "trace_schema_sha256": digest,
        "schema_version": schema["version"],
        "s2_task_manifest_sha256": sha256_json(
            json.loads(MANIFEST.read_text(encoding="utf-8"))
        ),
        "frozen_before_s2": True,
        "tier0_field": "dep_refs",
        "note": (
            "Schema frozen prior to S2 collection. Traces are append-only; "
            "never edit in place."
        ),
    }
    blob = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if find_rung_labels(blob):
        raise SystemExit("freeze stamp must not contain rung labels")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        prior = json.loads(OUT.read_text(encoding="utf-8"))
        if prior.get("trace_schema_sha256") != digest:
            raise SystemExit("SCHEMA_FREEZE drift vs current protocol schema")
        print(f"SCHEMA_FREEZE already present sha={digest}")
        return
    OUT.write_text(blob, encoding="utf-8")
    print(f"SCHEMA_FREEZE written sha={digest}")


if __name__ == "__main__":
    main()
