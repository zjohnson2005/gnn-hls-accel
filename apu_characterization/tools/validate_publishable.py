"""Check a replication or real-agent artifact against publishable validity gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def validate_artifact(data: dict) -> list[str]:
    errors: list[str] = []
    validity = data.get("result_validity")
    audit = data.get("audit") or {}

    if validity != "publishable":
        errors.append(f"result_validity is {validity!r}, not publishable")

    if not audit.get("pass"):
        errors.append("audit.pass is false")
    if not audit.get("publishable_ok"):
        errors.append("audit.publishable_ok is false")

    for v in audit.get("violations") or []:
        errors.append(f"violation: {v}")

    repro = audit.get("repro") or {}
    for v in repro.get("violations") or []:
        errors.append(f"repro: {v}")

    agg = data.get("aggregate") or {}
    for key in (
        "pooled_orch_measured_pct",
        "pooled_orch_reconcile_pct",
        "pooled_harness_strict_pct",
    ):
        if key not in agg:
            errors.append(f"aggregate missing {key} (run --refresh-only or re-run replication)")

    per_seed = data.get("per_seed_artifacts") or []
    if per_seed:
        sample = per_seed[0]["run"]["per_session"][0]
        if "orch_measured_cpu_ns" not in sample:
            errors.append("per_session missing orch_measured_cpu_ns (refresh or re-run)")

    git = data.get("git") or {}
    if git.get("dirty") == "yes" and not data.get("config", {}).get("allow_dirty"):
        errors.append("git dirty without allow_dirty flag")

    cfg = data.get("config") or {}
    backend = cfg.get("backend")
    if backend and backend != "openai":
        errors.append(f"backend={backend!r}; verifiable artifacts require openai")

    instr_version = int(cfg.get("instr_version") or 1)
    if instr_version >= 3:
        for key in (
            "pooled_measured_pct",
            "pooled_step_inferred_pct",
            "pooled_residual_provenance_pct",
        ):
            if key not in agg:
                errors.append(f"aggregate missing {key} (v3 replication artifact)")
    elif instr_version >= 2:
        for key in (
            "pooled_residual_unattributed_pct",
            "pooled_client_http_pct",
            "pooled_framework_pct",
        ):
            if key not in agg:
                errors.append(f"aggregate missing {key} (v2 replication artifact)")

    for art in per_seed:
        b = art.get("config", {}).get("backend") or art.get("run", {}).get("config", {}).get(
            "backend"
        )
        if b and b != "openai":
            errors.append(f"per-seed backend={b!r}; not verifiable")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "json",
        nargs="?",
        default="apu_characterization/out/replication_remote_search.json",
        type=Path,
    )
    args = parser.parse_args()
    data = json.loads(args.json.read_text(encoding="utf-8"))
    errors = validate_artifact(data)
    print(f"artifact: {args.json}")
    print(f"validity: {data.get('result_validity')}")
    print(f"audit pass: {(data.get('audit') or {}).get('pass')}")
    print(f"publishable_ok: {(data.get('audit') or {}).get('publishable_ok')}")
    if errors:
        print("\nFAIL:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("\nOK — artifact passes publishable gates")


if __name__ == "__main__":
    main()
