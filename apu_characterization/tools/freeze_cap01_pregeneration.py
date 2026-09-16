#!/usr/bin/env python3
"""Freeze CAP-01 generation config, verifier pins, and pre-generation protocol lock."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sqlite3
import sys
from pathlib import Path

from apu_characterization.cap01.bfcl_cap01_checker import check as _bfcl_check  # noqa: F401
from apu_characterization.cap01.contracts import sha256_bytes
from apu_characterization.cap01.depth_triage import depth_triage_policy_dict
from apu_characterization.cap01.generation import DEFAULT_PROMPT_TEMPLATE, GenerationConfig
from apu_characterization.cap01.protocol_lock import (
    build_pre_generation_locked_protocol,
    write_locked_protocol,
)

DOMAIN_PROMPT_TEMPLATES = {
    "FUNCTION_CALLING": (
        "Return raw JSON only. Do not wrap the output in markdown code fences "
        "(no ```json, no ```). No prose.\n\n"
        "Domain: {domain}\nTask:\n{prompt}"
    ),
    "TEXT_TO_SQL": (
        "Return the raw SQL statement only. Do not wrap the output in markdown "
        "code fences (no ```sql, no ```). No prose.\n\n"
        "Domain: {domain}\nTask:\n{prompt}"
    ),
    "CODE": (
        "Return raw Python source only. Do not wrap the output in markdown code "
        "fences (no ```python, no ```) and do not include prose explanation "
        "before or after the code.\n\n"
        "Domain: {domain}\nTask:\n{prompt}"
    ),
    "MATH": (
        "Show one brief final calculation step, then give the final answer on its "
        "own line as 'Final answer: <value>'. No other prose. Do not wrap the "
        "output in markdown code fences.\n\n"
        "Domain: {domain}\nTask:\n{prompt}"
    ),
    "STRUCTURED_EXTRACTION": (
        "Return one raw JSON object only, with a consistent schema across all "
        "outputs for a given task. Do not wrap the output in markdown code "
        "fences. No prose.\n\n"
        "Domain: {domain}\nTask:\n{prompt}"
    ),
}


def _write_json(path: Path, payload: object) -> str:
    body = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != body:
        raise FileExistsError(f"refusing to replace frozen artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return sha256_bytes(body.encode("utf-8"))


def build_generation_config(*, model: str, target_candidates: int) -> dict[str, object]:
    config = GenerationConfig(
        model=model,
        temperature=1.0,
        max_completion_tokens=4096,
        target_candidates=target_candidates,
        prompt_template=DEFAULT_PROMPT_TEMPLATE,
        prompt_templates=DOMAIN_PROMPT_TEMPLATES,
    )
    config.validate()
    payload = config.public_dict()
    payload["lock_phase"] = "pre_generation"
    payload["depth_triage"] = depth_triage_policy_dict()
    payload["digest"] = config.digest()
    return payload


def build_verifier_pin_manifest(corpus_manifest: Path) -> dict[str, object]:
    corpus = json.loads(corpus_manifest.read_text(encoding="utf-8"))
    tasks = corpus.get("tasks") or []
    fc = next(
        task for task in tasks if str(task.get("domain")) == "FUNCTION_CALLING"
    )
    checker_hash = str(fc["verifier"]["checker_source_sha256"])
    repo = Path(__file__).resolve().parents[2]
    adapter_paths = {
        "domain_verifiers.py": repo / "apu_characterization/cap01/domain_verifiers.py",
        "verifier.py": repo / "apu_characterization/cap01/verifier.py",
        "bfcl_cap01_checker.py": repo / "apu_characterization/cap01/bfcl_cap01_checker.py",
        "bfcl_shims/__init__.py": (
            repo / "apu_characterization/cap01/bfcl_shims/__init__.py"
        ),
        "bfcl_shims/java_parser.py": (
            repo / "apu_characterization/cap01/bfcl_shims/java_parser.py"
        ),
        "bfcl_shims/js_parser.py": (
            repo / "apu_characterization/cap01/bfcl_shims/js_parser.py"
        ),
    }
    adapter_sha256 = {
        name: sha256_bytes(path.read_bytes()) for name, path in adapter_paths.items()
    }
    return {
        "bfcl": {
            "version": "v4",
            "source_sha256": checker_hash,
            "adoption": "bfcl_eval.ast_checker via cap01 wrapper",
            "corpus_test_category": "live_multiple_python_only",
            "tree_sitter_policy": {
                "upstream_metadata_pins": {
                    "tree_sitter": "0.21.3",
                    "tree_sitter_java": "0.21.0",
                    "tree_sitter_javascript": "0.21.4",
                },
                "cap01_runtime": (
                    "Java/JS parsers stubbed via bfcl_shims so Python-only "
                    "live_multiple scoring does not require compiling "
                    "tree_sitter==0.21.3 on hosts without matching wheels "
                    "(died-ledger #11)."
                ),
            },
        },
        "adapters": {
            "note": (
                "Scoring-relevant adapter layer previously outside the BFCL "
                "wrapper pin; covered after died-ledger #11 coverage-hole fix."
            ),
            "sha256": adapter_sha256,
        },
        "code_sandbox": {
            "wall_seconds_default": 30,
            "python_flags": ["-B"],
            "note": (
                "Dropped -S so HumanEval+ numpy imports work; runner invokes "
                "check(entry_point); network blocked in-process (died-ledger #11)."
            ),
        },
        "sqlite": {"version": sqlite3.sqlite_version},
        "cpython": {
            "version": (
                f"{sys.version_info.major}.{sys.version_info.minor}."
                f"{sys.version_info.micro}"
            )
        },
        "jsonschema": {"version": importlib.metadata.version("jsonschema")},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus-manifest",
        type=Path,
        default=Path("apu_characterization/out/cap01/corpus.json"),
    )
    parser.add_argument(
        "--generation-config",
        type=Path,
        default=Path("apu_characterization/out/cap01/generation_config.json"),
    )
    parser.add_argument(
        "--verifier-pin-manifest",
        type=Path,
        default=Path("apu_characterization/out/cap01/verifier_pin_manifest.json"),
    )
    parser.add_argument(
        "--locked-protocol",
        type=Path,
        default=Path("apu_characterization/out/cap01/protocol_cap01_v2.locked.json"),
    )
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--target-candidates", type=int, default=2048)
    args = parser.parse_args()

    generation_payload = build_generation_config(
        model=args.model,
        target_candidates=args.target_candidates,
    )
    generation_digest = _write_json(args.generation_config, generation_payload)
    verifier_pins = build_verifier_pin_manifest(args.corpus_manifest)
    verifier_digest = _write_json(args.verifier_pin_manifest, verifier_pins)
    locked = build_pre_generation_locked_protocol(
        corpus_manifest=args.corpus_manifest,
        generation_config=args.generation_config,
        verifier_pin_manifest=args.verifier_pin_manifest,
    )
    protocol_digest = write_locked_protocol(args.locked_protocol, locked)

    print(f"generation_config={args.generation_config}")
    print(f"generation_config_sha256={generation_digest}")
    print(f"verifier_pin_manifest={args.verifier_pin_manifest}")
    print(f"verifier_pin_manifest_sha256={verifier_digest}")
    print(f"locked_protocol={args.locked_protocol}")
    print(f"locked_protocol_sha256={protocol_digest}")
    print(f"lock_phase={locked['lock_phase']}")
    print(f"corpus_manifest_sha256={locked['lock_fields']['corpus_manifest_sha256']}")
    print("GENERATION CLEARED")


if __name__ == "__main__":
    main()
