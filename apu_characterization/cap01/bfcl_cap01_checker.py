"""CAP-01 BFCL ast_checker wrapper (adopted without modifying ast_checker)."""

from __future__ import annotations

import json
import re
from typing import Any


def _openai_style_to_bfcl(call: dict) -> dict:
    """Map {name, parameters|arguments} → {name: params} BFCL AST item."""
    if "name" in call and ("parameters" in call or "arguments" in call):
        params = call.get("parameters", call.get("arguments", {}))
        if not isinstance(params, dict):
            raise ValueError("OpenAI-style call parameters must be an object")
        return {str(call["name"]): params}
    return call


def _parse_candidate(candidate: Any) -> list:
    if isinstance(candidate, str):
        text = candidate.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*\n(.*)\n```", text, re.DOTALL | re.I)
        if fenced:
            text = fenced.group(1).strip()
        candidate = json.loads(text)
    if isinstance(candidate, dict):
        return [_openai_style_to_bfcl(candidate)]
    if isinstance(candidate, list):
        return [
            _openai_style_to_bfcl(item) if isinstance(item, dict) else item
            for item in candidate
        ]
    raise ValueError("unsupported candidate format")


def _language_for(category: str):
    from bfcl_eval.constants.enums import Language

    lowered = category.lower()
    if "javascript" in lowered:
        return Language.JAVASCRIPT
    if "java" in lowered:
        return Language.JAVA
    return Language.PYTHON


def _ensure_bfcl_on_path() -> None:
    """Locate unpacked bfcl_eval whether loaded from package or corpus asset."""
    import sys
    from pathlib import Path

    here = Path(__file__).resolve()
    candidates: list[Path] = []
    for parent in here.parents:
        candidates.append(
            parent / "apu_characterization/out/cap01/live_sources/bfcl-wheel/unpacked"
        )
        candidates.append(parent / "out/cap01/live_sources/bfcl-wheel/unpacked")
    for unpacked in candidates:
        if unpacked.is_dir() and (unpacked / "bfcl_eval").is_dir():
            path = str(unpacked)
            if path not in sys.path:
                sys.path.insert(0, path)
            return
    raise ModuleNotFoundError(
        "bfcl_eval not found; expected out/cap01/live_sources/bfcl-wheel/unpacked"
    )


def check(record: dict) -> bool:
    # CAP-01 corpus is Python live_multiple only. Install import shims so
    # bfcl_eval.ast_checker loads without tree_sitter==0.21.3 and without the
    # full MODEL_CONFIG_MAPPING API-handler dependency graph.
    from apu_characterization.cap01.bfcl_shims import install_bfcl_runtime_shims

    _ensure_bfcl_on_path()
    install_bfcl_runtime_shims()
    from bfcl_eval.eval_checker.ast_eval.ast_checker import ast_checker

    model_output = _parse_candidate(record["candidate"])
    result = ast_checker(
        record["functions"],
        model_output,
        record["reference"],
        _language_for(str(record.get("test_category", ""))),
        str(record["test_category"]),
        "cap01",
    )
    return bool(result.get("valid"))
