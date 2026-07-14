"""Reproducibility manifest helpers for MCP-01 runs.

The measurement implementation is deliberately duck typed.  Workstream B may
add fields, but these helpers enforce the pins required by ``mcp_tax_v1.5``.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .contracts import (
    PROTOCOL_VERSION,
    CellPlan,
    canonical_json_bytes,
    protocol_sha256,
    validate_manifest as validate_contract_manifest,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def capture_git_state(repo_root: Path) -> dict[str, Any]:
    """Capture the commit and cleanliness without changing repository state."""
    try:
        commit = _git(repo_root, "rev-parse", "HEAD")
        dirty = bool(
            _git(repo_root, "status", "--porcelain", "--untracked-files=no")
        )
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": "unknown"}
    return {"commit": commit, "dirty": "yes" if dirty else "no"}


def build_manifest(
    plan: CellPlan,
    *,
    repo_root: Path,
    core_pins: Mapping[str, Any],
    sdk_lock_path: Path,
    cert_path: Path | None = None,
    software: Mapping[str, Any] | None = None,
    git: Mapping[str, Any] | None = None,
    kernel_version: str | None = None,
    timestamp_utc: str | None = None,
    result_validity: str = "debug_only",
) -> dict[str, Any]:
    """Build a complete per-seed manifest from explicit measurement pins."""
    manifest: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "experiment": "mcp_tax",
        "cell_id": plan.coordinates.cell_id,
        "seed": plan.seed,
        "coordinates": {
            "transport": plan.coordinates.transport,
            "payload_bytes": plan.coordinates.payload_bytes,
            "schema_profile": plan.coordinates.schema_profile,
            "tool_count": plan.coordinates.tool_count,
            "implementation": plan.coordinates.implementation,
            "mode": plan.coordinates.mode,
        },
        "core_pins": dict(core_pins),
        "git": dict(git or capture_git_state(repo_root)),
        "software": dict(software or {}),
        "platform": platform.platform(),
        "kernel_version": kernel_version or platform.release(),
        "timestamp_utc": timestamp_utc
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cell_plan_sha256": plan.digest(),
        "protocol_sha256": protocol_sha256(),
        "sdk_lock": {
            "path": sdk_lock_path.as_posix(),
            "sha256": sha256_file(sdk_lock_path),
        },
        "certificate": None,
        "result_validity": result_validity,
    }
    if cert_path is not None:
        manifest["certificate"] = {
            "path": cert_path.as_posix(),
            "sha256": sha256_file(cert_path),
        }
    manifest["manifest_sha256"] = manifest_sha256(manifest)
    return manifest


def manifest_sha256(manifest: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def validate_manifest(
    manifest: Mapping[str, Any],
    *,
    plan: CellPlan | Mapping[str, Any] | None = None,
    require_clean: bool = False,
) -> list[str]:
    """Validate required fields, pins, and self hashes."""
    data = dict(manifest)
    errors = validate_contract_manifest(data)
    for field in ("protocol_sha256", "sdk_lock", "certificate", "manifest_sha256"):
        if field not in data:
            errors.append(f"missing manifest field: {field}")

    if data.get("protocol_sha256") != protocol_sha256():
        errors.append("protocol_sha256 mismatch")
    if data.get("manifest_sha256") != manifest_sha256(data):
        errors.append("manifest_sha256 mismatch")

    sdk = data.get("sdk_lock")
    if not isinstance(sdk, Mapping) or not _valid_sha256(sdk.get("sha256")):
        errors.append("SDK lock hash is missing")
    cert = data.get("certificate")
    transport = (data.get("coordinates") or {}).get("transport")
    if transport == "http_sse_tls_on":
        if not isinstance(cert, Mapping) or not _valid_sha256(cert.get("sha256")):
            errors.append("TLS transport requires certificate hash")

    pins = data.get("core_pins")
    if not isinstance(pins, Mapping):
        errors.append("core_pins must be an object")
    else:
        required_roles = ("client", "server", "os_analysis")
        for role in required_roles:
            if role not in pins:
                errors.append(f"missing core pin: {role}")
            elif not _as_core_list(pins.get(role)):
                errors.append(f"core pin set is empty: {role}")
        client = set(_as_core_list(pins.get("client")))
        server = set(_as_core_list(pins.get("server")))
        os_cores = set(_as_core_list(pins.get("os_analysis")))
        if client & server or client & os_cores or server & os_cores:
            errors.append("client/server/OS core pins must be disjoint")

    if require_clean and (data.get("git") or {}).get("dirty") != "no":
        errors.append("git capture is not clean")
    git = data.get("git") or {}
    if not git.get("commit"):
        errors.append("git commit pin is missing")
    if git.get("dirty") not in {"yes", "no"}:
        errors.append("git dirty pin must be 'yes' or 'no'")
    if not data.get("kernel_version"):
        errors.append("kernel version pin is missing")
    if not _valid_sha256(data.get("cell_plan_sha256")):
        errors.append("cell_plan_sha256 is invalid")
    if isinstance(plan, CellPlan):
        if data.get("cell_id") != plan.coordinates.cell_id:
            errors.append("manifest cell_id does not match plan")
        if data.get("seed") != plan.seed:
            errors.append("manifest seed does not match plan")
        if data.get("cell_plan_sha256") != plan.digest():
            errors.append("cell_plan_sha256 mismatch")
    elif isinstance(plan, Mapping):
        plan_payload = {
            key: value
            for key, value in plan.items()
            if key not in {"request_hashes", "canonical_hashes"}
        }
        plan_digest = hashlib.sha256(canonical_json_bytes(plan_payload)).hexdigest()
        if data.get("cell_plan_sha256") != plan_digest:
            errors.append("cell_plan_sha256 mismatch")
        if data.get("seed") != plan.get("seed"):
            errors.append("manifest seed does not match plan")
        if data.get("coordinates") != plan.get("coordinates"):
            errors.append("manifest coordinates do not match plan")
    return errors


def _valid_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value.lower())


def _as_core_list(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, str):
        values: list[int] = []
        for part in value.split(","):
            part = part.strip()
            if "-" in part:
                start, end = (int(item) for item in part.split("-", 1))
                values.extend(range(start, end + 1))
            elif part:
                values.append(int(part))
        return values
    return [int(item) for item in value]


def write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
