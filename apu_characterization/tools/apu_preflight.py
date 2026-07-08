"""Pre-replication verification (no OpenAI). Run before run_linux_replication_v3."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Allow: python apu_characterization/tools/apu_preflight.py from repo root
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _run(module: str) -> None:
    rc = subprocess.call([sys.executable, "-m", module])
    if rc != 0:
        raise SystemExit(rc)


def main() -> None:
    from apu_characterization.capture_setup import GIT_IGNORE_RUNTIME_REFRESH, probe_git

    live = probe_git()
    if live.get("dirty") == "yes":
        paths = live.get("dirty_paths") or ["?"]
        raise SystemExit(
            "Pre-flight FAIL: git tree is dirty before replication.\n"
            f"  paths: {paths[:8]}\n"
            "  Commit or stash, then re-run. On WSL /mnt/c/: git config core.autocrlf true"
        )

    _run("apu_characterization.setup_validate")
    _run("apu_characterization.tests.test_resolution")
    _run("apu_characterization.tests.test_attribution_provenance")

    # Simulate driver: capture_setup dirties only ignored runtime paths.
    _run("apu_characterization.capture_setup")

    post = probe_git(ignore_paths=GIT_IGNORE_RUNTIME_REFRESH)
    if post.get("dirty") == "yes":
        paths = post.get("dirty_paths") or ["?"]
        raise SystemExit(
            "Post-capture FAIL: unexpected dirty paths after setup refresh.\n"
            f"  paths: {paths}"
        )

    print("preflight OK — safe to run run_linux_replication_v3.ps1")


if __name__ == "__main__":
    main()
