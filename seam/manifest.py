"""Run-manifest emission and validation (blueprint §5.2, spec §6.1).

Every experimental run emits exactly one manifest. **No manifest, no data** — and conversely, no
number may be reported that does not trace to a ``run_id`` recorded here (spec §9.2).

What :func:`emit` guarantees, in order:

1. Git state is captured, and a dirty tree is **refused** unless ``allow_dirty`` is passed — in
   which case that fact is written into the manifest.
2. The configuration is fully resolved and hashed, so the manifest pins the exact configuration the
   run behaved according to.
3. Provenance artifacts are hashed **from bytes on disk at emit time** (blueprint AF-002), never
   transcribed from a document.
4. The manifest validates against ``seam/schemas/run_manifest.schema.json`` **before** it is
   written. An invalid manifest never reaches ``raw/``.
5. The run directory is sealed write-once.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from seam import SPEC_VERSION
from seam.blinding import blinded_label_for, get_or_create_salt, record_unblind_entry
from seam.config import ResolvedConfig
from seam.errors import ManifestValidationError, ProvenanceError
from seam.gitinfo import GitState, assert_clean_or_allowed, capture_git_state
from seam.hashing import sha256_file, sha256_tree
from seam.jsonlog import add_json_sink, log_event, remove_json_sink, utc_now_iso
from seam.rawstore import RunDir, create_run_dir

__all__ = [
    "SCHEMA_PATH",
    "RunHandle",
    "build_manifest",
    "emit",
    "is_elevated",
    "load_schema",
    "validate_manifest",
]

SCHEMA_PATH: Final = Path(__file__).parent / "schemas" / "run_manifest.schema.json"

_MANIFEST_FILENAME: Final = "manifest.json"
_SUMMARY_FILENAME: Final = "summary.json"
_EVENTS_FILENAME: Final = "events.ndjson"


@dataclass(frozen=True, slots=True)
class RunHandle:
    """The result of a successful :func:`emit`."""

    run_id: str
    manifest: dict[str, Any]
    run_dir: RunDir
    raw_sha256: str


# ==================================================================================================
# Elevation
# ==================================================================================================


def is_elevated() -> bool:
    """Return whether the process has Administrator (or root) privileges.

    Recorded in every manifest because RAPL MSR access (spec §3.1 signal S2) requires elevation, so
    a non-elevated run cannot have produced RAPL data. Returns a definite boolean and logs rather
    than raising, since elevation is a recorded property of a run, not a precondition for emitting a
    manifest.
    """
    if sys.platform == "win32":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        except (AttributeError, OSError) as exc:
            log_event(
                "manifest.elevation_check_failed",
                severity="warning",
                message="could not determine elevation; recording elevated=False",
                error=str(exc),
            )
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


# ==================================================================================================
# Schema validation
# ==================================================================================================


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    """Load and cache the run-manifest JSON Schema."""
    if not SCHEMA_PATH.is_file():
        raise ManifestValidationError(f"manifest schema not found at {SCHEMA_PATH}")
    parsed: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return parsed


def validate_manifest(manifest: dict[str, Any]) -> None:
    """Validate a manifest against the schema.

    Every error is collected and reported together, rather than only the first, because fixing
    manifests one field per run is needlessly slow.

    Raises:
        ManifestValidationError: If the manifest is invalid, or if ``jsonschema`` is unavailable.
            A missing validator is a hard failure: an unvalidated manifest would defeat the entire
            point of having a schema, so the run stops rather than proceeding unchecked.
    """
    try:
        import jsonschema
    except ImportError as exc:
        raise ManifestValidationError(
            "jsonschema is required to validate run manifests (`pip install jsonschema`). "
            "Refusing to emit an unvalidated manifest."
        ) from exc

    validator_cls = jsonschema.validators.validator_for(load_schema())
    validator = validator_cls(load_schema(), format_checker=validator_cls.FORMAT_CHECKER)

    errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path))
    if errors:
        rendered = "\n".join(
            f"  - {'/'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
            for err in errors
        )
        raise ManifestValidationError(
            f"manifest failed schema validation with {len(errors)} error(s):\n{rendered}"
        )


# ==================================================================================================
# Manifest construction
# ==================================================================================================


def _hash_provenance_artifacts(config: ResolvedConfig, repo_root: Path) -> list[dict[str, str]]:
    """Hash every declared provenance artifact at emit time.

    Raises:
        ProvenanceError: If the list is empty or an artifact is missing. Blueprint §5.2 requires
            each run to pin the provenance snapshot it relied on, so a missing artifact invalidates
            the run rather than degrading it to a null hash.
    """
    declared = config.get("provenance_artifacts") or []
    if not declared:
        raise ProvenanceError(
            "platform config declares no provenance_artifacts; blueprint §5.2 requires every run "
            "to pin the provenance snapshot it relied on"
        )

    artifacts: list[dict[str, str]] = []
    for relative in declared:
        path = repo_root / relative
        if not path.is_file():
            raise ProvenanceError(
                f"declared provenance artifact is missing: {relative} (looked in {path}). "
                f"Refusing to emit a manifest with an unpinned provenance chain."
            )
        artifacts.append({"path": str(relative), "sha256": sha256_file(path)})
    return artifacts


def build_manifest(
    *,
    run_id: str,
    config: ResolvedConfig,
    git_state: GitState,
    allow_dirty: bool,
    target: str,
    workload: dict[str, Any],
    condition_label: str,
    blinded_label: str,
    repo_root: Path,
    model: dict[str, Any] | None = None,
    drivers: dict[str, Any] | None = None,
    power_state: dict[str, Any] | None = None,
    thermal: dict[str, Any] | None = None,
    topology_override: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    raw_sha256: str | None = None,
    self_check: str = "pass",
) -> dict[str, Any]:
    """Assemble a manifest dict. Does not validate or write it.

    Split out from :func:`emit` so tests can build manifests without touching git, the filesystem,
    or hardware.

    ``topology_override`` exists for one legitimate case: the topology-verification run itself,
    which *produces* the mapping and therefore cannot read it from a config that does not yet
    contain it.
    """
    topology = topology_override or {
        "p_cpus": config.get("topology.p_cpus"),
        "lpe_cpus": config.get("topology.lpe_cpus"),
        "verified": bool(config.get("topology.verified", False)),
    }

    # Thermal constants are null until M2.3 freezes them (AMENDMENTS.md AM-006). The illustrative
    # values in spec §6.1 are schema examples and are deliberately not used as defaults.
    thermal_block: dict[str, Any] = {
        "ambient_c": None,
        "warmup_s": config.get("thermal.warmup_s"),
        "cooldown_ceiling_c": config.get("thermal.cooldown_ceiling_c"),
        "throttle_residency_pct": None,
        "throttle_threshold_pct": config.get("thermal.throttle_threshold_pct"),
        "excluded": False,
    }
    if thermal:
        thermal_block.update(thermal)

    npu_config = config.get("npu_config") or {}

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "spec_version": SPEC_VERSION,
        "timestamp_utc": utc_now_iso(),
        "git_sha": git_state.sha,
        "git_dirty": git_state.dirty,
        "allow_dirty": allow_dirty,
        "git_branch": git_state.branch,
        "git_dirty_files": list(git_state.dirty_files) if git_state.dirty else None,
        "config_hash": config.config_hash,
        "config_sources": list(config.sources),
        "elevated": is_elevated(),
        "platform": {
            "id": config.require("platform_id"),
            "cpu": config.require("identity.cpu"),
            "family": config.require("identity.family"),
            "topology": topology,
            "os_build": str(config.require("identity.os_build")),
            "provenance_artifacts": _hash_provenance_artifacts(config, repo_root),
            # Blueprint §5.2 fields absent from spec §6.1 (AM-003). Null until captured; M2 fills
            # them. Never defaulted to a plausible-looking value.
            "microcode": None,
            "bios_version": None,
            "kernel": None,
            "power_cap_w": None,
            "cpu_governor": None,
        },
        "drivers": {
            "npu": None,
            "igpu": None,
            "openvino": None,
            "genai": None,
            "lhm_bridge": None,
        },
        "power_state": {
            "on_battery": None,
            "battery_pct_start": None,
            "battery_pct_end": None,
            "charging": None,
            "power_plan": None,
            "display_brightness": None,
            "defender_realtime": None,
            "windows_update_paused": None,
        },
        "thermal": thermal_block,
        "target": target,
        "model": {
            "name": None,
            "revision": None,
            "quantization": None,
            "ir_sha256": None,
        },
        "npu_config": {
            "MAX_PROMPT_LEN": npu_config.get("MAX_PROMPT_LEN"),
            "NPUW_LLM_PREFILL_CHUNK_SIZE": npu_config.get("NPUW_LLM_PREFILL_CHUNK_SIZE"),
        },
        "workload": {
            "kind": workload["kind"],
            "benchmark": workload["benchmark"],
            "task_ids": list(workload.get("task_ids") or []),
            "seed": workload.get("seed"),
            "n_repeats": workload.get("n_repeats"),
        },
        "condition_label": condition_label,
        "blinded_label": blinded_label,
        "outputs": {
            "samples": None,
            "steps": None,
            "summary": _SUMMARY_FILENAME,
            "events_path": _EVENTS_FILENAME,
        },
        "integrity": {
            "self_check": self_check,
            "raw_sha256": raw_sha256,
        },
    }

    if drivers:
        manifest["drivers"].update(drivers)
    if power_state:
        manifest["power_state"].update(power_state)
    if model:
        manifest["model"].update(model)
    if outputs:
        manifest["outputs"].update(outputs)

    return manifest


# ==================================================================================================
# Emission
# ==================================================================================================


def emit(
    *,
    config: ResolvedConfig,
    target: str,
    workload: dict[str, Any],
    condition_label: str,
    repo_root: Path,
    allow_dirty: bool = False,
    summary: dict[str, Any] | None = None,
    model: dict[str, Any] | None = None,
    drivers: dict[str, Any] | None = None,
    power_state: dict[str, Any] | None = None,
    thermal: dict[str, Any] | None = None,
    topology_override: dict[str, Any] | None = None,
    self_check: str = "pass",
    seal: bool = True,
) -> RunHandle:
    """Emit a schema-valid manifest into a fresh, sealed ``raw/<run_id>/`` directory.

    Args:
        config: Fully resolved configuration; its hash is recorded.
        target: One of ``cpu-p``, ``cpu-lpe``, ``igpu``, ``npu``, ``cloud``.
        workload: Must carry ``kind`` and ``benchmark``; ``task_ids``, ``seed``, ``n_repeats``
            optional.
        condition_label: The true condition. Written to the manifest but **never read by
            analysis**, which consumes ``blinded_label`` only.
        repo_root: Repository root.
        allow_dirty: Permit a dirty git tree. Recorded in the manifest when used.
        summary: Written to ``summary.json`` before the manifest, so it is covered by
            ``integrity.raw_sha256``.
        seal: Seal the run directory on success. Only a run that writes more data afterwards should
            pass False, and it must seal explicitly.

    Returns:
        A :class:`RunHandle`.

    Raises:
        DirtyTreeError: Dirty tree without ``allow_dirty``.
        ProvenanceError: A declared provenance artifact is missing.
        ManifestValidationError: The assembled manifest is not schema-valid.
    """
    git_state = capture_git_state(cwd=repo_root)
    assert_clean_or_allowed(git_state, allow_dirty=allow_dirty)

    salt = get_or_create_salt(repo_root)
    blinded_label = blinded_label_for(condition_label, salt=salt)

    run_id = str(uuid.uuid4())
    run_dir = create_run_dir(run_id, repo_root=repo_root)

    # Route structured events into the run directory from here on, so the log of what happened is
    # part of the sealed artifact rather than lost to the console.
    add_json_sink(run_dir.path / _EVENTS_FILENAME)

    log_event(
        "manifest.emit_started",
        message=f"emitting manifest for run {run_id}",
        run_id=run_id,
        target=target,
        workload_kind=workload.get("kind"),
        benchmark=workload.get("benchmark"),
        blinded_label=blinded_label,
        git_sha=git_state.sha,
        git_dirty=git_state.dirty,
        allow_dirty=allow_dirty,
        config_hash=config.config_hash,
    )

    run_dir.write_json(_SUMMARY_FILENAME, summary if summary is not None else {})

    # `integrity.raw_sha256` covers the run's DATA outputs only. Two files are necessarily excluded:
    #   - manifest.json, because a hash stored inside a file cannot cover that file;
    #   - events.ndjson, because emitting this manifest is itself a logged event, so the log keeps
    #     growing after the hash is taken.
    # The seal marker separately records a tree hash over everything except itself, which is what
    # verify_sealed() checks. So the data and the full run are both checksummed — by two different
    # values, for two different purposes.
    raw_sha256 = sha256_tree(run_dir.path, exclude={_MANIFEST_FILENAME, _EVENTS_FILENAME})

    manifest = build_manifest(
        run_id=run_id,
        config=config,
        git_state=git_state,
        allow_dirty=allow_dirty,
        target=target,
        workload=workload,
        condition_label=condition_label,
        blinded_label=blinded_label,
        repo_root=repo_root,
        model=model,
        drivers=drivers,
        power_state=power_state,
        thermal=thermal,
        topology_override=topology_override,
        raw_sha256=raw_sha256,
        self_check=self_check,
    )

    # Validate before writing. An invalid manifest must never reach raw/, because raw/ is
    # write-once and a bad manifest there could not be corrected.
    validate_manifest(manifest)

    run_dir.write_json(_MANIFEST_FILENAME, manifest)
    record_unblind_entry(condition_label, blinded_label, repo_root=repo_root)

    log_event(
        "manifest.emitted",
        message=f"manifest written for run {run_id}",
        run_id=run_id,
        raw_sha256=raw_sha256,
        path=str(run_dir.path / _MANIFEST_FILENAME),
    )

    if seal:
        # Deregister the sink first: raw/ is write-once, so an event appended after the seal would
        # invalidate the recorded tree hash and hit a read-only file.
        remove_json_sink(run_dir.path / _EVENTS_FILENAME)
        run_dir.seal(self_check=self_check)

    return RunHandle(
        run_id=run_id,
        manifest=manifest,
        run_dir=run_dir,
        raw_sha256=raw_sha256,
    )
