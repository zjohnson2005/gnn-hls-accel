"""Immutable protocol lock for TLP-01 after T0 manifests exist."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from apu_characterization.tlp01.contracts import (
    EXPECTATIONS_PATH,
    PROTOCOL_PATH,
    expectations_sha256,
    load_protocol,
    sha256_json,
    validate_lock,
    validate_template,
)


def build_locked_protocol(
    *,
    s2_task_manifest: Mapping[str, Any],
    protocol_path: Path = PROTOCOL_PATH,
) -> dict[str, Any]:
    template = load_protocol(protocol_path)
    errors = validate_template(template)
    if errors:
        raise ValueError("template failed validation: " + "; ".join(errors))
    locked = deepcopy(template)
    locked["status"] = "locked"
    locked["lock_fields"] = {
        "trace_schema_sha256": sha256_json(template["trace_schema"]),
        "s2_task_manifest_sha256": sha256_json(dict(s2_task_manifest)),
        "expectations_sha256": expectations_sha256(EXPECTATIONS_PATH),
        "dependence_oracle_config_sha256": sha256_json(
            template["dependence_oracles"]
        ),
        "machine_model_ladder_sha256": sha256_json(template["machine_models"]),
        "speculation_frontier_sha256": sha256_json(
            template["speculation_frontier"]
        ),
    }
    locked["locked_population"] = {
        "s2_target_sessions": template["trace_sources"]["S2"]["target_sessions"],
        "s2_seeds": template["trace_sources"]["S2"]["seeds"],
        "s3_required_for_v1": template["trace_sources"]["S3"]["required_for_v1"],
        "task_manifest_task_count": len(s2_task_manifest.get("tasks") or []),
    }
    lock_errors = validate_lock(locked)
    if lock_errors:
        raise ValueError("lock failed validation: " + "; ".join(lock_errors))
    return locked


def write_locked_protocol(locked: Mapping[str, Any], path: Path) -> Path:
    payload = json.dumps(locked, indent=2, sort_keys=True) + "\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing != payload:
            raise FileExistsError(
                f"refusing to replace differing locked protocol at {path}"
            )
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")
    return path
