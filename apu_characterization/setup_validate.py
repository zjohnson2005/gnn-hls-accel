"""Validate setup.json before experiments run."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SETUP_JSON = Path("apu_characterization/out/setup.json")

REQUIRED_HARDWARE = ("cpu_model", "cores_logical", "ram_total_gb")
REQUIRED_GIT = ("commit", "dirty")
REQUIRED_SOFTWARE = ("python", "os")
REQUIRED_TOP = ("kernel", "setup_digest")


def validate_setup(setup: dict[str, Any], *, strict: bool = True) -> list[str]:
    errors: list[str] = []

    if not setup.get("setup_digest"):
        errors.append("setup_digest missing")

    if not strict:
        return errors

    for key in REQUIRED_HARDWARE:
        val = setup.get("hardware", {}).get(key)
        if val in (None, "unknown", "missing"):
            errors.append(f"hardware.{key} missing or unknown")

    git = setup.get("git", {})
    for key in REQUIRED_GIT:
        if not git.get(key):
            errors.append(f"git.{key} missing")
    if git.get("dirty") == "yes":
        errors.append("git tree is dirty; commit before measurement (or --allow-dirty)")
    if git.get("commit") in (None, "unknown", ""):
        hint = git.get("git_path", "git")
        errors.append(
            "git commit unknown; install Git, ensure it is on PATH "
            f"(probe: {hint}), then re-run capture_setup"
        )

    sw = setup.get("software", {})
    for key in REQUIRED_SOFTWARE:
        if not sw.get(key):
            errors.append(f"software.{key} missing")

    if not setup.get("kernel"):
        errors.append("kernel missing")

    if sys.platform != "win32":
        gov = setup.get("hardware", {}).get("cpu_governor")
        if not gov:
            errors.append("hardware.cpu_governor missing on Linux (re-run capture_setup)")
        elif gov.startswith("n/a"):
            kernel = (setup.get("kernel") or "").lower()
            if "wsl" not in kernel and "microsoft-standard-wsl" not in kernel:
                errors.append(
                    f"hardware.cpu_governor unavailable ({gov!r}); "
                    "native Linux should expose cpufreq sysfs"
                )

    openai = setup.get("openai", {})
    for key in ("model", "temperature", "timeout_s"):
        if key not in openai:
            errors.append(f"openai.{key} not recorded")
    if not openai.get("api_key_set"):
        errors.append("openai.api_key_set is false; set OPENAI_API_KEY before publishable runs")

    return errors


def load_and_validate(*, strict: bool = True) -> dict[str, Any]:
    if not SETUP_JSON.is_file():
        raise SystemExit(
            "setup record missing: run `python -m apu_characterization.capture_setup` first"
        )
    setup = json.loads(SETUP_JSON.read_text(encoding="utf-8"))
    errors = validate_setup(setup, strict=strict)
    if errors:
        msg = "Setup validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise SystemExit(msg)
    return setup


def main() -> None:
    setup = load_and_validate(strict="--allow-dirty" not in sys.argv)
    print(f"setup OK: digest {setup.get('setup_digest')}")


if __name__ == "__main__":
    main()
