from pathlib import Path

p = Path("seam/tools/affinity_matrix.py")
t = p.read_text(encoding="utf-8")
replacements = [
    (
        "def run_one(config_id: str, *, spec_path: Path, platform: str, threads: int | None = None) -> dict[str, Any]:",
        "def run_one(\n"
        "    config_id: str, *, spec_path: Path, platform: str, threads: int | None = None\n"
        ") -> dict[str, Any]:",
    ),
    (
        "def _spawn(config_id: str, *, spec_path: Path, platform: str, threads: int | None = None) -> dict[str, Any]:",
        "def _spawn(\n"
        "    config_id: str, *, spec_path: Path, platform: str, threads: int | None = None\n"
        ") -> dict[str, Any]:",
    ),
    (
        '    """A cell run is ok only when every scored generation has non-empty positive-duration windows."""',
        '    """A cell run is ok only when every scored gen has non-empty positive-duration windows."""',
    ),
    (
        '        if isinstance(entry, dict) and entry.get("method") in {"sha256", "git-blob-sha1", "size-only"}',
        "        if isinstance(entry, dict)\n"
        '        and entry.get("method") in {"sha256", "git-blob-sha1", "size-only"}',
    ),
    (
        '        verification["failures"] = list(verification.get("failures") or []) + [\n'
        '            f"sealed manifest missing at {sealed_manifest.as_posix()}"\n'
        "        ]",
        '        prior = list(verification.get("failures") or [])\n'
        '        verification["failures"] = [\n'
        "            *prior,\n"
        '            f"sealed manifest missing at {sealed_manifest.as_posix()}",\n'
        "        ]",
    ),
    (
        "    from seam.manifest import emit\n"
        "    from seam.model_provenance import load_local_spec, quantization_summary\n"
        "    from seam.powerstate import manifest_power_state, capture_power_state\n"
        "\n"
        "    from seam.model_provenance import manifest_model_block\n",
        "    from seam.manifest import emit\n"
        "    from seam.model_provenance import load_local_spec, manifest_model_block\n"
        "    from seam.powerstate import capture_power_state, manifest_power_state\n",
    ),
]
for old, new in replacements:
    if old not in t:
        print("MISSING:", old[:80])
    else:
        t = t.replace(old, new)
        print("ok:", old[:60])
p.write_text(t, encoding="utf-8", newline="\n")
